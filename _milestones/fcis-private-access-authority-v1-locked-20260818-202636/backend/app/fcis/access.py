"""
FCIS Private Access Authority v1

Purpose:
Protect private FCIS intelligence behind the existing authenticated
identity authority plus a live database authorization check.

V1 access contract:

- valid bearer identity
- live User record exists
- live User status == "active"
- live User role == "admin"

This module does not:
- create users
- change user roles
- change user status
- create routes
- expose FCIS publicly
"""

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.cms.security import get_current_user
from backend.app.database import SessionLocal
from backend.app.models import User


FCIS_ALLOWED_ROLES = (
    "admin",
)


def authorize_fcis_user(
    db: Session,
    current_user: dict,
):
    """
    Authorize one already-authenticated identity against
    the live User authority.

    Returns a normalized FCIS operator identity on success.
    Raises HTTPException on failure.
    """

    if not isinstance(current_user, dict):
        raise HTTPException(
            status_code=401,
            detail="Authenticated identity is required.",
        )

    user_id = current_user.get("user_id")

    if not isinstance(user_id, int) or user_id <= 0:
        raise HTTPException(
            status_code=401,
            detail="Authenticated user identity is invalid.",
        )

    user = db.query(User).filter(
        User.id == user_id
    ).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Account not found.",
        )

    if user.status != "active":
        raise HTTPException(
            status_code=403,
            detail="FCIS access requires an active account.",
        )

    if user.role not in FCIS_ALLOWED_ROLES:
        raise HTTPException(
            status_code=403,
            detail="FCIS access denied.",
        )

    return {
        "user_id": user.id,
        "email": user.email,
        "role": user.role,
        "status": user.status,
        "fcis_authorized": True,
    }


def require_fcis_access(
    current_user: dict = Depends(get_current_user),
):
    """
    FastAPI dependency for future private FCIS routes.

    Authentication:
        existing get_current_user bearer authority

    Authorization:
        live database FCIS authority
    """

    db = SessionLocal()

    try:
        return authorize_fcis_user(
            db=db,
            current_user=current_user,
        )

    finally:
        db.close()
