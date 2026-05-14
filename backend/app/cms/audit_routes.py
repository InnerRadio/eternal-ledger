from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import AuditLog
from backend.app.cms.security import require_roles

router = APIRouter(prefix="/cms/audit-logs", tags=["CMS Audit Logs"])


@router.get("/")
def list_audit_logs(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin"))
):
    logs = db.query(AuditLog).order_by(AuditLog.id.desc()).all()

    return {
        "module": "CMS Audit Logs",
        "status": "active",
        "count": len(logs),
        "records": [
            {
                "id": log.id,
                "user_id": log.user_id,
                "user_email": log.user_email,
                "user_role": log.user_role,
                "action": log.action,
                "target_type": log.target_type,
                "target_id": log.target_id,
                "details": log.details,
                "created_at": log.created_at,
            }
            for log in logs
        ]
    }
