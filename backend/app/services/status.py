from app.models import Record


def derive_status(record: Record) -> str:
    completed = [item for item in record.stage_statuses if item.is_completed and item.stage and item.stage.is_active]
    if completed:
        latest = max(completed, key=lambda x: (x.stage.display_order, x.stage_id))
        return latest.stage.code

    if record.client_email:
        return 'EMAIL_CAPTURED'

    return 'NEW'
