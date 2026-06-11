from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import (
    MetricEvent,
    Memorial,
    MediaAsset,
    Contribution,
    AffiliateClick,
    AffiliateConversion,
)
from backend.app.cms.security import require_roles

router = APIRouter(prefix="/cms/reports", tags=["CMS Reports"])


def metric_count_by_field(records, field):
    result = {}

    for record in records:
        value = getattr(record, field, None) or "unknown"

        if value not in result:
            result[value] = {
                "count": 0
            }

        result[value]["count"] += 1

    return result


def serialize_metric_event(event: MetricEvent):
    return {
        "id": event.id,
        "event_type": event.event_type,
        "project": event.project,
        "source": event.source,
        "actor_user_id": event.actor_user_id,
        "session_id": event.session_id,
        "target_type": event.target_type,
        "target_id": event.target_id,
        "campaign_id": event.campaign_id,
        "organization_id": event.organization_id,
        "affiliate_id": event.affiliate_id,
        "referral_code": event.referral_code,
        "page_url": event.page_url,
        "metadata_json": event.metadata_json,
        "created_at": event.created_at,
    }


@router.get("/metrics")
def cms_metrics_report(
    project: str | None = None,
    event_type: str | None = None,
    source: str | None = None,
    campaign_id: str | None = None,
    organization_id: int | None = None,
    referral_code: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    query = db.query(MetricEvent)

    if project:
        query = query.filter(MetricEvent.project == project)

    if event_type:
        query = query.filter(MetricEvent.event_type == event_type)

    if source:
        query = query.filter(MetricEvent.source == source)

    if campaign_id:
        query = query.filter(MetricEvent.campaign_id == campaign_id)

    if organization_id:
        query = query.filter(MetricEvent.organization_id == organization_id)

    if referral_code:
        query = query.filter(MetricEvent.referral_code == referral_code)

    records = query.order_by(MetricEvent.created_at.desc()).limit(limit).all()

    return {
        "module": "CMS Metrics Report",
        "status": "active",
        "count": len(records),
        "filters": {
            "project": project,
            "event_type": event_type,
            "source": source,
            "campaign_id": campaign_id,
            "organization_id": organization_id,
            "referral_code": referral_code,
            "limit": limit,
        },
        "records": [
            serialize_metric_event(event)
            for event in records
        ]
    }


@router.get("/metrics/summary")
def cms_metrics_summary_report(
    project: str | None = None,
    source: str | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    query = db.query(MetricEvent)

    if project:
        query = query.filter(MetricEvent.project == project)

    if source:
        query = query.filter(MetricEvent.source == source)

    records = query.all()

    return {
        "module": "CMS Metrics Summary",
        "status": "active",
        "count": len(records),
        "filters": {
            "project": project,
            "source": source,
        },
        "summary": {
            "by_event_type": metric_count_by_field(records, "event_type"),
            "by_project": metric_count_by_field(records, "project"),
            "by_source": metric_count_by_field(records, "source"),
            "by_target_type": metric_count_by_field(records, "target_type"),
            "by_campaign": metric_count_by_field(records, "campaign_id"),
            "by_organization": metric_count_by_field(records, "organization_id"),
            "by_referral_code": metric_count_by_field(records, "referral_code"),
        }
    }


@router.get("/metrics/pages")
def cms_metrics_pages_report(
    project: str | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    query = db.query(MetricEvent).filter(
        MetricEvent.event_type == "page_view"
    )

    if project:
        query = query.filter(MetricEvent.project == project)

    records = query.all()

    return {
        "module": "CMS Metrics Pages",
        "status": "active",
        "count": len(records),
        "filters": {
            "project": project,
            "event_type": "page_view",
        },
        "summary": {
            "by_page_url": metric_count_by_field(records, "page_url"),
            "by_target_id": metric_count_by_field(records, "target_id"),
            "by_source": metric_count_by_field(records, "source"),
            "by_referral_code": metric_count_by_field(records, "referral_code"),
        }
    }


@router.get("/metrics/events")
def cms_metrics_events_report(
    project: str | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    query = db.query(MetricEvent)

    if project:
        query = query.filter(MetricEvent.project == project)

    records = query.all()

    return {
        "module": "CMS Metrics Events",
        "status": "active",
        "count": len(records),
        "filters": {
            "project": project,
        },
        "summary": {
            "by_event_type": metric_count_by_field(records, "event_type"),
            "by_target_type": metric_count_by_field(records, "target_type"),
            "by_campaign": metric_count_by_field(records, "campaign_id"),
            "by_organization": metric_count_by_field(records, "organization_id"),
        }
    }


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
                ]),
                "approved_conversions": len([
                    conversion for conversion in affiliate_conversions
                    if conversion.status == "approved"
                ]),
                "by_conversion_type": count_by_field(affiliate_conversions, "conversion_type")
            }
        }
    }
