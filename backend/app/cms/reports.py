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
    AffiliateCommission,
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
        "client_event_at": event.client_event_at,
        "created_at": event.created_at,
    }


def ranked_metric_counts(records, field, limit: int = 25):
    counts = metric_count_by_field(records, field)

    ranked = [
        {
            field: key,
            "count": value["count"],
        }
        for key, value in counts.items()
        if key != "unknown"
    ]

    ranked.sort(key=lambda item: item["count"], reverse=True)

    return [
        {
            "rank": index + 1,
            **item
        }
        for index, item in enumerate(ranked[:limit])
    ]


def metric_records_for_project(db: Session, project: str | None = None):
    query = db.query(MetricEvent)

    if project:
        query = query.filter(MetricEvent.project == project)

    return query.all()


def commission_total_cents(records):
    return sum(
        record.amount_cents or 0
        for record in records
    )


def build_funnel_summary(
    views_count: int,
    clicks_count: int,
    enrollments_count: int,
    conversions_count: int,
    commissions_count: int,
    commission_cents: int
):
    click_through_rate = round((clicks_count / views_count) * 100, 2) if views_count else 0
    enrollment_rate = round((enrollments_count / clicks_count) * 100, 2) if clicks_count else 0
    conversion_rate = round((conversions_count / enrollments_count) * 100, 2) if enrollments_count else 0
    commission_per_conversion_cents = round(commission_cents / conversions_count, 2) if conversions_count else 0

    return {
        "views": views_count,
        "clicks": clicks_count,
        "enrollments": enrollments_count,
        "conversions": conversions_count,
        "commissions": commissions_count,
        "commission_cents": commission_cents,
        "rates": {
            "click_through_rate_percent": click_through_rate,
            "enrollment_rate_percent": enrollment_rate,
            "conversion_rate_percent": conversion_rate,
            "commission_per_conversion_cents": commission_per_conversion_cents,
        }
    }


def group_metric_events_by_session(records):
    sessions = {}

    for record in records:
        session_id = record.session_id or "unknown"

        if session_id not in sessions:
            sessions[session_id] = []

        sessions[session_id].append(record)

    return sessions


def serialize_session_summary(session_id, events):
    ordered = sorted(events, key=lambda event: event.client_event_at or event.created_at)

    start_time = (ordered[0].client_event_at or ordered[0].created_at) if ordered else None
    end_time = (ordered[-1].client_event_at or ordered[-1].created_at) if ordered else None

    duration_seconds = 0

    if start_time and end_time:
        duration_seconds = round((end_time - start_time).total_seconds(), 2)

    page_urls = sorted(set([
        event.page_url
        for event in ordered
        if event.page_url
    ]))

    event_types = metric_count_by_field(ordered, "event_type")

    scroll_events = [
        event
        for event in ordered
        if event.event_type == "scroll_depth"
    ]

    return {
        "session_id": session_id,
        "events": len(ordered),
        "duration_seconds": duration_seconds,
        "pages_visited": len(page_urls),
        "page_urls": page_urls,
        "first_event_type": ordered[0].event_type if ordered else None,
        "last_event_type": ordered[-1].event_type if ordered else None,
        "event_types": event_types,
        "scroll_events": len(scroll_events),
        "started_at": start_time,
        "ended_at": end_time,
    }


@router.get("/metrics/sessions")
def cms_metrics_sessions_report(
    project: str | None = None,
    source: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    query = db.query(MetricEvent)

    if project:
        query = query.filter(MetricEvent.project == project)

    if source:
        query = query.filter(MetricEvent.source == source)

    records = query.order_by(MetricEvent.created_at.desc()).limit(limit).all()

    sessions = group_metric_events_by_session(records)

    session_records = [
        serialize_session_summary(session_id, events)
        for session_id, events in sessions.items()
    ]

    session_records.sort(
        key=lambda item: item["ended_at"] or item["started_at"],
        reverse=True
    )

    return {
        "module": "CMS Metrics Sessions",
        "status": "active",
        "count": len(session_records),
        "filters": {
            "project": project,
            "source": source,
            "limit": limit,
        },
        "records": session_records
    }


@router.get("/intelligence/sessions")
def cms_metrics_session_intelligence(
    project: str | None = None,
    source: str | None = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    query = db.query(MetricEvent)

    if project:
        query = query.filter(MetricEvent.project == project)

    if source:
        query = query.filter(MetricEvent.source == source)

    records = query.order_by(MetricEvent.created_at.desc()).limit(limit).all()

    sessions = group_metric_events_by_session(records)

    session_records = [
        serialize_session_summary(session_id, events)
        for session_id, events in sessions.items()
    ]

    session_records.sort(
        key=lambda item: (
            item["events"],
            item["duration_seconds"],
            item["pages_visited"],
        ),
        reverse=True
    )

    return {
        "module": "CMS Metrics Intelligence Sessions",
        "status": "active",
        "count": len(session_records),
        "filters": {
            "project": project,
            "source": source,
            "limit": limit,
        },
        "records": [
            {
                "rank": index + 1,
                **record
            }
            for index, record in enumerate(session_records)
        ]
    }


@router.get("/attribution/campaigns")
def cms_attribution_campaign_funnels(
    project: str | None = None,
    limit: int = 25,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    metric_events = metric_records_for_project(db, project)

    clicks_query = db.query(AffiliateClick)
    conversions_query = db.query(AffiliateConversion)
    commissions_query = db.query(AffiliateCommission)

    if project:
        commissions_query = commissions_query.filter(AffiliateCommission.project == project)

    clicks = clicks_query.all()
    conversions = conversions_query.all()
    commissions = commissions_query.all()

    campaign_ids = sorted(set([
        record.campaign_id
        for record in metric_events
        if record.campaign_id
    ] + [
        click.campaign_id
        for click in clicks
        if click.campaign_id
    ]))

    records = []

    for campaign_id in campaign_ids:
        campaign_views = [
            event
            for event in metric_events
            if event.campaign_id == campaign_id and event.event_type in ["campaign_view", "page_view"]
        ]

        campaign_clicks = [
            click
            for click in clicks
            if click.campaign_id == campaign_id
        ]

        campaign_referral_codes = list(set([
            click.referral_code
            for click in campaign_clicks
            if click.referral_code
        ] + [
            event.referral_code
            for event in campaign_views
            if event.referral_code
        ]))

        campaign_conversions = [
            conversion
            for conversion in conversions
            if conversion.referral_code in campaign_referral_codes
        ]

        campaign_commissions = [
            commission
            for commission in commissions
            if commission.referral_code in campaign_referral_codes
        ]

        records.append({
            "campaign_id": campaign_id,
            "summary": build_funnel_summary(
                views_count=len(campaign_views),
                clicks_count=len(campaign_clicks),
                enrollments_count=0,
                conversions_count=len(campaign_conversions),
                commissions_count=len(campaign_commissions),
                commission_cents=commission_total_cents(campaign_commissions),
            )
        })

    records.sort(
        key=lambda record: (
            record["summary"]["conversions"],
            record["summary"]["commission_cents"],
            record["summary"]["clicks"],
            record["summary"]["views"],
        ),
        reverse=True
    )

    return {
        "module": "CMS Attribution Intelligence Campaigns",
        "status": "active",
        "count": len(records[:limit]),
        "filters": {
            "project": project,
            "limit": limit,
        },
        "records": [
            {
                "rank": index + 1,
                **record
            }
            for index, record in enumerate(records[:limit])
        ]
    }


@router.get("/attribution/affiliates")
def cms_attribution_affiliate_funnels(
    project: str | None = None,
    limit: int = 25,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    metric_events = metric_records_for_project(db, project)

    clicks = db.query(AffiliateClick).all()
    conversions = db.query(AffiliateConversion).all()

    commissions_query = db.query(AffiliateCommission)

    if project:
        commissions_query = commissions_query.filter(AffiliateCommission.project == project)

    commissions = commissions_query.all()

    referral_codes = sorted(set([
        event.referral_code
        for event in metric_events
        if event.referral_code
    ] + [
        click.referral_code
        for click in clicks
        if click.referral_code
    ] + [
        conversion.referral_code
        for conversion in conversions
        if conversion.referral_code
    ] + [
        commission.referral_code
        for commission in commissions
        if commission.referral_code
    ]))

    records = []

    for referral_code in referral_codes:
        affiliate_views = [
            event
            for event in metric_events
            if event.referral_code == referral_code
        ]

        affiliate_clicks = [
            click
            for click in clicks
            if click.referral_code == referral_code
        ]

        affiliate_conversions = [
            conversion
            for conversion in conversions
            if conversion.referral_code == referral_code
        ]

        affiliate_commissions = [
            commission
            for commission in commissions
            if commission.referral_code == referral_code
        ]

        records.append({
            "referral_code": referral_code,
            "summary": build_funnel_summary(
                views_count=len(affiliate_views),
                clicks_count=len(affiliate_clicks),
                enrollments_count=0,
                conversions_count=len(affiliate_conversions),
                commissions_count=len(affiliate_commissions),
                commission_cents=commission_total_cents(affiliate_commissions),
            )
        })

    records.sort(
        key=lambda record: (
            record["summary"]["conversions"],
            record["summary"]["commission_cents"],
            record["summary"]["clicks"],
            record["summary"]["views"],
        ),
        reverse=True
    )

    return {
        "module": "CMS Attribution Intelligence Affiliates",
        "status": "active",
        "count": len(records[:limit]),
        "filters": {
            "project": project,
            "limit": limit,
        },
        "records": [
            {
                "rank": index + 1,
                **record
            }
            for index, record in enumerate(records[:limit])
        ]
    }


@router.get("/intelligence/campaigns")
def cms_metrics_campaign_intelligence(
    project: str | None = None,
    limit: int = 25,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    records = metric_records_for_project(db, project)

    campaign_records = [
        record
        for record in records
        if record.campaign_id
    ]

    campaigns = ranked_metric_counts(campaign_records, "campaign_id", limit)

    return {
        "module": "CMS Metrics Intelligence Campaigns",
        "status": "active",
        "count": len(campaigns),
        "filters": {
            "project": project,
            "limit": limit,
        },
        "records": campaigns
    }


@router.get("/intelligence/organizations")
def cms_metrics_organization_intelligence(
    project: str | None = None,
    limit: int = 25,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    records = metric_records_for_project(db, project)

    organization_records = [
        record
        for record in records
        if record.organization_id
    ]

    organizations = ranked_metric_counts(organization_records, "organization_id", limit)

    return {
        "module": "CMS Metrics Intelligence Organizations",
        "status": "active",
        "count": len(organizations),
        "filters": {
            "project": project,
            "limit": limit,
        },
        "records": organizations
    }


@router.get("/intelligence/affiliates")
def cms_metrics_affiliate_intelligence(
    project: str | None = None,
    limit: int = 25,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    records = metric_records_for_project(db, project)

    affiliate_records = [
        record
        for record in records
        if record.referral_code or record.affiliate_id
    ]

    by_referral_code = ranked_metric_counts(affiliate_records, "referral_code", limit)
    by_affiliate_id = ranked_metric_counts(affiliate_records, "affiliate_id", limit)

    return {
        "module": "CMS Metrics Intelligence Affiliates",
        "status": "active",
        "filters": {
            "project": project,
            "limit": limit,
        },
        "records": {
            "by_referral_code": by_referral_code,
            "by_affiliate_id": by_affiliate_id,
        }
    }


@router.get("/intelligence/pages")
def cms_metrics_page_intelligence(
    project: str | None = None,
    limit: int = 25,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    records = metric_records_for_project(db, project)

    page_records = [
        record
        for record in records
        if record.event_type == "page_view"
    ]

    pages = ranked_metric_counts(page_records, "page_url", limit)
    targets = ranked_metric_counts(page_records, "target_id", limit)

    return {
        "module": "CMS Metrics Intelligence Pages",
        "status": "active",
        "filters": {
            "project": project,
            "limit": limit,
        },
        "records": {
            "by_page_url": pages,
            "by_target_id": targets,
        }
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
