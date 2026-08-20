from datetime import datetime

from sqlalchemy.orm import Session

from backend.app.models import (
    CanonicalRelationship,
    CanonicalizationProvenance,
    PartnerOrganization,
    User,
)


SUPPORTED_ENDPOINT_TYPES = {
    "organization",
    "user",
}

SUPPORTED_RELATIONSHIP_STATUSES = {
    "pending",
    "active",
    "inactive",
    "expired",
    "revoked",
}


def _clean_required_string(value, field_name):
    value = str(value or "").strip()

    if not value:
        raise ValueError(
            f"{field_name} is required."
        )

    return value


def _validate_endpoint(
    db: Session,
    endpoint_role: str,
    endpoint_type: str,
    endpoint_id: int,
):
    endpoint_type = _clean_required_string(
        endpoint_type,
        f"{endpoint_role}_type",
    )

    if endpoint_type not in SUPPORTED_ENDPOINT_TYPES:
        raise ValueError(
            f"{endpoint_role}_type {endpoint_type!r} is not supported "
            "by Canonical Relationship Authority v2."
        )

    if not isinstance(endpoint_id, int) or endpoint_id <= 0:
        raise ValueError(
            f"{endpoint_role}_id must be a positive integer."
        )

    if endpoint_type == "user":
        user = db.query(
            User
        ).filter(
            User.id == endpoint_id
        ).first()

        if not user:
            raise ValueError(
                f"{endpoint_role} user {endpoint_id} does not exist."
            )

        return user

    organization = db.query(
        PartnerOrganization
    ).filter(
        PartnerOrganization.id == endpoint_id
    ).first()

    if not organization:
        raise ValueError(
            f"{endpoint_role} organization {endpoint_id} does not exist."
        )

    provenance = db.query(
        CanonicalizationProvenance
    ).filter(
        CanonicalizationProvenance.target_type == "organization",
        CanonicalizationProvenance.target_id == endpoint_id,
    ).first()

    if not provenance:
        raise ValueError(
            f"{endpoint_role} organization {endpoint_id} does not have "
            "established canonical provenance."
        )

    return organization


def create_canonical_relationship(
    db: Session,
    *,
    source_type: str,
    source_id: int,
    target_type: str,
    target_id: int,
    relationship_type: str,
    relationship_basis: str,
    relationship_status: str,
    scope: str | None,
    evidence_source_type: str,
    evidence_source_id: int | None = None,
    evidence_reference: str | None = None,
    evidence_notes: str | None = None,
    effective_at: datetime | None = None,
    expires_at: datetime | None = None,
):
    """
    Create one recognized CanonicalRelationship.

    v2 invariants:

    - supported endpoints are user and organization
    - every endpoint must exist
    - organization endpoints must have established canonical provenance
    - user endpoint existence does not imply organization access
    - canonical relationship creation does not create OrganizationMember
    - canonical relationship creation does not grant permission
    - no self-edge for identical endpoint type and id
    - relationship_type is explicit
    - relationship_basis is explicit
    - relationship_status is controlled
    - evidence_source_type is required
    - expiry cannot precede effective date
    - equivalent edge is reused deterministically
    - caller owns commit / rollback
    """

    source_type = _clean_required_string(
        source_type,
        "source_type",
    )

    target_type = _clean_required_string(
        target_type,
        "target_type",
    )

    source = _validate_endpoint(
        db=db,
        endpoint_role="source",
        endpoint_type=source_type,
        endpoint_id=source_id,
    )

    target = _validate_endpoint(
        db=db,
        endpoint_role="target",
        endpoint_type=target_type,
        endpoint_id=target_id,
    )

    if (
        source_type == target_type
        and
        source_id == target_id
    ):
        raise ValueError(
            "Canonical Relationship Authority v2 does not permit self-edges."
        )

    relationship_type = _clean_required_string(
        relationship_type,
        "relationship_type",
    )

    relationship_basis = _clean_required_string(
        relationship_basis,
        "relationship_basis",
    )

    relationship_status = _clean_required_string(
        relationship_status,
        "relationship_status",
    )

    if relationship_status not in SUPPORTED_RELATIONSHIP_STATUSES:
        raise ValueError(
            "relationship_status must be one of: "
            + ", ".join(
                sorted(SUPPORTED_RELATIONSHIP_STATUSES)
            )
        )

    evidence_source_type = _clean_required_string(
        evidence_source_type,
        "evidence_source_type",
    )

    scope = (
        str(scope).strip()
        if scope is not None
        else None
    )

    if scope == "":
        scope = None

    evidence_reference = (
        str(evidence_reference).strip()
        if evidence_reference is not None
        else None
    )

    if evidence_reference == "":
        evidence_reference = None

    evidence_notes = (
        str(evidence_notes).strip()
        if evidence_notes is not None
        else None
    )

    if evidence_notes == "":
        evidence_notes = None

    if (
        evidence_source_id is not None
        and
        (
            not isinstance(evidence_source_id, int)
            or evidence_source_id <= 0
        )
    ):
        raise ValueError(
            "evidence_source_id must be a positive integer when supplied."
        )

    if (
        effective_at is not None
        and
        expires_at is not None
        and
        expires_at < effective_at
    ):
        raise ValueError(
            "expires_at cannot precede effective_at."
        )

    existing = db.query(
        CanonicalRelationship
    ).filter(
        CanonicalRelationship.source_type == source_type,
        CanonicalRelationship.source_id == source_id,
        CanonicalRelationship.target_type == target_type,
        CanonicalRelationship.target_id == target_id,
        CanonicalRelationship.relationship_type == relationship_type,
        CanonicalRelationship.relationship_basis == relationship_basis,
    ).first()

    if existing:
        return {
            "action": "reused",
            "relationship_id": existing.id,
            "source_type": existing.source_type,
            "source_id": existing.source_id,
            "target_type": existing.target_type,
            "target_id": existing.target_id,
            "relationship_type": existing.relationship_type,
            "relationship_basis": existing.relationship_basis,
            "relationship_status": existing.relationship_status,
        }

    relationship = CanonicalRelationship(
        source_type=source_type,
        source_id=source.id,
        target_type=target_type,
        target_id=target.id,
        relationship_type=relationship_type,
        relationship_basis=relationship_basis,
        relationship_status=relationship_status,
        scope=scope,
        evidence_source_type=evidence_source_type,
        evidence_source_id=evidence_source_id,
        evidence_reference=evidence_reference,
        evidence_notes=evidence_notes,
        effective_at=effective_at,
        expires_at=expires_at,
        created_at=datetime.utcnow(),
    )

    db.add(relationship)

    # Force constraint / persistence errors to surface while
    # transaction ownership remains with the caller.
    db.flush()

    return {
        "action": "created",
        "relationship_id": relationship.id,
        "source_type": relationship.source_type,
        "source_id": relationship.source_id,
        "target_type": relationship.target_type,
        "target_id": relationship.target_id,
        "relationship_type": relationship.relationship_type,
        "relationship_basis": relationship.relationship_basis,
        "relationship_status": relationship.relationship_status,
    }
