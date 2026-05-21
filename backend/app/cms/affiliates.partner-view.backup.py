from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import AffiliateClick, AffiliateConversion
from backend.app.cms.security import require_roles

router = APIRouter(prefix="/cms/affiliates", tags=["CMS Affiliates"])


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
