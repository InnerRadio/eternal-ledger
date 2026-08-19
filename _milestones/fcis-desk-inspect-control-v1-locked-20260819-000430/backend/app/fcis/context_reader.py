from sqlalchemy.orm import Session

from backend.app.models import (
    CanonicalContext,
    PartnerOrganization,
)


SUPPORTED_SUBJECT_TYPE = "organization"


def resolve_context_subject(
    db: Session,
    subject_type: str,
    subject_id: int,
):
    if subject_type != SUPPORTED_SUBJECT_TYPE:
        raise ValueError(
            f"Unsupported FCIS context subject type: {subject_type!r}"
        )

    organization = db.query(
        PartnerOrganization
    ).filter(
        PartnerOrganization.id == subject_id
    ).first()

    if not organization:
        return {
            "type": subject_type,
            "id": subject_id,
            "resolved": False,
            "name": None,
        }

    return {
        "type": subject_type,
        "id": subject_id,
        "resolved": True,
        "name": organization.organization_name,
        "organization_type": organization.organization_type,
        "project": organization.project,
        "status": organization.status,
    }


def get_context(
    db: Session,
    context_id: int,
):
    context = db.query(
        CanonicalContext
    ).filter(
        CanonicalContext.id == context_id
    ).first()

    if not context:
        return None

    return _serialize_context(
        db,
        context,
    )


def get_context_for_node(
    db: Session,
    subject_type: str,
    subject_id: int,
    *,
    context_type: str | None = None,
    status: str | None = None,
    scope: str | None = None,
):
    query = db.query(
        CanonicalContext
    ).filter(
        CanonicalContext.subject_type == subject_type,
        CanonicalContext.subject_id == subject_id,
    )

    if context_type is not None:
        query = query.filter(
            CanonicalContext.context_type
            == context_type
        )

    if status is not None:
        query = query.filter(
            CanonicalContext.context_status
            == status
        )

    if scope is not None:
        query = query.filter(
            CanonicalContext.scope == scope
        )

    rows = query.order_by(
        CanonicalContext.id.asc()
    ).all()

    return [
        _serialize_context(
            db,
            row,
        )
        for row in rows
    ]


def get_active_context_for_node(
    db: Session,
    subject_type: str,
    subject_id: int,
):
    return get_context_for_node(
        db,
        subject_type,
        subject_id,
        status="active",
    )


def get_needs(
    db: Session,
    subject_type: str,
    subject_id: int,
):
    return get_context_for_node(
        db,
        subject_type,
        subject_id,
        context_type="need",
        status="active",
    )


def get_offers(
    db: Session,
    subject_type: str,
    subject_id: int,
):
    return get_context_for_node(
        db,
        subject_type,
        subject_id,
        context_type="offer",
        status="active",
    )


def get_capabilities(
    db: Session,
    subject_type: str,
    subject_id: int,
):
    return get_context_for_node(
        db,
        subject_type,
        subject_id,
        context_type="capability",
        status="active",
    )


def get_active_context_graph(
    db: Session,
):
    rows = db.query(
        CanonicalContext
    ).filter(
        CanonicalContext.context_status == "active"
    ).order_by(
        CanonicalContext.id.asc()
    ).all()

    return [
        _serialize_context(
            db,
            row,
        )
        for row in rows
    ]


def get_context_index(
    db: Session,
):
    """
    Return active canonical context grouped by context_type
    and context_key.

    This is a factual index only.

    It does NOT:
    - infer compatibility
    - generate opportunity candidates
    - create relationships
    - write context
    """

    rows = get_active_context_graph(db)

    index = {}

    for row in rows:
        context_type = row["context_type"]
        context_key = row["context_key"]

        index.setdefault(
            context_type,
            {},
        ).setdefault(
            context_key,
            [],
        ).append(row)

    return index


def _serialize_context(
    db: Session,
    context: CanonicalContext,
):
    subject = resolve_context_subject(
        db,
        context.subject_type,
        context.subject_id,
    )

    return {
        "id": context.id,
        "subject": subject,
        "context_type": context.context_type,
        "context_key": context.context_key,
        "context_value": context.context_value,
        "context_status": context.context_status,
        "scope": context.scope,
        "evidence": {
            "source_type": context.evidence_source_type,
            "source_id": context.evidence_source_id,
            "reference": context.evidence_reference,
            "notes": context.evidence_notes,
        },
        "effective_at": context.effective_at,
        "expires_at": context.expires_at,
        "created_at": context.created_at,
        "updated_at": context.updated_at,
    }
