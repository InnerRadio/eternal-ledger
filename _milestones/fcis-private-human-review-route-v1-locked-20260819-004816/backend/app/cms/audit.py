from datetime import datetime, timezone

from backend.app.models import AuditLog


def write_audit_log(
    db,
    action: str,
    current_user: dict | None = None,
    target_type: str | None = None,
    target_id: int | None = None,
    details: str | None = None
):
    log = AuditLog(
        user_id=current_user.get("user_id") if current_user else None,
        user_email=current_user.get("email") if current_user else None,
        user_role=current_user.get("role") if current_user else None,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
        created_at=datetime.now(timezone.utc)
    )

    db.add(log)
    db.commit()
    db.refresh(log)

    return log
