from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import Memorial, MediaAsset, Contribution
from backend.app.environment_themes import ENVIRONMENT_THEMES

router = APIRouter(prefix="/public", tags=["Public API"])


@router.get("/memorials")
def public_memorials(
    db: Session = Depends(get_db)
):
    memorials = db.query(Memorial).filter(
        Memorial.status == "reviewed"
    ).all()

    records = []

    for memorial in memorials:
        media = db.query(MediaAsset).filter(
            MediaAsset.memorial_id == memorial.id,
            MediaAsset.status.in_(["reviewed", "published"])
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
        Memorial.status == "reviewed"
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
        MediaAsset.status.in_(["reviewed", "published"])
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
        Contribution.status.in_(["reviewed", "published"])
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
