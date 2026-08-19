import json
import re
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from backend.app.models import (
    CanonicalizationProvenance,
    OnboardingRecord,
    PartnerOrganization,
)


SOURCE_TYPE = "onboarding_record"
TARGET_TYPE = "organization"

DECISION_REUSE = "REUSE"
DECISION_CREATE = "CREATE"
DECISION_REVIEW = "REVIEW"
DECISION_REJECT = "REJECT"


def _clean_text(value):
    return str(value or "").strip()


def normalize_name(value):
    """
    Produce a comparison signal only.

    This value is NOT canonical identity authority.
    """
    value = _clean_text(value).lower()

    if not value:
        return None

    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()

    return value or None


def normalize_location(value):
    """
    Produce a lightweight comparison signal only.

    Multi-location architecture remains outside resolver v1.
    """
    value = _clean_text(value).lower()

    if not value:
        return None

    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()

    return value or None


def normalize_domain(value):
    """
    Normalize a submitted website into a comparison domain.

    Exact domain equality is strong evidence.
    It is NOT universal canonical identity authority.
    """
    value = _clean_text(value).lower()

    if not value:
        return None

    candidate = value

    if "://" not in candidate:
        candidate = "https://" + candidate

    try:
        parsed = urlparse(candidate)
        host = (parsed.hostname or "").strip().lower()
    except Exception:
        host = ""

    if not host:
        return None

    if host.startswith("www."):
        host = host[4:]

    return host or None


def _load_payload(source):
    try:
        payload = json.loads(source.payload_json or "{}")
    except Exception as exc:
        raise ValueError(
            f"OnboardingRecord {source.id} has malformed payload_json."
        ) from exc

    if not isinstance(payload, dict):
        raise ValueError(
            f"OnboardingRecord {source.id} payload_json is not an object."
        )

    return payload


def _starter_facts(payload):
    return {
        "acting_capacity": _clean_text(
            payload.get("acting_capacity")
        ) or None,
        "organization_name": _clean_text(
            payload.get("organization_name")
        ) or None,
        "organization_type": _clean_text(
            payload.get("organization_type")
        ) or None,
        "website_url": _clean_text(
            payload.get("website_url")
        ) or None,
        "location": _clean_text(
            payload.get("location")
        ) or None,
    }


def _comparison_signals(facts):
    return {
        "normalized_name": normalize_name(
            facts.get("organization_name")
        ),
        "normalized_domain": normalize_domain(
            facts.get("website_url")
        ),
        "normalized_location": normalize_location(
            facts.get("location")
        ),
    }


def _organization_signals(organization):
    return {
        "normalized_name": normalize_name(
            organization.organization_name
        ),
        "normalized_domain": normalize_domain(
            organization.website_url
        ),
        "normalized_location": normalize_location(
            organization.location
        ),
    }


def _candidate_evidence(source_signals, organization):
    target_signals = _organization_signals(
        organization
    )

    evidence = []

    if (
        source_signals.get("normalized_domain")
        and
        source_signals.get("normalized_domain")
        == target_signals.get("normalized_domain")
    ):
        evidence.append({
            "signal": "exact_normalized_domain",
            "strength": "strong",
            "source_value": source_signals.get(
                "normalized_domain"
            ),
            "target_value": target_signals.get(
                "normalized_domain"
            ),
        })

    if (
        source_signals.get("normalized_name")
        and
        source_signals.get("normalized_name")
        == target_signals.get("normalized_name")
    ):
        evidence.append({
            "signal": "exact_normalized_name",
            "strength": "supporting",
            "source_value": source_signals.get(
                "normalized_name"
            ),
            "target_value": target_signals.get(
                "normalized_name"
            ),
        })

    if (
        source_signals.get("normalized_location")
        and
        source_signals.get("normalized_location")
        == target_signals.get("normalized_location")
    ):
        evidence.append({
            "signal": "exact_normalized_location",
            "strength": "supporting",
            "source_value": source_signals.get(
                "normalized_location"
            ),
            "target_value": target_signals.get(
                "normalized_location"
            ),
        })

    return evidence


def resolve_organization(
    db: Session,
    *,
    onboarding_id: int,
    established_target_id: int | None = None,
):
    """
    Decide how one onboarding source should proceed toward a
    canonical Organization.

    Resolver v1 is deliberately READ-ONLY.

    Possible decisions:

    REUSE
      Existing provenance already establishes the target, or an
      explicitly established target_id is supplied by a higher authority.

    CREATE
      Sufficient new-Organization starter facts exist and no candidate
      collision is detected.

    REVIEW
      Existing Organization evidence is suggestive, but canonical
      target identity is not authoritative.

    REJECT
      Intake is invalid or insufficient for Organization resolution.

    Important:

    - no PartnerOrganization is created here
    - no provenance is written here
    - no User/Organization relationship is created here
    - no permission is granted here
    - no eligibility or commerce decision occurs here
    - no publication or Directory mutation occurs here
    """

    if (
        not isinstance(onboarding_id, int)
        or onboarding_id <= 0
    ):
        return {
            "decision": DECISION_REJECT,
            "reason": "invalid_onboarding_id",
        }

    source = db.query(
        OnboardingRecord
    ).filter(
        OnboardingRecord.id == onboarding_id
    ).first()

    if not source:
        return {
            "decision": DECISION_REJECT,
            "reason": "onboarding_record_not_found",
            "source_id": onboarding_id,
        }

    if source.verification_status != "verified":
        return {
            "decision": DECISION_REJECT,
            "reason": "onboarding_not_verified",
            "source_id": source.id,
        }

    provenance = db.query(
        CanonicalizationProvenance
    ).filter(
        CanonicalizationProvenance.source_type
        == SOURCE_TYPE,
        CanonicalizationProvenance.source_id
        == source.id,
        CanonicalizationProvenance.target_type
        == TARGET_TYPE,
    ).first()

    if provenance:
        target = db.query(
            PartnerOrganization
        ).filter(
            PartnerOrganization.id
            == provenance.target_id
        ).first()

        if not target:
            return {
                "decision": DECISION_REJECT,
                "reason": "provenance_target_missing",
                "source_id": source.id,
                "target_id": provenance.target_id,
                "provenance_id": provenance.id,
            }

        return {
            "decision": DECISION_REUSE,
            "reason": "existing_source_provenance",
            "source_type": SOURCE_TYPE,
            "source_id": source.id,
            "target_type": TARGET_TYPE,
            "target_id": target.id,
            "provenance_id": provenance.id,
            "authoritative": True,
        }

    payload = _load_payload(
        source
    )

    facts = _starter_facts(
        payload
    )

    if facts.get("acting_capacity") != "organization":
        return {
            "decision": DECISION_REJECT,
            "reason": "not_organization_acting_capacity",
            "source_id": source.id,
            "acting_capacity": facts.get(
                "acting_capacity"
            ),
        }

    if not facts.get("organization_name"):
        return {
            "decision": DECISION_REJECT,
            "reason": "organization_name_missing",
            "source_id": source.id,
            "facts": facts,
        }

    source_signals = _comparison_signals(
        facts
    )

    if established_target_id is not None:
        if (
            not isinstance(established_target_id, int)
            or established_target_id <= 0
        ):
            return {
                "decision": DECISION_REJECT,
                "reason": "invalid_established_target_id",
                "source_id": source.id,
            }

        target = db.query(
            PartnerOrganization
        ).filter(
            PartnerOrganization.id
            == established_target_id
        ).first()

        if not target:
            return {
                "decision": DECISION_REJECT,
                "reason": "established_target_not_found",
                "source_id": source.id,
                "target_id": established_target_id,
            }

        return {
            "decision": DECISION_REUSE,
            "reason": "explicitly_established_target",
            "source_type": SOURCE_TYPE,
            "source_id": source.id,
            "target_type": TARGET_TYPE,
            "target_id": target.id,
            "authoritative": True,
            "facts": facts,
            "comparison_signals": source_signals,
        }

    candidates = []

    organizations = db.query(
        PartnerOrganization
    ).filter(
        PartnerOrganization.status == "active"
    ).all()

    for organization in organizations:
        evidence = _candidate_evidence(
            source_signals,
            organization,
        )

        if not evidence:
            continue

        candidates.append({
            "organization_id": organization.id,
            "organization_name": organization.organization_name,
            "organization_type": organization.organization_type,
            "website_url": organization.website_url,
            "location": organization.location,
            "evidence": evidence,
            "has_strong_signal": any(
                item.get("strength") == "strong"
                for item in evidence
            ),
        })

    if candidates:
        candidates.sort(
            key=lambda item: (
                not item.get("has_strong_signal"),
                item.get("organization_id"),
            )
        )

        return {
            "decision": DECISION_REVIEW,
            "reason": "possible_existing_organization",
            "source_type": SOURCE_TYPE,
            "source_id": source.id,
            "facts": facts,
            "comparison_signals": source_signals,
            "candidate_count": len(candidates),
            "candidates": candidates,
            "authoritative": False,
        }

    return {
        "decision": DECISION_CREATE,
        "reason": "sufficient_new_organization_evidence_no_collision",
        "source_type": SOURCE_TYPE,
        "source_id": source.id,
        "facts": facts,
        "comparison_signals": source_signals,
        "candidate_count": 0,
        "candidates": [],
        "authoritative": False,
    }
