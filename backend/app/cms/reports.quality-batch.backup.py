from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import (
    Memorial,
    MediaAsset,
    Contribution,
    AffiliateClick,
    AffiliateConversion,
)
from backend.app.cms.security import require_roles

router = APIRouter(prefix="/cms/reports", tags=["CMS Reports"])


@router.get("/summary")
def cms_summary_report(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    memorials = db.query(Memorial).all()
    media_assets = db.query(MediaAsset).all()
    contributions = db.query(Contribution).all()
    affiliate_clicks = db.query(AffiliateClick).all()
    affiliate_conversions = db.query(AffiliateConversion).all()

    def count_by_status(records):
        counts = {}
        for record in records:
            status = getattr(record, "status", "unknown") or "unknown"
            counts[status] = counts.get(status, 0) + 1
        return counts

    def count_by_field(records, field):
        counts = {}
        for record in records:
            value = getattr(record, field, "unknown") or "unknown"
            counts[value] = counts.get(value, 0) + 1
        return counts

    return {
        "module": "CMS Reports",
        "status": "active",
        "summary": {
            "memorials": {
                "total": len(memorials),
                "by_status": count_by_status(memorials),
                "by_environment_theme": count_by_field(memorials, "environment_theme")
            },
            "media_assets": {
                "total": len(media_assets),
                "by_status": count_by_status(media_assets),
                "by_media_type": count_by_field(media_assets, "media_type")
            },
            "contributions": {
                "total": len(contributions),
                "by_status": count_by_status(contributions),
                "by_contribution_type": count_by_field(contributions, "contribution_type")
            },
            "affiliate_program": {
                "total_clicks": len(affiliate_clicks),
                "total_conversions": len(affiliate_conversions),
                "pending_conversions": len([
                    conversion for conversion in affiliate_conversions
                    if conversion.status == "pending"
                ])
            }
        }
    }
