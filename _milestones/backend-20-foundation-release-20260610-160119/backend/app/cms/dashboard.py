from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import AuditLog, Memorial
from backend.app.cms.security import require_roles

router = APIRouter(prefix="/cms", tags=["CMS Dashboard"])


@router.get("/dashboard")
def cms_dashboard(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    active_memorials = db.query(Memorial).filter(Memorial.status != "deleted").count()
    deleted_memorials = db.query(Memorial).filter(Memorial.status == "deleted").count()
    total_audit_logs = db.query(AuditLog).count()

    recent_activity = (
        db.query(AuditLog)
        .order_by(AuditLog.id.desc())
        .limit(5)
        .all()
    )

    return {
        "module": "CMS Dashboard",
        "status": "active",
        "current_user": current_user,
        "summary": {
            "active_memorials": active_memorials,
            "deleted_memorials": deleted_memorials,
            "total_audit_logs": total_audit_logs
        },
        "recent_activity": [
            {
                "id": log.id,
                "action": log.action,
                "user_email": log.user_email,
                "user_role": log.user_role,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "details": log.details,
                "created_at": log.created_at
            }
            for log in recent_activity
        ]
    }
