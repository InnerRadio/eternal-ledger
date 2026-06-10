from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import Contribution, ContributionCreate
from backend.app.cms.security import require_roles

router = APIRouter(prefix="/cms/contributions", tags=["CMS Contributions"])


def serialize_contribution(contribution: Contribution):
    return {
        "id": contribution.id,
        "memorial_id": contribution.memorial_id,
        "contributor_name": contribution.contributor_name,
        "contribution_type": contribution.contribution_type,
        "content": contribution.content,
        "media_asset_id": contribution.media_asset_id,
        "status": contribution.status,
        "ipfs_cid": contribution.ipfs_cid,
        "xrpl_tx_hash": contribution.xrpl_tx_hash,
        "created_at": contribution.created_at,
    }


@router.get("/")
def list_contributions(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "editor", "reviewer"))
):
    contributions = db.query(Contribution).all()

    return {
        "module": "CMS Contributions",
        "status": "active",
        "count": len(contributions),
        "records": [
            serialize_contribution(contribution)
            for contribution in contributions
        ]
    }


@router.post("/")
def create_contribution(
    payload: ContributionCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "editor"))
):
    contribution = Contribution(
        memorial_id=payload.memorial_id,
        contributor_name=payload.contributor_name,
        contribution_type=payload.contribution_type,
        content=payload.content,
        media_asset_id=payload.media_asset_id,
        status=payload.status,
    )

    db.add(contribution)
    db.commit()
    db.refresh(contribution)

    return {
        "module": "CMS Contributions",
        "status": "created",
        "record": serialize_contribution(contribution)
    }


@router.patch("/{contribution_id}/status")
def update_contribution_status(
    contribution_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "editor"))
):
    contribution = db.query(Contribution).filter(
        Contribution.id == contribution_id
    ).first()

    if not contribution:
        return {
            "module": "CMS Contributions",
            "status": "error",
            "message": "Contribution not found."
        }

    allowed_statuses = ["draft", "submitted", "in_review", "changes_requested", "approved", "published", "archived", "deleted"]

    if status not in allowed_statuses:
        return {
            "module": "CMS Contributions",
            "status": "error",
            "message": "Invalid status.",
            "allowed_statuses": allowed_statuses
        }

    contribution.status = status

    db.commit()
    db.refresh(contribution)

    return {
        "module": "CMS Contributions",
        "status": "updated",
        "record": serialize_contribution(contribution)
    }


def change_contribution_status(
    contribution_id: int,
    next_status: str,
    allowed_current_statuses: list[str],
    db: Session
):
    contribution = db.query(Contribution).filter(
        Contribution.id == contribution_id
    ).first()

    if not contribution:
        return {
            "module": "CMS Contributions",
            "status": "error",
            "message": "Contribution not found."
        }

    if contribution.status not in allowed_current_statuses:
        return {
            "module": "CMS Contributions",
            "status": "error",
            "message": "Invalid status transition.",
            "current_status": contribution.status,
            "allowed_current_statuses": allowed_current_statuses,
            "next_status": next_status
        }

    contribution.status = next_status

    db.commit()
    db.refresh(contribution)

    return {
        "module": "CMS Contributions",
        "status": next_status,
        "record": serialize_contribution(contribution)
    }


@router.post("/{contribution_id}/start-review")
def start_contribution_review(
    contribution_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "reviewer"))
):
    return change_contribution_status(
        contribution_id=contribution_id,
        next_status="in_review",
        allowed_current_statuses=["submitted"],
        db=db
    )


@router.post("/{contribution_id}/request-changes")
def request_contribution_changes(
    contribution_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "reviewer"))
):
    return change_contribution_status(
        contribution_id=contribution_id,
        next_status="changes_requested",
        allowed_current_statuses=["in_review"],
        db=db
    )


@router.post("/{contribution_id}/approve")
def approve_contribution(
    contribution_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "reviewer"))
):
    return change_contribution_status(
        contribution_id=contribution_id,
        next_status="approved",
        allowed_current_statuses=["in_review"],
        db=db
    )


@router.post("/{contribution_id}/publish")
def publish_contribution(
    contribution_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin"))
):
    return change_contribution_status(
        contribution_id=contribution_id,
        next_status="published",
        allowed_current_statuses=["approved"],
        db=db
    )


@router.delete("/{contribution_id}")
def delete_contribution(
    contribution_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin"))
):
    contribution = db.query(Contribution).filter(
        Contribution.id == contribution_id
    ).first()

    if not contribution:
        return {
            "module": "CMS Contributions",
            "status": "error",
            "message": "Contribution not found."
        }

    db.delete(contribution)
    db.commit()

    return {
        "module": "CMS Contributions",
        "status": "deleted",
        "contribution_id": contribution_id
    }
