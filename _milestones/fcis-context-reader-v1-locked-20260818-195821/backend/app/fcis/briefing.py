from collections import Counter

from sqlalchemy.orm import Session

from backend.app.fcis.relationship_reader import (
    get_graph_relationships,
)


def build_private_briefing(
    db: Session,
):
    relationships = get_graph_relationships(db)

    active = [
        relationship
        for relationship in relationships
        if relationship["relationship_status"] == "active"
    ]

    pending = [
        relationship
        for relationship in relationships
        if relationship["relationship_status"] == "pending"
    ]

    relationship_types = Counter(
        relationship["relationship_type"]
        for relationship in relationships
    )

    observations = []

    for relationship in active:

        source = relationship["source"]
        target = relationship["target"]

        observations.append({
            "kind": "active_relationship",
            "priority": "normal",
            "headline": (
                f'{source["name"]} → {target["name"]}'
            ),
            "summary": (
                f'{relationship["relationship_type"]} '
                f'via {relationship["relationship_basis"]}'
            ),
            "relationship_id": relationship["id"],
        })

    for relationship in pending:

        source = relationship["source"]
        target = relationship["target"]

        observations.append({
            "kind": "pending_relationship",
            "priority": "review",
            "headline": (
                f'{source["name"]} ↔ {target["name"]}'
            ),
            "summary": (
                "Pending relationship requires review: "
                f'{relationship["relationship_type"]} / '
                f'{relationship["relationship_basis"]}'
            ),
            "relationship_id": relationship["id"],
        })

    # --------------------------------------------------------------
    # PRIVATE OPPORTUNITY CANDIDATE HEURISTIC v1
    #
    # Important:
    # This does NOT create CanonicalRelationship.
    # It merely surfaces graph patterns for human review.
    # --------------------------------------------------------------

    by_source = {}

    for relationship in active:
        source_id = (
            relationship["source"]["type"],
            relationship["source"]["id"],
        )

        by_source.setdefault(
            source_id,
            [],
        ).append(relationship)

    opportunity_candidates = []

    for source_key, source_relationships in by_source.items():

        if len(source_relationships) < 2:
            continue

        source = source_relationships[0]["source"]

        targets = [
            relationship["target"]
            for relationship in source_relationships
        ]

        opportunity_candidates.append({
            "kind": "shared_connection_pattern",
            "priority": "inspect",
            "source": source,
            "connected_nodes": targets,
            "relationship_ids": [
                relationship["id"]
                for relationship in source_relationships
            ],
            "observation": (
                f'{source["name"]} has multiple active relationships '
                "within the same canonical neighborhood."
            ),
            "human_question": (
                "Is there a useful introduction, collaboration, "
                "campaign, or other opportunity worth investigating?"
            ),
            "canonical_fact_created": False,
        })

    return {
        "privacy": "INTERNAL FCIS — OUR EYES ONLY",
        "relationship_count": len(relationships),
        "active_relationship_count": len(active),
        "pending_relationship_count": len(pending),
        "relationship_types": dict(relationship_types),
        "observations": observations,
        "opportunity_candidates": opportunity_candidates,
    }


def render_private_briefing(
    briefing: dict,
):
    lines = []

    lines.append("=" * 78)
    lines.append("FCIS PRIVATE BRIEFING")
    lines.append("OUR EYES ONLY")
    lines.append("=" * 78)

    lines.append("")
    lines.append(
        f'Relationships: {briefing["relationship_count"]}'
    )
    lines.append(
        f'Active:        {briefing["active_relationship_count"]}'
    )
    lines.append(
        f'Pending:       {briefing["pending_relationship_count"]}'
    )

    lines.append("")
    lines.append("RELATIONSHIP TYPES")

    for relationship_type, count in sorted(
        briefing["relationship_types"].items()
    ):
        lines.append(
            f"  {relationship_type}: {count}"
        )

    lines.append("")
    lines.append("WHAT CHANGED / NEEDS ATTENTION")

    if not briefing["observations"]:
        lines.append("  Nothing currently requires attention.")

    for index, observation in enumerate(
        briefing["observations"],
        1,
    ):
        lines.append("")
        lines.append(
            f'{index}. [{observation["priority"].upper()}] '
            f'{observation["headline"]}'
        )
        lines.append(
            f'   {observation["summary"]}'
        )
        lines.append(
            f'   Relationship #{observation["relationship_id"]}'
        )

    lines.append("")
    lines.append("OPPORTUNITY CANDIDATES")

    candidates = briefing["opportunity_candidates"]

    if not candidates:
        lines.append(
            "  No graph patterns currently surfaced."
        )

    for index, candidate in enumerate(
        candidates,
        1,
    ):
        lines.append("")
        lines.append(
            f'{index}. {candidate["source"]["name"]}'
        )

        lines.append("   Connected to:")

        for node in candidate["connected_nodes"]:
            lines.append(
                f'     - {node["name"]}'
            )

        lines.append(
            f'   Observation: {candidate["observation"]}'
        )

        lines.append(
            f'   Question: {candidate["human_question"]}'
        )

        lines.append(
            "   ACTION: HUMAN REVIEW ONLY"
        )

    lines.append("")
    lines.append("-" * 78)
    lines.append(
        "FCIS discovers opportunity. Humans authorize action."
    )
    lines.append("-" * 78)

    return "\n".join(lines)
