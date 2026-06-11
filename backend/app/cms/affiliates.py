from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import AffiliateClick, AffiliateConversion, AffiliateCommission
from backend.app.cms.security import require_roles

router = APIRouter(prefix="/cms/affiliates", tags=["CMS Affiliates"])


COMMISSION_STATUSES = [
    "pending",
    "approved",
    "payable",
    "paid",
    "cancelled",
    "void",
]


def serialize_commission(commission: AffiliateCommission):
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


def change_commission_status(
    commission_id: int,
    status: str,
    db: Session
):
    if status not in COMMISSION_STATUSES:
        return {
            "module": "CMS Affiliate Commissions",
            "status": "error",
            "message": "Invalid commission status.",
            "allowed_statuses": COMMISSION_STATUSES,
        }

    commission = db.query(AffiliateCommission).filter(
        AffiliateCommission.id == commission_id
    ).first()

    if not commission:
        return {
            "module": "CMS Affiliate Commissions",
            "status": "error",
            "message": "Commission not found.",
        }

    commission.status = status

    db.commit()
    db.refresh(commission)

    return {
        "module": "CMS Affiliate Commissions",
        "status": "updated",
        "record": serialize_commission(commission)
    }


@router.get("/commissions")
def list_affiliate_commissions(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    commissions = db.query(AffiliateCommission).order_by(
        AffiliateCommission.created_at.desc()
    ).all()

    return {
        "module": "CMS Affiliate Commissions",
        "status": "active",
        "count": len(commissions),
        "records": [
            serialize_commission(commission)
            for commission in commissions
        ]
    }


@router.post("/commissions/create")
def create_affiliate_commission(
    conversion_id: int | None = None,
    affiliate_id: str | None = None,
    referral_code: str | None = None,
    project: str = "PurPaws",
    commission_type: str = "signup",
    amount_cents: int = 0,
    currency: str = "CAD",
    status: str = "pending",
    notes: str | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    if status not in COMMISSION_STATUSES:
        return {
            "module": "CMS Affiliate Commissions",
            "status": "error",
            "message": "Invalid commission status.",
            "allowed_statuses": COMMISSION_STATUSES,
        }

    commission = AffiliateCommission(
        conversion_id=conversion_id,
        affiliate_id=affiliate_id,
        referral_code=referral_code,
        project=project,
        commission_type=commission_type,
        amount_cents=amount_cents,
        currency=currency,
        status=status,
        notes=notes
    )

    db.add(commission)
    db.commit()
    db.refresh(commission)

    return {
        "module": "CMS Affiliate Commissions",
        "status": "created",
        "record": serialize_commission(commission)
    }


@router.post("/commissions/{commission_id}/approve")
def approve_affiliate_commission(
    commission_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    return change_commission_status(
        commission_id=commission_id,
        status="approved",
        db=db
    )


@router.post("/commissions/{commission_id}/payable")
def payable_affiliate_commission(
    commission_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    return change_commission_status(
        commission_id=commission_id,
        status="payable",
        db=db
    )


@router.post("/commissions/{commission_id}/paid")
def paid_affiliate_commission(
    commission_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    return change_commission_status(
        commission_id=commission_id,
        status="paid",
        db=db
    )


@router.post("/commissions/{commission_id}/void")
def void_affiliate_commission(
    commission_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    return change_commission_status(
        commission_id=commission_id,
        status="void",
        db=db
    )


@router.get("/clicks")
def list_affiliate_clicks(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    clicks = db.query(AffiliateClick).order_by(AffiliateClick.created_at.desc()).all()

    return {
        "module": "CMS Affiliates",
        "status": "active",
        "count": len(clicks),
        "records": [
            {
                "id": click.id,
                "affiliate_id": click.affiliate_id,
                "referral_code": click.referral_code,
                "campaign_id": click.campaign_id,
                "ad_id": click.ad_id,
                "source_url": click.source_url,
                "destination_url": click.destination_url,
                "ip_address": click.ip_address,
                "user_agent": click.user_agent,
                "created_at": click.created_at,
            }
            for click in clicks
        ]
    }


@router.get("/conversions")
def list_affiliate_conversions(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    conversions = db.query(AffiliateConversion).order_by(AffiliateConversion.created_at.desc()).all()

    return {
        "module": "CMS Affiliate Conversions",
        "status": "active",
        "count": len(conversions),
        "records": [
            {
                "id": conversion.id,
                "affiliate_id": conversion.affiliate_id,
                "referral_code": conversion.referral_code,
                "conversion_type": conversion.conversion_type,
                "target_type": conversion.target_type,
                "target_id": conversion.target_id,
                "status": conversion.status,
                "created_at": conversion.created_at,
            }
            for conversion in conversions
        ]
    }


@router.post("/track-click")
def track_affiliate_click(
    request: Request,
    affiliate_id: str | None = None,
    referral_code: str | None = None,
    campaign_id: str | None = None,
    ad_id: str | None = None,
    destination_url: str | None = None,
    db: Session = Depends(get_db)
):
    click = AffiliateClick(
        affiliate_id=affiliate_id,
        referral_code=referral_code,
        campaign_id=campaign_id,
        ad_id=ad_id,
        source_url=str(request.headers.get("referer") or ""),
        destination_url=destination_url,
        ip_address=request.client.host if request.client else None,
        user_agent=str(request.headers.get("user-agent") or ""),
    )

    db.add(click)
    db.commit()
    db.refresh(click)

    return {
        "module": "Affiliate Tracking",
        "status": "tracked",
        "record": {
            "id": click.id,
            "affiliate_id": click.affiliate_id,
            "referral_code": click.referral_code,
            "campaign_id": click.campaign_id,
            "ad_id": click.ad_id,
            "destination_url": click.destination_url,
            "created_at": click.created_at,
        }
    }


@router.get("/partner-inquiries")
def list_partner_inquiries(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    from backend.app.models import PartnerInquiry

    inquiries = db.query(PartnerInquiry)\
        .order_by(PartnerInquiry.created_at.desc())\
        .all()

    return {
        "module": "Partner Inquiries",
        "status": "active",
        "count": len(inquiries),
        "records": [
            {
                "id": inquiry.id,
                "name": inquiry.name,
                "email": inquiry.email,
                "interest_type": inquiry.interest_type,
                "organization": inquiry.organization,
                "message": inquiry.message,
                "status": inquiry.status,
                "created_at": inquiry.created_at
            }
            for inquiry in inquiries
        ]
    }


@router.post("/partner-inquiries/{inquiry_id}/status")
def update_partner_inquiry_status(
    inquiry_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    from backend.app.models import PartnerInquiry

    inquiry = db.query(PartnerInquiry)\
        .filter(PartnerInquiry.id == inquiry_id)\
        .first()

    if not inquiry:
        return {
            "status": "error",
            "message": "Inquiry not found"
        }

    inquiry.status = status

    if status in ["approved", "partner", "affiliate", "sponsor"]:
        conversion = AffiliateConversion(
            affiliate_id=None,
            referral_code=None,
            conversion_type=f"partner_inquiry_{status}",
            target_type="partner_inquiry",
            target_id=inquiry.id,
            status="approved"
        )

        db.add(conversion)

    db.commit()
    db.refresh(inquiry)

    return {
        "module": "Partner Inquiry Status",
        "status": "updated",
        "record": {
            "id": inquiry.id,
            "name": inquiry.name,
            "email": inquiry.email,
            "interest_type": inquiry.interest_type,
            "status": inquiry.status,
            "updated": True
        }
    }


@router.post("/conversions/log")
def log_affiliate_conversion(
    affiliate_id: str | None = None,
    referral_code: str | None = None,
    conversion_type: str = "partner_inquiry",
    target_type: str | None = None,
    target_id: int | None = None,
    status: str = "pending",
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    conversion = AffiliateConversion(
        affiliate_id=affiliate_id,
        referral_code=referral_code,
        conversion_type=conversion_type,
        target_type=target_type,
        target_id=target_id,
        status=status
    )

    db.add(conversion)
    db.commit()
    db.refresh(conversion)

    return {
        "module": "Affiliate Conversion",
        "status": "logged",
        "record": {
            "id": conversion.id,
            "affiliate_id": conversion.affiliate_id,
            "referral_code": conversion.referral_code,
            "conversion_type": conversion.conversion_type,
            "target_type": conversion.target_type,
            "target_id": conversion.target_id,
            "status": conversion.status,
            "created_at": conversion.created_at
        }
    }
