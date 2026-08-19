from sqlalchemy.orm import Session

from backend.app.fcis.context_reader import (
    get_context_index,
)
from backend.app.fcis.relationship_reader import (
    get_graph_relationships,
)


def _relationship_context_between(
    relationships,
    subject_a,
    subject_b,
):
    matches = []

    a_key = (
        subject_a["type"],
        subject_a["id"],
    )

    b_key = (
        subject_b["type"],
        subject_b["id"],
    )

    for relationship in relationships:

        source_key = (
            relationship["source"]["type"],
            relationship["source"]["id"],
        )

        target_key = (
            relationship["target"]["type"],
            relationship["target"]["id"],
        )

        if {
            source_key,
            target_key,
        } == {
            a_key,
            b_key,
        }:
            matches.append({
                "relationship_id": relationship["id"],
                "relationship_type": relationship["relationship_type"],
                "relationship_basis": relationship["relationship_basis"],
                "relationship_status": relationship["relationship_status"],
                "scope": relationship["scope"],
            })

    return matches


def find_need_offer_correlations(
    db: Session,
):
    """
    Produce private FCIS correlation hypotheses.

    v1 rule:

        active NEED.context_key
        ==
        active OFFER.context_key

    Guardrails:

    - same-subject matches are rejected
    - canonical context is never modified
    - canonical relationships are never created
    - no score is assigned
    - no recommendation is made
    - no external action is authorized
    """

    index = get_context_index(db)

    needs = index.get(
        "need",
        {},
    )

    offers = index.get(
        "offer",
        {},
    )

    relationships = get_graph_relationships(db)

    correlations = []

    for context_key in sorted(needs):

        matching_offers = offers.get(
            context_key,
            [],
        )

        if not matching_offers:
            continue

        for need in needs[context_key]:

            for offer in matching_offers:

                need_subject = need["subject"]
                offer_subject = offer["subject"]

                if (
                    need_subject["type"]
                    == offer_subject["type"]
                    and
                    need_subject["id"]
                    == offer_subject["id"]
                ):
                    continue

                relationship_context = (
                    _relationship_context_between(
                        relationships,
                        need_subject,
                        offer_subject,
                    )
                )

                correlations.append({
                    "correlation_type": "need_offer_alignment",
                    "context_key": context_key,

                    "need": {
                        "context_id": need["id"],
                        "subject": need_subject,
                        "context_value": need["context_value"],
                        "scope": need["scope"],
                    },

                    "offer": {
                        "context_id": offer["id"],
                        "subject": offer_subject,
                        "context_value": offer["context_value"],
                        "scope": offer["scope"],
                    },

                    "relationship_context": relationship_context,

                    "hypothesis": (
                        f'{need_subject["name"]} has an active need '
                        f'for {context_key}, while '
                        f'{offer_subject["name"]} has an active offer '
                        f'for {context_key}.'
                    ),

                    "human_question": (
                        "Is this alignment worth investigating?"
                    ),

                    "canonical_fact_created": False,
                    "relationship_created": False,
                    "action_authorized": False,
                    "human_review_required": True,
                })

    return correlations
