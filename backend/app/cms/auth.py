from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import User, UserCreate, UserLogin
from backend.app.cms.security import (
    require_roles,
    create_access_token,
    get_password_hash,
    verify_password,
)

router = APIRouter(prefix="/cms", tags=["CMS Auth"])


@router.post("/register")
def cms_register(user: UserCreate, db: Session = Depends(get_db), current_user: dict = Depends(require_roles('super_admin', 'admin'))):
    existing_user = db.query(User).filter(
        User.email == user.email
    ).first()

    if existing_user:
        return {
            "status": "error",
            "message": "User already exists."
        }

    db_user = User(
        email=user.email,
        hashed_password=get_password_hash(user.password),
        role=user.role,
        status="active"
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return {
        "status": "created",
        "user": {
            "id": db_user.id,
            "email": db_user.email,
            "role": db_user.role,
            "status": db_user.status
        }
    }


@router.post("/login")
def cms_login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        User.email == credentials.email
    ).first()

    if not user:
        return {
            "status": "error",
            "message": "Invalid credentials."
        }

    if not verify_password(credentials.password, user.hashed_password):
        return {
            "status": "error",
            "message": "Invalid credentials."
        }

    token = create_access_token({
        "sub": user.email,
        "role": user.role,
        "user_id": user.id
    })

    return {
        "status": "authenticated",
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
            "role": user.role
        }
    }
