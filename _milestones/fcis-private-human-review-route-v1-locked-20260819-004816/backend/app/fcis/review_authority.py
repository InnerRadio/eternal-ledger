"""
FCIS Human Review Write Authority v1

Private durable authority for current-state human review.

BOUNDARY

A Human Review records human judgment about an FCIS surfaced
Need ↔ Offer alignment.

It does NOT:

- create canonical facts
- create canonical context
- create canonical relationships
- authorize outreach
- authorize publication
- authorize external action
- expose a public endpoint

Every durable Human Review write must produce an AuditLog entry.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.app.models import (
    FCISHumanReview,
)

from backend.app.cms.audit import (
    write_audit_log,
)

from backend.app.fcis.review_contract import (
    REVIEW_SCHEMA_VERSION,
    normalize_disposition,
    validate_context_pair,
    validate_surfaced_card_id,
    validate_reviewer,
    review_identity,
)


REVIEW_AUTHORITY_VERSION = "fcis_human_review_authority_v1"


def _utc_now():
    return datetime.now(
        timezone.utc
    )


def _extract_card_contract(card: dict) -> dict:
    if not isinstance(card, dict):
        raise ValueError(
            "Opportunity Card must be a dictionary."
        )

    card_id = validate_surfaced_card_id(
        card.get("card_id")
    )

    need = card.get(
        "need_context"
    )

    offer = card.get(
        "offer_context"
    )

    if not isinstance(need, dict):
        raise ValueError(
            "Opportunity Card need_context is required."
        )

    if not isinstance(offer, dict):
        raise ValueError(
            "Opportunity Card offer_context is required."
        )

    need_context_id = need.get(
        "context_id"
    )

    offer_context_id = offer.get(
        "context_id"
    )

    need_context_id, offer_context_id = (
        validate_context_pair(
            need_context_id,
            offer_context_id,
        )
    )

    if need.get("context_type") != "need":
        raise ValueError(
            "Opportunity Card Need context type mismatch."
        )

    if offer.get("context_type") != "offer":
        raise ValueError(
            "Opportunity Card Offer context type mismatch."
        )

    need_key = need.get(
        "context_key"
    )

    offer_key = offer.get(
        "context_key"
    )

    if not need_key:
        raise ValueError(
            "Opportunity Card Need context key is required."
        )

    if not offer_key:
        raise ValueError(
            "Opportunity Card Offer context key is required."
        )

    if need_key != offer_key:
        raise ValueError(
            "Opportunity Card Need and Offer context keys do not align."
        )

    return {
        "card_id":
            card_id,
        "need_context_id":
            need_context_id,
        "offer_context_id":
            offer_context_id,
        "context_key":
            need_key,
        "review_identity":
            review_identity(
                need_context_id,
                offer_context_id,
            ),
    }


def get_human_review(
    db: Session,
    need_context_id: int,
    offer_context_id: int,
):
    need_context_id, offer_context_id = (
        validate_context_pair(
            need_context_id,
            offer_context_id,
        )
    )

    return (
        db.query(
            FCISHumanReview
        )
        .filter(
            FCISHumanReview.need_context_id
            == need_context_id,
            FCISHumanReview.offer_context_id
            == offer_context_id,
        )
        .first()
    )


def write_human_review(
    db: Session,
    card: dict,
    disposition: str,
    current_user: dict,
    reviewer_note: str | None = None,
):
    """
    Create or update the one current Human Review record for the
    canonical Need ↔ Offer context pair represented by `card`.

    This function is a durable write authority.

    It is not currently exposed through any route.
    """

    if not isinstance(current_user, dict):
        raise ValueError(
            "current_user is required."
        )

    card_contract = _extract_card_contract(
        card
    )

    disposition = normalize_disposition(
        disposition
    )

    reviewer = validate_reviewer(
        current_user.get("user_id"),
        current_user.get("email"),
        current_user.get("role"),
    )

    if reviewer["reviewer_role"] != "admin":
        raise ValueError(
            "FCIS Human Review writes require an admin reviewer."
        )

    if reviewer_note is not None:
        if not isinstance(
            reviewer_note,
            str,
        ):
            raise ValueError(
                "reviewer_note must be a string or None."
            )

        reviewer_note = reviewer_note.strip()

        if not reviewer_note:
            reviewer_note = None

    now = _utc_now()

    review = get_human_review(
        db,
        card_contract[
            "need_context_id"
        ],
        card_contract[
            "offer_context_id"
        ],
    )

    if review is None:

        review = FCISHumanReview(
            need_context_id=
                card_contract[
                    "need_context_id"
                ],
            offer_context_id=
                card_contract[
                    "offer_context_id"
                ],
            surfaced_card_id=
                card_contract[
                    "card_id"
                ],
            disposition=
                disposition,
            reviewer_user_id=
                reviewer[
                    "reviewer_user_id"
                ],
            reviewer_email=
                reviewer[
                    "reviewer_email"
                ],
            reviewer_role=
                reviewer[
                    "reviewer_role"
                ],
            reviewer_note=
                reviewer_note,
            reviewed_at=
                now,
            created_at=
                now,
            updated_at=
                None,
        )

        db.add(
            review
        )

        action = (
            "create_fcis_human_review"
        )

        mutation = "created"

    else:

        previous_disposition = (
            review.disposition
        )

        review.surfaced_card_id = (
            card_contract[
                "card_id"
            ]
        )

        review.disposition = (
            disposition
        )

        review.reviewer_user_id = (
            reviewer[
                "reviewer_user_id"
            ]
        )

        review.reviewer_email = (
            reviewer[
                "reviewer_email"
            ]
        )

        review.reviewer_role = (
            reviewer[
                "reviewer_role"
            ]
        )

        review.reviewer_note = (
            reviewer_note
        )

        review.reviewed_at = (
            now
        )

        review.updated_at = (
            now
        )

        action = (
            "update_fcis_human_review"
        )

        mutation = "updated"

    try:
        # Obtain the durable review ID without committing yet.
        #
        # The existing write_audit_log() helper performs the commit.
        # Therefore the Human Review row and its AuditLog row are
        # committed together by that existing transaction boundary.
        db.flush()

        details = (
            "FCIS Human Review "
            + mutation
            + " | review="
            + card_contract[
                "review_identity"
            ]
            + " | card="
            + card_contract[
                "card_id"
            ]
            + " | context_key="
            + str(
                card_contract[
                    "context_key"
                ]
            )
            + " | disposition="
            + disposition
        )

        write_audit_log(
            db=db,
            action=action,
            current_user={
                "user_id":
                    reviewer[
                        "reviewer_user_id"
                    ],
                "email":
                    reviewer[
                        "reviewer_email"
                    ],
                "role":
                    reviewer[
                        "reviewer_role"
                    ],
            },
            target_type=
                "fcis_human_review",
            target_id=
                review.id,
            details=
                details,
        )

        db.refresh(
            review
        )

    except Exception:
        db.rollback()
        raise

    return {
        "schema_version":
            REVIEW_SCHEMA_VERSION,
        "authority_version":
            REVIEW_AUTHORITY_VERSION,
        "mutation":
            mutation,
        "review_id":
            review.id,
        "review_identity":
            card_contract[
                "review_identity"
            ],
        "need_context_id":
            review.need_context_id,
        "offer_context_id":
            review.offer_context_id,
        "surfaced_card_id":
            review.surfaced_card_id,
        "disposition":
            review.disposition,
        "reviewer_user_id":
            review.reviewer_user_id,
        "reviewer_email":
            review.reviewer_email,
        "reviewer_role":
            review.reviewer_role,
        "reviewer_note":
            review.reviewer_note,
        "reviewed_at":
            review.reviewed_at,
        "created_at":
            review.created_at,
        "updated_at":
            review.updated_at,
        "canonical_fact_created":
            False,
        "relationship_created":
            False,
        "action_authorized":
            False,
        "public":
            False,
    }
