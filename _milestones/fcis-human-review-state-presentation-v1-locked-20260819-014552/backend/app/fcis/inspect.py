"""
FCIS Inspect Detail Authority v1

Read-only inspection assembler for one private FCIS
Opportunity Card.

BOUNDARY

This module does not:
- create canonical facts
- create canonical context
- create canonical relationships
- mutate canonical context
- persist workflow state
- authorize external action
- publish intelligence
"""

from sqlalchemy.orm import Session

from backend.app.fcis.context_reader import (
    get_context,
)

from backend.app.fcis.review_authority import (
    get_human_review,
)


INSPECT_SCHEMA_VERSION = "fcis_inspect_detail_v1"


def _inspect_context(
    db: Session,
    *,
    expected_context_id: int,
    expected_context_type: str,
):
    """
    Resolve one canonical context row through the existing
    FCIS read authority and verify that it still matches the
    Opportunity Card contract.
    """

    context = get_context(
        db,
        expected_context_id,
    )

    if context is None:
        return {
            "resolved": False,
            "context_id": expected_context_id,
            "expected_context_type": expected_context_type,
            "context": None,
            "warning": (
                "Canonical context could not be resolved."
            ),
        }

    actual_context_type = context.get(
        "context_type"
    )

    type_matches = (
        actual_context_type
        == expected_context_type
    )

    warning = None

    if not type_matches:
        warning = (
            "Canonical context type no longer matches "
            "the Opportunity Card expectation."
        )

    return {
        "resolved": True,
        "context_id": expected_context_id,
        "expected_context_type": expected_context_type,
        "actual_context_type": actual_context_type,
        "type_matches": type_matches,
        "context": context,
        "warning": warning,
    }


def assemble_inspect_detail(
    db: Session,
    card: dict,
):
    """
    Assemble read-only inspection detail for one existing
    Opportunity Card.

    The Opportunity Card remains the correlation envelope.

    Canonical context truth is re-read by context ID from the
    existing FCIS Context Reader so INSPECT does not duplicate
    or invent evidence authority.
    """

    need_context = card[
        "need_context"
    ]

    offer_context = card[
        "offer_context"
    ]

    need_detail = _inspect_context(
        db,
        expected_context_id=need_context[
            "context_id"
        ],
        expected_context_type="need",
    )

    offer_detail = _inspect_context(
        db,
        expected_context_id=offer_context[
            "context_id"
        ],
        expected_context_type="offer",
    )

    warnings = [
        detail["warning"]
        for detail in (
            need_detail,
            offer_detail,
        )
        if detail.get("warning")
    ]

    human_review_row = get_human_review(
        db,
        need_detail["context_id"],
        offer_detail["context_id"],
    )

    human_review = None

    if human_review_row is not None:
        human_review = {
            "review_id":
                human_review_row.id,
            "surfaced_card_id":
                human_review_row.surfaced_card_id,
            "disposition":
                human_review_row.disposition,
            "reviewer_user_id":
                human_review_row.reviewer_user_id,
            "reviewer_email":
                human_review_row.reviewer_email,
            "reviewer_role":
                human_review_row.reviewer_role,
            "reviewer_note":
                human_review_row.reviewer_note,
            "reviewed_at":
                human_review_row.reviewed_at,
            "created_at":
                human_review_row.created_at,
            "updated_at":
                human_review_row.updated_at,
        }

    return {
        "schema_version": INSPECT_SCHEMA_VERSION,

        "card_id": card["card_id"],
        "card_type": card["card_type"],
        "display_status": card[
            "display_status"
        ],

        "participants": card[
            "participants"
        ],

        "signal": card[
            "signal"
        ],

        "why_surfaced": card[
            "why_surfaced"
        ],

        "need": need_detail,
        "offer": offer_detail,

        "relationship_context": card.get(
            "relationship_context",
            [],
        ),

        "caution": card.get(
            "caution"
        ),

        "human_question": card[
            "human_question"
        ],

        "human_review_required": card[
            "human_review_required"
        ],

        "human_review": human_review,

        "safety_boundary": {
            "canonical_fact_created": card[
                "canonical_fact_created"
            ],
            "relationship_created": card[
                "relationship_created"
            ],
            "action_authorized": card[
                "action_authorized"
            ],
            "workflow_persisted": card[
                "workflow_persisted"
            ],
            "public": card[
                "public"
            ],
        },

        "warnings": warnings,

        "read_only": True,
    }
