from collections import defaultdict
from datetime import datetime, timedelta, timezone
from datetime import date as date_type

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Integer, cast, func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import require_roles
from app.models import Record, RecordStageStatus, RecordUpdateLog, Role, StageDefinition, User
from app.schemas import (
    AssigneeSummary,
    DashboardSummary,
    StageProgressDetailItem,
    StageProgressDetailResponse,
    StageProgressResponse,
    StageProgressRow,
    StatusSummary,
)
from app.services.po_status import is_po_received_raw

router = APIRouter(prefix='/dashboard', tags=['dashboard'])


def _has_stage(record: Record, stage_code: str) -> bool:
    if stage_code == 'PO_RECEIVED' and is_po_received_raw(record.po_status_raw):
        return True
    return any(
        item.is_completed and item.stage and item.stage.code == stage_code and item.stage.is_active
        for item in record.stage_statuses
    )


def _count_recent_email_changes(
    db: Session,
    *,
    since: datetime,
    base_record_query,
    updated_by_user_id: int | None = None,
    updated_by_role: Role | None = None,
    captured_only: bool,
) -> int:
    query = (
        db.query(func.count(func.distinct(RecordUpdateLog.record_id)))
        .join(Record, Record.id == RecordUpdateLog.record_id)
        .filter(
            Record.is_active.is_(True),
            RecordUpdateLog.field_name == 'client_email',
            RecordUpdateLog.created_at >= since,
        )
    )

    if updated_by_user_id is not None:
        query = query.filter(RecordUpdateLog.updated_by_user_id == updated_by_user_id)
    elif updated_by_role is not None:
        query = query.join(User, User.id == RecordUpdateLog.updated_by_user_id).filter(User.role == updated_by_role)

    base_filtered = base_record_query.with_entities(Record.id).subquery()
    query = query.filter(RecordUpdateLog.record_id.in_(base_filtered))

    if captured_only:
        query = query.filter(
            (func.coalesce(RecordUpdateLog.old_value, '') == ''),
            (func.coalesce(RecordUpdateLog.new_value, '') != ''),
        )
    else:
        query = query.filter(
            (func.coalesce(RecordUpdateLog.old_value, '') != ''),
            (func.coalesce(RecordUpdateLog.new_value, '') != ''),
            (RecordUpdateLog.old_value != RecordUpdateLog.new_value),
        )

    result = query.scalar()
    return int(result or 0)


@router.get('/summary', response_model=DashboardSummary)
def summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.SUPER_ADMIN, Role.ASSIGNEE, Role.EMAIL_TEAM)),
):
    base_query = db.query(Record).filter(Record.is_active.is_(True))

    total = base_query.count()
    with_email = base_query.filter(Record.client_email.is_not(None), Record.client_email != '').count()
    without_email = (
        base_query
        .filter((Record.client_email.is_(None)) | (Record.client_email == ''))
        .filter(Record.status != 'PO_RECEIVED')
        .count()
    )
    pending = base_query.filter(Record.email_alert_pending.is_(True)).count()
    unassigned = base_query.filter(Record.assignee_id.is_(None)).count()
    unassigned_with_email = (
        base_query
        .filter(Record.assignee_id.is_(None))
        .filter(Record.client_email.is_not(None), Record.client_email != '')
        .count()
    )

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    if current_user.role == Role.ASSIGNEE:
        recent_captured = _count_recent_email_changes(
            db,
            since=since,
            base_record_query=base_query,
            updated_by_user_id=current_user.id,
            captured_only=True,
        )
        recent_updated = _count_recent_email_changes(
            db,
            since=since,
            base_record_query=base_query,
            updated_by_user_id=current_user.id,
            captured_only=False,
        )
    else:
        recent_captured = _count_recent_email_changes(
            db,
            since=since,
            base_record_query=base_query,
            updated_by_role=Role.ASSIGNEE,
            captured_only=True,
        )
        recent_updated = _count_recent_email_changes(
            db,
            since=since,
            base_record_query=base_query,
            updated_by_role=Role.ASSIGNEE,
            captured_only=False,
        )

    return DashboardSummary(
        total_records=total,
        with_client_email=with_email,
        without_client_email=without_email,
        alerts_pending=pending,
        unassigned=unassigned,
        unassigned_with_client_email=unassigned_with_email,
        recent_email_captured_24h=recent_captured,
        recent_email_updated_24h=recent_updated,
    )


@router.get('/by-assignee', response_model=list[AssigneeSummary])
def by_assignee(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.SUPER_ADMIN, Role.ASSIGNEE, Role.EMAIL_TEAM)),
):
    assignees = (
        db.query(User)
        .filter(User.role.in_([Role.ASSIGNEE, Role.SUPER_ADMIN]), User.is_active.is_(True))
        .order_by(User.full_name.asc())
        .all()
    )

    since = datetime.now(timezone.utc) - timedelta(hours=24)
    assignee_ids = [item.id for item in assignees]
    recent_captured_by_user = {
        int(user_id): int(count)
        for user_id, count in (
            db.query(
                RecordUpdateLog.updated_by_user_id,
                func.count(func.distinct(RecordUpdateLog.record_id)).label('count'),
            )
            .filter(
                RecordUpdateLog.updated_by_user_id.in_(assignee_ids),
                RecordUpdateLog.field_name == 'client_email',
                RecordUpdateLog.created_at >= since,
                (func.coalesce(RecordUpdateLog.old_value, '') == ''),
                (func.coalesce(RecordUpdateLog.new_value, '') != ''),
            )
            .group_by(RecordUpdateLog.updated_by_user_id)
            .all()
        )
        if user_id is not None
    }
    recent_updated_by_user = {
        int(user_id): int(count)
        for user_id, count in (
            db.query(
                RecordUpdateLog.updated_by_user_id,
                func.count(func.distinct(RecordUpdateLog.record_id)).label('count'),
            )
            .filter(
                RecordUpdateLog.updated_by_user_id.in_(assignee_ids),
                RecordUpdateLog.field_name == 'client_email',
                RecordUpdateLog.created_at >= since,
                (func.coalesce(RecordUpdateLog.old_value, '') != ''),
                (func.coalesce(RecordUpdateLog.new_value, '') != ''),
                (RecordUpdateLog.old_value != RecordUpdateLog.new_value),
            )
            .group_by(RecordUpdateLog.updated_by_user_id)
            .all()
        )
        if user_id is not None
    }

    records = (
        db.query(Record)
        .options(joinedload(Record.stage_statuses).joinedload(RecordStageStatus.stage))
        .filter(Record.is_active.is_(True))
        .all()
    )

    grouped: dict[int | None, list[Record]] = defaultdict(list)
    for item in records:
        grouped[item.assignee_id].append(item)

    result: list[AssigneeSummary] = []
    for assignee in assignees:
        rows = grouped.get(assignee.id, [])
        total = len(rows)
        if assignee.role == Role.SUPER_ADMIN and total == 0:
            continue
        with_email = sum(1 for item in rows if item.client_email)
        alerts_pending = sum(1 for item in rows if item.email_alert_pending)
        po_received = sum(1 for item in rows if _has_stage(item, 'PO_RECEIVED'))
        proposal_sent = sum(1 for item in rows if _has_stage(item, 'PROPOSAL_SENT'))
        feasibility_pending = sum(
            1
            for item in rows
            if not _has_stage(item, 'EMAIL_RECEIVED_FROM_BSNL_AFTER_FEASIBILITY')
        )
        recent_email_captured_24h = recent_captured_by_user.get(assignee.id, 0)
        recent_email_updated_24h = recent_updated_by_user.get(assignee.id, 0)

        result.append(
            AssigneeSummary(
                assignee_id=assignee.id,
                assignee_name=assignee.full_name,
                total=total,
                with_client_email=with_email,
                recent_email_captured_24h=recent_email_captured_24h,
                recent_email_updated_24h=recent_email_updated_24h,
                alerts_pending=alerts_pending,
                po_received=po_received,
                proposal_sent=proposal_sent,
                feasibility_pending=feasibility_pending,
            )
        )

    return result


@router.get('/by-status', response_model=list[StatusSummary])
def by_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.SUPER_ADMIN, Role.ASSIGNEE, Role.EMAIL_TEAM)),
):
    query = db.query(Record.status, func.count(Record.id).label('count')).filter(Record.is_active.is_(True))

    rows = query.group_by(Record.status).order_by(Record.status.asc()).all()
    return [StatusSummary(status=row.status, count=int(row.count)) for row in rows]


def _week_start_utc(today: datetime) -> datetime:
    base = today.astimezone(timezone.utc)
    monday = base.date() - timedelta(days=base.date().weekday())
    return datetime(monday.year, monday.month, monday.day, tzinfo=timezone.utc)


@router.get('/stage-progress', response_model=StageProgressResponse)
def stage_progress(
    start_date: date_type | None = Query(default=None),
    days: int = Query(default=7, ge=1, le=31),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.SUPER_ADMIN, Role.ASSIGNEE, Role.EMAIL_TEAM)),
):
    now = datetime.now(timezone.utc)
    start_dt = (
        datetime(start_date.year, start_date.month, start_date.day, tzinfo=timezone.utc)
        if start_date
        else _week_start_utc(now)
    )
    end_dt = start_dt + timedelta(days=days)
    date_keys = [(start_dt + timedelta(days=i)).date().isoformat() for i in range(days)]

    base_record_query = db.query(Record.id).filter(Record.is_active.is_(True))
    if current_user.role == Role.ASSIGNEE:
        base_record_query = base_record_query.filter(Record.assignee_id == current_user.id)
    base_record_ids = base_record_query.subquery()

    stages = db.query(StageDefinition).filter(StageDefinition.is_active.is_(True)).order_by(StageDefinition.display_order.asc(), StageDefinition.id.asc()).all()

    email_counts_by_day = {k: 0 for k in date_keys}
    email_rows = (
        db.query(func.date(RecordUpdateLog.created_at).label('day'), func.count(func.distinct(RecordUpdateLog.record_id)).label('count'))
        .filter(
            RecordUpdateLog.field_name == 'client_email',
            RecordUpdateLog.created_at >= start_dt,
            RecordUpdateLog.created_at < end_dt,
            (func.coalesce(RecordUpdateLog.old_value, '') == ''),
            (func.coalesce(RecordUpdateLog.new_value, '') != ''),
            RecordUpdateLog.record_id.in_(base_record_ids),
        )
        .group_by(func.date(RecordUpdateLog.created_at))
        .all()
    )
    for day, count in email_rows:
        if day:
            email_counts_by_day[str(day)] = int(count or 0)

    stage_id_expr = cast(func.split_part(RecordUpdateLog.field_name, ':', 2), Integer)
    stage_counts = {}
    stage_rows = (
        db.query(
            StageDefinition.id.label('stage_id'),
            StageDefinition.code.label('stage_code'),
            StageDefinition.name.label('stage_name'),
            func.date(RecordUpdateLog.created_at).label('day'),
            func.count(func.distinct(RecordUpdateLog.record_id)).label('count'),
        )
        .join(StageDefinition, StageDefinition.id == stage_id_expr)
        .filter(
            StageDefinition.is_active.is_(True),
            RecordUpdateLog.field_name.like('stage:%'),
            RecordUpdateLog.created_at >= start_dt,
            RecordUpdateLog.created_at < end_dt,
            RecordUpdateLog.new_value.like('True|%'),
            RecordUpdateLog.record_id.in_(base_record_ids),
        )
        .group_by(StageDefinition.id, StageDefinition.code, StageDefinition.name, func.date(RecordUpdateLog.created_at))
        .all()
    )
    for stage_id, stage_code, stage_name, day, count in stage_rows:
        stage_counts[(int(stage_id), str(day))] = int(count or 0)

    def counts_for_stage_id(stage_id: int) -> list[int]:
        return [stage_counts.get((stage_id, day), 0) for day in date_keys]

    rows: list[StageProgressRow] = [StageProgressRow(key='EMAIL_FOLLOW_UP', label='Email follow-up', counts=[email_counts_by_day[d] for d in date_keys])]
    for stage in stages:
        rows.append(StageProgressRow(key=stage.code, label=stage.name, counts=counts_for_stage_id(stage.id)))

    return StageProgressResponse(
        start_date=start_dt.date().isoformat(),
        days=days,
        dates=date_keys,
        rows=rows,
    )


@router.get('/stage-progress/details', response_model=StageProgressDetailResponse)
def stage_progress_details(
    day: date_type = Query(...),
    stage_key: str = Query(..., min_length=1, max_length=120),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.SUPER_ADMIN, Role.ASSIGNEE, Role.EMAIL_TEAM)),
):
    start_dt = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    end_dt = start_dt + timedelta(days=1)

    base_record_query = db.query(Record.id, Record.assignee_id).filter(Record.is_active.is_(True))
    if current_user.role == Role.ASSIGNEE:
        base_record_query = base_record_query.filter(Record.assignee_id == current_user.id)
    base_record_ids = base_record_query.with_entities(Record.id).subquery()

    stage_label = stage_key

    if stage_key.upper() == 'EMAIL_FOLLOW_UP':
        stage_label = 'Email follow-up'
        rows = (
            db.query(
                Record.assignee_id.label('assignee_id'),
                func.count(func.distinct(RecordUpdateLog.record_id)).label('count'),
            )
            .join(Record, Record.id == RecordUpdateLog.record_id)
            .filter(
                RecordUpdateLog.field_name == 'client_email',
                RecordUpdateLog.created_at >= start_dt,
                RecordUpdateLog.created_at < end_dt,
                (func.coalesce(RecordUpdateLog.old_value, '') == ''),
                (func.coalesce(RecordUpdateLog.new_value, '') != ''),
                RecordUpdateLog.record_id.in_(base_record_ids),
            )
            .group_by(Record.assignee_id)
            .all()
        )
        counts_by_assignee = {assignee_id: int(count or 0) for assignee_id, count in rows}
    else:
        stage = (
            db.query(StageDefinition)
            .filter(func.upper(StageDefinition.code) == stage_key.upper(), StageDefinition.is_active.is_(True))
            .first()
        )
        if not stage:
            return StageProgressDetailResponse(date=day.isoformat(), stage_key=stage_key, stage_label=stage_key, items=[])

        stage_label = stage.name
        stage_id_expr = cast(func.split_part(RecordUpdateLog.field_name, ':', 2), Integer)
        rows = (
            db.query(
                Record.assignee_id.label('assignee_id'),
                func.count(func.distinct(RecordUpdateLog.record_id)).label('count'),
            )
            .join(Record, Record.id == RecordUpdateLog.record_id)
            .filter(
                RecordUpdateLog.field_name.like('stage:%'),
                stage_id_expr == stage.id,
                RecordUpdateLog.created_at >= start_dt,
                RecordUpdateLog.created_at < end_dt,
                RecordUpdateLog.new_value.like('True|%'),
                RecordUpdateLog.record_id.in_(base_record_ids),
            )
            .group_by(Record.assignee_id)
            .all()
        )
        counts_by_assignee = {assignee_id: int(count or 0) for assignee_id, count in rows}

    assignee_ids = [aid for aid in counts_by_assignee.keys() if aid is not None]
    assignees = (
        db.query(User.id, User.full_name)
        .filter(User.id.in_(assignee_ids))
        .all()
        if assignee_ids
        else []
    )
    name_by_id = {int(uid): name for uid, name in assignees}

    items: list[StageProgressDetailItem] = []
    for assignee_id, count in sorted(counts_by_assignee.items(), key=lambda x: (-x[1], x[0] or 0)):
        if count <= 0:
            continue
        items.append(
            StageProgressDetailItem(
                assignee_id=assignee_id,
                assignee_name=name_by_id.get(int(assignee_id), 'Unassigned') if assignee_id is not None else 'Unassigned',
                record_count=count,
            )
        )

    return StageProgressDetailResponse(
        date=day.isoformat(),
        stage_key=stage_key,
        stage_label=stage_label,
        items=items,
    )
