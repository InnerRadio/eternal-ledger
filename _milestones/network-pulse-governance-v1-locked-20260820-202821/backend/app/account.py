from fastapi import APIRouter, Depends, Request, File, Form, UploadFile
from sqlalchemy.orm import Session
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timedelta
import secrets
import string

from backend.app.database import get_db
from backend.app.models import User, UserCreate, UserLogin, MemorialCreate, ContributionCreate, Memorial, Contribution, MediaAsset, AccountSecurityEvent, AffiliateConversion, AffiliateClick, AffiliateCommission, AffiliateCampaign, AffiliateCampaignEnrollment, PartnerOrganization, OrganizationMember, PublicProfile, ContactRelayMessage, CommunicationPermission, PartnerTaxonomyCategory, PartnerTaxonomyAssignment, PartnerCampaign
from backend.app.cms.security import (
    create_access_token,
    get_current_user,
    get_password_hash,
    verify_password,
    require_active_account,
)
from backend.app.platform_ranking_aggregation import build_platform_ranking_aggregation


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
        "max_assets_per_account": 10,
        "max_storage_bytes": 25 * 1024 * 1024,
    },
    "member": {
        "max_file_size": 25 * 1024 * 1024,
        "allowed_media_types": ["image", "audio"],
        "max_per_memorial": 20,
        "max_assets_per_account": 100,
        "max_storage_bytes": 500 * 1024 * 1024,
    },
    "creator": {
        "max_file_size": 50 * 1024 * 1024,
        "allowed_media_types": ["image", "audio", "video"],
        "max_per_memorial": 50,
        "max_assets_per_account": 500,
        "max_storage_bytes": 5 * 1024 * 1024 * 1024,
    },
    "rescue": {
        "max_file_size": 50 * 1024 * 1024,
        "allowed_media_types": ["image", "audio", "video"],
        "max_per_memorial": 50,
        "max_assets_per_account": 1000,
        "max_storage_bytes": 10 * 1024 * 1024 * 1024,
    },
    "affiliate": {
        "max_file_size": 25 * 1024 * 1024,
        "allowed_media_types": ["image", "audio"],
        "max_per_memorial": 20,
        "max_assets_per_account": 100,
        "max_storage_bytes": 500 * 1024 * 1024,
    },
    "admin": {
        "max_file_size": 50 * 1024 * 1024,
        "allowed_media_types": ["image", "audio", "video"],
        "max_per_memorial": 100,
        "max_assets_per_account": None,
        "max_storage_bytes": None,
    },
    "super_admin": {
        "max_file_size": 50 * 1024 * 1024,
        "allowed_media_types": ["image", "audio", "video"],
        "max_per_memorial": 100,
        "max_assets_per_account": None,
        "max_storage_bytes": None,
    },
}


MEDIA_EXTENSIONS = {
    "image": [".jpg", ".jpeg", ".png", ".webp"],
    "audio": [".mp3", ".wav", ".m4a"],
    "video": [".mp4", ".mov", ".webm"],
}


def media_tier_limits_for_role(role: str):
    return MEDIA_TIER_LIMITS.get(role, MEDIA_TIER_LIMITS["free"])


def account_media_usage(db: Session, user_id: int):
    assets = db.query(MediaAsset).filter(
        MediaAsset.uploaded_by_user_id == user_id,
        MediaAsset.status != "deleted"
    ).all()

    total_assets = len(assets)
    total_storage_bytes = sum(asset.file_size_bytes or 0 for asset in assets)

    return {
        "total_assets": total_assets,
        "total_storage_bytes": total_storage_bytes,
    }


def account_media_quota(db: Session, user_id: int, role: str):
    limits = media_tier_limits_for_role(role)
    usage = account_media_usage(db=db, user_id=user_id)

    max_assets = limits.get("max_assets_per_account")
    max_storage = limits.get("max_storage_bytes")

    return {
        "role": role,
        "usage": usage,
        "limits": {
            "max_assets_per_account": max_assets,
            "max_storage_bytes": max_storage,
            "max_file_size": limits.get("max_file_size"),
            "max_per_memorial": limits.get("max_per_memorial"),
            "allowed_media_types": limits.get("allowed_media_types"),
        },
        "remaining": {
            "assets": None if max_assets is None else max(max_assets - usage["total_assets"], 0),
            "storage_bytes": None if max_storage is None else max(max_storage - usage["total_storage_bytes"], 0),
        }
    }


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


def serialize_contribution(contribution: Contribution):
    return {
        "id": contribution.id,
        "memorial_id": contribution.memorial_id,
        "contributor_name": contribution.contributor_name,
        "contribution_type": contribution.contribution_type,
        "content": contribution.content,
        "media_asset_id": contribution.media_asset_id,
        "created_by_user_id": contribution.created_by_user_id,
        "status": contribution.status,
        "ipfs_cid": contribution.ipfs_cid,
        "xrpl_tx_hash": contribution.xrpl_tx_hash,
        "created_at": contribution.created_at,
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

def resolve_referring_affiliate(
    db: Session,
    referring_affiliate_id: int | None = None,
    referral_code: str | None = None
):
    if referral_code:
        referrer = db.query(User).filter(
            User.referral_code == referral_code
        ).first()

        if referrer:
            return referrer

    if referring_affiliate_id:
        referrer = db.query(User).filter(
            User.id == referring_affiliate_id
        ).first()

        if referrer:
            return referrer

    return None


def log_signup_conversion(
    db: Session,
    referrer: User | None,
    new_user: User
):
    if not referrer:
        return None

    conversion = AffiliateConversion(
        affiliate_id=referrer.affiliate_id,
        referral_code=referrer.referral_code,
        conversion_type="signup",
        target_type="user",
        target_id=new_user.id,
        status="pending"
    )

    db.add(conversion)
    db.commit()
    db.refresh(conversion)

    return conversion


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


def serialize_account_campaign(
    campaign: AffiliateCampaign,
    enrollment: AffiliateCampaignEnrollment | None = None
):
    return {
        "id": campaign.id,
        "campaign_id": campaign.campaign_id,
        "project": campaign.project,
        "title": campaign.title,
        "description": campaign.description,
        "campaign_type": campaign.campaign_type,
        "sponsor_name": campaign.sponsor_name,
        "payout_type": campaign.payout_type,
        "payout_amount_cents": campaign.payout_amount_cents,
        "payout_percent": campaign.payout_percent,
        "currency": campaign.currency,
        "status": campaign.status,
        "starts_at": campaign.starts_at,
        "ends_at": campaign.ends_at,
        "created_at": campaign.created_at,
        "enrollment": {
            "id": enrollment.id,
            "status": enrollment.status,
            "joined_at": enrollment.joined_at,
        } if enrollment else None
    }


def serialize_account_enrollment(
    enrollment: AffiliateCampaignEnrollment,
    campaign: AffiliateCampaign | None = None
):
    return {
        "id": enrollment.id,
        "campaign_id": enrollment.campaign_id,
        "affiliate_id": enrollment.affiliate_id,
        "referral_code": enrollment.referral_code,
        "user_id": enrollment.user_id,
        "status": enrollment.status,
        "joined_at": enrollment.joined_at,
        "campaign": serialize_account_campaign(campaign) if campaign else None
    }


def summarize_by_status(records, amount_field: str | None = None):
    summary = {}

    for record in records:
        status = getattr(record, "status", "unknown") or "unknown"

        if status not in summary:
            summary[status] = {
                "count": 0
            }

            if amount_field:
                summary[status]["amount_cents"] = 0

        summary[status]["count"] += 1

        if amount_field:
            summary[status]["amount_cents"] += getattr(record, amount_field, 0) or 0

    return summary


def serialize_affiliate_conversion(conversion: AffiliateConversion):
    return {
        "id": conversion.id,
        "affiliate_id": conversion.affiliate_id,
        "referral_code": conversion.referral_code,
        "conversion_type": conversion.conversion_type,
        "target_type": conversion.target_type,
        "target_id": conversion.target_id,
        "status": conversion.status,
        "created_at": conversion.created_at,
    }


def serialize_affiliate_commission(commission: AffiliateCommission):
    return {
        "id": commission.id,
        "conversion_id": commission.conversion_id,
        "affiliate_id": commission.affiliate_id,
        "referral_code": commission.referral_code,
        "project": commission.project,
        "commission_type": commission.commission_type,
        "amount_cents": commission.amount_cents,
        "currency": commission.currency,
        "status": commission.status,
        "notes": commission.notes,
        "created_at": commission.created_at,
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

    referrer = resolve_referring_affiliate(
        db=db,
        referring_affiliate_id=user.referring_affiliate_id,
        referral_code=user.referral_code
    )

    db_user = User(
        email=user.email,
        hashed_password=get_password_hash(user.password),
        role=role,
        status="active",
        affiliate_id=generate_affiliate_id(),
        referral_code=generate_referral_code(),
        referring_affiliate_id=referrer.id if referrer else None
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    signup_conversion = log_signup_conversion(
        db=db,
        referrer=referrer,
        new_user=db_user
    )

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
        "user": serialize_user(db_user),
        "referral": {
            "referred_by_user_id": referrer.id if referrer else None,
            "conversion_id": signup_conversion.id if signup_conversion else None,
            "status": signup_conversion.status if signup_conversion else None
        }
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

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {
            "module": "Account Dashboard",
            "status": "error",
            "message": "User not found."
        }

    memorials = db.query(Memorial).filter(Memorial.created_by_user_id == user_id).all()
    contributions = db.query(Contribution).filter(Contribution.created_by_user_id == user_id).all()
    media_assets = db.query(MediaAsset).filter(MediaAsset.uploaded_by_user_id == user_id).all()

    from backend.app.dashboard_organization_visibility import (
        get_visible_organizations,
    )

    organization_visibility = get_visible_organizations(
        db,
        user_id=user.id,
    )

    organization_memberships = organization_visibility[
        "memberships"
    ]

    organizations = organization_visibility[
        "organizations"
    ]

    organization_by_id = {
        organization.id: organization
        for organization in organizations
    }

    active_organizations = []

    for membership in organization_memberships:
        organization = organization_by_id.get(membership.organization_id)

        if not organization:
            continue

        active_organizations.append({
            "organization": {
                "id": organization.id,
                "organization_name": organization.organization_name,
                "organization_type": organization.organization_type,
                "project": organization.project,
                "status": organization.status,
            },
            "membership": {
                "id": membership.id,
                "role": membership.role,
                "status": membership.status,
                "created_at": membership.created_at,
            }
        })

    account_role = user.role or "free"
    organization_roles = [
        membership.role
        for membership in organization_memberships
        if membership.role
    ]

    has_creator_access = account_role in ["creator", "admin", "super_admin"]
    has_rescue_access = account_role in ["rescue", "admin", "super_admin"]
    has_partner_access = len(active_organizations) > 0 or account_role in ["admin", "super_admin"]
    has_affiliate_access = bool(user.affiliate_id or user.referral_code)
    has_admin_access = account_role in ["admin", "super_admin"]

    dashboard_access = {
        "member": True,
        "affiliate": has_affiliate_access,
        "creator": has_creator_access,
        "rescue": has_rescue_access,
        "partner": has_partner_access,
        "admin": has_admin_access,
    }

    all_features = [
        {
            "key": "memorials",
            "label": "Memorials",
            "enabled": True,
            "reason": "Available to all active accounts."
        },
        {
            "key": "contributions",
            "label": "Contributions",
            "enabled": True,
            "reason": "Available to all active accounts."
        },
        {
            "key": "media_library",
            "label": "Media Library",
            "enabled": True,
            "reason": "Available within account tier limits."
        },
        {
            "key": "affiliate_tools",
            "label": "Affiliate Tools",
            "enabled": has_affiliate_access,
            "reason": "Available after account verification and affiliate identity assignment."
        },
        {
            "key": "creator_tools",
            "label": "Creator Tools",
            "enabled": has_creator_access,
            "reason": "Requires creator access or upgrade."
        },
        {
            "key": "rescue_tools",
            "label": "Rescue Tools",
            "enabled": has_rescue_access,
            "reason": "Requires rescue access or rescue organization approval."
        },
        {
            "key": "partner_tools",
            "label": "Partner Tools",
            "enabled": has_partner_access,
            "reason": "Requires active organization relationship."
        },
        {
            "key": "xrpl_verification",
            "label": "XRPL Verification",
            "enabled": False,
            "reason": "Planned XRPL integration module."
        },
        {
            "key": "white_label_modules",
            "label": "White Label Modules",
            "enabled": has_partner_access or has_admin_access,
            "reason": "Requires partner, organization, or admin access."
        },
    ]

    enabled_features = [
        feature
        for feature in all_features
        if feature["enabled"]
    ]

    locked_features = [
        feature
        for feature in all_features
        if not feature["enabled"]
    ]

    upgrade_paths = [
        {
            "key": "creator_upgrade",
            "label": "Creator Dashboard",
            "target_dashboard": "creator",
            "available": not has_creator_access,
            "message": "Upgrade or apply for creator access."
        },
        {
            "key": "rescue_upgrade",
            "label": "Rescue Dashboard",
            "target_dashboard": "rescue",
            "available": not has_rescue_access,
            "message": "Apply for rescue organization access."
        },
        {
            "key": "partner_upgrade",
            "label": "Partner Dashboard",
            "target_dashboard": "partner",
            "available": not has_partner_access,
            "message": "Connect this account to a partner organization."
        },
        {
            "key": "xrpl_upgrade",
            "label": "XRPL Verification",
            "target_dashboard": "xrpl",
            "available": True,
            "message": "XRPL verification will be enabled in a future platform module."
        },
    ]

    return {
        "module": "Account Dashboard",
        "status": "active",
        "version": "v25-dashboard-foundation",
        "identity": {
            "user_id": user.id,
            "email": user.email,
            "role": account_role,
            "status": user.status,
            "affiliate_id": user.affiliate_id,
            "referral_code": user.referral_code,
            "referring_affiliate_id": user.referring_affiliate_id,
        },
        "dashboard_access": dashboard_access,
        "organizations": {
            "count": len(active_organizations),
            "records": active_organizations,
            "roles": organization_roles,
        },
        "features": {
            "available": all_features,
            "enabled": enabled_features,
            "locked": locked_features,
        },
        "upgrade_paths": [
            upgrade_path
            for upgrade_path in upgrade_paths
            if upgrade_path["available"]
        ],
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



@router.get("/member")
def account_member_dashboard(
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {"module": "Member Dashboard", "status": "error", "message": "User not found."}

    memorials = db.query(Memorial).filter(Memorial.created_by_user_id == user_id).order_by(Memorial.id.desc()).all()
    contributions = db.query(Contribution).filter(Contribution.created_by_user_id == user_id).order_by(Contribution.id.desc()).all()
    media_assets = db.query(MediaAsset).filter(MediaAsset.uploaded_by_user_id == user_id).order_by(MediaAsset.id.desc()).all()

    referred_users = db.query(User).filter(User.referring_affiliate_id == user.id).order_by(User.id.desc()).all()

    clicks = db.query(AffiliateClick).filter(
        AffiliateClick.referral_code == user.referral_code
    ).order_by(AffiliateClick.created_at.desc()).all() if user.referral_code else []

    conversions = db.query(AffiliateConversion).filter(
        AffiliateConversion.referral_code == user.referral_code
    ).order_by(AffiliateConversion.created_at.desc()).all() if user.referral_code else []

    commissions = db.query(AffiliateCommission).filter(
        AffiliateCommission.referral_code == user.referral_code
    ).order_by(AffiliateCommission.created_at.desc()).all() if user.referral_code else []

    campaigns = db.query(AffiliateCampaign).filter(
        AffiliateCampaign.status == "active"
    ).order_by(AffiliateCampaign.created_at.desc()).all()

    enrollments = db.query(AffiliateCampaignEnrollment).filter(
        AffiliateCampaignEnrollment.user_id == user.id
    ).order_by(AffiliateCampaignEnrollment.joined_at.desc()).all()

    campaign_by_id = {campaign.campaign_id: campaign for campaign in campaigns}

    from backend.app.dashboard_organization_visibility import (
        get_visible_organizations,
    )

    organization_visibility = get_visible_organizations(
        db,
        user_id=user.id,
    )

    organization_memberships = organization_visibility[
        "memberships"
    ]

    organizations = organization_visibility[
        "organizations"
    ]

    organization_by_id = {
        organization.id: organization
        for organization in organizations
    }

    active_organizations = []

    for membership in organization_memberships:
        organization = organization_by_id.get(membership.organization_id)

        if not organization:
            continue

        active_organizations.append({
            "organization": {
                "id": organization.id,
                "organization_name": organization.organization_name,
                "organization_type": organization.organization_type,
                "project": organization.project,
                "status": organization.status,
            },
            "membership": {
                "id": membership.id,
                "role": membership.role,
                "status": membership.status,
                "created_at": membership.created_at,
            }
        })

    account_role = user.role or "free"
    media_quota = account_media_quota(db=db, user_id=user.id, role=account_role)

    total_commission_cents = sum(commission.amount_cents or 0 for commission in commissions)

    outstanding_commission_cents = sum(
        commission.amount_cents or 0
        for commission in commissions
        if commission.status in ["pending", "approved", "payable"]
    )

    return {
        "module": "Member Dashboard",
        "status": "active",
        "version": "v26-member-dashboard",
        "identity": {
            "user_id": user.id,
            "email": user.email,
            "role": account_role,
            "status": user.status,
            "affiliate_id": user.affiliate_id,
            "referral_code": user.referral_code,
            "referring_affiliate_id": user.referring_affiliate_id,
        },
        "summary": {
            "memorials": {"total": len(memorials), "by_status": status_counts(memorials)},
            "contributions": {"total": len(contributions), "by_status": status_counts(contributions)},
            "media_assets": {
                "total": len(media_assets),
                "by_status": status_counts(media_assets),
                "quota": media_quota,
            },
            "affiliate": {
                "referral_signups": len(referred_users),
                "clicks": len(clicks),
                "conversions": {
                    "total": len(conversions),
                    "by_status": summarize_by_status(conversions),
                },
                "commissions": {
                    "total": len(commissions),
                    "by_status": summarize_by_status(commissions, amount_field="amount_cents"),
                    "total_commission_cents": total_commission_cents,
                    "outstanding_commission_cents": outstanding_commission_cents,
                }
            },
            "opportunities": {
                "available_campaigns": len(campaigns),
                "joined_campaigns": len(enrollments),
            },
            "organizations": {"count": len(active_organizations)}
        },
        "recent": {
            "memorials": [
                {
                    "id": memorial.id,
                    "companion_name": memorial.companion_name,
                    "status": memorial.status,
                    "project": memorial.project,
                    "archive_type": memorial.archive_type,
                }
                for memorial in memorials[:10]
            ],
            "contributions": [serialize_contribution(contribution) for contribution in contributions[:10]],
            "media_assets": [serialize_media(asset) for asset in media_assets[:10]],
            "referred_users": [
                {
                    "id": referred_user.id,
                    "email": referred_user.email,
                    "role": referred_user.role,
                    "status": referred_user.status,
                }
                for referred_user in referred_users[:10]
            ],
            "campaigns": [
                serialize_account_enrollment(enrollment, campaign_by_id.get(enrollment.campaign_id))
                for enrollment in enrollments[:10]
            ],
            "organizations": active_organizations[:10],
        },
        "quick_actions": [
            {"key": "create_memorial", "label": "Create Memorial", "method": "POST", "endpoint": "/account/memorials"},
            {"key": "upload_media", "label": "Upload Media", "method": "POST", "endpoint": "/account/media"},
            {"key": "view_affiliate", "label": "View Affiliate Dashboard", "method": "GET", "endpoint": "/account/affiliate"},
            {"key": "view_opportunities", "label": "View Opportunities", "method": "GET", "endpoint": "/account/opportunities"},
        ]
    }


@router.get("/affiliate")
def account_affiliate_dashboard(
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {
            "module": "Account Affiliate Dashboard",
            "status": "error",
            "message": "User not found."
        }

    referred_users = db.query(User).filter(
        User.referring_affiliate_id == user.id
    ).order_by(User.id.desc()).all()

    clicks = db.query(AffiliateClick).filter(
        AffiliateClick.referral_code == user.referral_code
    ).order_by(AffiliateClick.created_at.desc()).all()

    conversions = db.query(AffiliateConversion).filter(
        AffiliateConversion.referral_code == user.referral_code
    ).order_by(AffiliateConversion.created_at.desc()).all()

    commissions = db.query(AffiliateCommission).filter(
        AffiliateCommission.referral_code == user.referral_code
    ).order_by(AffiliateCommission.created_at.desc()).all()

    total_commission_cents = sum(
        commission.amount_cents or 0
        for commission in commissions
    )

    paid_commission_cents = sum(
        commission.amount_cents or 0
        for commission in commissions
        if commission.status == "paid"
    )

    outstanding_commission_cents = sum(
        commission.amount_cents or 0
        for commission in commissions
        if commission.status in ["pending", "approved", "payable"]
    )

    return {
        "module": "Account Affiliate Dashboard",
        "status": "active",
        "affiliate": {
            "user_id": user.id,
            "affiliate_id": user.affiliate_id,
            "referral_code": user.referral_code,
            "role": user.role,
            "account_status": user.status,
        },
        "summary": {
            "referral_signups": len(referred_users),
            "clicks": len(clicks),
            "conversions": {
                "total": len(conversions),
                "by_status": summarize_by_status(conversions),
            },
            "commissions": {
                "total": len(commissions),
                "by_status": summarize_by_status(commissions, amount_field="amount_cents"),
                "total_commission_cents": total_commission_cents,
                "paid_commission_cents": paid_commission_cents,
                "outstanding_commission_cents": outstanding_commission_cents,
            }
        },
        "recent": {
            "referred_users": [
                {
                    "id": referred_user.id,
                    "email": referred_user.email,
                    "role": referred_user.role,
                    "status": referred_user.status,
                    "created_affiliate_id": referred_user.affiliate_id,
                    "created_referral_code": referred_user.referral_code,
                }
                for referred_user in referred_users[:10]
            ],
            "conversions": [
                serialize_affiliate_conversion(conversion)
                for conversion in conversions[:10]
            ],
            "commissions": [
                serialize_affiliate_commission(commission)
                for commission in commissions[:10]
            ]
        }
    }


@router.get("/opportunities")
def account_opportunities(
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {
            "module": "Account Opportunities",
            "status": "error",
            "message": "User not found."
        }

    campaigns = db.query(AffiliateCampaign).filter(
        AffiliateCampaign.status == "active"
    ).order_by(AffiliateCampaign.created_at.desc()).all()

    enrollments = db.query(AffiliateCampaignEnrollment).filter(
        AffiliateCampaignEnrollment.user_id == user.id
    ).all()

    enrollment_by_campaign = {
        enrollment.campaign_id: enrollment
        for enrollment in enrollments
    }

    return {
        "module": "Account Opportunities",
        "status": "active",
        "count": len(campaigns),
        "affiliate": {
            "user_id": user.id,
            "affiliate_id": user.affiliate_id,
            "referral_code": user.referral_code,
            "role": user.role,
        },
        "records": [
            serialize_account_campaign(
                campaign,
                enrollment_by_campaign.get(campaign.campaign_id)
            )
            for campaign in campaigns
        ]
    }


@router.post("/opportunities/{campaign_id}/join")
def account_join_opportunity(
    campaign_id: str,
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {
            "module": "Account Opportunities",
            "status": "error",
            "message": "User not found."
        }

    campaign = db.query(AffiliateCampaign).filter(
        AffiliateCampaign.campaign_id == campaign_id,
        AffiliateCampaign.status == "active"
    ).first()

    if not campaign:
        return {
            "module": "Account Opportunities",
            "status": "error",
            "message": "Active campaign not found."
        }

    existing = db.query(AffiliateCampaignEnrollment).filter(
        AffiliateCampaignEnrollment.campaign_id == campaign_id,
        AffiliateCampaignEnrollment.user_id == user.id
    ).first()

    if existing:
        return {
            "module": "Account Opportunities",
            "status": "already_enrolled",
            "record": serialize_account_enrollment(existing, campaign)
        }

    enrollment = AffiliateCampaignEnrollment(
        campaign_id=campaign.campaign_id,
        affiliate_id=user.affiliate_id,
        referral_code=user.referral_code,
        user_id=user.id,
        status="active"
    )

    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)

    return {
        "module": "Account Opportunities",
        "status": "joined",
        "record": serialize_account_enrollment(enrollment, campaign)
    }


@router.get("/opportunities/my-campaigns")
def account_my_campaigns(
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {
            "module": "Account Opportunities",
            "status": "error",
            "message": "User not found."
        }

    enrollments = db.query(AffiliateCampaignEnrollment).filter(
        AffiliateCampaignEnrollment.user_id == user.id
    ).order_by(AffiliateCampaignEnrollment.joined_at.desc()).all()

    campaigns = db.query(AffiliateCampaign).filter(
        AffiliateCampaign.campaign_id.in_([
            enrollment.campaign_id
            for enrollment in enrollments
        ])
    ).all() if enrollments else []

    campaign_by_id = {
        campaign.campaign_id: campaign
        for campaign in campaigns
    }

    return {
        "module": "Account My Campaigns",
        "status": "active",
        "count": len(enrollments),
        "affiliate": {
            "user_id": user.id,
            "affiliate_id": user.affiliate_id,
            "referral_code": user.referral_code,
            "role": user.role,
        },
        "records": [
            serialize_account_enrollment(
                enrollment,
                campaign_by_id.get(enrollment.campaign_id)
            )
            for enrollment in enrollments
        ]
    }


@router.get("/organization")
def account_organization_dashboard(
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {
            "module": "Account Organization Dashboard",
            "status": "error",
            "message": "User not found."
        }

    from backend.app.dashboard_organization_visibility import (
        get_visible_organizations,
    )

    organization_visibility = get_visible_organizations(
        db,
        user_id=user.id,
    )

    memberships = organization_visibility[
        "memberships"
    ]

    if not memberships:
        return {
            "module": "Account Organization Dashboard",
            "status": "active",
            "count": 0,
            "message": "No active organizations attached to this account.",
            "records": []
        }

    organizations = organization_visibility[
        "organizations"
    ]

    membership_by_org_id = organization_visibility[
        "membership_by_org_id"
    ]

    records = []

    for org in organizations:
        membership = membership_by_org_id.get(org.id)

        campaigns = db.query(AffiliateCampaign).filter(
            AffiliateCampaign.sponsor_name == org.organization_name
        ).order_by(AffiliateCampaign.created_at.desc()).all()

        campaign_ids = [
            campaign.campaign_id
            for campaign in campaigns
        ]

        enrollments = db.query(AffiliateCampaignEnrollment).filter(
            AffiliateCampaignEnrollment.campaign_id.in_(campaign_ids)
        ).all() if campaign_ids else []

        referral_codes = [
            enrollment.referral_code
            for enrollment in enrollments
            if enrollment.referral_code
        ]

        conversions = db.query(AffiliateConversion).filter(
            AffiliateConversion.referral_code.in_(referral_codes)
        ).all() if referral_codes else []

        commissions = db.query(AffiliateCommission).filter(
            AffiliateCommission.referral_code.in_(referral_codes)
        ).all() if referral_codes else []

        clicks = db.query(AffiliateClick).filter(
            AffiliateClick.campaign_id.in_(campaign_ids)
        ).all() if campaign_ids else []

        total_commission_cents = sum(
            commission.amount_cents or 0
            for commission in commissions
        )

        paid_commission_cents = sum(
            commission.amount_cents or 0
            for commission in commissions
            if commission.status == "paid"
        )

        outstanding_commission_cents = sum(
            commission.amount_cents or 0
            for commission in commissions
            if commission.status in ["pending", "approved", "payable"]
        )

        clicks_by_campaign = {}

        for click in clicks:
            clicks_by_campaign.setdefault(click.campaign_id, []).append(click)

        enrollments_by_campaign = {}

        for enrollment in enrollments:
            enrollments_by_campaign.setdefault(enrollment.campaign_id, []).append(enrollment)

        conversions_by_referral_code = {}

        for conversion in conversions:
            conversions_by_referral_code.setdefault(conversion.referral_code, []).append(conversion)

        commissions_by_referral_code = {}

        for commission in commissions:
            commissions_by_referral_code.setdefault(commission.referral_code, []).append(commission)

        campaign_performance = []

        for campaign in campaigns:
            campaign_enrollments = enrollments_by_campaign.get(campaign.campaign_id, [])

            campaign_referral_codes = [
                enrollment.referral_code
                for enrollment in campaign_enrollments
                if enrollment.referral_code
            ]

            campaign_conversions = []

            for code in campaign_referral_codes:
                campaign_conversions.extend(conversions_by_referral_code.get(code, []))

            campaign_commissions = []

            for code in campaign_referral_codes:
                campaign_commissions.extend(commissions_by_referral_code.get(code, []))

            campaign_total_commission_cents = sum(
                commission.amount_cents or 0
                for commission in campaign_commissions
            )

            campaign_paid_commission_cents = sum(
                commission.amount_cents or 0
                for commission in campaign_commissions
                if commission.status == "paid"
            )

            campaign_performance.append({
                "campaign": serialize_account_campaign(campaign),
                "summary": {
                    "clicks": len(clicks_by_campaign.get(campaign.campaign_id, [])),
                    "enrollments": {
                        "total": len(campaign_enrollments),
                        "by_status": summarize_by_status(campaign_enrollments),
                    },
                    "conversions": {
                        "total": len(campaign_conversions),
                        "by_status": summarize_by_status(campaign_conversions),
                    },
                    "commissions": {
                        "total": len(campaign_commissions),
                        "by_status": summarize_by_status(campaign_commissions, amount_field="amount_cents"),
                        "total_commission_cents": campaign_total_commission_cents,
                        "paid_commission_cents": campaign_paid_commission_cents,
                    }
                }
            })

        records.append({
            "organization": {
                "id": org.id,
                "organization_name": org.organization_name,
                "organization_type": org.organization_type,
                "project": org.project,
                "contact_name": org.contact_name,
                "contact_email": org.contact_email,
                "website_url": org.website_url,
                "location": org.location,
                "status": org.status,
                "notes": org.notes,
                "created_at": org.created_at,
            },
            "membership": {
                "id": membership.id if membership else None,
                "role": membership.role if membership else None,
                "status": membership.status if membership else None,
                "created_at": membership.created_at if membership else None,
            },
            "summary": {
                "campaigns": {
                    "total": len(campaigns),
                    "by_status": summarize_by_status(campaigns),
                },
                "enrollments": {
                    "total": len(enrollments),
                    "by_status": summarize_by_status(enrollments),
                },
                "conversions": {
                    "total": len(conversions),
                    "by_status": summarize_by_status(conversions),
                },
                "commissions": {
                    "total": len(commissions),
                    "by_status": summarize_by_status(commissions, amount_field="amount_cents"),
                    "total_commission_cents": total_commission_cents,
                    "paid_commission_cents": paid_commission_cents,
                    "outstanding_commission_cents": outstanding_commission_cents,
                },
            },
            "campaign_performance": campaign_performance,
            "recent": {
                "campaigns": [
                    serialize_account_campaign(campaign)
                    for campaign in campaigns[:10]
                ],
                "enrollments": [
                    serialize_account_enrollment(enrollment)
                    for enrollment in enrollments[:10]
                ],
                "conversions": [
                    serialize_affiliate_conversion(conversion)
                    for conversion in conversions[:10]
                ],
                "commissions": [
                    serialize_affiliate_commission(commission)
                    for commission in commissions[:10]
                ],
            }
        })

    return {
        "module": "Account Organization Dashboard",
        "status": "active",
        "count": len(records),
        "user": {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "affiliate_id": user.affiliate_id,
            "referral_code": user.referral_code,
        },
        "records": records
    }


def serialize_public_profile(profile: PublicProfile | None):
    if not profile:
        return None

    return {
        "id": profile.id,
        "user_id": profile.user_id,
        "username": profile.username,
        "display_name": profile.display_name,
        "headline": profile.headline,
        "bio": profile.bio,
        "website_url": profile.website_url,
        "avatar_url": profile.avatar_url,
        "banner_url": profile.banner_url,
        "location": profile.location,
        "public_profile_status": profile.public_profile_status,
        "verification_status": profile.verification_status,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
    }


@router.get("/public-profile")
def account_public_profile(
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {
            "module": "Account Public Profile",
            "status": "error",
            "message": "User not found."
        }

    profile = db.query(PublicProfile).filter(
        PublicProfile.user_id == user.id
    ).first()

    return {
        "module": "Account Public Profile",
        "status": "active",
        "identity": {
            "user_id": user.id,
            "role": user.role,
            "account_status": user.status,
            "affiliate_id": user.affiliate_id,
        },
        "record": serialize_public_profile(profile),
    }


@router.post("/public-profile")
def account_save_public_profile(
    username: str | None = None,
    display_name: str | None = None,
    headline: str | None = None,
    bio: str | None = None,
    website_url: str | None = None,
    avatar_url: str | None = None,
    banner_url: str | None = None,
    location: str | None = None,
    public_profile_status: str = "pending",
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {
            "module": "Account Public Profile",
            "status": "error",
            "message": "User not found."
        }

    if username:
        username_clean = username.strip().lower()

        existing = db.query(PublicProfile).filter(
            PublicProfile.username == username_clean,
            PublicProfile.user_id != user.id
        ).first()

        if existing:
            return {
                "module": "Account Public Profile",
                "status": "error",
                "message": "Username is already taken."
            }
    else:
        username_clean = None

    profile = db.query(PublicProfile).filter(
        PublicProfile.user_id == user.id
    ).first()

    if not profile:
        profile = PublicProfile(
            user_id=user.id
        )
        db.add(profile)

    profile.username = username_clean
    profile.display_name = display_name
    profile.headline = headline
    profile.bio = bio
    profile.website_url = website_url
    profile.avatar_url = avatar_url
    profile.banner_url = banner_url
    profile.location = location
    profile.public_profile_status = public_profile_status
    profile.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(profile)

    return {
        "module": "Account Public Profile",
        "status": "saved",
        "identity": {
            "user_id": user.id,
            "role": user.role,
            "account_status": user.status,
            "affiliate_id": user.affiliate_id,
        },
        "record": serialize_public_profile(profile),
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
    role = current_user.get("role") or "free"

    assets = db.query(MediaAsset).filter(
        MediaAsset.uploaded_by_user_id == user_id
    ).order_by(MediaAsset.id.desc()).all()

    return {
        "module": "Account Media",
        "status": "active",
        "count": len(assets),
        "quota": account_media_quota(db=db, user_id=user_id, role=role),
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

    quota = account_media_quota(db=db, user_id=user_id, role=role)
    max_assets = quota["limits"]["max_assets_per_account"]
    max_storage = quota["limits"]["max_storage_bytes"]

    if max_assets is not None and quota["usage"]["total_assets"] >= max_assets:
        return {
            "module": "Account Media",
            "status": "error",
            "message": "Account media asset quota reached.",
            "quota": quota,
            "upgrade_hint": "Upgrade your account to add more media assets."
        }

    if max_storage is not None and quota["usage"]["total_storage_bytes"] + len(content) > max_storage:
        return {
            "module": "Account Media",
            "status": "error",
            "message": "Account storage quota exceeded.",
            "quota": quota,
            "incoming_file_size_bytes": len(content),
            "upgrade_hint": "Upgrade your account to increase storage."
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
        file_size_bytes=len(content),
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


@router.get("/creator")
def account_creator_dashboard(
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {
            "module": "Creator Dashboard",
            "status": "error",
            "message": "User not found."
        }

    account_role = user.role or "free"
    has_creator_access = account_role in ["creator", "admin", "super_admin"]

    memorials = db.query(Memorial).filter(
        Memorial.created_by_user_id == user.id
    ).order_by(Memorial.id.desc()).all()

    contributions = db.query(Contribution).filter(
        Contribution.created_by_user_id == user.id
    ).order_by(Contribution.id.desc()).all()

    media_assets = db.query(MediaAsset).filter(
        MediaAsset.uploaded_by_user_id == user.id
    ).order_by(MediaAsset.id.desc()).all()

    campaigns = db.query(AffiliateCampaign).filter(
        AffiliateCampaign.status == "active"
    ).order_by(AffiliateCampaign.created_at.desc()).all()

    enrollments = db.query(AffiliateCampaignEnrollment).filter(
        AffiliateCampaignEnrollment.user_id == user.id
    ).order_by(AffiliateCampaignEnrollment.joined_at.desc()).all()

    enrollment_by_campaign = {
        enrollment.campaign_id: enrollment
        for enrollment in enrollments
    }

    clicks = db.query(AffiliateClick).filter(
        AffiliateClick.referral_code == user.referral_code
    ).order_by(AffiliateClick.created_at.desc()).all() if user.referral_code else []

    conversions = db.query(AffiliateConversion).filter(
        AffiliateConversion.referral_code == user.referral_code
    ).order_by(AffiliateConversion.created_at.desc()).all() if user.referral_code else []

    commissions = db.query(AffiliateCommission).filter(
        AffiliateCommission.referral_code == user.referral_code
    ).order_by(AffiliateCommission.created_at.desc()).all() if user.referral_code else []

    from backend.app.dashboard_organization_visibility import (
        get_visible_organizations,
    )

    organization_visibility = get_visible_organizations(
        db,
        user_id=user.id,
    )

    organization_memberships = organization_visibility[
        "memberships"
    ]

    organizations = organization_visibility[
        "organizations"
    ]

    organization_by_id = {
        organization.id: organization
        for organization in organizations
    }

    active_organizations = []

    for membership in organization_memberships:
        organization = organization_by_id.get(membership.organization_id)

        if not organization:
            continue

        active_organizations.append({
            "organization": {
                "id": organization.id,
                "organization_name": organization.organization_name,
                "organization_type": organization.organization_type,
                "project": organization.project,
                "status": organization.status,
            },
            "membership": {
                "id": membership.id,
                "role": membership.role,
                "status": membership.status,
                "created_at": membership.created_at,
            }
        })

    total_commission_cents = sum(
        commission.amount_cents or 0
        for commission in commissions
    )

    paid_commission_cents = sum(
        commission.amount_cents or 0
        for commission in commissions
        if commission.status == "paid"
    )

    outstanding_commission_cents = sum(
        commission.amount_cents or 0
        for commission in commissions
        if commission.status in ["pending", "approved", "payable"]
    )

    joined_campaign_ids = [
        enrollment.campaign_id
        for enrollment in enrollments
    ]

    leaderboard_score = (
        len(clicks)
        + (len(conversions) * 10)
        + (len(enrollments) * 15)
        + (len(memorials) * 5)
        + (len(contributions) * 3)
        + (len(media_assets) * 2)
        + (len(active_organizations) * 20)
        + int(total_commission_cents / 100)
    )

    locked_features = [
        {
            "key": "creator_store",
            "label": "Creator Store",
            "enabled": False,
            "status": "locked",
            "upgrade_path": "Creator Commerce"
        },
        {
            "key": "creator_subscriptions",
            "label": "Creator Subscriptions",
            "enabled": False,
            "status": "locked",
            "upgrade_path": "Creator Memberships"
        },
        {
            "key": "creator_marketplace",
            "label": "Creator Marketplace",
            "enabled": False,
            "status": "locked",
            "upgrade_path": "Marketplace Access"
        },
        {
            "key": "creator_sponsorships",
            "label": "Creator Sponsorships",
            "enabled": False,
            "status": "locked",
            "upgrade_path": "Campaign Sponsorship Tools"
        },
        {
            "key": "creator_verification",
            "label": "Creator Verification",
            "enabled": False,
            "status": "locked",
            "upgrade_path": "Verified Creator Identity"
        },
        {
            "key": "xrpl_creator_identity",
            "label": "XRPL Creator Identity",
            "enabled": False,
            "status": "locked",
            "upgrade_path": "XRPL Verification Layer"
        }
    ]

    return {
        "module": "Creator Dashboard",
        "status": "active" if has_creator_access else "locked",
        "version": "v27-creator-dashboard",
        "access": {
            "enabled": has_creator_access,
            "role": account_role,
            "upgrade_path": None if has_creator_access else "Upgrade to Creator access."
        },
        "identity": {
            "user_id": user.id,
            "email": user.email,
            "role": account_role,
            "status": user.status,
            "affiliate_id": user.affiliate_id,
            "referral_code": user.referral_code,
            "referring_affiliate_id": user.referring_affiliate_id,
        },
        "creator_profile": {
            "creator_id": f"creator-{user.id}",
            "creator_type": account_role if account_role == "creator" else "unverified",
            "creator_status": "active" if has_creator_access else "locked",
            "public_profile_status": "pending",
            "portfolio_status": "pending"
        },
        "summary": {
            "memorials": {"total": len(memorials), "by_status": status_counts(memorials)},
            "contributions": {"total": len(contributions), "by_status": status_counts(contributions)},
            "media_assets": {
                "total": len(media_assets),
                "by_status": status_counts(media_assets),
                "quota": account_media_quota(db=db, user_id=user.id, role=account_role),
            },
            "opportunities": {
                "available": len(campaigns),
                "joined": len(enrollments),
            },
            "organizations": {
                "total": len(active_organizations),
            },
            "affiliate_attribution": {
                "clicks": len(clicks),
                "conversions": {
                    "total": len(conversions),
                    "by_status": summarize_by_status(conversions),
                },
                "commissions": {
                    "total": len(commissions),
                    "by_status": summarize_by_status(commissions, amount_field="amount_cents"),
                    "total_commission_cents": total_commission_cents,
                    "paid_commission_cents": paid_commission_cents,
                    "outstanding_commission_cents": outstanding_commission_cents,
                }
            },
            "leaderboard": {
                "score": leaderboard_score,
                "rank_scope": "creator-platform",
                "rank": None,
                "status": "scoring_active",
                "note": "Rank will be calculated globally when leaderboard aggregation is enabled."
            }
        },
        "leaderboard": {
            "score": leaderboard_score,
            "components": {
                "clicks": len(clicks),
                "conversions": len(conversions),
                "campaign_enrollments": len(enrollments),
                "memorials": len(memorials),
                "contributions": len(contributions),
                "media_assets": len(media_assets),
                "organizations": len(active_organizations),
                "commission_points": int(total_commission_cents / 100),
            },
            "formula": {
                "click": 1,
                "conversion": 10,
                "campaign_enrollment": 15,
                "memorial": 5,
                "contribution": 3,
                "media_asset": 2,
                "organization": 20,
                "commission_point": "1 point per dollar"
            }
        },
        "opportunities": {
            "available": [
                serialize_account_campaign(
                    campaign,
                    enrollment_by_campaign.get(campaign.campaign_id)
                )
                for campaign in campaigns[:10]
            ],
            "joined_campaign_ids": joined_campaign_ids
        },
        "organizations": active_organizations,
        "recent": {
            "memorials": [
                {
                    "id": memorial.id,
                    "companion_name": memorial.companion_name,
                    "status": memorial.status,
                    "created_by_user_id": memorial.created_by_user_id,
                    "created_at": memorial.created_at,
                }
                for memorial in memorials[:10]
            ],
            "contributions": [
                serialize_contribution(contribution)
                for contribution in contributions[:10]
            ],
            "media_assets": [
                serialize_media(asset)
                for asset in media_assets[:10]
            ],
            "conversions": [
                serialize_affiliate_conversion(conversion)
                for conversion in conversions[:10]
            ],
            "commissions": [
                serialize_affiliate_commission(commission)
                for commission in commissions[:10]
            ]
        },
        "features": [
            {
                "key": "creator_dashboard",
                "label": "Creator Dashboard",
                "enabled": has_creator_access,
                "status": "enabled" if has_creator_access else "locked",
                "upgrade_path": None if has_creator_access else "Creator access required."
            },
            {
                "key": "creator_media_library",
                "label": "Creator Media Library",
                "enabled": True,
                "status": "enabled",
                "upgrade_path": None
            },
            {
                "key": "creator_opportunities",
                "label": "Creator Opportunities",
                "enabled": True,
                "status": "enabled",
                "upgrade_path": None
            },
            {
                "key": "creator_leaderboard",
                "label": "Creator Leaderboard",
                "enabled": True,
                "status": "enabled",
                "upgrade_path": None
            },
            *locked_features
        ],
        "quick_actions": [
            {"key": "view_member_dashboard", "label": "View Member Dashboard", "method": "GET", "endpoint": "/account/member"},
            {"key": "view_media", "label": "View Media Library", "method": "GET", "endpoint": "/account/media"},
            {"key": "upload_media", "label": "Upload Media", "method": "POST", "endpoint": "/account/media/upload"},
            {"key": "view_opportunities", "label": "View Opportunities", "method": "GET", "endpoint": "/account/opportunities"},
            {"key": "view_my_campaigns", "label": "View My Campaigns", "method": "GET", "endpoint": "/account/opportunities/my-campaigns"},
            {"key": "view_affiliate_dashboard", "label": "View Affiliate Dashboard", "method": "GET", "endpoint": "/account/affiliate"},
            {"key": "view_organizations", "label": "View Organizations", "method": "GET", "endpoint": "/account/organization"},
        ]
    }


@router.get("/rescue")
def account_rescue_dashboard(
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {
            "module": "Rescue Dashboard",
            "status": "error",
            "message": "User not found."
        }

    account_role = user.role or "free"
    has_rescue_access = account_role in ["rescue", "admin", "super_admin"]

    memorials = db.query(Memorial).filter(
        Memorial.created_by_user_id == user.id
    ).order_by(Memorial.id.desc()).all()

    contributions = db.query(Contribution).filter(
        Contribution.created_by_user_id == user.id
    ).order_by(Contribution.id.desc()).all()

    media_assets = db.query(MediaAsset).filter(
        MediaAsset.uploaded_by_user_id == user.id
    ).order_by(MediaAsset.id.desc()).all()

    campaigns = db.query(AffiliateCampaign).filter(
        AffiliateCampaign.status == "active"
    ).order_by(AffiliateCampaign.created_at.desc()).all()

    enrollments = db.query(AffiliateCampaignEnrollment).filter(
        AffiliateCampaignEnrollment.user_id == user.id
    ).order_by(AffiliateCampaignEnrollment.joined_at.desc()).all()

    enrollment_by_campaign = {
        enrollment.campaign_id: enrollment
        for enrollment in enrollments
    }

    clicks = db.query(AffiliateClick).filter(
        AffiliateClick.referral_code == user.referral_code
    ).order_by(AffiliateClick.created_at.desc()).all() if user.referral_code else []

    conversions = db.query(AffiliateConversion).filter(
        AffiliateConversion.referral_code == user.referral_code
    ).order_by(AffiliateConversion.created_at.desc()).all() if user.referral_code else []

    commissions = db.query(AffiliateCommission).filter(
        AffiliateCommission.referral_code == user.referral_code
    ).order_by(AffiliateCommission.created_at.desc()).all() if user.referral_code else []

    from backend.app.dashboard_organization_visibility import (
        get_visible_organizations,
    )

    organization_visibility = get_visible_organizations(
        db,
        user_id=user.id,
    )

    organization_memberships = organization_visibility[
        "memberships"
    ]

    organizations = organization_visibility[
        "organizations"
    ]

    organization_by_id = {
        organization.id: organization
        for organization in organizations
    }

    active_organizations = []
    rescue_organizations = []

    for membership in organization_memberships:
        organization = organization_by_id.get(membership.organization_id)

        if not organization:
            continue

        record = {
            "organization": {
                "id": organization.id,
                "organization_name": organization.organization_name,
                "organization_type": organization.organization_type,
                "project": organization.project,
                "status": organization.status,
            },
            "membership": {
                "id": membership.id,
                "role": membership.role,
                "status": membership.status,
                "created_at": membership.created_at,
            }
        }

        active_organizations.append(record)

        org_type = (organization.organization_type or "").lower()
        member_role = (membership.role or "").lower()

        if "rescue" in org_type or "rescue" in member_role:
            rescue_organizations.append(record)

    total_commission_cents = sum(
        commission.amount_cents or 0
        for commission in commissions
    )

    paid_commission_cents = sum(
        commission.amount_cents or 0
        for commission in commissions
        if commission.status == "paid"
    )

    outstanding_commission_cents = sum(
        commission.amount_cents or 0
        for commission in commissions
        if commission.status in ["pending", "approved", "payable"]
    )

    joined_campaign_ids = [
        enrollment.campaign_id
        for enrollment in enrollments
    ]

    reviewed_memorials = [
        memorial
        for memorial in memorials
        if memorial.status in ["reviewed", "approved", "published"]
    ]

    submitted_memorials = [
        memorial
        for memorial in memorials
        if memorial.status in ["submitted", "reviewed", "approved", "published"]
    ]

    submitted_contributions = [
        contribution
        for contribution in contributions
        if contribution.status in ["submitted", "reviewed", "approved", "published"]
    ]

    rescue_leaderboard_score = (
        (len(rescue_organizations) * 30)
        + (len(reviewed_memorials) * 20)
        + (len(submitted_memorials) * 10)
        + (len(submitted_contributions) * 5)
        + (len(media_assets) * 2)
        + (len(enrollments) * 15)
        + (len(conversions) * 10)
        + len(clicks)
        + int(total_commission_cents / 100)
    )

    locked_features = [
        {
            "key": "adoption_management",
            "label": "Adoption Management",
            "enabled": False,
            "status": "locked",
            "upgrade_path": "Rescue Operations"
        },
        {
            "key": "foster_management",
            "label": "Foster Management",
            "enabled": False,
            "status": "locked",
            "upgrade_path": "Foster Network Tools"
        },
        {
            "key": "intake_tracking",
            "label": "Intake Tracking",
            "enabled": False,
            "status": "locked",
            "upgrade_path": "Animal Intake Module"
        },
        {
            "key": "rescue_verification",
            "label": "Rescue Verification",
            "enabled": False,
            "status": "locked",
            "upgrade_path": "Verified Rescue Identity"
        },
        {
            "key": "donation_campaigns",
            "label": "Donation Campaigns",
            "enabled": False,
            "status": "locked",
            "upgrade_path": "Rescue Fundraising"
        },
        {
            "key": "xrpl_rescue_identity",
            "label": "XRPL Rescue Identity",
            "enabled": False,
            "status": "locked",
            "upgrade_path": "XRPL Verification Layer"
        }
    ]

    return {
        "module": "Rescue Dashboard",
        "status": "active" if has_rescue_access else "locked",
        "version": "v28-rescue-dashboard",
        "access": {
            "enabled": has_rescue_access,
            "role": account_role,
            "upgrade_path": None if has_rescue_access else "Apply for rescue organization access."
        },
        "identity": {
            "user_id": user.id,
            "email": user.email,
            "role": account_role,
            "status": user.status,
            "affiliate_id": user.affiliate_id,
            "referral_code": user.referral_code,
            "referring_affiliate_id": user.referring_affiliate_id,
        },
        "rescue_profile": {
            "rescue_id": f"rescue-{user.id}",
            "rescue_type": account_role if account_role == "rescue" else "unverified",
            "rescue_status": "active" if has_rescue_access else "locked",
            "public_profile_status": "pending",
            "verification_status": "pending",
            "organization_count": len(rescue_organizations)
        },
        "summary": {
            "memorials": {
                "total": len(memorials),
                "submitted": len(submitted_memorials),
                "reviewed_or_published": len(reviewed_memorials),
                "by_status": status_counts(memorials)
            },
            "contributions": {
                "total": len(contributions),
                "submitted": len(submitted_contributions),
                "by_status": status_counts(contributions)
            },
            "media_assets": {
                "total": len(media_assets),
                "by_status": status_counts(media_assets),
                "quota": account_media_quota(db=db, user_id=user.id, role=account_role),
            },
            "opportunities": {
                "available": len(campaigns),
                "joined": len(enrollments),
            },
            "organizations": {
                "total": len(active_organizations),
                "rescue_related": len(rescue_organizations),
            },
            "affiliate_attribution": {
                "clicks": len(clicks),
                "conversions": {
                    "total": len(conversions),
                    "by_status": summarize_by_status(conversions),
                },
                "commissions": {
                    "total": len(commissions),
                    "by_status": summarize_by_status(commissions, amount_field="amount_cents"),
                    "total_commission_cents": total_commission_cents,
                    "paid_commission_cents": paid_commission_cents,
                    "outstanding_commission_cents": outstanding_commission_cents,
                }
            },
            "leaderboard": {
                "score": rescue_leaderboard_score,
                "rank_scope": "rescue-platform",
                "rank": None,
                "status": "scoring_active",
                "note": "Rank will be calculated globally when rescue leaderboard aggregation is enabled."
            }
        },
        "leaderboard": {
            "score": rescue_leaderboard_score,
            "components": {
                "rescue_organizations": len(rescue_organizations),
                "reviewed_memorials": len(reviewed_memorials),
                "submitted_memorials": len(submitted_memorials),
                "submitted_contributions": len(submitted_contributions),
                "media_assets": len(media_assets),
                "campaign_enrollments": len(enrollments),
                "conversions": len(conversions),
                "clicks": len(clicks),
                "commission_points": int(total_commission_cents / 100),
            },
            "formula": {
                "rescue_organization": 30,
                "reviewed_memorial": 20,
                "submitted_memorial": 10,
                "submitted_contribution": 5,
                "media_asset": 2,
                "campaign_enrollment": 15,
                "conversion": 10,
                "click": 1,
                "commission_point": "1 point per dollar"
            }
        },
        "opportunities": {
            "available": [
                serialize_account_campaign(
                    campaign,
                    enrollment_by_campaign.get(campaign.campaign_id)
                )
                for campaign in campaigns[:10]
            ],
            "joined_campaign_ids": joined_campaign_ids
        },
        "organizations": {
            "all": active_organizations,
            "rescue_related": rescue_organizations
        },
        "recent": {
            "memorials": [
                {
                    "id": memorial.id,
                    "companion_name": memorial.companion_name,
                    "status": memorial.status,
                    "created_by_user_id": memorial.created_by_user_id,
                    "created_at": memorial.created_at,
                }
                for memorial in memorials[:10]
            ],
            "contributions": [
                serialize_contribution(contribution)
                for contribution in contributions[:10]
            ],
            "media_assets": [
                serialize_media(asset)
                for asset in media_assets[:10]
            ],
            "conversions": [
                serialize_affiliate_conversion(conversion)
                for conversion in conversions[:10]
            ],
            "commissions": [
                serialize_affiliate_commission(commission)
                for commission in commissions[:10]
            ]
        },
        "features": [
            {
                "key": "rescue_dashboard",
                "label": "Rescue Dashboard",
                "enabled": has_rescue_access,
                "status": "enabled" if has_rescue_access else "locked",
                "upgrade_path": None if has_rescue_access else "Rescue access required."
            },
            {
                "key": "rescue_media_library",
                "label": "Rescue Media Library",
                "enabled": True,
                "status": "enabled",
                "upgrade_path": None
            },
            {
                "key": "rescue_opportunities",
                "label": "Rescue Opportunities",
                "enabled": True,
                "status": "enabled",
                "upgrade_path": None
            },
            {
                "key": "rescue_leaderboard",
                "label": "Rescue Leaderboard",
                "enabled": True,
                "status": "enabled",
                "upgrade_path": None
            },
            *locked_features
        ],
        "quick_actions": [
            {"key": "view_member_dashboard", "label": "View Member Dashboard", "method": "GET", "endpoint": "/account/member"},
            {"key": "view_media", "label": "View Media Library", "method": "GET", "endpoint": "/account/media"},
            {"key": "upload_media", "label": "Upload Media", "method": "POST", "endpoint": "/account/media/upload"},
            {"key": "view_opportunities", "label": "View Opportunities", "method": "GET", "endpoint": "/account/opportunities"},
            {"key": "view_my_campaigns", "label": "View My Campaigns", "method": "GET", "endpoint": "/account/opportunities/my-campaigns"},
            {"key": "view_affiliate_dashboard", "label": "View Affiliate Dashboard", "method": "GET", "endpoint": "/account/affiliate"},
            {"key": "view_organizations", "label": "View Organizations", "method": "GET", "endpoint": "/account/organization"},
        ]
    }


@router.get("/partner")
def account_partner_dashboard(
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {
            "module": "Partner Dashboard",
            "status": "error",
            "message": "User not found."
        }

    account_role = user.role or "free"

    from backend.app.dashboard_organization_visibility import (
        get_visible_organizations,
    )

    organization_visibility = get_visible_organizations(
        db,
        user_id=user.id,
    )

    memberships = organization_visibility[
        "memberships"
    ]

    organizations = organization_visibility[
        "organizations"
    ]

    membership_by_org_id = organization_visibility[
        "membership_by_org_id"
    ]

    has_partner_access = len(organizations) > 0 or account_role in ["admin", "super_admin"]

    partner_records = []
    creator_relationships = []
    rescue_relationships = []

    total_campaigns = 0
    total_enrollments = 0
    total_conversions = 0
    total_commissions = 0
    total_clicks = 0
    total_commission_cents = 0
    paid_commission_cents = 0
    outstanding_commission_cents = 0

    for org in organizations:
        membership = membership_by_org_id.get(org.id)

        campaigns = db.query(AffiliateCampaign).filter(
            AffiliateCampaign.sponsor_name == org.organization_name
        ).order_by(AffiliateCampaign.created_at.desc()).all()

        campaign_ids = [
            campaign.campaign_id
            for campaign in campaigns
        ]

        enrollments = db.query(AffiliateCampaignEnrollment).filter(
            AffiliateCampaignEnrollment.campaign_id.in_(campaign_ids)
        ).all() if campaign_ids else []

        referral_codes = [
            enrollment.referral_code
            for enrollment in enrollments
            if enrollment.referral_code
        ]

        conversions = db.query(AffiliateConversion).filter(
            AffiliateConversion.referral_code.in_(referral_codes)
        ).all() if referral_codes else []

        commissions = db.query(AffiliateCommission).filter(
            AffiliateCommission.referral_code.in_(referral_codes)
        ).all() if referral_codes else []

        clicks = db.query(AffiliateClick).filter(
            AffiliateClick.campaign_id.in_(campaign_ids)
        ).all() if campaign_ids else []

        org_total_commission_cents = sum(
            commission.amount_cents or 0
            for commission in commissions
        )

        org_paid_commission_cents = sum(
            commission.amount_cents or 0
            for commission in commissions
            if commission.status == "paid"
        )

        org_outstanding_commission_cents = sum(
            commission.amount_cents or 0
            for commission in commissions
            if commission.status in ["pending", "approved", "payable"]
        )

        total_campaigns += len(campaigns)
        total_enrollments += len(enrollments)
        total_conversions += len(conversions)
        total_commissions += len(commissions)
        total_clicks += len(clicks)
        total_commission_cents += org_total_commission_cents
        paid_commission_cents += org_paid_commission_cents
        outstanding_commission_cents += org_outstanding_commission_cents

        org_type = (org.organization_type or "").lower()
        member_role = (membership.role or "").lower() if membership else ""

        if "creator" in org_type or "creator" in member_role:
            creator_relationships.append({
                "organization_id": org.id,
                "organization_name": org.organization_name,
                "organization_type": org.organization_type,
                "membership_role": membership.role if membership else None
            })

        if "rescue" in org_type or "rescue" in member_role:
            rescue_relationships.append({
                "organization_id": org.id,
                "organization_name": org.organization_name,
                "organization_type": org.organization_type,
                "membership_role": membership.role if membership else None
            })

        partner_records.append({
            "organization": {
                "id": org.id,
                "organization_name": org.organization_name,
                "organization_type": org.organization_type,
                "project": org.project,
                "contact_name": org.contact_name,
                "contact_email": org.contact_email,
                "website_url": org.website_url,
                "location": org.location,
                "status": org.status,
                "notes": org.notes,
                "created_at": org.created_at,
            },
            "membership": {
                "id": membership.id if membership else None,
                "role": membership.role if membership else None,
                "status": membership.status if membership else None,
                "created_at": membership.created_at if membership else None,
            },
            "summary": {
                "campaigns": {
                    "total": len(campaigns),
                    "by_status": summarize_by_status(campaigns),
                },
                "enrollments": {
                    "total": len(enrollments),
                    "by_status": summarize_by_status(enrollments),
                },
                "conversions": {
                    "total": len(conversions),
                    "by_status": summarize_by_status(conversions),
                },
                "clicks": {
                    "total": len(clicks),
                },
                "commissions": {
                    "total": len(commissions),
                    "by_status": summarize_by_status(commissions, amount_field="amount_cents"),
                    "total_commission_cents": org_total_commission_cents,
                    "paid_commission_cents": org_paid_commission_cents,
                    "outstanding_commission_cents": org_outstanding_commission_cents,
                },
            },
            "recent": {
                "campaigns": [
                    serialize_account_campaign(campaign)
                    for campaign in campaigns[:10]
                ],
                "enrollments": [
                    serialize_account_enrollment(enrollment)
                    for enrollment in enrollments[:10]
                ],
                "conversions": [
                    serialize_affiliate_conversion(conversion)
                    for conversion in conversions[:10]
                ],
                "commissions": [
                    serialize_affiliate_commission(commission)
                    for commission in commissions[:10]
                ],
            }
        })

    partner_leaderboard_score = (
        (len(organizations) * 40)
        + (total_campaigns * 25)
        + (total_enrollments * 15)
        + (total_conversions * 10)
        + total_clicks
        + (len(creator_relationships) * 20)
        + (len(rescue_relationships) * 20)
        + int(total_commission_cents / 100)
    )

    locked_features = [
        {
            "key": "partner_white_label_console",
            "label": "White Label Console",
            "enabled": False,
            "status": "locked",
            "upgrade_path": "White Label Partner Deployment"
        },
        {
            "key": "partner_billing",
            "label": "Partner Billing",
            "enabled": False,
            "status": "locked",
            "upgrade_path": "Partner Billing Module"
        },
        {
            "key": "partner_team_management",
            "label": "Team Management",
            "enabled": False,
            "status": "locked",
            "upgrade_path": "Organization Team Tools"
        },
        {
            "key": "partner_creator_network",
            "label": "Creator Network",
            "enabled": False,
            "status": "locked",
            "upgrade_path": "Creator Relationship Management"
        },
        {
            "key": "partner_rescue_network",
            "label": "Rescue Network",
            "enabled": False,
            "status": "locked",
            "upgrade_path": "Rescue Relationship Management"
        },
        {
            "key": "xrpl_partner_identity",
            "label": "XRPL Partner Identity",
            "enabled": False,
            "status": "locked",
            "upgrade_path": "XRPL Verification Layer"
        }
    ]

    return {
        "module": "Partner Dashboard",
        "status": "active" if has_partner_access else "locked",
        "version": "v29-partner-dashboard",
        "access": {
            "enabled": has_partner_access,
            "role": account_role,
            "upgrade_path": None if has_partner_access else "Connect this account to a partner organization."
        },
        "identity": {
            "user_id": user.id,
            "email": user.email,
            "role": account_role,
            "status": user.status,
            "affiliate_id": user.affiliate_id,
            "referral_code": user.referral_code,
            "referring_affiliate_id": user.referring_affiliate_id,
        },
        "partner_profile": {
            "partner_id": f"partner-{user.id}",
            "partner_status": "active" if has_partner_access else "locked",
            "organization_count": len(organizations),
            "public_profile_status": "pending",
            "verification_status": "pending"
        },
        "summary": {
            "organizations": {
                "total": len(organizations),
                "creator_relationships": len(creator_relationships),
                "rescue_relationships": len(rescue_relationships),
            },
            "campaigns": {
                "total": total_campaigns,
            },
            "enrollments": {
                "total": total_enrollments,
            },
            "conversions": {
                "total": total_conversions,
            },
            "clicks": {
                "total": total_clicks,
            },
            "commissions": {
                "total": total_commissions,
                "total_commission_cents": total_commission_cents,
                "paid_commission_cents": paid_commission_cents,
                "outstanding_commission_cents": outstanding_commission_cents,
            },
            "leaderboard": {
                "score": partner_leaderboard_score,
                "rank_scope": "partner-platform",
                "rank": None,
                "status": "scoring_active",
                "note": "Rank will be calculated globally when partner leaderboard aggregation is enabled."
            }
        },
        "leaderboard": {
            "score": partner_leaderboard_score,
            "components": {
                "organizations": len(organizations),
                "campaigns": total_campaigns,
                "campaign_enrollments": total_enrollments,
                "conversions": total_conversions,
                "clicks": total_clicks,
                "creator_relationships": len(creator_relationships),
                "rescue_relationships": len(rescue_relationships),
                "commission_points": int(total_commission_cents / 100),
            },
            "formula": {
                "organization": 40,
                "campaign": 25,
                "campaign_enrollment": 15,
                "conversion": 10,
                "click": 1,
                "creator_relationship": 20,
                "rescue_relationship": 20,
                "commission_point": "1 point per dollar"
            }
        },
        "relationships": {
            "creators": creator_relationships,
            "rescues": rescue_relationships,
        },
        "organizations": {
            "count": len(partner_records),
            "records": partner_records,
        },
        "features": [
            {
                "key": "partner_dashboard",
                "label": "Partner Dashboard",
                "enabled": has_partner_access,
                "status": "enabled" if has_partner_access else "locked",
                "upgrade_path": None if has_partner_access else "Partner organization access required."
            },
            {
                "key": "partner_organization_analytics",
                "label": "Organization Analytics",
                "enabled": has_partner_access,
                "status": "enabled" if has_partner_access else "locked",
                "upgrade_path": None if has_partner_access else "Partner organization access required."
            },
            {
                "key": "partner_leaderboard",
                "label": "Partner Leaderboard",
                "enabled": True,
                "status": "enabled",
                "upgrade_path": None
            },
            *locked_features
        ],
        "quick_actions": [
            {"key": "view_organization_dashboard", "label": "View Organization Dashboard", "method": "GET", "endpoint": "/account/organization"},
            {"key": "view_member_dashboard", "label": "View Member Dashboard", "method": "GET", "endpoint": "/account/member"},
            {"key": "view_creator_dashboard", "label": "View Creator Dashboard", "method": "GET", "endpoint": "/account/creator"},
            {"key": "view_rescue_dashboard", "label": "View Rescue Dashboard", "method": "GET", "endpoint": "/account/rescue"},
            {"key": "view_opportunities", "label": "View Opportunities", "method": "GET", "endpoint": "/account/opportunities"},
            {"key": "view_my_campaigns", "label": "View My Campaigns", "method": "GET", "endpoint": "/account/opportunities/my-campaigns"},
            {"key": "view_affiliate_dashboard", "label": "View Affiliate Dashboard", "method": "GET", "endpoint": "/account/affiliate"},
        ]
    }


@router.get("/leaderboard")
def account_platform_leaderboard(
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {
            "module": "Platform Leaderboard",
            "status": "error",
            "message": "User not found."
        }

    aggregation = build_platform_ranking_aggregation(db)

    return {
        "module": "Platform Leaderboard",
        "status": "active",
        "version": "v30a-platform-leaderboard",
        "viewer": {
            "user_id": user.id,
            "email": user.email,
            "role": user.role,
            "affiliate_id": user.affiliate_id,
            "referral_code": user.referral_code,
        },
        "summary": aggregation["summary"],
        "leaderboards": {
            "creators": aggregation["leaderboards"]["creators"][:25],
            "rescues": aggregation["leaderboards"]["rescues"][:25],
            "partners": aggregation["leaderboards"]["partners"][:25],
            "affiliates": aggregation["leaderboards"]["affiliates"][:25],
        },
        "notes": [
            "This endpoint aggregates platform-wide discovery and reputation scores.",
            "Scores are provisional until dedicated leaderboard persistence is added.",
            "Future versions may use MetricEvent for richer global analytics."
        ]
    }



def serialize_contact_relay_message(message: ContactRelayMessage):
    return {
        "id": message.id,
        "project": message.project,
        "source_context": message.source_context,
        "source_listing_type": message.source_listing_type,
        "source_listing_id": message.source_listing_id,
        "recipient_type": message.recipient_type,
        "recipient_id": message.recipient_id,
        "sender_name": message.sender_name,
        "sender_email": message.sender_email,
        "subject": message.subject,
        "message": message.message,
        "status": message.status,
        "privacy_status": message.privacy_status,
        "created_at": message.created_at,
        "reviewed_at": message.reviewed_at,
        "resolved_at": message.resolved_at,
    }


@router.get("/contact-relay")
def account_contact_relay_inbox(
    status: str | None = None,
    recipient_type: str | None = None,
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {
            "module": "Contact Relay Inbox",
            "status": "error",
            "message": "User not found."
        }

    account_role = user.role or "free"
    has_admin_access = account_role in ["admin", "super_admin"]

    query = db.query(ContactRelayMessage)

    if status:
        query = query.filter(ContactRelayMessage.status == status)

    if recipient_type:
        query = query.filter(ContactRelayMessage.recipient_type == recipient_type)

    if not has_admin_access:
        query = query.filter(ContactRelayMessage.recipient_id == user.id)

    messages = query.order_by(
        ContactRelayMessage.created_at.desc(),
        ContactRelayMessage.id.desc()
    ).all()

    return {
        "module": "Contact Relay Inbox",
        "status": "active",
        "version": "network-communications-contact-relay-inbox-v1",
        "viewer": {
            "user_id": user.id,
            "role": account_role,
            "admin_access": has_admin_access
        },
        "filters": {
            "status": status,
            "recipient_type": recipient_type
        },
        "count": len(messages),
        "records": [
            serialize_contact_relay_message(message)
            for message in messages
        ]
    }



@router.get("/contact-relay/summary")
def account_contact_relay_summary(
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {
            "module": "Contact Relay Summary",
            "status": "error",
            "message": "User not found."
        }

    account_role = user.role or "free"
    has_admin_access = account_role in ["admin", "super_admin"]

    query = db.query(ContactRelayMessage)

    if not has_admin_access:
        query = query.filter(ContactRelayMessage.recipient_id == user.id)

    messages = query.order_by(
        ContactRelayMessage.created_at.desc(),
        ContactRelayMessage.id.desc()
    ).all()

    by_status = {}

    for message in messages:
        key = message.status or "unknown"

        if key not in by_status:
            by_status[key] = 0

        by_status[key] += 1

    recent = messages[:5]

    return {
        "module": "Contact Relay Summary",
        "status": "active",
        "version": "network-communications-contact-relay-summary-v1",
        "viewer": {
            "user_id": user.id,
            "role": account_role,
            "admin_access": has_admin_access
        },
        "summary": {
            "total": len(messages),
            "by_status": by_status,
            "new": by_status.get("new", 0),
            "reviewed": by_status.get("reviewed", 0),
            "resolved": by_status.get("resolved", 0)
        },
        "recent": [
            serialize_contact_relay_message(message)
            for message in recent
        ]
    }



def serialize_communication_permission(permission: CommunicationPermission):
    return {
        "id": permission.id,
        "project": permission.project,
        "listing_type": permission.listing_type,
        "listing_id": permission.listing_id,
        "allow_contact_relay": permission.allow_contact_relay,
        "allow_founder_inquiries": permission.allow_founder_inquiries,
        "allow_creator_inquiries": permission.allow_creator_inquiries,
        "allow_rescue_inquiries": permission.allow_rescue_inquiries,
        "allow_partner_inquiries": permission.allow_partner_inquiries,
        "allow_organization_inquiries": permission.allow_organization_inquiries,
        "auto_accept": permission.auto_accept,
        "status": permission.status,
        "created_at": permission.created_at,
        "updated_at": permission.updated_at,
    }



def serialize_partner_taxonomy_category(category: PartnerTaxonomyCategory):
    return {
        "id": category.id,
        "parent_id": category.parent_id,
        "name": category.name,
        "slug": category.slug,
        "description": category.description,
        "taxonomy_type": category.taxonomy_type,
        "project": category.project,
        "status": category.status,
        "sort_order": category.sort_order,
        "created_at": category.created_at,
        "updated_at": category.updated_at,
    }


@router.get("/taxonomy/categories")
def account_taxonomy_categories(
    parent_id: int | None = None,
    status: str | None = None,
    project: str = "PurPaws",
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {
            "module": "Partner Taxonomy Admin",
            "status": "error",
            "message": "User not found."
        }

    account_role = user.role or "free"
    has_admin_access = account_role in ["admin", "super_admin"]

    if not has_admin_access:
        return {
            "module": "Partner Taxonomy Admin",
            "status": "error",
            "message": "Admin access required."
        }

    query = db.query(PartnerTaxonomyCategory).filter(
        PartnerTaxonomyCategory.project == project
    )

    if parent_id is not None:
        query = query.filter(PartnerTaxonomyCategory.parent_id == parent_id)

    if status:
        query = query.filter(PartnerTaxonomyCategory.status == status)

    categories = query.order_by(
        PartnerTaxonomyCategory.parent_id.asc(),
        PartnerTaxonomyCategory.sort_order.asc(),
        PartnerTaxonomyCategory.name.asc(),
        PartnerTaxonomyCategory.id.asc()
    ).all()

    return {
        "module": "Partner Taxonomy Admin",
        "status": "active",
        "version": "public-discovery-taxonomy-admin-v1",
        "viewer": {
            "user_id": user.id,
            "role": account_role,
            "admin_access": has_admin_access
        },
        "filters": {
            "parent_id": parent_id,
            "status": status,
            "project": project
        },
        "count": len(categories),
        "records": [
            serialize_partner_taxonomy_category(category)
            for category in categories
        ]
    }


@router.post("/taxonomy/categories")
def account_upsert_taxonomy_category(
    name: str,
    slug: str,
    category_id: int | None = None,
    parent_id: int | None = None,
    description: str | None = None,
    taxonomy_type: str = "partner",
    project: str = "PurPaws",
    status: str = "active",
    sort_order: int = 100,
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {
            "module": "Partner Taxonomy Admin",
            "status": "error",
            "message": "User not found."
        }

    account_role = user.role or "free"
    has_admin_access = account_role in ["admin", "super_admin"]

    if not has_admin_access:
        return {
            "module": "Partner Taxonomy Admin",
            "status": "error",
            "message": "Admin access required."
        }

    clean_name = (name or "").strip()
    clean_slug = (slug or "").strip().lower()

    if not clean_name:
        return {
            "module": "Partner Taxonomy Admin",
            "status": "error",
            "message": "name is required."
        }

    if not clean_slug:
        return {
            "module": "Partner Taxonomy Admin",
            "status": "error",
            "message": "slug is required."
        }

    category = None

    if category_id:
        category = db.query(PartnerTaxonomyCategory).filter(
            PartnerTaxonomyCategory.id == category_id
        ).first()

    if not category:
        category = db.query(PartnerTaxonomyCategory).filter(
            PartnerTaxonomyCategory.project == project,
            PartnerTaxonomyCategory.slug == clean_slug,
            PartnerTaxonomyCategory.parent_id == parent_id
        ).first()

    created = False

    if not category:
        category = PartnerTaxonomyCategory(
            parent_id=parent_id,
            name=clean_name,
            slug=clean_slug,
            description=description,
            taxonomy_type=taxonomy_type,
            project=project,
            status=status,
            sort_order=sort_order,
        )
        db.add(category)
        created = True
    else:
        category.parent_id = parent_id
        category.name = clean_name
        category.slug = clean_slug
        category.description = description
        category.taxonomy_type = taxonomy_type
        category.project = project
        category.status = status
        category.sort_order = sort_order
        category.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(category)

    return {
        "module": "Partner Taxonomy Admin",
        "status": "created" if created else "updated",
        "version": "public-discovery-taxonomy-admin-v1",
        "viewer": {
            "user_id": user.id,
            "role": account_role,
            "admin_access": has_admin_access
        },
        "record": serialize_partner_taxonomy_category(category)
    }



def serialize_partner_taxonomy_assignment(
    assignment: PartnerTaxonomyAssignment,
    db: Session
):
    organization = db.query(PartnerOrganization).filter(
        PartnerOrganization.id == assignment.partner_organization_id
    ).first()

    category = db.query(PartnerTaxonomyCategory).filter(
        PartnerTaxonomyCategory.id == assignment.taxonomy_category_id
    ).first()

    return {
        "id": assignment.id,
        "partner_organization_id": assignment.partner_organization_id,
        "partner_organization_name": organization.organization_name if organization else None,
        "taxonomy_category_id": assignment.taxonomy_category_id,
        "taxonomy_category_name": category.name if category else None,
        "taxonomy_category_slug": category.slug if category else None,
        "taxonomy_parent_id": category.parent_id if category else None,
        "assignment_context": assignment.assignment_context,
        "campaign_id": assignment.campaign_id,
        "project": assignment.project,
        "status": assignment.status,
        "created_at": assignment.created_at,
        "updated_at": assignment.updated_at,
    }



def serialize_partner_campaign(campaign: PartnerCampaign, db: Session):
    organization = db.query(PartnerOrganization).filter(
        PartnerOrganization.id == campaign.partner_organization_id
    ).first()

    taxonomy_assignments = db.query(PartnerTaxonomyAssignment).filter(
        PartnerTaxonomyAssignment.assignment_context == "campaign",
        PartnerTaxonomyAssignment.campaign_id == campaign.id,
        PartnerTaxonomyAssignment.status == "active"
    ).all()

    categories = []

    for assignment in taxonomy_assignments:
        category = db.query(PartnerTaxonomyCategory).filter(
            PartnerTaxonomyCategory.id == assignment.taxonomy_category_id
        ).first()

        if category:
            categories.append({
                "assignment_id": assignment.id,
                "category_id": category.id,
                "parent_id": category.parent_id,
                "name": category.name,
                "slug": category.slug,
                "status": category.status,
            })

    return {
        "id": campaign.id,
        "partner_organization_id": campaign.partner_organization_id,
        "partner_organization_name": organization.organization_name if organization else None,
        "name": campaign.name,
        "slug": campaign.slug,
        "headline": campaign.headline,
        "description": campaign.description,
        "campaign_type": campaign.campaign_type,
        "project": campaign.project,
        "landing_url": campaign.landing_url,
        "asset_url": campaign.asset_url,
        "budget_cents": campaign.budget_cents,
        "currency": campaign.currency,
        "status": campaign.status,
        "start_date": campaign.start_date,
        "end_date": campaign.end_date,
        "taxonomy": categories,
        "created_at": campaign.created_at,
        "updated_at": campaign.updated_at,
    }


@router.get("/partner-campaigns")
def account_partner_campaigns(
    partner_organization_id: int | None = None,
    status: str | None = None,
    project: str = "PurPaws",
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    from backend.app.organization_access_authority import (
        evaluate_organization_access,
    )

    user_id = current_user.get("user_id")

    user = db.query(User).filter(
        User.id == user_id
    ).first()

    if not user:
        return {
            "module": "Partner Campaigns",
            "status": "error",
            "message": "User not found."
        }

    account_role = user.role or "free"
    has_admin_access = account_role in [
        "admin",
        "super_admin",
    ]

    query = db.query(
        PartnerCampaign
    ).filter(
        PartnerCampaign.project == project
    )

    if partner_organization_id:
        query = query.filter(
            PartnerCampaign.partner_organization_id
            == partner_organization_id
        )

    if status:
        query = query.filter(
            PartnerCampaign.status == status
        )

    if not has_admin_access:
        candidate_memberships = db.query(
            OrganizationMember
        ).filter(
            OrganizationMember.user_id == user.id,
            OrganizationMember.status == "active",
        ).all()

        authorized_organization_ids = []

        for membership in candidate_memberships:
            decision = evaluate_organization_access(
                db,
                user_id=user.id,
                organization_id=membership.organization_id,
                capability="view_organization",
            )

            if decision.allowed:
                authorized_organization_ids.append(
                    membership.organization_id
                )

        query = query.filter(
            PartnerCampaign.partner_organization_id.in_(
                authorized_organization_ids
            )
        )

    campaigns = query.order_by(
        PartnerCampaign.created_at.desc(),
        PartnerCampaign.id.desc()
    ).all()

    return {
        "module": "Partner Campaigns",
        "status": "active",
        "version": "partner-campaigns-v1",
        "viewer": {
            "user_id": user.id,
            "role": account_role,
            "admin_access": has_admin_access
        },
        "filters": {
            "partner_organization_id": partner_organization_id,
            "status": status,
            "project": project
        },
        "count": len(campaigns),
        "records": [
            serialize_partner_campaign(
                campaign,
                db,
            )
            for campaign in campaigns
        ]
    }


@router.get("/partner-campaigns/{campaign_id}")
def account_partner_campaign_detail(
    campaign_id: int,
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    from backend.app.organization_access_authority import (
        evaluate_organization_access,
    )

    user_id = current_user.get("user_id")

    user = db.query(User).filter(
        User.id == user_id
    ).first()

    if not user:
        return {
            "module": "Partner Campaign Detail",
            "status": "error",
            "message": "User not found."
        }

    account_role = user.role or "free"
    has_admin_access = account_role in [
        "admin",
        "super_admin",
    ]

    campaign = db.query(
        PartnerCampaign
    ).filter(
        PartnerCampaign.id == campaign_id
    ).first()

    if not campaign:
        return {
            "module": "Partner Campaign Detail",
            "status": "error",
            "message": "Partner campaign not found."
        }

    decision = evaluate_organization_access(
        db,
        user_id=user.id,
        organization_id=campaign.partner_organization_id,
        capability="view_organization",
    )

    if not decision.allowed:
        return {
            "module": "Partner Campaign Detail",
            "status": "error",
            "message": "You do not have access to this campaign.",
            "access_reason": decision.reason,
        }

    return {
        "module": "Partner Campaign Detail",
        "status": "active",
        "version": "partner-campaigns-v1",
        "viewer": {
            "user_id": user.id,
            "role": account_role,
            "admin_access": has_admin_access
        },
        "record": serialize_partner_campaign(
            campaign,
            db,
        )
    }


@router.post("/partner-campaigns")
def account_upsert_partner_campaign(
    partner_organization_id: int,
    name: str,
    slug: str,
    campaign_id: int | None = None,
    headline: str | None = None,
    description: str | None = None,
    campaign_type: str = "affiliate_promotion",
    project: str = "PurPaws",
    landing_url: str | None = None,
    asset_url: str | None = None,
    budget_cents: int = 0,
    currency: str = "CAD",
    status: str = "draft",
    start_date: str | None = None,
    end_date: str | None = None,
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    from backend.app.organization_access_authority import (
        evaluate_organization_access,
    )

    user_id = current_user.get("user_id")

    user = db.query(User).filter(
        User.id == user_id
    ).first()

    if not user:
        return {
            "module": "Partner Campaigns",
            "status": "error",
            "message": "User not found."
        }

    account_role = user.role or "free"
    has_admin_access = account_role in [
        "admin",
        "super_admin",
    ]

    decision = evaluate_organization_access(
        db,
        user_id=user.id,
        organization_id=partner_organization_id,
        capability="manage_campaigns",
    )

    if not decision.allowed:
        return {
            "module": "Partner Campaigns",
            "status": "error",
            "message": (
                "You do not have access to create or update "
                "campaigns for this organization."
            ),
            "access_reason": decision.reason,
        }

    organization = db.query(
        PartnerOrganization
    ).filter(
        PartnerOrganization.id == partner_organization_id
    ).first()

    if not organization:
        return {
            "module": "Partner Campaigns",
            "status": "error",
            "message": "Partner organization not found."
        }

    clean_name = (
        name or ""
    ).strip()

    clean_slug = (
        slug or ""
    ).strip().lower()

    if not clean_name:
        return {
            "module": "Partner Campaigns",
            "status": "error",
            "message": "name is required."
        }

    if not clean_slug:
        return {
            "module": "Partner Campaigns",
            "status": "error",
            "message": "slug is required."
        }

    def parse_dt(value):
        if not value:
            return None

        try:
            return datetime.fromisoformat(
                str(value).replace(
                    "Z",
                    "+00:00",
                )
            ).replace(
                tzinfo=None
            )
        except Exception:
            return None

    campaign = None

    if campaign_id:
        campaign = db.query(
            PartnerCampaign
        ).filter(
            PartnerCampaign.id == campaign_id
        ).first()

    if not campaign:
        campaign = db.query(
            PartnerCampaign
        ).filter(
            PartnerCampaign.partner_organization_id
            == partner_organization_id,
            PartnerCampaign.slug == clean_slug,
            PartnerCampaign.project == project
        ).first()

    created = False

    if not campaign:
        campaign = PartnerCampaign(
            partner_organization_id=partner_organization_id,
            name=clean_name,
            slug=clean_slug,
            headline=headline,
            description=description,
            campaign_type=campaign_type,
            project=project,
            landing_url=landing_url,
            asset_url=asset_url,
            budget_cents=budget_cents,
            currency=currency,
            status=status,
            start_date=parse_dt(start_date),
            end_date=parse_dt(end_date),
        )

        db.add(campaign)
        created = True

    else:
        campaign.partner_organization_id = partner_organization_id
        campaign.name = clean_name
        campaign.slug = clean_slug
        campaign.headline = headline
        campaign.description = description
        campaign.campaign_type = campaign_type
        campaign.project = project
        campaign.landing_url = landing_url
        campaign.asset_url = asset_url
        campaign.budget_cents = budget_cents
        campaign.currency = currency
        campaign.status = status
        campaign.start_date = parse_dt(
            start_date
        )
        campaign.end_date = parse_dt(
            end_date
        )
        campaign.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(campaign)

    return {
        "module": "Partner Campaigns",
        "status": (
            "created"
            if created
            else "updated"
        ),
        "version": "partner-campaigns-v1",
        "viewer": {
            "user_id": user.id,
            "role": account_role,
            "admin_access": has_admin_access
        },
        "record": serialize_partner_campaign(
            campaign,
            db,
        )
    }


@router.get("/taxonomy/assignments")
def account_taxonomy_assignments(
    partner_organization_id: int | None = None,
    taxonomy_category_id: int | None = None,
    assignment_context: str | None = None,
    campaign_id: int | None = None,
    status: str | None = None,
    project: str = "PurPaws",
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {
            "module": "Partner Taxonomy Assignments",
            "status": "error",
            "message": "User not found."
        }

    account_role = user.role or "free"
    has_admin_access = account_role in ["admin", "super_admin"]

    if not has_admin_access:
        return {
            "module": "Partner Taxonomy Assignments",
            "status": "error",
            "message": "Admin access required."
        }

    query = db.query(PartnerTaxonomyAssignment).filter(
        PartnerTaxonomyAssignment.project == project
    )

    if partner_organization_id:
        query = query.filter(
            PartnerTaxonomyAssignment.partner_organization_id == partner_organization_id
        )

    if taxonomy_category_id:
        query = query.filter(
            PartnerTaxonomyAssignment.taxonomy_category_id == taxonomy_category_id
        )

    if assignment_context:
        query = query.filter(
            PartnerTaxonomyAssignment.assignment_context == assignment_context
        )

    if campaign_id:
        query = query.filter(
            PartnerTaxonomyAssignment.campaign_id == campaign_id
        )

    if status:
        query = query.filter(
            PartnerTaxonomyAssignment.status == status
        )

    assignments = query.order_by(
        PartnerTaxonomyAssignment.partner_organization_id.asc(),
        PartnerTaxonomyAssignment.assignment_context.asc(),
        PartnerTaxonomyAssignment.id.asc()
    ).all()

    return {
        "module": "Partner Taxonomy Assignments",
        "status": "active",
        "version": "public-discovery-taxonomy-assignment-admin-v1",
        "viewer": {
            "user_id": user.id,
            "role": account_role,
            "admin_access": has_admin_access
        },
        "filters": {
            "partner_organization_id": partner_organization_id,
            "taxonomy_category_id": taxonomy_category_id,
            "assignment_context": assignment_context,
            "campaign_id": campaign_id,
            "status": status,
            "project": project
        },
        "count": len(assignments),
        "records": [
            serialize_partner_taxonomy_assignment(assignment, db)
            for assignment in assignments
        ]
    }


@router.post("/taxonomy/assignments")
def account_upsert_taxonomy_assignment(
    partner_organization_id: int,
    taxonomy_category_id: int,
    assignment_context: str = "organization",
    campaign_id: int | None = None,
    project: str = "PurPaws",
    status: str = "active",
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {
            "module": "Partner Taxonomy Assignments",
            "status": "error",
            "message": "User not found."
        }

    account_role = user.role or "free"
    has_admin_access = account_role in ["admin", "super_admin"]

    if not has_admin_access:
        return {
            "module": "Partner Taxonomy Assignments",
            "status": "error",
            "message": "Admin access required."
        }

    organization = db.query(PartnerOrganization).filter(
        PartnerOrganization.id == partner_organization_id
    ).first()

    if not organization:
        return {
            "module": "Partner Taxonomy Assignments",
            "status": "error",
            "message": "Partner organization not found."
        }

    category = db.query(PartnerTaxonomyCategory).filter(
        PartnerTaxonomyCategory.id == taxonomy_category_id
    ).first()

    if not category:
        return {
            "module": "Partner Taxonomy Assignments",
            "status": "error",
            "message": "Taxonomy category not found."
        }

    assignment = db.query(PartnerTaxonomyAssignment).filter(
        PartnerTaxonomyAssignment.partner_organization_id == partner_organization_id,
        PartnerTaxonomyAssignment.taxonomy_category_id == taxonomy_category_id,
        PartnerTaxonomyAssignment.assignment_context == assignment_context,
        PartnerTaxonomyAssignment.campaign_id == campaign_id,
        PartnerTaxonomyAssignment.project == project
    ).first()

    created = False

    if not assignment:
        assignment = PartnerTaxonomyAssignment(
            partner_organization_id=partner_organization_id,
            taxonomy_category_id=taxonomy_category_id,
            assignment_context=assignment_context,
            campaign_id=campaign_id,
            project=project,
            status=status,
        )
        db.add(assignment)
        created = True
    else:
        assignment.status = status
        assignment.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(assignment)

    return {
        "module": "Partner Taxonomy Assignments",
        "status": "created" if created else "updated",
        "version": "public-discovery-taxonomy-assignment-admin-v1",
        "viewer": {
            "user_id": user.id,
            "role": account_role,
            "admin_access": has_admin_access
        },
        "record": serialize_partner_taxonomy_assignment(assignment, db)
    }


@router.get("/communication-permissions")
def account_communication_permissions(
    listing_type: str | None = None,
    listing_id: int | None = None,
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {
            "module": "Communication Permissions",
            "status": "error",
            "message": "User not found."
        }

    account_role = user.role or "free"
    has_admin_access = account_role in ["admin", "super_admin"]

    query = db.query(CommunicationPermission)

    if listing_type:
        query = query.filter(CommunicationPermission.listing_type == listing_type)

    if listing_id:
        query = query.filter(CommunicationPermission.listing_id == listing_id)

    if not has_admin_access:
        query = query.filter(CommunicationPermission.listing_id == user.id)

    permissions = query.order_by(
        CommunicationPermission.listing_type.asc(),
        CommunicationPermission.listing_id.asc(),
        CommunicationPermission.id.asc()
    ).all()

    return {
        "module": "Communication Permissions",
        "status": "active",
        "version": "network-communications-permissions-api-v1",
        "viewer": {
            "user_id": user.id,
            "role": account_role,
            "admin_access": has_admin_access
        },
        "filters": {
            "listing_type": listing_type,
            "listing_id": listing_id
        },
        "count": len(permissions),
        "records": [
            serialize_communication_permission(permission)
            for permission in permissions
        ]
    }


@router.post("/communication-permissions")
def account_update_communication_permission(
    listing_type: str,
    listing_id: int,
    allow_contact_relay: int | None = None,
    allow_founder_inquiries: int | None = None,
    allow_creator_inquiries: int | None = None,
    allow_rescue_inquiries: int | None = None,
    allow_partner_inquiries: int | None = None,
    allow_organization_inquiries: int | None = None,
    auto_accept: int | None = None,
    status: str | None = None,
    project: str = "PurPaws",
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {
            "module": "Communication Permissions",
            "status": "error",
            "message": "User not found."
        }

    account_role = user.role or "free"
    has_admin_access = account_role in ["admin", "super_admin"]

    if not has_admin_access and listing_id != user.id:
        return {
            "module": "Communication Permissions",
            "status": "error",
            "message": "You do not have access to update this communication permission."
        }

    permission = db.query(CommunicationPermission).filter(
        CommunicationPermission.project == project,
        CommunicationPermission.listing_type == listing_type,
        CommunicationPermission.listing_id == listing_id
    ).first()

    if not permission:
        permission = CommunicationPermission(
            project=project,
            listing_type=listing_type,
            listing_id=listing_id,
            status="active"
        )
        db.add(permission)

    updates = {
        "allow_contact_relay": allow_contact_relay,
        "allow_founder_inquiries": allow_founder_inquiries,
        "allow_creator_inquiries": allow_creator_inquiries,
        "allow_rescue_inquiries": allow_rescue_inquiries,
        "allow_partner_inquiries": allow_partner_inquiries,
        "allow_organization_inquiries": allow_organization_inquiries,
        "auto_accept": auto_accept,
        "status": status,
    }

    for key, value in updates.items():
        if value is not None:
            setattr(permission, key, value)

    permission.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(permission)

    return {
        "module": "Communication Permissions",
        "status": "updated",
        "version": "network-communications-permissions-api-v1",
        "viewer": {
            "user_id": user.id,
            "role": account_role,
            "admin_access": has_admin_access
        },
        "record": serialize_communication_permission(permission)
    }


@router.get("/contact-relay/{message_id}")
def account_contact_relay_message(
    message_id: int,
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {
            "module": "Contact Relay Message",
            "status": "error",
            "message": "User not found."
        }

    account_role = user.role or "free"
    has_admin_access = account_role in ["admin", "super_admin"]

    message = db.query(ContactRelayMessage).filter(
        ContactRelayMessage.id == message_id
    ).first()

    if not message:
        return {
            "module": "Contact Relay Message",
            "status": "error",
            "message": "Contact relay message not found."
        }

    if not has_admin_access and message.recipient_id != user.id:
        return {
            "module": "Contact Relay Message",
            "status": "error",
            "message": "You do not have access to this relay message."
        }

    return {
        "module": "Contact Relay Message",
        "status": "active",
        "version": "network-communications-contact-relay-message-v1",
        "viewer": {
            "user_id": user.id,
            "role": account_role,
            "admin_access": has_admin_access
        },
        "record": serialize_contact_relay_message(message)
    }



def account_can_access_contact_relay_message(
    user: User,
    message: ContactRelayMessage
):
    account_role = user.role or "free"
    has_admin_access = account_role in ["admin", "super_admin"]

    if has_admin_access:
        return True

    return message.recipient_id == user.id


@router.post("/contact-relay/{message_id}/review")
def account_contact_relay_review(
    message_id: int,
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {
            "module": "Contact Relay Review",
            "status": "error",
            "message": "User not found."
        }

    message = db.query(ContactRelayMessage).filter(
        ContactRelayMessage.id == message_id
    ).first()

    if not message:
        return {
            "module": "Contact Relay Review",
            "status": "error",
            "message": "Contact relay message not found."
        }

    if not account_can_access_contact_relay_message(user, message):
        return {
            "module": "Contact Relay Review",
            "status": "error",
            "message": "You do not have access to this relay message."
        }

    message.status = "reviewed"
    message.reviewed_at = datetime.utcnow()

    db.commit()
    db.refresh(message)

    return {
        "module": "Contact Relay Review",
        "status": "reviewed",
        "version": "network-communications-contact-relay-workflow-v1",
        "record": serialize_contact_relay_message(message)
    }


@router.post("/contact-relay/{message_id}/resolve")
def account_contact_relay_resolve(
    message_id: int,
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db)
):
    user_id = current_user.get("user_id")

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {
            "module": "Contact Relay Resolve",
            "status": "error",
            "message": "User not found."
        }

    message = db.query(ContactRelayMessage).filter(
        ContactRelayMessage.id == message_id
    ).first()

    if not message:
        return {
            "module": "Contact Relay Resolve",
            "status": "error",
            "message": "Contact relay message not found."
        }

    if not account_can_access_contact_relay_message(user, message):
        return {
            "module": "Contact Relay Resolve",
            "status": "error",
            "message": "You do not have access to this relay message."
        }

    message.status = "resolved"
    message.resolved_at = datetime.utcnow()

    if not message.reviewed_at:
        message.reviewed_at = datetime.utcnow()

    db.commit()
    db.refresh(message)

    return {
        "module": "Contact Relay Resolve",
        "status": "resolved",
        "version": "network-communications-contact-relay-workflow-v1",
        "record": serialize_contact_relay_message(message)
    }


@router.get("/network-pulse")
def account_network_pulse(
    db: Session = Depends(get_db)
):
    users = db.query(User).all()

    organizations = db.query(PartnerOrganization).filter(
        PartnerOrganization.status == "active"
    ).all()

    memorials = db.query(Memorial).all()
    contributions = db.query(Contribution).all()
    media_assets = db.query(MediaAsset).all()

    campaigns = db.query(AffiliateCampaign).filter(
        AffiliateCampaign.status == "active"
    ).order_by(AffiliateCampaign.created_at.desc()).all()

    creator_count = len([
        user for user in users
        if (user.role or "").lower() == "creator"
    ])

    rescue_count = len([
        user for user in users
        if (user.role or "").lower() == "rescue"
    ])

    affiliate_count = len([
        user for user in users
        if user.affiliate_id or user.referral_code
    ])

    rescue_organization_count = len([
        organization for organization in organizations
        if "rescue" in ((organization.organization_type or "").lower())
    ])

    featured_campaign = campaigns[0] if campaigns else None

    return {
        "module": "Network Pulse",
        "status": "active",
        "version": "v30b-network-pulse",
        "visibility": "public",
        "philosophy": "The Pulse Medallion is the public-facing heartbeat of the community.",
        "network": {
            "members": len(users),
            "organizations": len(organizations),
            "creators": creator_count,
            "rescues": rescue_count,
            "rescue_organizations": rescue_organization_count,
            "affiliates": affiliate_count,
        },
        "activity": {
            "memorials": len(memorials),
            "contributions": len(contributions),
            "media_assets": len(media_assets),
            "active_campaigns": len(campaigns),
        },
        "leaderboard_highlights": {
            "top_creator": None,
            "top_rescue": None,
            "top_partner": None,
            "note": "Public-safe leaderboard highlights will be promoted from v30A leaderboard scoring in a future pulse layer."
        },
        "featured": {
            "creator": None,
            "rescue": None,
            "organization": None,
            "campaign": serialize_account_campaign(featured_campaign) if featured_campaign else None,
        },
        "pulse_layers": [
            {
                "key": "community_activity",
                "label": "Community Activity",
                "enabled": True,
                "locked": False,
            },
            {
                "key": "network_size",
                "label": "Network Size",
                "enabled": True,
                "locked": False,
            },
            {
                "key": "leaderboard_highlights",
                "label": "Leaderboard Highlights",
                "enabled": False,
                "locked": True,
                "reason": "Requires public-safe leaderboard promotion layer."
            },
            {
                "key": "featured_creators",
                "label": "Featured Creators",
                "enabled": False,
                "locked": True,
                "reason": "Requires featured community curation."
            },
            {
                "key": "featured_rescues",
                "label": "Featured Rescues",
                "enabled": False,
                "locked": True,
                "reason": "Requires featured rescue curation."
            },
            {
                "key": "featured_organizations",
                "label": "Featured Organizations",
                "enabled": False,
                "locked": True,
                "reason": "Requires public organization profiles."
            },
            {
                "key": "featured_opportunities",
                "label": "Featured Opportunities",
                "enabled": bool(featured_campaign),
                "locked": not bool(featured_campaign),
                "reason": "Available when active public campaigns exist."
            },
            {
                "key": "xrpl_verification",
                "label": "XRPL Verification",
                "enabled": False,
                "locked": True,
                "reason": "Future ledger verification pulse layer."
            },
        ],
        "coming_soon": [
            "Leaderboard Highlights",
            "Featured Creators",
            "Featured Rescues",
            "Featured Organizations",
            "Featured Campaigns",
            "Featured Opportunities",
            "XRPL Verification",
            "White Label Communities",
        ],
        "notes": [
            "This endpoint is public-safe and does not require account authentication.",
            "Network Pulse is community heartbeat data, not private analytics.",
            "Future versions may promote public-safe highlights from leaderboard and campaign systems."
        ]
    }

