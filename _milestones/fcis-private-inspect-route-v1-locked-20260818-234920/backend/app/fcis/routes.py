"""
FCIS Private Routes

Authenticated, authorized, read-only browser access to
FCIS Private Intelligence.

This router does not belong to public_api.py.
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from backend.app.database import get_db

from backend.app.fcis.access import (
    require_fcis_access,
)

from backend.app.fcis.desk import (
    render_private_intelligence_desk,
)

from backend.app.fcis.opportunity_cards import (
    assemble_opportunity_cards,
)

from backend.app.fcis.inspect import (
    assemble_inspect_detail,
)

from backend.app.fcis.inspect_view import (
    render_inspect_detail,
)


router = APIRouter(
    prefix="/fcis",
    tags=["FCIS Private"],
)


PRIVATE_HEADERS = {
    "Cache-Control": "no-store",
    "Pragma": "no-cache",
    "X-FCIS-Private": "true",
}


@router.get(
    "/desk",
    response_class=HTMLResponse,
)
def fcis_private_desk(
    current_user: dict = Depends(
        require_fcis_access
    ),
    db: Session = Depends(get_db),
):
    html = render_private_intelligence_desk(
        db
    )

    return HTMLResponse(
        content=html,
        status_code=200,
        headers=PRIVATE_HEADERS,
    )


@router.get(
    "/inspect/{card_id}",
    response_class=HTMLResponse,
)
def fcis_private_inspect(
    card_id: str,
    current_user: dict = Depends(
        require_fcis_access
    ),
    db: Session = Depends(get_db),
):
    cards = assemble_opportunity_cards(
        db
    )

    card = next(
        (
            candidate
            for candidate in cards
            if candidate.get("card_id") == card_id
        ),
        None,
    )

    if card is None:
        raise HTTPException(
            status_code=404,
            detail="FCIS Opportunity Card not found.",
        )

    detail = assemble_inspect_detail(
        db,
        card,
    )

    html = render_inspect_detail(
        detail
    )

    return HTMLResponse(
        content=html,
        status_code=200,
        headers=PRIVATE_HEADERS,
    )
