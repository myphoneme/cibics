from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Record, RecordStageStatus, Role, StageDefinition, User
from app.security import get_password_hash
from app.services.stages import ensure_default_stages, ensure_record_stage_rows, get_active_stages
from app.services.status import derive_status

settings = get_settings()

HEADER_ROW = 2
DATA_START_ROW = 3

ASSIGNEE_EMAIL_DOMAIN = 'cibics.local'

EXCEL_STAGE_MAP = {
    'email sent to customer': 'EMAIL_SENT_TO_CUSTOMER',
    'Data received from Customer': 'DATA_RECEIVED_FROM_CUSTOMER',
    'email sent to bsnl for feasibility': 'EMAIL_SENT_TO_BSNL_FOR_FEASIBILITY',
    'email received from BSNL after feasibility': 'EMAIL_RECEIVED_FROM_BSNL_AFTER_FEASIBILITY',
    'Proposal sent': 'PROPOSAL_SENT',
    'Po received': 'PO_RECEIVED',
}


def _to_text(value: Any) -> str | None:
    if value is None:
        return None
    txt = str(value).strip()
    return txt if txt else None


def _to_bool(value: Any) -> bool:
    if value is None:
        return False
    txt = str(value).strip().lower()
    return txt not in {'', '0', 'false', 'no', 'none'}


def _normalize_name(name: str) -> str:
    return ' '.join(name.replace('\n', ' ').split()).strip()


def _slugify_name(name: str) -> str:
    cleaned = ''.join(ch.lower() if ch.isalnum() else '.' for ch in name)
    cleaned = '.'.join(part for part in cleaned.split('.') if part)
    return cleaned[:40] or 'assignee'


def _is_default_status(value: str | None) -> bool:
    if not value:
        return True
    normalized = value.strip().lower().replace('-', ' ').replace('_', ' ')
    normalized = ' '.join(normalized.split())
    return normalized in {'po received', 'po recieve', 'po recieved', 'po-received'}


def ensure_assignee_users(db: Session, names: set[str]) -> int:
    created = 0
    existing_names = {
        _normalize_name(name).lower()
        for (name,) in db.query(User.full_name).filter(User.role == Role.ASSIGNEE).all()
    }

    for raw_name in names:
        name = _normalize_name(raw_name)
        if not name or name.lower() in existing_names:
            continue

        base = _slugify_name(name)
        email = f'{base}@{ASSIGNEE_EMAIL_DOMAIN}'
        suffix = 1
        while db.query(User.id).filter(func.lower(User.email) == email.lower()).first():
            suffix += 1
            email = f'{base}{suffix}@{ASSIGNEE_EMAIL_DOMAIN}'

        user = User(
            full_name=name,
            email=email,
            password_hash=get_password_hash(settings.default_assignee_password),
            role=Role.ASSIGNEE,
            is_active=True,
            receive_alert=True,
        )
        db.add(user)
        existing_names.add(name.lower())
        created += 1

    db.flush()
    return created


def _assignee_by_name(db: Session, name: str | None) -> User | None:
    if not name:
        return None
    normalized = _normalize_name(name)
    if not normalized:
        return None

    return (
        db.query(User)
        .filter(User.role == Role.ASSIGNEE)
        .filter(func.lower(User.full_name) == normalized.lower())
        .first()
    )


def import_phoneme_excel(db: Session, filepath: str) -> dict[str, int]:
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f'File not found: {path}')

    ensure_default_stages(db)
    active_stages = get_active_stages(db)

    wb = load_workbook(path, data_only=True)
    ws = wb.active

    headers = {}
    for col_idx in range(1, ws.max_column + 1):
        value = _to_text(ws.cell(HEADER_ROW, col_idx).value)
        if value:
            headers[col_idx] = value

    expected = {
        'Sl.no',
        'List Type',
        'Type',
        'PO STATUS',
        'Custodian Code',
        'UNLO Code',
        'Short Name',
        'Custodian Organization',
        'State',
        'Site Address',
        'Pincode',
        'Category of Site',
        'Custodian Contact Person Name',
        'Custodian Contact Person Number',
        'Custodian Email',
        'Customer Name',
        'Mobile No',
        'Email id',
    }
    existing_headers = set(headers.values())
    if not expected.issubset(existing_headers):
        missing = sorted(expected - existing_headers)
        raise ValueError(f'Workbook missing expected headers: {missing}')

    records_processed = 0
    created = 0
    updated = 0

    assignee_names = set()
    processed_records: list[Record] = []

    header_to_col = {name: idx for idx, name in headers.items()}
    stage_by_code = {item.code: item for item in active_stages}

    for row_idx in range(DATA_START_ROW, ws.max_row + 1):
        row_values = {name: ws.cell(row_idx, idx).value for name, idx in header_to_col.items()}
        if not any(value not in (None, '') for value in row_values.values()):
            continue

        po_status_raw = _to_text(row_values.get('PO STATUS'))
        assignee_hint = _normalize_name(po_status_raw) if po_status_raw and not _is_default_status(po_status_raw) else None
        if assignee_hint:
            assignee_names.add(assignee_hint)

        existing = db.query(Record).filter(Record.source_row == row_idx).one_or_none()

        if existing is None:
            existing = Record(source_row=row_idx)
            db.add(existing)
            db.flush()
            created += 1
        else:
            updated += 1

        # Overwrite behavior: source excel is authoritative.
        existing.sl_no = _to_text(row_values.get('Sl.no'))
        existing.list_type = _to_text(row_values.get('List Type'))
        existing.type = _to_text(row_values.get('Type'))
        existing.po_status_raw = po_status_raw
        existing.custodian_code = _to_text(row_values.get('Custodian Code'))
        existing.unlo_code = _to_text(row_values.get('UNLO Code'))
        existing.short_name = _to_text(row_values.get('Short Name'))
        existing.custodian_organization = _to_text(row_values.get('Custodian Organization'))
        existing.state = _to_text(row_values.get('State'))
        existing.site_address = _to_text(row_values.get('Site Address'))
        existing.city = _to_text(ws.cell(row_idx, 12).value)
        existing.pincode = _to_text(row_values.get('Pincode'))
        existing.category_of_site = _to_text(row_values.get('Category of Site'))
        existing.custodian_contact_person_name = _to_text(row_values.get('Custodian Contact Person Name'))
        existing.custodian_contact_person_number = _to_text(row_values.get('Custodian Contact Person Number'))
        existing.custodian_email = _to_text(row_values.get('Custodian Email'))

        existing.customer_name = _to_text(row_values.get('Customer Name'))
        existing.mobile_no = _to_text(row_values.get('Mobile No'))
        existing.client_email = _to_text(row_values.get('Email id'))
        existing.assignee_name_hint = assignee_hint
        existing.assignee_id = None
        existing.email_alert_pending = False
        existing.last_email_alert_at = None

        ensure_record_stage_rows(db, existing, active_stages)
        stage_rows = {
            item.stage.code: item
            for item in (
                db.query(RecordStageStatus)
                .join(StageDefinition, StageDefinition.id == RecordStageStatus.stage_id)
                .filter(RecordStageStatus.record_id == existing.id, StageDefinition.is_active.is_(True))
                .all()
            )
        }

        for excel_key, stage_code in EXCEL_STAGE_MAP.items():
            stage_obj = stage_by_code.get(stage_code)
            stage_row = stage_rows.get(stage_code)
            if not stage_obj or not stage_row:
                continue

            completed = _to_bool(row_values.get(excel_key))
            stage_row.is_completed = completed
            stage_row.completed_at = datetime.now(timezone.utc) if completed else None
            stage_row.notes = None

        existing.status = derive_status(existing)

        processed_records.append(existing)
        records_processed += 1

    assignees_created = ensure_assignee_users(db, assignee_names)

    for item in processed_records:
        if item.assignee_name_hint:
            assignee = _assignee_by_name(db, item.assignee_name_hint)
            item.assignee_id = assignee.id if assignee else None
        else:
            item.assignee_id = None

    db.commit()

    return {
        'imported': records_processed,
        'created': created,
        'updated': updated,
        'assignees_created': assignees_created,
    }
