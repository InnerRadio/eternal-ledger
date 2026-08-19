"""
FCIS Private Routes

Authenticated, authorized browser access to
FCIS Private Intelligence.

Read routes:
- GET /fcis/desk
- GET /fcis/inspect/{card_id}

Human Review write route:
- POST /fcis/review/{card_id}

This router does not belong to public_api.py.

Human Review durable mutation is delegated exclusively to the
FCIS Human Review Write Authority.
"""

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
)
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
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

from backend.app.fcis.review_authority import (
    write_human_review,
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


class FCISHumanReviewRequest(BaseModel):
    disposition: str
    reviewer_note: str | None = None


def _resolve_current_opportunity_card(
    db: Session,
    card_id: str,
):
    cards = assemble_opportunity_cards(
        db
    )

    return next(
        (
            candidate
            for candidate in cards
            if candidate.get("card_id") == card_id
        ),
        None,
    )


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
    card = _resolve_current_opportunity_card(
        db,
        card_id,
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


@router.post(
    "/review/{card_id}",
)
def fcis_private_human_review(
    card_id: str,
    payload: FCISHumanReviewRequest,
    response: Response,
    current_user: dict = Depends(
        require_fcis_access
    ),
    db: Session = Depends(get_db),
):
    """
    Persist current-state human judgment about one current
    FCIS Opportunity Card.

    This route does not own Human Review persistence.
    Durable mutation is delegated to write_human_review().

    Human Review remains separate from canonical truth and does
    not authorize relationships, actions, outreach, publication,
    or public projection.
    """

    card = _resolve_current_opportunity_card(
        db,
        card_id,
    )

    if card is None:
        raise HTTPException(
            status_code=404,
            detail="FCIS Opportunity Card not found.",
        )

    try:
        result = write_human_review(
            db=db,
            card=card,
            disposition=payload.disposition,
            current_user=current_user,
            reviewer_note=payload.reviewer_note,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    for name, value in PRIVATE_HEADERS.items():
        response.headers[
            name
        ] = value

    return result
