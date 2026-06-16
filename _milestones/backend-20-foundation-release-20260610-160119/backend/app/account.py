from fastapi import APIRouter, Depends, Request, File, Form, UploadFile
from sqlalchemy.orm import Session
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timedelta
import secrets
import string

from backend.app.database import get_db
from backend.app.models import User, UserCreate, UserLogin, MemorialCreate, ContributionCreate, Memorial, Contribution, MediaAsset, AccountSecurityEvent
from backend.app.cms.security import (
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
    require_active_account,
)


router = APIRouter(prefix="/account", tags=["Account"])

UPLOAD_DIR = Path("/var/www/eternal-ledger-github/uploads/media")


ACCOUNT_ALLOWED_ROLES = [
    "free",
    "member",
    "creator",
    "rescue",
    "affiliate",
]


MEDIA_TIER_LIMITS = {
    "free": {
        "max_file_size": 5 * 1024 * 1024,
        "allowed_media_types": ["image"],
        "max_per_memorial": 3,
    },
    "member": {
        "max_file_size": 25 * 1024 * 1024,
        "allowed_media_types": ["image", "audio"],
        "max_per_memorial": 20,
    },
    "creator": {
        "max_file_size": 50 * 1024 * 1024,
        "allowed_media_types": ["image", "audio", "video"],
        "max_per_memorial": 50,
    },
    "rescue": {
        "max_file_size": 50 * 1024 * 1024,
        "allowed_media_types": ["image", "audio", "video"],
        "max_per_memorial": 50,
    },
    "affiliate": {
        "max_file_size": 25 * 1024 * 1024,
        "allowed_media_types": ["image", "audio"],
        "max_per_memorial": 20,
    },
    "admin": {
        "max_file_size": 50 * 1024 * 1024,
        "allowed_media_types": ["image", "audio", "video"],
        "max_per_memorial": 100,
    },
    "super_admin": {
        "max_file_size": 50 * 1024 * 1024,
        "allowed_media_types": ["image", "audio", "video"],
        "max_per_memorial": 100,
    },
}


MEDIA_EXTENSIONS = {
    "image": [".jpg", ".jpeg", ".png", ".webp"],
    "audio": [".mp3", ".wav", ".m4a"],
    "video": [".mp4", ".mov", ".webm"],
}


def media_tier_limits_for_role(role: str):
    return MEDIA_TIER_LIMITS.get(role, MEDIA_TIER_LIMITS["free"])


def serialize_media(asset: MediaAsset):
    return {
        "id": asset.id,
        "memorial_id": asset.memorial_id,
        "file_path": asset.file_path,
        "original_filename": asset.original_filename,
        "media_type": asset.media_type,
        "status": asset.status,
        "uploaded_by_user_id": asset.uploaded_by_user_id,
        "ipfs_cid": asset.ipfs_cid,
        "xrpl_tx_hash": asset.xrpl_tx_hash,
        "created_at": asset.created_at,
    }


LOGIN_LOCKOUT_WINDOW_MINUTES = 15
LOGIN_LOCKOUT_BAD_PASSWORD_LIMIT = 5


def recent_bad_password_count(db: Session, user_id: int):
    cutoff = datetime.utcnow() - timedelta(minutes=LOGIN_LOCKOUT_WINDOW_MINUTES)

    return db.query(AccountSecurityEvent).filter(
        AccountSecurityEvent.user_id == user_id,
        AccountSecurityEvent.event_type == "login_failed",
        AccountSecurityEvent.status == "bad_password",
        AccountSecurityEvent.created_at >= cutoff
    ).count()


STATUS_FLOW = [
    "draft",
    "submitted",
    "in_review",
    "changes_requested",
    "approved",
    "published",
    "archived",
    "deleted",
]


def generate_affiliate_id(length=12):
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_referral_code(length=8):
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))



def get_request_ip(request: Request):
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()

    return request.client.host if request.client else None


def write_account_security_event(
    db: Session,
    event_type: str,
    status: str,
    request: Request,
    email: str | None = None,
    user_id: int | None = None
):
    event = AccountSecurityEvent(
        user_id=user_id,
        email=email,
        event_type=event_type,
        status=status,
        ip_address=get_request_ip(request),
        user_agent=str(request.headers.get("user-agent") or "")
    )

    db.add(event)
    db.commit()
    return event

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


def status_counts(records):
    counts = {status: 0 for status in STATUS_FLOW}
    for record in records:
        if record.status in counts:
            counts[record.status] += 1
    return counts


@router.post("/register")
def account_register(user: UserCreate, request: Request, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user.email).first()

    if existing_user:
        write_account_security_event(
            db=db,
            event_type="register",
            status="user_exists",
            request=request,
            email=user.email,
            user_id=existing_user.id
        )

        return {
            "module": "Account",
            "status": "error",
            "message": "User already exists."
        }

    role = user.role if user.role in ACCOUNT_ALLOWED_ROLES else "free"

    db_user = User(
        email=user.email,
        hashed_password=get_password_hash(user.password),
        role=role,
        status="active",
        affiliate_id=generate_affiliate_id(),
        referral_code=generate_referral_code(),
        referring_affiliate_id=user.referring_affiliate_id
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    write_account_security_event(
        db=db,
        event_type="register",
        status="success",
        request=request,
        email=db_user.email,
        user_id=db_user.id
    )

    token = create_access_token({
        "sub": db_user.email,
        "role": db_user.role,
        "user_id": db_user.id
    })

    return {
        "module": "Account",
        "status": "registered",
        "access_token": token,
        "token_type": "bearer",
        "user": serialize_user(db_user)
    }


@router.post("/login")
def account_login(credentials: UserLogin, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()

    if not user:
        write_account_security_event(
            db=db,
            event_type="login_failed",
            status="unknown_user",
            request=request,
            email=credentials.email
        )

        return {
            "module": "Account",
            "status": "error",
            "message": "Invalid credentials."
        }

    if user.status != "active":
        write_account_security_event(
            db=db,
            event_type="blocked_login_attempt",
            status=user.status,
            request=request,
            email=user.email,
            user_id=user.id
        )

        return {
            "module": "Account",
            "status": "error",
            "message": "Account is not active."
        }

    bad_password_count = recent_bad_password_count(db=db, user_id=user.id)

    if bad_password_count >= LOGIN_LOCKOUT_BAD_PASSWORD_LIMIT:
        write_account_security_event(
            db=db,
            event_type="login_lockout",
            status="too_many_bad_passwords",
            request=request,
            email=user.email,
            user_id=user.id
        )

        return {
            "module": "Account",
            "status": "error",
            "message": "Too many failed login attempts. Try again later.",
            "lockout_window_minutes": LOGIN_LOCKOUT_WINDOW_MINUTES
        }

    if not verify_password(credentials.password, user.hashed_password):
        write_account_security_event(
            db=db,
            event_type="login_failed",
            status="bad_password",
            request=request,
            email=user.email,
            user_id=user.id
        )

        return {
            "module": "Account",
            "status": "error",
            "message": "Invalid credentials."
        }

    write_account_security_event(
        db=db,
        event_type="login_success",
        status="success",
        request=request,
        email=user.email,
        user_id=user.id
    )

    token = create_access_token({
        "sub": user.email,
        "role": user.role,
        "user_id": user.id
    })

    return {
        "module": "Account",
        "status": "authenticated",
        "access_token": token,
        "token_type": "bearer",
        "user": serialize_user(user)
    }


@router.get("/me")
def account_me(
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == current_user.get("user_id")).first()

    if not user:
        return {
            "module": "Account",
            "status": "error",
            "message": "User not found."
        }

    return {
        "module": "Account",
        "status": "active",
        "user": serialize_user(user)
    }


@router.get("/dashboard")
def account_dashboard(
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")

    memorials = db.query(Memorial).filter(Memorial.created_by_user_id == user_id).all()
    contributions = db.query(Contribution).filter(Contribution.created_by_user_id == user_id).all()
    media_assets = db.query(MediaAsset).filter(MediaAsset.uploaded_by_user_id == user_id).all()

    return {
        "module": "Account Dashboard",
        "status": "active",
        "user_id": user_id,
        "summary": {
            "memorials": {
                "total": len(memorials),
                "by_status": status_counts(memorials)
            },
            "contributions": {
                "total": len(contributions),
                "by_status": status_counts(contributions)
            },
            "media_assets": {
                "total": len(media_assets),
                "by_status": status_counts(media_assets)
            }
        }
    }


@router.get("/memorials")
def account_memorials(
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")
    records = db.query(Memorial).filter(Memorial.created_by_user_id == user_id).all()

    return {
        "module": "Account Memorials",
        "status": "active",
        "count": len(records),
        "records": [
            {
                "id": memorial.id,
                "companion_name": memorial.companion_name,
                "years": memorial.years,
                "story": memorial.story,
                "archive_type": memorial.archive_type,
                "project": memorial.project,
                "environment_theme": memorial.environment_theme,
                "atmosphere_intensity": memorial.atmosphere_intensity,
                "status": memorial.status,
                "created_by_user_id": memorial.created_by_user_id,
            }
            for memorial in records
        ]
    }


@router.post("/memorials")
def account_create_memorial(
    memorial_data: MemorialCreate,
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")

    memorial = Memorial(
        companion_name=memorial_data.companion_name,
        years=memorial_data.years,
        story=memorial_data.story,
        archive_type=memorial_data.archive_type,
        project=memorial_data.project,
        environment_theme=memorial_data.environment_theme,
        atmosphere_intensity=memorial_data.atmosphere_intensity,
        status="draft",
        created_by_user_id=user_id,
    )

    db.add(memorial)
    db.commit()
    db.refresh(memorial)

    return {
        "module": "Account Memorials",
        "status": "created",
        "record": {
            "id": memorial.id,
            "companion_name": memorial.companion_name,
            "years": memorial.years,
            "story": memorial.story,
            "archive_type": memorial.archive_type,
            "project": memorial.project,
            "environment_theme": memorial.environment_theme,
            "atmosphere_intensity": memorial.atmosphere_intensity,
            "status": memorial.status,
            "created_by_user_id": memorial.created_by_user_id,
        }
    }


@router.post("/memorials/{memorial_id}/submit")
def account_submit_memorial(
    memorial_id: int,
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")

    memorial = db.query(Memorial).filter(
        Memorial.id == memorial_id,
        Memorial.created_by_user_id == user_id
    ).first()

    if not memorial:
        return {
            "module": "Account Memorials",
            "status": "error",
            "message": "Memorial not found."
        }

    if memorial.status not in ["draft", "changes_requested"]:
        return {
            "module": "Account Memorials",
            "status": "error",
            "message": "Only draft or changes_requested memorials can be submitted.",
            "current_status": memorial.status
        }

    memorial.status = "submitted"

    db.commit()
    db.refresh(memorial)

    return {
        "module": "Account Memorials",
        "status": "submitted",
        "record": {
            "id": memorial.id,
            "companion_name": memorial.companion_name,
            "status": memorial.status,
            "created_by_user_id": memorial.created_by_user_id,
        }
    }


@router.post("/contributions")
def account_create_contribution(
    contribution_data: ContributionCreate,
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")

    memorial = db.query(Memorial).filter(
        Memorial.id == contribution_data.memorial_id,
        Memorial.status.in_(["published", "approved", "changes_requested", "draft", "submitted", "in_review"])
    ).first()

    if not memorial:
        return {
            "module": "Account Contributions",
            "status": "error",
            "message": "Memorial not found."
        }

    contribution = Contribution(
        memorial_id=contribution_data.memorial_id,
        contributor_name=contribution_data.contributor_name,
        contribution_type=contribution_data.contribution_type,
        content=contribution_data.content,
        media_asset_id=contribution_data.media_asset_id,
        status="draft",
        created_by_user_id=user_id,
    )

    db.add(contribution)
    db.commit()
    db.refresh(contribution)

    return {
        "module": "Account Contributions",
        "status": "created",
        "record": {
            "id": contribution.id,
            "memorial_id": contribution.memorial_id,
            "contributor_name": contribution.contributor_name,
            "contribution_type": contribution.contribution_type,
            "content": contribution.content,
            "media_asset_id": contribution.media_asset_id,
            "status": contribution.status,
            "created_by_user_id": contribution.created_by_user_id,
        }
    }


@router.post("/contributions/{contribution_id}/submit")
def account_submit_contribution(
    contribution_id: int,
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")

    contribution = db.query(Contribution).filter(
        Contribution.id == contribution_id,
        Contribution.created_by_user_id == user_id
    ).first()

    if not contribution:
        return {
            "module": "Account Contributions",
            "status": "error",
            "message": "Contribution not found."
        }

    if contribution.status not in ["draft", "changes_requested"]:
        return {
            "module": "Account Contributions",
            "status": "error",
            "message": "Only draft or changes_requested contributions can be submitted.",
            "current_status": contribution.status
        }

    contribution.status = "submitted"

    db.commit()
    db.refresh(contribution)

    return {
        "module": "Account Contributions",
        "status": "submitted",
        "record": {
            "id": contribution.id,
            "memorial_id": contribution.memorial_id,
            "status": contribution.status,
            "created_by_user_id": contribution.created_by_user_id,
        }
    }


@router.get("/media")
def account_media(
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")

    assets = db.query(MediaAsset).filter(
        MediaAsset.uploaded_by_user_id == user_id
    ).order_by(MediaAsset.id.desc()).all()

    return {
        "module": "Account Media",
        "status": "active",
        "count": len(assets),
        "records": [
            serialize_media(asset)
            for asset in assets
        ]
    }


@router.post("/media/upload")
async def account_upload_media(
    file: UploadFile = File(...),
    memorial_id: int | None = Form(None),
    media_type: str = Form("image"),
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")
    role = current_user.get("role") or "free"
    limits = media_tier_limits_for_role(role)

    if media_type not in limits["allowed_media_types"]:
        return {
            "module": "Account Media",
            "status": "error",
            "message": "Media type is not allowed for this account tier.",
            "role": role,
            "allowed_media_types": limits["allowed_media_types"]
        }

    if memorial_id == 0:
        memorial_id = None

    if memorial_id is not None:
        memorial = db.query(Memorial).filter(Memorial.id == memorial_id).first()

        if not memorial:
            return {
                "module": "Account Media",
                "status": "error",
                "message": "Memorial not found."
            }

        existing_count = db.query(MediaAsset).filter(
            MediaAsset.memorial_id == memorial_id,
            MediaAsset.uploaded_by_user_id == user_id,
            MediaAsset.status != "deleted"
        ).count()

        if existing_count >= limits["max_per_memorial"]:
            return {
                "module": "Account Media",
                "status": "error",
                "message": "Media limit reached for this memorial.",
                "role": role,
                "max_per_memorial": limits["max_per_memorial"]
            }

    original_filename = file.filename or "uploaded-file"
    extension = Path(original_filename).suffix.lower()

    if extension not in MEDIA_EXTENSIONS.get(media_type, []):
        return {
            "module": "Account Media",
            "status": "error",
            "message": "File extension is not allowed for this media type.",
            "media_type": media_type,
            "allowed_extensions": MEDIA_EXTENSIONS.get(media_type, [])
        }

    content = await file.read()

    if len(content) > limits["max_file_size"]:
        return {
            "module": "Account Media",
            "status": "error",
            "message": "File exceeds account tier upload limit.",
            "role": role,
            "max_file_size_bytes": limits["max_file_size"],
            "received_size_bytes": len(content)
        }

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    stored_filename = f"{uuid4().hex}{extension}"
    stored_path = UPLOAD_DIR / stored_filename
    stored_path.write_bytes(content)

    public_file_path = f"/uploads/media/{stored_filename}"

    asset = MediaAsset(
        memorial_id=memorial_id,
        file_path=public_file_path,
        original_filename=original_filename,
        media_type=media_type,
        status="draft",
        uploaded_by_user_id=user_id,
    )

    db.add(asset)
    db.commit()
    db.refresh(asset)

    return {
        "module": "Account Media",
        "status": "uploaded",
        "record": serialize_media(asset)
    }


@router.post("/media/{asset_id}/submit")
def account_submit_media(
    asset_id: int,
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")

    asset = db.query(MediaAsset).filter(
        MediaAsset.id == asset_id,
        MediaAsset.uploaded_by_user_id == user_id
    ).first()

    if not asset:
        return {
            "module": "Account Media",
            "status": "error",
            "message": "Media asset not found."
        }

    if asset.status not in ["draft", "changes_requested"]:
        return {
            "module": "Account Media",
            "status": "error",
            "message": "Only draft or changes_requested media can be submitted.",
            "current_status": asset.status
        }

    asset.status = "submitted"

    db.commit()
    db.refresh(asset)

    return {
        "module": "Account Media",
        "status": "submitted",
        "record": serialize_media(asset)
    }


@router.get("/contributions")
def account_contributions(
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")
    records = db.query(Contribution).filter(Contribution.created_by_user_id == user_id).all()

    return {
        "module": "Account Contributions",
        "status": "active",
        "count": len(records),
        "records": [
            {
                "id": contribution.id,
                "memorial_id": contribution.memorial_id,
                "contributor_name": contribution.contributor_name,
                "contribution_type": contribution.contribution_type,
                "content": contribution.content,
                "media_asset_id": contribution.media_asset_id,
                "status": contribution.status,
                "created_by_user_id": contribution.created_by_user_id,
                "ipfs_cid": contribution.ipfs_cid,
                "xrpl_tx_hash": contribution.xrpl_tx_hash,
                "created_at": contribution.created_at,
            }
            for contribution in records
        ]
    }
