from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import User, AccountSecurityEvent
from backend.app.cms.security import require_roles


router = APIRouter(prefix="/cms/users", tags=["CMS Users"])


ACCOUNT_ROLES = [
    "free",
    "member",
    "creator",
    "rescue",
    "affiliate",
    "admin",
    "super_admin",
]

ADMIN_ASSIGNABLE_ROLES = [
    "free",
    "member",
    "creator",
    "rescue",
    "affiliate",
]


def change_user_role(
    user_id: int,
    role: str,
    db: Session,
    current_user: dict
):
    current_role = current_user.get("role")

    if role not in ACCOUNT_ROLES:
        return {
            "module": "CMS Users",
            "status": "error",
            "message": "Invalid user role.",
            "allowed_roles": ACCOUNT_ROLES,
        }

    if current_role == "admin" and role not in ADMIN_ASSIGNABLE_ROLES:
        return {
            "module": "CMS Users",
            "status": "error",
            "message": "Admin users cannot assign elevated CMS roles.",
            "allowed_roles": ADMIN_ASSIGNABLE_ROLES,
        }

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {
            "module": "CMS Users",
            "status": "error",
            "message": "User not found.",
        }

    if user.role in ["admin", "super_admin"] and current_role != "super_admin":
        return {
            "module": "CMS Users",
            "status": "error",
            "message": "Only super_admin can change CMS administrator roles.",
        }

    old_role = user.role
    user.role = role

    db.commit()
    db.refresh(user)

    return {
        "module": "CMS Users",
        "status": "role_updated",
        "old_role": old_role,
        "new_role": user.role,
        "record": serialize_user(user)
    }


USER_STATUSES = [
    "active",
    "suspended",
    "blocked",
    "pending_review",
    "deleted",
]


def serialize_user(user: User):
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "status": user.status,
        "affiliate_id": user.affiliate_id,
        "referral_code": user.referral_code,
        "referring_affiliate_id": user.referring_affiliate_id,
    }


def serialize_security_event(event: AccountSecurityEvent):
    return {
        "id": event.id,
        "user_id": event.user_id,
        "email": event.email,
        "event_type": event.event_type,
        "status": event.status,
        "ip_address": event.ip_address,
        "user_agent": event.user_agent,
        "created_at": event.created_at,
    }


def change_user_status(user_id: int, status: str, db: Session):
    if status not in USER_STATUSES:
        return {
            "module": "CMS Users",
            "status": "error",
            "message": "Invalid user status.",
            "allowed_statuses": USER_STATUSES,
        }

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {
            "module": "CMS Users",
            "status": "error",
            "message": "User not found.",
        }

    user.status = status

    db.commit()
    db.refresh(user)

    return {
        "module": "CMS Users",
        "status": "updated",
        "record": serialize_user(user)
    }


@router.get("/")
def list_users(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin"))
):
    users = db.query(User).order_by(User.id.desc()).all()

    return {
        "module": "CMS Users",
        "status": "active",
        "count": len(users),
        "records": [
            serialize_user(user)
            for user in users
        ]
    }


@router.post("/{user_id}/role")
def update_user_role(
    user_id: int,
    role: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin"))
):
    return change_user_role(
        user_id=user_id,
        role=role,
        db=db,
        current_user=current_user
    )


@router.post("/{user_id}/block")
def block_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin"))
):
    return change_user_status(user_id=user_id, status="blocked", db=db)


@router.post("/{user_id}/suspend")
def suspend_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin"))
):
    return change_user_status(user_id=user_id, status="suspended", db=db)


@router.post("/{user_id}/pending-review")
def pending_review_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin"))
):
    return change_user_status(user_id=user_id, status="pending_review", db=db)


@router.post("/{user_id}/activate")
def activate_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin"))
):
    return change_user_status(user_id=user_id, status="active", db=db)


@router.post("/{user_id}/delete")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin"))
):
    return change_user_status(user_id=user_id, status="deleted", db=db)


@router.get("/security-summary")
def security_summary(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin"))
):
    events = db.query(AccountSecurityEvent).order_by(
        AccountSecurityEvent.id.desc()
    ).limit(500).all()

    by_event_type = {}
    by_status = {}
    by_ip = {}

    for event in events:
        by_event_type[event.event_type] = by_event_type.get(event.event_type, 0) + 1
        by_status[event.status] = by_status.get(event.status, 0) + 1

        if event.ip_address:
            by_ip[event.ip_address] = by_ip.get(event.ip_address, 0) + 1

    top_ips = [
        {"ip_address": ip, "count": count}
        for ip, count in sorted(by_ip.items(), key=lambda item: item[1], reverse=True)[:10]
    ]

    recent_events = [
        serialize_security_event(event)
        for event in events[:20]
    ]

    return {
        "module": "CMS Security Summary",
        "status": "active",
        "window": "latest_500_events",
        "total_events": len(events),
        "by_event_type": by_event_type,
        "by_status": by_status,
        "top_ips": top_ips,
        "recent_events": recent_events
    }


@router.get("/security-events")
def list_security_events(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin"))
):
    events = db.query(AccountSecurityEvent).order_by(
        AccountSecurityEvent.id.desc()
    ).limit(100).all()

    return {
        "module": "CMS Security Events",
        "status": "active",
        "count": len(events),
        "records": [
            serialize_security_event(event)
            for event in events
        ]
    }
