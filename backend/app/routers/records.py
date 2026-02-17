from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import require_roles
from app.importers.excel_importer import analyze_phoneme_excel_bytes, import_phoneme_excel_bytes
from app.models import Record, RecordStageStatus, RecordUpdateLog, Role, StageDefinition, User
from app.schemas import (
    ImportPreviewResponse,
    ImportUploadResponse,
    PaginatedRecords,
    RecordOut,
    RecordPatch,
    RecordStageOut,
    StageCreate,
    StageOut,
    StageUpdate,
)
from app.services.alerts import send_email_alert
from app.services.stages import apply_stage_completion, ensure_record_stage_rows, get_active_stages
from app.services.status import derive_status

router = APIRouter(prefix='/records', tags=['records'])

ASSIGNEE_ALLOWED = {'customer_name', 'mobile_no', 'client_email', 'notes'}
EMAIL_TEAM_ALLOWED = {'stage_updates', 'email_alert_pending', 'notes'}


def _serialize_record(record: Record) -> RecordOut:
    stage_items = sorted(
        [
            RecordStageOut(
                stage_id=item.stage_id,
                stage_code=item.stage.code,
                stage_name=item.stage.name,
                display_order=item.stage.display_order,
                is_completed=item.is_completed,
                completed_at=item.completed_at,
                notes=item.notes,
            )
            for item in record.stage_statuses
            if item.stage and item.stage.is_active
        ],
        key=lambda x: (x.display_order, x.stage_id),
    )

    return RecordOut(
        id=record.id,
        source_row=record.source_row,
        sl_no=record.sl_no,
        list_type=record.list_type,
        type=record.type,
        po_status_raw=record.po_status_raw,
        custodian_code=record.custodian_code,
        unlo_code=record.unlo_code,
        short_name=record.short_name,
        custodian_organization=record.custodian_organization,
        state=record.state,
        site_address=record.site_address,
        city=record.city,
        pincode=record.pincode,
        category_of_site=record.category_of_site,
        custodian_contact_person_name=record.custodian_contact_person_name,
        custodian_contact_person_number=record.custodian_contact_person_number,
        custodian_email=record.custodian_email,
        customer_name=record.customer_name,
        mobile_no=record.mobile_no,
        client_email=record.client_email,
        status=record.status,
        assignee_name_hint=record.assignee_name_hint,
        assignee_id=record.assignee_id,
        email_alert_pending=record.email_alert_pending,
        notes=record.notes,
        is_active=record.is_active,
        updated_by=record.updated_by,
        deleted_by=record.deleted_by,
        created_at=record.created_at,
        updated_at=record.updated_at,
        assignee=record.assignee,
        stage_updates=stage_items,
    )


def _make_log(record_id: int, user_id: int | None, field_name: str, old_value: str | None, new_value: str | None) -> RecordUpdateLog:
    return RecordUpdateLog(
        record_id=record_id,
        updated_by_user_id=user_id,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
        updated_by=user_id,
    )


def _gather_recipients(db: Session) -> list[str]:
    recipients = (
        db.query(User.email)
        .filter(User.is_active.is_(True), User.receive_alert.is_(True))
        .all()
    )
    return sorted({email for (email,) in recipients if email})


@router.get('/stages', response_model=list[StageOut])
def list_stages(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.SUPER_ADMIN, Role.ASSIGNEE, Role.EMAIL_TEAM)),
):
    return get_active_stages(db)


@router.post('/stages', response_model=StageOut, status_code=status.HTTP_201_CREATED)
def create_stage(
    payload: StageCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(Role.SUPER_ADMIN)),
):
    existing = db.query(StageDefinition).filter(func.lower(StageDefinition.code) == payload.code.lower()).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail='Stage code already exists')

    stage = StageDefinition(
        code=payload.code.upper().strip(),
        name=payload.name.strip(),
        display_order=payload.display_order,
        is_default=False,
        updated_by=admin.id,
    )
    db.add(stage)
    db.flush()

    record_ids = [item.id for item in db.query(Record.id).filter(Record.is_active.is_(True)).all()]
    for record_id in record_ids:
        db.add(RecordStageStatus(record_id=record_id, stage_id=stage.id, updated_by=admin.id))

    db.commit()
    db.refresh(stage)
    return stage


@router.patch('/stages/{stage_id}', response_model=StageOut)
def update_stage(
    stage_id: int,
    payload: StageUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(Role.SUPER_ADMIN)),
):
    stage = db.get(StageDefinition, stage_id)
    if not stage:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Stage not found')

    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(stage, key, value)
    stage.updated_by = admin.id

    db.commit()
    db.refresh(stage)
    return stage


@router.post('/import/preview', response_model=ImportPreviewResponse)
def preview_import_records(
    file: UploadFile = File(...),
    preview_limit: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles(Role.SUPER_ADMIN)),
):
    if not file.filename.lower().endswith('.xlsx'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Please upload an .xlsx file')

    try:
        content = file.file.read()
        result = analyze_phoneme_excel_bytes(db, content, preview_limit=preview_limit)
        return ImportPreviewResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post('/import/upload', response_model=ImportUploadResponse)
def upload_import_records(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles(Role.SUPER_ADMIN)),
):
    if not file.filename.lower().endswith('.xlsx'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Please upload an .xlsx file')

    try:
        content = file.file.read()
        result = import_phoneme_excel_bytes(db, content)
        return ImportUploadResponse(**result)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get('/import/template')
def download_import_template(
    _admin: User = Depends(require_roles(Role.SUPER_ADMIN)),
):
    project_root = Path(__file__).resolve().parents[3]
    template_path = project_root / 'Phoneme.xlsx'
    if not template_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Template not found')
    return FileResponse(path=str(template_path), filename='Phoneme.xlsx')


@router.get('', response_model=PaginatedRecords)
def list_records(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=200),
    assignee_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias='status'),
    state: str | None = Query(default=None),
    has_client_email: bool | None = Query(default=None),
    alert_pending: bool | None = Query(default=None),
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.SUPER_ADMIN, Role.ASSIGNEE, Role.EMAIL_TEAM)),
):
    filters = [Record.is_active.is_(True)]

    if current_user.role == Role.ASSIGNEE:
        if assignee_id is not None and assignee_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='You are not authorized to filter records for another assignee',
            )
        filters.append(Record.assignee_id == current_user.id)
        assignee_id = None

    if assignee_id is not None:
        filters.append(Record.assignee_id == assignee_id)
    if status_filter is not None:
        filters.append(Record.status == status_filter)
    if state:
        filters.append(func.lower(Record.state) == state.lower())
    if has_client_email is not None:
        if has_client_email:
            filters.append(and_(Record.client_email.is_not(None), Record.client_email != ''))
        else:
            filters.append(or_(Record.client_email.is_(None), Record.client_email == ''))
    if alert_pending is not None:
        filters.append(Record.email_alert_pending == alert_pending)
    if q:
        pattern = f'%{q.strip()}%'
        filters.append(
            or_(
                Record.short_name.ilike(pattern),
                Record.custodian_organization.ilike(pattern),
                Record.custodian_code.ilike(pattern),
                Record.unlo_code.ilike(pattern),
                Record.custodian_email.ilike(pattern),
                Record.client_email.ilike(pattern),
                Record.assignee_name_hint.ilike(pattern),
            )
        )

    query = db.query(Record).options(
        joinedload(Record.assignee),
        joinedload(Record.stage_statuses).joinedload(RecordStageStatus.stage),
    )
    query = query.filter(*filters)

    total = query.count()
    items = (
        query.order_by(Record.email_alert_pending.desc(), Record.updated_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return PaginatedRecords(total=total, page=page, page_size=page_size, items=[_serialize_record(item) for item in items])


@router.delete('/{record_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_record(
    record_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(Role.SUPER_ADMIN)),
):
    record = db.query(Record).filter(Record.id == record_id, Record.is_active.is_(True)).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Record not found')

    record.is_active = False
    record.deleted_by = admin.id
    record.deleted_at = datetime.now(timezone.utc)
    record.updated_by = admin.id
    db.commit()


@router.get('/{record_id}', response_model=RecordOut)
def get_record(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.SUPER_ADMIN, Role.ASSIGNEE, Role.EMAIL_TEAM)),
):
    record = (
        db.query(Record)
        .options(
            joinedload(Record.assignee),
            joinedload(Record.stage_statuses).joinedload(RecordStageStatus.stage),
        )
        .filter(Record.id == record_id, Record.is_active.is_(True))
        .first()
    )
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Record not found')

    if current_user.role == Role.ASSIGNEE and record.assignee_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Not allowed for this record')

    return _serialize_record(record)


@router.patch('/{record_id}', response_model=RecordOut)
def patch_record(
    record_id: int,
    payload: RecordPatch,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.SUPER_ADMIN, Role.ASSIGNEE, Role.EMAIL_TEAM)),
):
    record = (
        db.query(Record)
        .options(
            joinedload(Record.assignee),
            joinedload(Record.stage_statuses).joinedload(RecordStageStatus.stage),
        )
        .filter(Record.id == record_id, Record.is_active.is_(True))
        .first()
    )
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Record not found')

    data = payload.model_dump(exclude_unset=True)
    if not data:
        return _serialize_record(record)

    if current_user.role == Role.ASSIGNEE:
        if record.assignee_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Not allowed for this record')
        disallowed = set(data.keys()) - ASSIGNEE_ALLOWED
        if disallowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f'Assignee cannot update fields: {sorted(disallowed)}',
            )
    elif current_user.role == Role.EMAIL_TEAM:
        disallowed = set(data.keys()) - EMAIL_TEAM_ALLOWED
        if disallowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f'Email team cannot update fields: {sorted(disallowed)}',
            )

    stage_updates = data.pop('stage_updates', None)

    old_email = record.client_email or ''

    for field, new_value in data.items():
        old_value = getattr(record, field)
        if old_value != new_value:
            setattr(record, field, new_value)
            db.add(
                _make_log(
                    record_id=record.id,
                    user_id=current_user.id,
                    field_name=field,
                    old_value='' if old_value is None else str(old_value),
                    new_value='' if new_value is None else str(new_value),
                )
            )

    if stage_updates is not None:
        stages = get_active_stages(db)
        ensure_record_stage_rows(db, record, stages, updated_by=current_user.id)

        stage_map = {item.stage_id: item for item in record.stage_statuses if item.stage and item.stage.is_active}
        active_ids = {item.id for item in stages}

        for update in stage_updates:
            stage_id = update['stage_id']
            if stage_id not in active_ids:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f'Invalid stage_id: {stage_id}')

            stage_row = stage_map.get(stage_id)
            if not stage_row:
                stage_row = RecordStageStatus(record_id=record.id, stage_id=stage_id, updated_by=current_user.id)
                db.add(stage_row)
                db.flush()
                record.stage_statuses.append(stage_row)

            old_repr, new_repr = apply_stage_completion(
                stage_status=stage_row,
                is_completed=update['is_completed'],
                notes=update.get('notes'),
                updated_by=current_user.id,
            )
            if old_repr != new_repr:
                db.add(
                    _make_log(
                        record_id=record.id,
                        user_id=current_user.id,
                        field_name=f'stage:{stage_id}',
                        old_value=old_repr,
                        new_value=new_repr,
                    )
                )

    record.updated_by = current_user.id
    record.status = derive_status(record)

    new_email = record.client_email or ''
    email_changed = new_email.strip().lower() != old_email.strip().lower()
    email_captured = bool(new_email.strip()) and email_changed

    if email_captured:
        record.email_alert_pending = True
        record.last_email_alert_at = datetime.now(timezone.utc)

        recipients = _gather_recipients(db)
        subject = f'Email Captured: {record.short_name or record.custodian_organization or record.id}'
        body = (
            f'Record ID: {record.id}\n'
            f'Source Row: {record.source_row}\n'
            f'Assignee: {record.assignee.full_name if record.assignee else record.assignee_name_hint or "Unassigned"}\n'
            f'Customer Name: {record.customer_name or ""}\n'
            f'Mobile No: {record.mobile_no or ""}\n'
            f'Client Email: {record.client_email or ""}\n'
            f'Organization: {record.custodian_organization or ""}\n'
            f'State: {record.state or ""}\n'
        )
        background_tasks.add_task(send_email_alert, subject, body, recipients)

    db.commit()
    db.refresh(record)
    record = (
        db.query(Record)
        .options(
            joinedload(Record.assignee),
            joinedload(Record.stage_statuses).joinedload(RecordStageStatus.stage),
        )
        .filter(Record.id == record.id)
        .first()
    )
    return _serialize_record(record)


@router.post('/{record_id}/acknowledge-alert', response_model=RecordOut)
def acknowledge_alert(
    record_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.SUPER_ADMIN, Role.EMAIL_TEAM)),
):
    record = (
        db.query(Record)
        .options(
            joinedload(Record.assignee),
            joinedload(Record.stage_statuses).joinedload(RecordStageStatus.stage),
        )
        .filter(Record.id == record_id, Record.is_active.is_(True))
        .first()
    )
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Record not found')

    old_value = record.email_alert_pending
    record.email_alert_pending = False
    record.updated_by = current_user.id
    db.add(
        _make_log(
            record_id=record.id,
            user_id=current_user.id,
            field_name='email_alert_pending',
            old_value=str(old_value),
            new_value='False',
        )
    )

    db.commit()
    db.refresh(record)
    return _serialize_record(record)
