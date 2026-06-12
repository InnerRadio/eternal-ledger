from fastapi import APIRouter, Depends
from datetime import datetime
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import Memorial, MediaAsset, Contribution, MetricEvent, User, AffiliateCampaign, PartnerOrganization
from backend.app.environment_themes import ENVIRONMENT_THEMES


def parse_client_event_at(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None

router = APIRouter(prefix="/public", tags=["Public API"])


@router.post("/metrics/track")
def public_track_metric_event(
    event_type: str,
    project: str = "PurPaws",
    source: str = "public",
    session_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    campaign_id: str | None = None,
    organization_id: int | None = None,
    affiliate_id: str | None = None,
    referral_code: str | None = None,
    page_url: str | None = None,
    metadata_json: str | None = None,
    client_event_at: str | None = None,
    db: Session = Depends(get_db)
):
    event = MetricEvent(
        event_type=event_type,
        project=project,
        source=source,
        session_id=session_id,
        target_type=target_type,
        target_id=target_id,
        campaign_id=campaign_id,
        organization_id=organization_id,
        affiliate_id=affiliate_id,
        referral_code=referral_code,
        page_url=page_url,
        metadata_json=metadata_json,
        client_event_at=parse_client_event_at(client_event_at),
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    return {
        "module": "Public Metrics",
        "status": "tracked",
        "record": {
            "id": event.id,
            "event_type": event.event_type,
            "project": event.project,
            "source": event.source,
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
    }


@router.post("/metrics/batch")
def public_track_metric_events_batch(
    events_json: str,
    db: Session = Depends(get_db)
):
    import json

    try:
        events_data = json.loads(events_json)
    except Exception:
        return {
            "module": "Public Metrics Batch",
            "status": "error",
            "message": "Invalid events_json payload."
        }

    if not isinstance(events_data, list):
        return {
            "module": "Public Metrics Batch",
            "status": "error",
            "message": "events_json must be a JSON list."
        }

    created = []

    for item in events_data:
        if not isinstance(item, dict):
            continue

        event_type = item.get("event_type")

        if not event_type:
            continue

        event = MetricEvent(
            event_type=event_type,
            project=item.get("project") or "PurPaws",
            source=item.get("source") or "public",
            session_id=item.get("session_id"),
            target_type=item.get("target_type"),
            target_id=item.get("target_id"),
            campaign_id=item.get("campaign_id"),
            organization_id=item.get("organization_id"),
            affiliate_id=item.get("affiliate_id"),
            referral_code=item.get("referral_code"),
            page_url=item.get("page_url"),
            metadata_json=item.get("metadata_json"),
            client_event_at=parse_client_event_at(item.get("client_event_at")),
        )

        db.add(event)
        created.append(event)

    db.commit()

    for event in created:
        db.refresh(event)

    return {
        "module": "Public Metrics Batch",
        "status": "tracked",
        "count": len(created),
        "records": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "project": event.project,
                "source": event.source,
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
            for event in created
        ]
    }


@router.get("/memorials")
def public_memorials(
    db: Session = Depends(get_db)
):
    memorials = db.query(Memorial).filter(
        Memorial.status == "published"
    ).all()

    records = []

    for memorial in memorials:
        media = db.query(MediaAsset).filter(
            MediaAsset.memorial_id == memorial.id,
            MediaAsset.status == "published"
        ).first()

        records.append({
            "id": memorial.id,
            "companion_name": memorial.companion_name,
            "years": memorial.years,
            "story": memorial.story,
            "archive_type": memorial.archive_type,
            "project": memorial.project,
            "status": memorial.status,
            "environment_theme": memorial.environment_theme,
            "atmosphere_intensity": memorial.atmosphere_intensity,
            "primary_media": media.file_path if media else None
        })

    return {
        "module": "Public Memorials",
        "status": "active",
        "count": len(records),
        "records": records
    }


@router.get("/memorials/{memorial_id}")
def public_memorial_detail(
    memorial_id: int,
    db: Session = Depends(get_db)
):
    memorial = db.query(Memorial).filter(
        Memorial.id == memorial_id,
        Memorial.status == "published"
    ).first()

    if not memorial:
        return {
            "module": "Public Memorial",
            "status": "error",
            "message": "Memorial not found."
        }

    return {
        "module": "Public Memorial",
        "status": "active",
        "record": {
            "id": memorial.id,
            "companion_name": memorial.companion_name,
            "years": memorial.years,
            "story": memorial.story,
            "archive_type": memorial.archive_type,
            "project": memorial.project,
            "status": memorial.status,
            "environment_theme": memorial.environment_theme,
            "atmosphere_intensity": memorial.atmosphere_intensity
        }
    }


@router.get("/memorials/{memorial_id}/media")
def public_memorial_media(
    memorial_id: int,
    db: Session = Depends(get_db)
):
    assets = db.query(MediaAsset).filter(
        MediaAsset.memorial_id == memorial_id,
        MediaAsset.status == "published"
    ).all()

    return {
        "module": "Public Memorial Media",
        "status": "active",
        "memorial_id": memorial_id,
        "count": len(assets),
        "records": [
            {
                "id": asset.id,
                "file_path": asset.file_path,
                "original_filename": asset.original_filename,
                "media_type": asset.media_type,
                "status": asset.status,
                "ipfs_cid": asset.ipfs_cid,
                "xrpl_tx_hash": asset.xrpl_tx_hash,
                "created_at": asset.created_at,
            }
            for asset in assets
        ]
    }


@router.get("/memorials/{memorial_id}/contributions")
def public_memorial_contributions(
    memorial_id: int,
    db: Session = Depends(get_db)
):
    contributions = db.query(Contribution).filter(
        Contribution.memorial_id == memorial_id,
        Contribution.status == "published"
    ).all()

    return {
        "module": "Public Contributions",
        "status": "active",
        "memorial_id": memorial_id,
        "count": len(contributions),
        "records": [
            {
                "id": contribution.id,
                "contributor_name": contribution.contributor_name,
                "contribution_type": contribution.contribution_type,
                "content": contribution.content,
                "media_asset_id": contribution.media_asset_id,
                "status": contribution.status,
                "ipfs_cid": contribution.ipfs_cid,
                "xrpl_tx_hash": contribution.xrpl_tx_hash,
                "created_at": contribution.created_at,
            }
            for contribution in contributions
        ]
    }


@router.get("/environment-themes")
def public_environment_themes():
    return {
        "module": "Environment Themes",
        "status": "active",
        "count": len(ENVIRONMENT_THEMES),
        "records": ENVIRONMENT_THEMES
    }


@router.get("/pulse")
def public_network_pulse(
    db: Session = Depends(get_db)
):
    memorial_count = db.query(Memorial).filter(
        Memorial.status == "published"
    ).count()

    media_count = db.query(MediaAsset).filter(
        MediaAsset.status == "published"
    ).count()

    contribution_count = db.query(Contribution).filter(
        Contribution.status == "published"
    ).count()

    users = db.query(User).all()

    organizations = db.query(PartnerOrganization).filter(
        PartnerOrganization.status == "active"
    ).all()

    opportunities = db.query(AffiliateCampaign).filter(
        AffiliateCampaign.status == "active"
    ).order_by(AffiliateCampaign.created_at.desc()).limit(6).all()

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

    opportunity_records = [
        {
            "id": opportunity.id,
            "campaign_id": opportunity.campaign_id,
            "label": "Opportunity",
            "title": opportunity.title,
            "description": opportunity.description,
            "project": opportunity.project,
            "sponsor_name": opportunity.sponsor_name,
            "opportunity_type": opportunity.campaign_type,
            "payout_type": opportunity.payout_type,
            "payout_amount_cents": opportunity.payout_amount_cents,
            "payout_percent": opportunity.payout_percent,
            "currency": opportunity.currency,
            "status": opportunity.status,
            "starts_at": opportunity.starts_at,
            "ends_at": opportunity.ends_at,
            "created_at": opportunity.created_at,
        }
        for opportunity in opportunities
    ]

    featured_opportunity = opportunity_records[0] if opportunity_records else None

    return {
        "module": "PurPaws Network Pulse",
        "status": "active",
        "version": "v30b-public-network-pulse",
        "visibility": "public",
        "network": "PurPaws Continuity Network",
        "philosophy": "The Pulse Medallion is the public-facing heartbeat of the community.",

        "metrics": {
            "published_memorials": memorial_count,
            "published_media_assets": media_count,
            "published_contributions": contribution_count,

            "members": len(users),
            "organizations": len(organizations),
            "creators": creator_count,
            "rescues": rescue_count,
            "rescue_organizations": rescue_organization_count,
            "affiliates": affiliate_count,
            "active_opportunities": len(opportunity_records)
        },

        "continuity": {
            "memorials": memorial_count,
            "media_assets": media_count,
            "contributions": contribution_count
        },

        "community": {
            "members": len(users),
            "organizations": len(organizations),
            "creators": creator_count,
            "rescues": rescue_count,
            "rescue_organizations": rescue_organization_count,
            "affiliates": affiliate_count
        },

        "opportunities": {
            "label": "Opportunities",
            "description": "Public-facing campaigns and side-hustle paths available through the PurPaws network.",
            "count": len(opportunity_records),
            "featured": featured_opportunity,
            "records": opportunity_records
        },

        "pulse_layers": [
            {
                "key": "continuity",
                "label": "Continuity Layer",
                "enabled": True,
                "locked": False
            },
            {
                "key": "community",
                "label": "Community Layer",
                "enabled": True,
                "locked": False
            },
            {
                "key": "opportunities",
                "label": "Opportunities",
                "enabled": bool(opportunity_records),
                "locked": not bool(opportunity_records),
                "reason": "Available when active public campaigns exist."
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
                "key": "xrpl_verification",
                "label": "XRPL Verification",
                "enabled": False,
                "locked": True,
                "reason": "Future ledger verification pulse layer."
            }
        ],

        "systems": {
            "xrpl": "planned",
            "eternal_ledger": "active",
            "continuity_layer": "operational",
            "community_layer": "active",
            "opportunity_layer": "active" if opportunity_records else "waiting"
        },

        "coming_soon": [
            "Leaderboard Highlights",
            "Featured Creators",
            "Featured Rescues",
            "Featured Organizations",
            "XRPL Verification",
            "White Label Communities"
        ],

        "notes": [
            "This endpoint is public-safe and does not require account authentication.",
            "The legacy metrics object is preserved for compatibility with existing Pulse Medallion UI.",
            "AffiliateCampaign records are presented publicly as Opportunities."
        ]
    }


@router.get("/trails")
def public_trails(db: Session = Depends(get_db)):
    contributions = db.query(Contribution).filter(
        Contribution.status == "published"
    ).order_by(Contribution.created_at.desc()).limit(12).all()

    records = []

    for contribution in contributions:
        memorial = db.query(Memorial).filter(
            Memorial.id == contribution.memorial_id
        ).first()

        records.append({
            "id": contribution.id,
            "title": memorial.companion_name if memorial else "PurPaws Trail Note",
            "trail_type": contribution.contribution_type,
            "content": contribution.content,
            "memorial_id": contribution.memorial_id,
            "media_asset_id": contribution.media_asset_id,
            "status": contribution.status,
            "ipfs_cid": contribution.ipfs_cid,
            "xrpl_tx_hash": contribution.xrpl_tx_hash,
            "created_at": contribution.created_at,
        })

    return {
        "module": "PurPaws Trails",
        "status": "active",
        "count": len(records),
        "records": records
    }

