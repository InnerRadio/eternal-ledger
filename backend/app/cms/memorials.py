from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.cms.security import require_roles
from backend.app.cms.audit import write_audit_log
from backend.app.models import Memorial, MemorialCreate, MemorialUpdate

router = APIRouter(prefix="/cms/memorials", tags=["CMS Memorials"])


@router.get("/")
def list_memorials(db: Session = Depends(get_db), current_user: dict = Depends(require_roles('super_admin', 'admin', 'developer'))):
    memorials = db.query(Memorial).filter(Memorial.status != "deleted").all()

    return {
        "module": "CMS Memorials",
        "status": "active",
        "count": len(memorials),
        "records": [
            {
                "id": memorial.id,
                "companion_name": memorial.companion_name,
                "years": memorial.years,
                "archive_type": memorial.archive_type,
                "project": memorial.project,
                "status": memorial.status,
                "environment_theme": memorial.environment_theme,
                "atmosphere_intensity": memorial.atmosphere_intensity
            }
            for memorial in memorials
        ]
    }


@router.get("/deleted")
def list_deleted_memorials(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles('super_admin', 'admin'))
):
    memorials = db.query(Memorial).filter(Memorial.status == "deleted").all()

    return {
        "module": "CMS Deleted Memorials",
        "status": "active",
        "count": len(memorials),
        "records": [
            {
                "id": memorial.id,
                "companion_name": memorial.companion_name,
                "years": memorial.years,
                "archive_type": memorial.archive_type,
                "project": memorial.project,
                "status": memorial.status,
                "environment_theme": memorial.environment_theme,
                "atmosphere_intensity": memorial.atmosphere_intensity
            }
            for memorial in memorials
        ]
    }


@router.get("/{memorial_id}")
def get_memorial(memorial_id: int, db: Session = Depends(get_db), current_user: dict = Depends(require_roles('super_admin', 'admin', 'developer'))):
    memorial = db.query(Memorial).filter(
        Memorial.id == memorial_id
    ).first()

    if not memorial:
        return {
            "status": "not_found",
            "memorial_id": memorial_id
        }

    return {
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


@router.patch("/{memorial_id}")
def update_memorial(
    memorial_id: int,
    updates: MemorialUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles('super_admin', 'admin', 'developer'))
):
    memorial = db.query(Memorial).filter(
        Memorial.id == memorial_id
    ).first()

    if not memorial:
        return {
            "status": "not_found",
            "memorial_id": memorial_id
        }

    update_data = updates.dict(exclude_unset=True)

    for field, value in update_data.items():
        setattr(memorial, field, value)

    db.commit()
    db.refresh(memorial)

    write_audit_log(
        db=db,
        action="update_memorial",
        current_user=current_user,
        target_type="memorial",
        target_id=memorial.id,
        details=f"Updated memorial record {memorial.id}"
    )

    return {
        "status": "updated",
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


@router.post("/create")
def create_memorial_cms(
    memorial_data: MemorialCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles('super_admin', 'admin', 'editor'))
):
    memorial = Memorial(
        companion_name=memorial_data.companion_name,
        years=memorial_data.years,
        story=memorial_data.story,
        archive_type=memorial_data.archive_type,
        project=memorial_data.project,
        status="draft"
    )

    db.add(memorial)
    db.commit()
    db.refresh(memorial)

    write_audit_log(
        db=db,
        action="create_memorial",
        current_user=current_user,
        target_type="memorial",
        target_id=memorial.id,
        details=f"Created memorial record {memorial.id}"
    )

    return {
        "status": "created",
        "record": {
            "id": memorial.id,
            "companion_name": memorial.companion_name,
            "years": memorial.years,
            "archive_type": memorial.archive_type,
            "project": memorial.project,
            "status": memorial.status,
                "environment_theme": memorial.environment_theme,
                "atmosphere_intensity": memorial.atmosphere_intensity
        }
    }


@router.delete("/{memorial_id}")
def delete_memorial(
    memorial_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles('super_admin', 'admin'))
):
    memorial = db.query(Memorial).filter(Memorial.id == memorial_id).first()

    if not memorial:
        raise HTTPException(status_code=404, detail="Memorial not found.")

    memorial.status = "deleted"

    db.commit()
    db.refresh(memorial)

    write_audit_log(
        db=db,
        action="delete_memorial",
        current_user=current_user,
        target_type="memorial",
        target_id=memorial.id,
        details=f"Soft deleted memorial record {memorial.id}"
    )

    return {
        "status": "deleted",
        "record": {
            "id": memorial.id,
            "companion_name": memorial.companion_name,
            "status": memorial.status,
                "environment_theme": memorial.environment_theme,
                "atmosphere_intensity": memorial.atmosphere_intensity
        }
    }


@router.post("/{memorial_id}/restore")
def restore_memorial(
    memorial_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles('super_admin', 'admin'))
):
    memorial = db.query(Memorial).filter(Memorial.id == memorial_id).first()

    if not memorial:
        raise HTTPException(status_code=404, detail="Memorial not found.")

    memorial.status = "published"

    db.commit()
    db.refresh(memorial)

    write_audit_log(
        db=db,
        action="restore_memorial",
        current_user=current_user,
        target_type="memorial",
        target_id=memorial.id,
        details=f"Restored memorial record {memorial.id}"
    )

    return {
        "status": "restored",
        "record": {
            "id": memorial.id,
            "companion_name": memorial.companion_name,
            "status": memorial.status,
                "environment_theme": memorial.environment_theme,
                "atmosphere_intensity": memorial.atmosphere_intensity
        }
    }


def change_memorial_status(
    memorial_id: int,
    next_status: str,
    allowed_current_statuses: list[str],
    action: str,
    details: str,
    db: Session,
    current_user: dict
):
    memorial = db.query(Memorial).filter(Memorial.id == memorial_id).first()

    if not memorial:
        raise HTTPException(status_code=404, detail="Memorial not found.")

    if memorial.status not in allowed_current_statuses:
        return {
            "status": "error",
            "message": "Invalid status transition.",
            "current_status": memorial.status,
            "allowed_current_statuses": allowed_current_statuses,
            "next_status": next_status
        }

    memorial.status = next_status

    db.commit()
    db.refresh(memorial)

    write_audit_log(
        db=db,
        action=action,
        current_user=current_user,
        target_type="memorial",
        target_id=memorial.id,
        details=details
    )

    return {
        "status": next_status,
        "record": {
            "id": memorial.id,
            "companion_name": memorial.companion_name,
            "status": memorial.status,
            "environment_theme": memorial.environment_theme,
            "atmosphere_intensity": memorial.atmosphere_intensity
        }
    }


@router.post("/{memorial_id}/start-review")
def start_memorial_review(
    memorial_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles('super_admin', 'admin', 'reviewer'))
):
    return change_memorial_status(
        memorial_id=memorial_id,
        next_status="in_review",
        allowed_current_statuses=["submitted"],
        action="start_memorial_review",
        details=f"Started review for memorial record {memorial_id}",
        db=db,
        current_user=current_user
    )


@router.post("/{memorial_id}/request-changes")
def request_memorial_changes(
    memorial_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles('super_admin', 'admin', 'reviewer'))
):
    return change_memorial_status(
        memorial_id=memorial_id,
        next_status="changes_requested",
        allowed_current_statuses=["in_review"],
        action="request_memorial_changes",
        details=f"Requested changes for memorial record {memorial_id}",
        db=db,
        current_user=current_user
    )


@router.post("/{memorial_id}/approve")
def approve_memorial(
    memorial_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles('super_admin', 'admin', 'reviewer'))
):
    return change_memorial_status(
        memorial_id=memorial_id,
        next_status="approved",
        allowed_current_statuses=["in_review"],
        action="approve_memorial",
        details=f"Approved memorial record {memorial_id}",
        db=db,
        current_user=current_user
    )


@router.post("/{memorial_id}/publish")
def publish_memorial(
    memorial_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles('super_admin', 'admin'))
):
    return change_memorial_status(
        memorial_id=memorial_id,
        next_status="published",
        allowed_current_statuses=["approved"],
        action="publish_memorial",
        details=f"Published memorial record {memorial_id}",
        db=db,
        current_user=current_user
    )
