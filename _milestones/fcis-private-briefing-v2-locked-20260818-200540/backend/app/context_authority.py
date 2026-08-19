from datetime import datetime

from sqlalchemy.orm import Session

from backend.app.models import (
    CanonicalContext,
    CanonicalizationProvenance,
    PartnerOrganization,
)


SUPPORTED_SUBJECT_TYPE = "organization"

SUPPORTED_CONTEXT_TYPES = {
    "need",
    "offer",
    "capability",
    "interest",
    "goal",
    "constraint",
    "resource",
    "preference",
    "availability",
    "requirement",
}

SUPPORTED_CONTEXT_STATUSES = {
    "pending",
    "active",
    "inactive",
    "expired",
    "revoked",
}


def _clean_required_string(
    value,
    field_name,
):
    value = str(value or "").strip()

    if not value:
        raise ValueError(
            f"{field_name} is required."
        )

    return value


def _clean_optional_string(value):
    if value is None:
        return None

    value = str(value).strip()

    if value == "":
        return None

    return value


def _validate_subject(
    db: Session,
    subject_type: str,
    subject_id: int,
):
    subject_type = _clean_required_string(
        subject_type,
        "subject_type",
    )

    if subject_type != SUPPORTED_SUBJECT_TYPE:
        raise ValueError(
            f"subject_type {subject_type!r} is not supported "
            "by Canonical Context Write Authority v1."
        )

    if (
        not isinstance(subject_id, int)
        or subject_id <= 0
    ):
        raise ValueError(
            "subject_id must be a positive integer."
        )

    organization = db.query(
        PartnerOrganization
    ).filter(
        PartnerOrganization.id == subject_id
    ).first()

    if not organization:
        raise ValueError(
            f"subject organization {subject_id} does not exist."
        )

    provenance = db.query(
        CanonicalizationProvenance
    ).filter(
        CanonicalizationProvenance.target_type
        == SUPPORTED_SUBJECT_TYPE,
        CanonicalizationProvenance.target_id
        == subject_id,
    ).first()

    if not provenance:
        raise ValueError(
            f"subject organization {subject_id} does not have "
            "established canonical provenance."
        )

    return organization


def create_canonical_context(
    db: Session,
    *,
    subject_type: str,
    subject_id: int,
    context_type: str,
    context_key: str,
    context_value: str | None = None,
    context_status: str = "pending",
    scope: str | None = None,
    evidence_source_type: str,
    evidence_source_id: int | None = None,
    evidence_reference: str | None = None,
    evidence_notes: str | None = None,
    effective_at: datetime | None = None,
    expires_at: datetime | None = None,
):
    """
    Create one recognized CanonicalContext assertion.

    v1 invariants:

    - organization subjects only
    - subject must exist
    - subject must have established canonical provenance
    - context_type uses controlled vocabulary
    - context_key is explicit
    - context_status uses controlled vocabulary
    - evidence_source_type is required
    - evidence_source_id must be positive when supplied
    - expiry cannot precede effective date
    - equivalent evidence-backed assertion is reused
    - caller owns commit / rollback

    Important:

    This authority records context truth supplied by evidence.

    It does NOT:
    - infer opportunities
    - create relationships
    - publish anything
    - authorize external action
    """

    subject_type = _clean_required_string(
        subject_type,
        "subject_type",
    )

    subject = _validate_subject(
        db=db,
        subject_type=subject_type,
        subject_id=subject_id,
    )

    context_type = _clean_required_string(
        context_type,
        "context_type",
    )

    if context_type not in SUPPORTED_CONTEXT_TYPES:
        raise ValueError(
            "context_type must be one of: "
            + ", ".join(
                sorted(SUPPORTED_CONTEXT_TYPES)
            )
        )

    context_key = _clean_required_string(
        context_key,
        "context_key",
    )

    context_value = _clean_optional_string(
        context_value
    )

    context_status = _clean_required_string(
        context_status,
        "context_status",
    )

    if context_status not in SUPPORTED_CONTEXT_STATUSES:
        raise ValueError(
            "context_status must be one of: "
            + ", ".join(
                sorted(SUPPORTED_CONTEXT_STATUSES)
            )
        )

    scope = _clean_optional_string(
        scope
    )

    evidence_source_type = _clean_required_string(
        evidence_source_type,
        "evidence_source_type",
    )

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

    evidence_reference = _clean_optional_string(
        evidence_reference
    )

    evidence_notes = _clean_optional_string(
        evidence_notes
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

    query = db.query(
        CanonicalContext
    ).filter(
        CanonicalContext.subject_type == subject_type,
        CanonicalContext.subject_id == subject.id,
        CanonicalContext.context_type == context_type,
        CanonicalContext.context_key == context_key,
        CanonicalContext.evidence_source_type
        == evidence_source_type,
    )

    if evidence_source_id is None:
        query = query.filter(
            CanonicalContext.evidence_source_id.is_(None)
        )
    else:
        query = query.filter(
            CanonicalContext.evidence_source_id
            == evidence_source_id
        )

    existing = query.first()

    if existing:
        return {
            "action": "reused",
            "context_id": existing.id,
            "subject_type": existing.subject_type,
            "subject_id": existing.subject_id,
            "context_type": existing.context_type,
            "context_key": existing.context_key,
            "context_value": existing.context_value,
            "context_status": existing.context_status,
            "scope": existing.scope,
        }

    context = CanonicalContext(
        subject_type=subject_type,
        subject_id=subject.id,
        context_type=context_type,
        context_key=context_key,
        context_value=context_value,
        context_status=context_status,
        scope=scope,
        evidence_source_type=evidence_source_type,
        evidence_source_id=evidence_source_id,
        evidence_reference=evidence_reference,
        evidence_notes=evidence_notes,
        effective_at=effective_at,
        expires_at=expires_at,
        created_at=datetime.utcnow(),
    )

    db.add(context)

    # Surface persistence / constraint errors while
    # transaction ownership remains with the caller.
    db.flush()

    return {
        "action": "created",
        "context_id": context.id,
        "subject_type": context.subject_type,
        "subject_id": context.subject_id,
        "context_type": context.context_type,
        "context_key": context.context_key,
        "context_value": context.context_value,
        "context_status": context.context_status,
        "scope": context.scope,
    }
