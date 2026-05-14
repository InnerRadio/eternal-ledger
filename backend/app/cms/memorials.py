from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.cms.security import require_roles
from backend.app.cms.audit import write_audit_log
from backend.app.models import Memorial, MemorialUpdate

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
                "status": memorial.status
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
                "status": memorial.status
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
            "status": memorial.status
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
            "status": memorial.status
        }
    }


@router.get("/create")
def create_memorial_cms():
    return {
        "module": "CMS Memorials",
        "status": "placeholder",
        "message": "CMS memorial creation workflow planned."
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
            "status": memorial.status
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

    memorial.status = "reviewed"

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
            "status": memorial.status
        }
    }
