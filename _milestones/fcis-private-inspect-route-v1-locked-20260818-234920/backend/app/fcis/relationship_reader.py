from sqlalchemy.orm import Session

from backend.app.models import (
    CanonicalRelationship,
    PartnerOrganization,
)


SUPPORTED_NODE_TYPE = "organization"


def resolve_node(
    db: Session,
    node_type: str,
    node_id: int,
):
    if node_type != SUPPORTED_NODE_TYPE:
        raise ValueError(
            f"Unsupported FCIS node type: {node_type!r}"
        )

    organization = db.query(
        PartnerOrganization
    ).filter(
        PartnerOrganization.id == node_id
    ).first()

    if not organization:
        return {
            "type": node_type,
            "id": node_id,
            "resolved": False,
            "name": None,
        }

    return {
        "type": node_type,
        "id": node_id,
        "resolved": True,
        "name": organization.organization_name,
        "organization_type": organization.organization_type,
        "project": organization.project,
        "status": organization.status,
    }


def get_relationship(
    db: Session,
    relationship_id: int,
):
    relationship = db.query(
        CanonicalRelationship
    ).filter(
        CanonicalRelationship.id == relationship_id
    ).first()

    if not relationship:
        return None

    return _serialize_relationship(
        db,
        relationship,
    )


def get_relationships_for_node(
    db: Session,
    node_type: str,
    node_id: int,
    *,
    status: str | None = None,
    relationship_type: str | None = None,
):
    query = db.query(
        CanonicalRelationship
    ).filter(
        (
            (
                CanonicalRelationship.source_type == node_type
            )
            &
            (
                CanonicalRelationship.source_id == node_id
            )
        )
        |
        (
            (
                CanonicalRelationship.target_type == node_type
            )
            &
            (
                CanonicalRelationship.target_id == node_id
            )
        )
    )

    if status is not None:
        query = query.filter(
            CanonicalRelationship.relationship_status
            == status
        )

    if relationship_type is not None:
        query = query.filter(
            CanonicalRelationship.relationship_type
            == relationship_type
        )

    relationships = query.order_by(
        CanonicalRelationship.id.asc()
    ).all()

    return [
        _serialize_relationship(
            db,
            relationship,
        )
        for relationship in relationships
    ]


def get_graph_relationships(
    db: Session,
    *,
    status: str | None = None,
):
    query = db.query(
        CanonicalRelationship
    )

    if status is not None:
        query = query.filter(
            CanonicalRelationship.relationship_status
            == status
        )

    relationships = query.order_by(
        CanonicalRelationship.id.asc()
    ).all()

    return [
        _serialize_relationship(
            db,
            relationship,
        )
        for relationship in relationships
    ]


def get_node_neighborhood(
    db: Session,
    node_type: str,
    node_id: int,
):
    node = resolve_node(
        db,
        node_type,
        node_id,
    )

    relationships = get_relationships_for_node(
        db,
        node_type,
        node_id,
    )

    neighbors = {}

    for relationship in relationships:

        if (
            relationship["source"]["type"] == node_type
            and
            relationship["source"]["id"] == node_id
        ):
            other = relationship["target"]
            direction = "outgoing"

        else:
            other = relationship["source"]
            direction = "incoming"

        key = (
            other["type"],
            other["id"],
        )

        neighbors[key] = {
            **other,
            "direction": direction,
        }

    return {
        "node": node,
        "relationship_count": len(relationships),
        "neighbor_count": len(neighbors),
        "neighbors": list(neighbors.values()),
        "relationships": relationships,
    }


def _serialize_relationship(
    db: Session,
    relationship: CanonicalRelationship,
):
    source = resolve_node(
        db,
        relationship.source_type,
        relationship.source_id,
    )

    target = resolve_node(
        db,
        relationship.target_type,
        relationship.target_id,
    )

    return {
        "id": relationship.id,
        "source": source,
        "target": target,
        "relationship_type": relationship.relationship_type,
        "relationship_basis": relationship.relationship_basis,
        "relationship_status": relationship.relationship_status,
        "scope": relationship.scope,
        "evidence": {
            "source_type": relationship.evidence_source_type,
            "source_id": relationship.evidence_source_id,
            "reference": relationship.evidence_reference,
            "notes": relationship.evidence_notes,
        },
        "effective_at": relationship.effective_at,
        "expires_at": relationship.expires_at,
        "created_at": relationship.created_at,
    }
