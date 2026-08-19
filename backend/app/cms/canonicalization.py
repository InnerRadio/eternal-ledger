from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.cms.security import require_active_account
from backend.app.canonicalizer import canonicalize_directory_organization


router = APIRouter(
    prefix="/cms/canonicalization",
    tags=["CMS Canonicalization"],
)


@router.post("/onboarding/{onboarding_id}/organization")
def cms_canonicalize_onboarding_organization(
    onboarding_id: int,
    current_user: dict = Depends(require_active_account),
    db: Session = Depends(get_db),
):
    """
    Explicit administrative invocation of canonical organization creation.

    v1 deliberately does not attach canonicalization automatically to:
    - onboarding verification
    - account creation
    - workspace save
    - publication
    - Directory rendering
    """

    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=403,
            detail="Administrator access required.",
        )

    try:
        result = canonicalize_directory_organization(
            db=db,
            onboarding_id=onboarding_id,
        )

        db.commit()

        return {
            "module": "CMS Canonicalization",
            "status": "success",
            "version": "canonicalization-invocation-v1",
            "result": result,
        }

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except RuntimeError as exc:
        db.rollback()

        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    except Exception:
        db.rollback()
        raise
