import json
from datetime import datetime

from sqlalchemy.orm import Session

from backend.app.models import (
    OnboardingRecord,
    PartnerOrganization,
    CanonicalizationProvenance,
)


SOURCE_TYPE = "onboarding_record"
TARGET_TYPE_ORGANIZATION = "organization"


def canonicalize_directory_organization(
    db: Session,
    onboarding_id: int,
):
    """
    Canonicalize one verified, published Directory onboarding record
    into one PartnerOrganization target.

    v1 invariants:

    - provenance is queried before target creation
    - same source + target type reuses the same target
    - no name / website / location matching
    - no entity resolution
    - no OrganizationMember creation
    - no inferred user / organization relationship
    - no eligibility determination
    - no commerce determination
    - no publication or Directory mutation
    - caller owns commit / rollback
    """

    source = db.query(OnboardingRecord).filter(
        OnboardingRecord.id == onboarding_id
    ).first()

    if not source:
        raise ValueError(
            f"OnboardingRecord {onboarding_id} not found."
        )

    if source.path != "directory":
        raise ValueError(
            f"OnboardingRecord {onboarding_id} is not a directory source."
        )

    if source.verification_status != "verified":
        raise ValueError(
            f"OnboardingRecord {onboarding_id} is not verified."
        )

    if source.status != "published":
        raise ValueError(
            f"OnboardingRecord {onboarding_id} is not published."
        )

    provenance = db.query(CanonicalizationProvenance).filter(
        CanonicalizationProvenance.source_type == SOURCE_TYPE,
        CanonicalizationProvenance.source_id == source.id,
        CanonicalizationProvenance.target_type == TARGET_TYPE_ORGANIZATION,
    ).first()

    if provenance:

        target = db.query(PartnerOrganization).filter(
            PartnerOrganization.id == provenance.target_id
        ).first()

        if not target:
            raise RuntimeError(
                "Canonicalization provenance exists but target "
                f"PartnerOrganization {provenance.target_id} is missing."
            )

        return {
            "action": "reused",
            "source_type": SOURCE_TYPE,
            "source_id": source.id,
            "target_type": TARGET_TYPE_ORGANIZATION,
            "target_id": target.id,
            "provenance_id": provenance.id,
        }

    try:
        payload = json.loads(source.payload_json or "{}")
    except Exception as exc:
        raise ValueError(
            f"OnboardingRecord {onboarding_id} has malformed payload_json."
        ) from exc

    if not isinstance(payload, dict):
        raise ValueError(
            f"OnboardingRecord {onboarding_id} payload_json is not an object."
        )

    organization_name = str(
        payload.get("listing_name") or ""
    ).strip()

    if not organization_name:
        raise ValueError(
            f"OnboardingRecord {onboarding_id} has no listing_name."
        )

    organization_type = str(
        payload.get("category") or "other"
    ).strip() or "other"

    contact_email = str(
        payload.get("contact_email") or ""
    ).strip() or None

    website_url = str(
        payload.get("website") or ""
    ).strip() or None

    location = str(
        payload.get("location") or ""
    ).strip() or None

    target = PartnerOrganization(
        organization_name=organization_name,
        organization_type=organization_type,
        project="PurPaws",
        contact_email=contact_email,
        website_url=website_url,
        location=location,
    )

    db.add(target)

    # Obtain target.id without committing the transaction.
    db.flush()

    provenance = CanonicalizationProvenance(
        source_type=SOURCE_TYPE,
        source_id=source.id,
        target_type=TARGET_TYPE_ORGANIZATION,
        target_id=target.id,
        created_at=datetime.utcnow(),
    )

    db.add(provenance)

    # Force constraint / persistence errors to surface while the
    # organization and provenance still belong to one transaction.
    db.flush()

    return {
        "action": "created",
        "source_type": SOURCE_TYPE,
        "source_id": source.id,
        "target_type": TARGET_TYPE_ORGANIZATION,
        "target_id": target.id,
        "provenance_id": provenance.id,
    }
