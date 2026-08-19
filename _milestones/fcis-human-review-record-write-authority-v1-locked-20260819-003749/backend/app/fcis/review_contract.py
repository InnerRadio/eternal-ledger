"""
FCIS Human Review Contract v1

Pure validation / identity contract.

NO DATABASE WRITES ARE AUTHORIZED BY THIS MODULE.

Human Review records represent human judgment about a
canonical Need ↔ Offer alignment.

Human Review does not modify canonical truth.
"""

REVIEW_SCHEMA_VERSION = "fcis_human_review_v1"

SUPPORTED_REVIEW_DISPOSITIONS = (
    "new",
    "investigating",
    "held",
    "dismissed",
)


def normalize_disposition(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError(
            "disposition must be a string."
        )

    normalized = value.strip().lower()

    if normalized not in SUPPORTED_REVIEW_DISPOSITIONS:
        raise ValueError(
            "disposition must be one of: "
            + ", ".join(
                SUPPORTED_REVIEW_DISPOSITIONS
            )
        )

    return normalized


def validate_context_pair(
    need_context_id: int,
    offer_context_id: int,
) -> tuple[int, int]:
    if (
        not isinstance(need_context_id, int)
        or isinstance(need_context_id, bool)
        or need_context_id <= 0
    ):
        raise ValueError(
            "need_context_id must be a positive integer."
        )

    if (
        not isinstance(offer_context_id, int)
        or isinstance(offer_context_id, bool)
        or offer_context_id <= 0
    ):
        raise ValueError(
            "offer_context_id must be a positive integer."
        )

    if need_context_id == offer_context_id:
        raise ValueError(
            "Need and Offer context IDs must be different."
        )

    return (
        need_context_id,
        offer_context_id,
    )


def review_identity(
    need_context_id: int,
    offer_context_id: int,
) -> str:
    need_context_id, offer_context_id = (
        validate_context_pair(
            need_context_id,
            offer_context_id,
        )
    )

    return (
        "need-offer-review:"
        + str(need_context_id)
        + ":"
        + str(offer_context_id)
    )


def validate_surfaced_card_id(
    surfaced_card_id: str,
) -> str:
    if not isinstance(
        surfaced_card_id,
        str,
    ):
        raise ValueError(
            "surfaced_card_id must be a string."
        )

    normalized = surfaced_card_id.strip()

    if not normalized:
        raise ValueError(
            "surfaced_card_id is required."
        )

    return normalized


def validate_reviewer(
    reviewer_user_id: int,
    reviewer_email: str,
    reviewer_role: str,
) -> dict:
    if (
        not isinstance(reviewer_user_id, int)
        or isinstance(reviewer_user_id, bool)
        or reviewer_user_id <= 0
    ):
        raise ValueError(
            "reviewer_user_id must be a positive integer."
        )

    if (
        not isinstance(reviewer_email, str)
        or not reviewer_email.strip()
    ):
        raise ValueError(
            "reviewer_email is required."
        )

    if (
        not isinstance(reviewer_role, str)
        or not reviewer_role.strip()
    ):
        raise ValueError(
            "reviewer_role is required."
        )

    return {
        "reviewer_user_id":
            reviewer_user_id,
        "reviewer_email":
            reviewer_email.strip(),
        "reviewer_role":
            reviewer_role.strip().lower(),
    }
