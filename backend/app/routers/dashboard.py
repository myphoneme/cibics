from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.deps import require_roles
from app.models import Record, RecordStageStatus, Role, User
from app.schemas import AssigneeSummary, DashboardSummary, StatusSummary
from app.services.po_status import is_po_received_raw

router = APIRouter(prefix='/dashboard', tags=['dashboard'])


def _has_stage(record: Record, stage_code: str) -> bool:
    if stage_code == 'PO_RECEIVED' and is_po_received_raw(record.po_status_raw):
        return True
    return any(
        item.is_completed and item.stage and item.stage.code == stage_code and item.stage.is_active
        for item in record.stage_statuses
    )


@router.get('/summary', response_model=DashboardSummary)
def summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.SUPER_ADMIN, Role.ASSIGNEE, Role.EMAIL_TEAM)),
):
    base_query = db.query(Record).filter(Record.is_active.is_(True))
    if current_user.role == Role.ASSIGNEE:
        base_query = base_query.filter(Record.assignee_id == current_user.id)

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

    return DashboardSummary(
        total_records=total,
        with_client_email=with_email,
        without_client_email=without_email,
        alerts_pending=pending,
        unassigned=unassigned,
    )


@router.get('/by-assignee', response_model=list[AssigneeSummary])
def by_assignee(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(Role.SUPER_ADMIN, Role.EMAIL_TEAM)),
):
    assignees = (
        db.query(User)
        .filter(User.role.in_([Role.ASSIGNEE, Role.SUPER_ADMIN]), User.is_active.is_(True))
        .order_by(User.full_name.asc())
        .all()
    )

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

        result.append(
            AssigneeSummary(
                assignee_id=assignee.id,
                assignee_name=assignee.full_name,
                total=total,
                with_client_email=with_email,
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
    if current_user.role == Role.ASSIGNEE:
        query = query.filter(Record.assignee_id == current_user.id)

    rows = query.group_by(Record.status).order_by(Record.status.asc()).all()
    return [StatusSummary(status=row.status, count=int(row.count)) for row in rows]
