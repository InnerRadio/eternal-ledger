"""
PurPaws Canonical Organization Resolution Review Authority v1

Purpose:
    Validate and append durable historical organization-resolution
    review judgments.

Locked decisions:
    ESTABLISHED
    NOT_SAME
    DEFERRED

Authority boundary:
    - review history only
    - append-only
    - no canonicalization provenance mutation
    - no relationship mutation
    - no permission mutation
    - no publication mutation
    - no reconciliation
"""

from datetime import datetime

from sqlalchemy.orm import Session

from .models import (
    CanonicalOrganizationResolutionReview,
    OnboardingRecord,
    PartnerOrganization,
)


DECISION_ESTABLISHED = "ESTABLISHED"
DECISION_NOT_SAME = "NOT_SAME"
DECISION_DEFERRED = "DEFERRED"

ALLOWED_DECISIONS = {
    DECISION_ESTABLISHED,
    DECISION_NOT_SAME,
    DECISION_DEFERRED,
}

SOURCE_TYPE_ONBOARDING = "onboarding_record"
TARGET_TYPE_ORGANIZATION = "partner_organization"


class OrganizationResolutionReviewError(ValueError):
    pass


def _clean_required_string(value, field_name):
    if value is None:
        raise OrganizationResolutionReviewError(
            f"{field_name} is required"
        )

    cleaned = str(value).strip()

    if not cleaned:
        raise OrganizationResolutionReviewError(
            f"{field_name} is required"
        )

    return cleaned


def _positive_int(value, field_name):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise OrganizationResolutionReviewError(
            f"{field_name} must be a positive integer"
        )

    if parsed <= 0:
        raise OrganizationResolutionReviewError(
            f"{field_name} must be a positive integer"
        )

    return parsed


def validate_review_request(
    db: Session,
    *,
    source_type,
    source_id,
    target_type,
    target_id,
    decision,
    basis,
    evidence_summary,
    reviewer_user_id,
):
    source_type = _clean_required_string(
        source_type,
        "source_type",
    )

    target_type = _clean_required_string(
        target_type,
        "target_type",
    )

    decision = _clean_required_string(
        decision,
        "decision",
    ).upper()

    basis = _clean_required_string(
        basis,
        "basis",
    )

    source_id = _positive_int(
        source_id,
        "source_id",
    )

    target_id = _positive_int(
        target_id,
        "target_id",
    )

    reviewer_user_id = _positive_int(
        reviewer_user_id,
        "reviewer_user_id",
    )

    if decision not in ALLOWED_DECISIONS:
        raise OrganizationResolutionReviewError(
            "decision must be ESTABLISHED, NOT_SAME, or DEFERRED"
        )

    if source_type != SOURCE_TYPE_ONBOARDING:
        raise OrganizationResolutionReviewError(
            "v1 source_type must be onboarding_record"
        )

    if target_type != TARGET_TYPE_ORGANIZATION:
        raise OrganizationResolutionReviewError(
            "v1 target_type must be partner_organization"
        )

    source = (
        db.query(OnboardingRecord)
        .filter(OnboardingRecord.id == source_id)
        .first()
    )

    if source is None:
        raise OrganizationResolutionReviewError(
            f"onboarding_record {source_id} does not exist"
        )

    target = (
        db.query(PartnerOrganization)
        .filter(PartnerOrganization.id == target_id)
        .first()
    )

    if target is None:
        raise OrganizationResolutionReviewError(
            f"partner_organization {target_id} does not exist"
        )

    if evidence_summary is None:
        evidence_summary = None
    else:
        evidence_summary = str(
            evidence_summary
        ).strip() or None

    return {
        "source_type": source_type,
        "source_id": source_id,
        "target_type": target_type,
        "target_id": target_id,
        "decision": decision,
        "basis": basis,
        "evidence_summary": evidence_summary,
        "reviewer_user_id": reviewer_user_id,
    }


def append_review(
    db: Session,
    *,
    source_type,
    source_id,
    target_type,
    target_id,
    decision,
    basis,
    evidence_summary=None,
    reviewer_user_id,
    reviewed_at=None,
    commit=False,
):
    """
    Append one historical review judgment.

    commit=False is the safe default.

    This function does not:
      - create canonicalization provenance
      - create relationships
      - grant permissions
      - publish anything
      - reconcile contradictory canonical state
    """

    values = validate_review_request(
        db,
        source_type=source_type,
        source_id=source_id,
        target_type=target_type,
        target_id=target_id,
        decision=decision,
        basis=basis,
        evidence_summary=evidence_summary,
        reviewer_user_id=reviewer_user_id,
    )

    if reviewed_at is None:
        reviewed_at = datetime.utcnow()

    review = CanonicalOrganizationResolutionReview(
        **values,
        reviewed_at=reviewed_at,
        created_at=datetime.utcnow(),
        updated_at=None,
    )

    db.add(review)
    db.flush()

    if commit:
        db.commit()
        db.refresh(review)

    return review


def get_current_effective_review(
    db: Session,
    *,
    source_type,
    source_id,
    target_type=None,
    target_id=None,
):
    source_type = _clean_required_string(
        source_type,
        "source_type",
    )

    source_id = _positive_int(
        source_id,
        "source_id",
    )

    query = (
        db.query(
            CanonicalOrganizationResolutionReview
        )
        .filter(
            CanonicalOrganizationResolutionReview.source_type
            == source_type,
            CanonicalOrganizationResolutionReview.source_id
            == source_id,
        )
    )

    if target_type is not None:
        target_type = _clean_required_string(
            target_type,
            "target_type",
        )

        query = query.filter(
            CanonicalOrganizationResolutionReview.target_type
            == target_type
        )

    if target_id is not None:
        target_id = _positive_int(
            target_id,
            "target_id",
        )

        query = query.filter(
            CanonicalOrganizationResolutionReview.target_id
            == target_id
        )

    return (
        query
        .order_by(
            CanonicalOrganizationResolutionReview.reviewed_at.desc(),
            CanonicalOrganizationResolutionReview.id.desc(),
        )
        .first()
    )
