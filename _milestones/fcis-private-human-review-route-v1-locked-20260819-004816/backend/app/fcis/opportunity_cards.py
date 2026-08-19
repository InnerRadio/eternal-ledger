"""
FCIS Opportunity Card Assembler v1

Transforms verified private FCIS correlations into structured,
read-only internal intelligence cards.

BOUNDARY

This module does not:
- create canonical facts
- create canonical context
- create canonical relationships
- authorize actions
- persist workflow state
- publish intelligence
"""

from backend.app.fcis.correlation import (
    find_need_offer_correlations,
)


CARD_SCHEMA_VERSION = "fcis_opportunity_card_v1"


def _display_key(value):
    if value is None:
        return ""

    return str(value).replace("_", " ").strip()


def _relationship_summary(relationships):
    return [
        {
            "relationship_id": relationship.get(
                "relationship_id"
            ),
            "relationship_type": relationship.get(
                "relationship_type"
            ),
            "relationship_basis": relationship.get(
                "relationship_basis"
            ),
            "relationship_status": relationship.get(
                "relationship_status"
            ),
            "scope": relationship.get(
                "scope"
            ),
        }
        for relationship in relationships
    ]


def _build_caution(relationships):
    if not relationships:
        return (
            "No canonical relationship currently connects "
            "these subjects."
        )

    non_active = [
        relationship
        for relationship in relationships
        if relationship.get("relationship_status") != "active"
    ]

    if non_active:
        return (
            "Existing relationship context is not fully active. "
            "Review relationship status before developing this signal."
        )

    return None


def assemble_opportunity_card(correlation):
    """
    Convert one verified FCIS correlation into one structured
    private Opportunity Card.

    IMPORTANT CONTRACT

    Correlation Engine v1 supplies:

    need:
      context_id
      subject
      context_value
      scope

    offer:
      context_id
      subject
      context_value
      scope

    context_key and correlation_type are supplied at the
    correlation level.

    The Correlation Engine only emits active need/offer rows,
    therefore active status is factual by construction in v1.
    """

    need = correlation["need"]
    offer = correlation["offer"]

    need_subject = need["subject"]
    offer_subject = offer["subject"]

    context_key = correlation["context_key"]
    signal = _display_key(context_key)

    relationships = correlation.get(
        "relationship_context",
        [],
    )

    need_context_id = need["context_id"]
    offer_context_id = offer["context_id"]

    card_id = (
        f"need-offer:"
        f"{need_subject['id']}:"
        f"{offer_subject['id']}:"
        f"{need_context_id}:"
        f"{offer_context_id}"
    )

    return {
        "schema_version": CARD_SCHEMA_VERSION,

        "card_id": card_id,

        "card_type": "need_offer_alignment",

        # Display state only.
        # No workflow persistence exists yet.
        "display_status": "new",

        "participants": {
            "need_subject": {
                "type": need_subject["type"],
                "id": need_subject["id"],
                "name": need_subject["name"],
            },
            "offer_subject": {
                "type": offer_subject["type"],
                "id": offer_subject["id"],
                "name": offer_subject["name"],
            },
        },

        "signal": {
            "context_key": context_key,
            "display": signal,
        },

        "why_surfaced": {
            "summary": correlation["hypothesis"],
            "correlation_type": correlation[
                "correlation_type"
            ],
        },

        "need_context": {
            "context_id": need_context_id,
            "subject_id": need_subject["id"],
            "subject_name": need_subject["name"],
            "context_type": "need",
            "context_key": context_key,
            "context_value": need.get(
                "context_value"
            ),
            "context_status": "active",
            "scope": need.get("scope"),
        },

        "offer_context": {
            "context_id": offer_context_id,
            "subject_id": offer_subject["id"],
            "subject_name": offer_subject["name"],
            "context_type": "offer",
            "context_key": context_key,
            "context_value": offer.get(
                "context_value"
            ),
            "context_status": "active",
            "scope": offer.get("scope"),
        },

        "relationship_context": _relationship_summary(
            relationships
        ),

        "caution": _build_caution(
            relationships
        ),

        "human_question": correlation[
            "human_question"
        ],

        "human_review_required": correlation[
            "human_review_required"
        ],

        "canonical_fact_created": correlation[
            "canonical_fact_created"
        ],

        "relationship_created": correlation[
            "relationship_created"
        ],

        "action_authorized": correlation[
            "action_authorized"
        ],

        "workflow_persisted": False,
        "public": False,
    }


def assemble_opportunity_cards(db):
    """
    Assemble all current verified FCIS need ↔ offer correlations
    into structured private intelligence cards.
    """

    correlations = find_need_offer_correlations(db)

    return [
        assemble_opportunity_card(correlation)
        for correlation in correlations
    ]
