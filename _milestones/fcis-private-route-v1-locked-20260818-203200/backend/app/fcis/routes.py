"""
FCIS Private Route v1

Authenticated, authorized, read-only browser access to
FCIS Private Intelligence Desk.

This router does not belong to public_api.py.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.fcis.access import require_fcis_access
from backend.app.fcis.desk import (
    render_private_intelligence_desk,
)


router = APIRouter(
    prefix="/fcis",
    tags=["FCIS Private"],
)


@router.get(
    "/desk",
    response_class=HTMLResponse,
)
def fcis_private_desk(
    current_user: dict = Depends(require_fcis_access),
    db: Session = Depends(get_db),
):
    html = render_private_intelligence_desk(
        db
    )

    return HTMLResponse(
        content=html,
        status_code=200,
        headers={
            "Cache-Control": "no-store",
            "Pragma": "no-cache",
            "X-FCIS-Private": "true",
        },
    )
