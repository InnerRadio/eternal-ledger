from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import Memorial, MediaAsset, Contribution, MetricEvent
from backend.app.environment_themes import ENVIRONMENT_THEMES

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

    return {
        "module": "PurPaws Continuity Pulse",
        "status": "active",
        "network": "PurPaws Continuity Network",

        "metrics": {
            "published_memorials": memorial_count,
            "published_media_assets": media_count,
            "published_contributions": contribution_count
        },

        "systems": {
            "xrpl": "connected",
            "eternal_ledger": "active",
            "continuity_layer": "operational"
        }
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

