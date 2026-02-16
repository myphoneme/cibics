from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import Record, RecordStageStatus, StageDefinition


DEFAULT_STAGES = [
    {
        'code': 'EMAIL_SENT_TO_CUSTOMER',
        'name': 'Email Sent To Customer',
        'display_order': 10,
    },
    {
        'code': 'DATA_RECEIVED_FROM_CUSTOMER',
        'name': 'Data Received From Customer',
        'display_order': 20,
    },
    {
        'code': 'EMAIL_SENT_TO_BSNL_FOR_FEASIBILITY',
        'name': 'Email Sent To BSNL For Feasibility',
        'display_order': 30,
    },
    {
        'code': 'EMAIL_RECEIVED_FROM_BSNL_AFTER_FEASIBILITY',
        'name': 'Email Received From BSNL After Feasibility',
        'display_order': 40,
    },
    {
        'code': 'PROPOSAL_SENT',
        'name': 'Proposal Sent',
        'display_order': 50,
    },
    {
        'code': 'PO_RECEIVED',
        'name': 'PO Received',
        'display_order': 60,
    },
]


def ensure_default_stages(db: Session, updated_by: int | None = None) -> None:
    existing = {item.code: item for item in db.query(StageDefinition).all()}

    for stage in DEFAULT_STAGES:
        if stage['code'] in existing:
            continue

        db.add(
            StageDefinition(
                code=stage['code'],
                name=stage['name'],
                display_order=stage['display_order'],
                is_default=True,
                updated_by=updated_by,
            )
        )

    db.flush()


def get_active_stages(db: Session) -> list[StageDefinition]:
    return (
        db.query(StageDefinition)
        .filter(StageDefinition.is_active.is_(True))
        .order_by(StageDefinition.display_order.asc(), StageDefinition.id.asc())
        .all()
    )


def ensure_record_stage_rows(
    db: Session,
    record: Record,
    stages: list[StageDefinition],
    updated_by: int | None = None,
) -> None:
    existing = {item.stage_id: item for item in record.stage_statuses}

    for stage in stages:
        if stage.id in existing:
            continue

        db.add(
            RecordStageStatus(
                record_id=record.id,
                stage_id=stage.id,
                is_completed=False,
                updated_by=updated_by,
            )
        )

    db.flush()


def apply_stage_completion(
    stage_status: RecordStageStatus,
    is_completed: bool,
    notes: str | None,
    updated_by: int | None,
) -> tuple[str, str]:
    old_repr = f"{stage_status.is_completed}|{stage_status.completed_at.isoformat() if stage_status.completed_at else ''}|{stage_status.notes or ''}"

    stage_status.is_completed = is_completed
    stage_status.notes = notes
    stage_status.updated_by = updated_by
    if is_completed:
        stage_status.completed_at = stage_status.completed_at or datetime.now(timezone.utc)
    else:
        stage_status.completed_at = None

    new_repr = f"{stage_status.is_completed}|{stage_status.completed_at.isoformat() if stage_status.completed_at else ''}|{stage_status.notes or ''}"
    return old_repr, new_repr
