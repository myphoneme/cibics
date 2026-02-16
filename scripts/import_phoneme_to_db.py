import hashlib
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from zipfile import ZipFile

from sqlalchemy import func

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.models import Record, RecordStageStatus, Role, User
from app.services.stages import ensure_default_stages, ensure_record_stage_rows, get_active_stages
from app.services.status import derive_status

NS = {'a': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

EXCEL_STAGE_MAP = {
    'email sent to customer': 'EMAIL_SENT_TO_CUSTOMER',
    'Data received from Customer': 'DATA_RECEIVED_FROM_CUSTOMER',
    'email sent to bsnl for feasibility': 'EMAIL_SENT_TO_BSNL_FOR_FEASIBILITY',
    'email received from BSNL after feasibility': 'EMAIL_RECEIVED_FROM_BSNL_AFTER_FEASIBILITY',
    'Proposal sent': 'PROPOSAL_SENT',
    'Po received': 'PO_RECEIVED',
}


def _to_text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def _to_bool(value):
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


def _split_ref(ref: str):
    m = re.match(r'([A-Z]+)([0-9]+)', ref)
    if not m:
        return None, None
    return m.group(1), int(m.group(2))


def _cell_value(cell, shared):
    t = cell.attrib.get('t')
    v = cell.find('a:v', NS)
    is_node = cell.find('a:is', NS)

    if t == 's' and v is not None and v.text is not None:
        idx = int(v.text)
        return shared[idx] if 0 <= idx < len(shared) else ''
    if t == 'inlineStr' and is_node is not None:
        return ''.join(tn.text or '' for tn in is_node.findall('.//a:t', NS))
    if v is not None and v.text is not None:
        return v.text
    return ''


def parse_xlsx_rows(path: Path):
    with ZipFile(path) as z:
        shared = []
        if 'xl/sharedStrings.xml' in z.namelist():
            ss_root = ET.fromstring(z.read('xl/sharedStrings.xml'))
            for si in ss_root.findall('a:si', NS):
                shared.append(''.join(t.text or '' for t in si.findall('.//a:t', NS)))

        root = ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
        rows = []
        for row in root.findall('a:sheetData/a:row', NS):
            row_num = int(row.attrib.get('r', '0'))
            cell_map = {}
            for cell in row.findall('a:c', NS):
                ref = cell.attrib.get('r', '')
                col, _ = _split_ref(ref)
                if not col:
                    continue
                cell_map[col] = _cell_value(cell, shared).strip()
            rows.append((row_num, cell_map))

    return rows


def get_password_hash(plain: str) -> str:
    # Fallback hash for offline import; rotate/reset passwords after app dependencies are installed.
    return 'sha256$' + hashlib.sha256(plain.encode('utf-8')).hexdigest()


def main():
    settings = get_settings()
    excel_path = Path('Phoneme.xlsx')
    if not excel_path.exists():
        raise FileNotFoundError(f'Excel file not found: {excel_path.resolve()}')

    rows = parse_xlsx_rows(excel_path)
    row_map = {row_num: cell_map for row_num, cell_map in rows}

    headers_by_col = row_map.get(2, {})
    if not headers_by_col:
        raise RuntimeError('Header row (row 2) not found in sheet.')

    records = []
    assignee_names = set()

    for row_idx in range(3, max(row_map) + 1):
        cells = row_map.get(row_idx, {})
        if not any((v or '').strip() for v in cells.values()):
            continue

        def by_col(col: str):
            return _to_text(cells.get(col, ''))

        by_header = {}
        for col, header in headers_by_col.items():
            if header:
                by_header[header] = _to_text(cells.get(col, ''))

        po_status_raw = by_header.get('PO STATUS')
        assignee_hint = _normalize_name(po_status_raw) if po_status_raw and not _is_default_status(po_status_raw) else None
        if assignee_hint:
            assignee_names.add(assignee_hint)

        record = {
            'source_row': row_idx,
            'sl_no': by_header.get('Sl.no'),
            'list_type': by_header.get('List Type'),
            'type': by_header.get('Type'),
            'po_status_raw': po_status_raw,
            'custodian_code': by_header.get('Custodian Code'),
            'unlo_code': by_header.get('UNLO Code'),
            'short_name': by_header.get('Short Name'),
            'custodian_organization': by_header.get('Custodian Organization'),
            'state': by_header.get('State'),
            'site_address': by_header.get('Site Address'),
            'city': by_col('L'),
            'pincode': by_header.get('Pincode'),
            'category_of_site': by_header.get('Category of Site'),
            'custodian_contact_person_name': by_header.get('Custodian Contact Person Name'),
            'custodian_contact_person_number': by_header.get('Custodian Contact Person Number'),
            'custodian_email': by_header.get('Custodian Email'),
            'customer_name': by_header.get('Customer Name'),
            'mobile_no': by_header.get('Mobile No'),
            'client_email': by_header.get('Email id'),
            'assignee_name_hint': assignee_hint,
            'stages': {
                stage_code: _to_bool(by_header.get(excel_col_name))
                for excel_col_name, stage_code in EXCEL_STAGE_MAP.items()
            },
        }
        records.append(record)

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        admin = User(
            full_name=settings.default_super_admin_name,
            email=settings.default_super_admin_email,
            password_hash=get_password_hash(settings.default_super_admin_password),
            role=Role.SUPER_ADMIN,
            is_active=True,
            receive_alert=True,
        )
        db.add(admin)
        db.flush()

        ensure_default_stages(db, updated_by=admin.id)
        active_stages = get_active_stages(db)
        stage_by_code = {item.code: item for item in active_stages}

        created_assignees = 0
        existing_names = set()
        for name in sorted(assignee_names):
            normalized = _normalize_name(name)
            if not normalized or normalized.lower() in existing_names:
                continue

            base = _slugify_name(normalized)
            email = f'{base}@cibics.local'
            suffix = 1
            while db.query(User.id).filter(func.lower(User.email) == email.lower()).first():
                suffix += 1
                email = f'{base}{suffix}@cibics.local'

            user = User(
                full_name=normalized,
                email=email,
                password_hash=get_password_hash(settings.default_assignee_password),
                role=Role.ASSIGNEE,
                is_active=True,
                receive_alert=True,
                updated_by=admin.id,
            )
            db.add(user)
            existing_names.add(normalized.lower())
            created_assignees += 1

        db.flush()

        assignee_by_name = {
            _normalize_name(item.full_name).lower(): item
            for item in db.query(User).filter(User.role == Role.ASSIGNEE).all()
        }

        inserted = 0
        for rec in records:
            assignee_id = None
            if rec['assignee_name_hint']:
                assignee = assignee_by_name.get(_normalize_name(rec['assignee_name_hint']).lower())
                assignee_id = assignee.id if assignee else None

            db_record = Record(
                source_row=rec['source_row'],
                sl_no=rec['sl_no'],
                list_type=rec['list_type'],
                type=rec['type'],
                po_status_raw=rec['po_status_raw'],
                custodian_code=rec['custodian_code'],
                unlo_code=rec['unlo_code'],
                short_name=rec['short_name'],
                custodian_organization=rec['custodian_organization'],
                state=rec['state'],
                site_address=rec['site_address'],
                city=rec['city'],
                pincode=rec['pincode'],
                category_of_site=rec['category_of_site'],
                custodian_contact_person_name=rec['custodian_contact_person_name'],
                custodian_contact_person_number=rec['custodian_contact_person_number'],
                custodian_email=rec['custodian_email'],
                customer_name=rec['customer_name'],
                mobile_no=rec['mobile_no'],
                client_email=rec['client_email'],
                assignee_name_hint=rec['assignee_name_hint'],
                assignee_id=assignee_id,
                email_alert_pending=False,
                updated_by=admin.id,
            )
            db.add(db_record)
            db.flush()

            ensure_record_stage_rows(db, db_record, active_stages, updated_by=admin.id)
            stage_rows = {
                item.stage_id: item
                for item in db.query(RecordStageStatus).filter(RecordStageStatus.record_id == db_record.id).all()
            }

            for stage_code, is_completed in rec['stages'].items():
                stage = stage_by_code.get(stage_code)
                if not stage:
                    continue
                row = stage_rows.get(stage.id)
                if not row:
                    continue
                row.is_completed = is_completed
                row.completed_at = db_record.updated_at if is_completed else None
                row.updated_by = admin.id

            db_record.status = derive_status(db_record)
            inserted += 1

        db.commit()

        po_counter = Counter(item['po_status_raw'] for item in records if item['po_status_raw'])
        print('Import completed.')
        print(f"Database: {settings.db_name} @ {settings.db_host}:{settings.db_port}")
        print(f'Total rows imported: {inserted}')
        print(f'Assignee users created: {created_assignees}')
        print('PO STATUS distribution:')
        for key, value in po_counter.items():
            print(f'  {key}: {value}')

    finally:
        db.close()


if __name__ == '__main__':
    main()
