from dataclasses import dataclass
from datetime import datetime
import hashlib
import secrets

from sqlalchemy.orm import Session

from backend.app.models import AttributionContext


REFERENCE_PREFIX = "ppj1_"
REFERENCE_RANDOM_BYTES = 32

# secrets.token_urlsafe(32) emits 43 URL-safe characters
# without padding. With the five-character ppj1_ prefix,
# the canonical v1 generated reference length is 48.
MAX_REFERENCE_LENGTH = 48

URLSAFE_CHARACTERS = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "0123456789"
    "-_"
)

ACTIVE_CONTEXT_STATUSES = frozenset({
    "inbound",
})


MALFORMED_REFERENCE = "MALFORMED_REFERENCE"
UNSUPPORTED_VERSION = "UNSUPPORTED_VERSION"
UNKNOWN_REFERENCE = "UNKNOWN_REFERENCE"
ACTIVE = "ACTIVE"
EXPIRED = "EXPIRED"
INVALID_CONTEXT = "INVALID_CONTEXT"


@dataclass(frozen=True)
class JourneyReferenceMaterial:
    raw_reference: str
    reference_hash: str


@dataclass(frozen=True)
class JourneyReferenceDecision:
    classification: str
    allowed: bool
    context: AttributionContext | None = None
    reference_hash: str | None = None
    reason: str | None = None


def hash_journey_reference(
    raw_reference: str,
) -> str:
    """
    Derive the canonical SHA-256 lowercase hexadecimal digest.

    This helper performs hashing only.

    It does not establish that the supplied value is a valid
    PurPaws journey reference.
    """

    if not isinstance(
        raw_reference,
        str,
    ):
        raise TypeError(
            "raw_reference must be a string."
        )

    return hashlib.sha256(
        raw_reference.encode("utf-8")
    ).hexdigest()


def generate_journey_reference(
) -> JourneyReferenceMaterial:
    """
    Generate opaque v1 journey continuity material.

    This function is pure with respect to persistence.

    It does not:
    - query the database
    - create AttributionContext
    - set cookies
    - bind participants
    - enroll campaigns
    - create conversions
    - determine rewards
    """

    random_part = secrets.token_urlsafe(
        REFERENCE_RANDOM_BYTES
    )

    raw_reference = (
        REFERENCE_PREFIX
        + random_part
    )

    if len(raw_reference) > MAX_REFERENCE_LENGTH:
        raise RuntimeError(
            "Generated journey reference exceeds the locked v1 maximum."
        )

    return JourneyReferenceMaterial(
        raw_reference=raw_reference,
        reference_hash=hash_journey_reference(
            raw_reference
        ),
    )


def validate_journey_reference(
    raw_reference,
) -> str | None:
    """
    Perform structural validation only.

    Returns:
        None
            structurally valid v1 reference

        MALFORMED_REFERENCE
            malformed or oversized input

        UNSUPPORTED_VERSION
            token-like reference using a non-v1 version
    """

    if not isinstance(
        raw_reference,
        str,
    ):
        return MALFORMED_REFERENCE

    if not raw_reference:
        return MALFORMED_REFERENCE

    if len(raw_reference) > MAX_REFERENCE_LENGTH:
        return MALFORMED_REFERENCE

    if raw_reference.startswith(
        REFERENCE_PREFIX
    ):
        opaque_part = raw_reference[
            len(REFERENCE_PREFIX):
        ]

        if not opaque_part:
            return MALFORMED_REFERENCE

        if any(
            character not in URLSAFE_CHARACTERS
            for character in opaque_part
        ):
            return MALFORMED_REFERENCE

        return None

    lowered = raw_reference.lower()

    if (
        lowered.startswith("ppj")
        and "_" in raw_reference
    ):
        return UNSUPPORTED_VERSION

    return MALFORMED_REFERENCE


def resolve_journey_reference(
    db: Session,
    raw_reference,
    *,
    now: datetime | None = None,
) -> JourneyReferenceDecision:
    """
    Resolve presented journey continuity against canonical persistence.

    This resolver is read-only.

    It does not:
    - create or update AttributionContext
    - rotate journey references
    - set cookies
    - bind participants
    - modify provenance
    - create conversions
    - determine rewards
    - create commissions
    """

    validation = validate_journey_reference(
        raw_reference
    )

    if validation is not None:
        return JourneyReferenceDecision(
            classification=validation,
            allowed=False,
            reason=(
                "Presented journey reference is not eligible "
                "for canonical v1 resolution."
            ),
        )

    reference_hash = hash_journey_reference(
        raw_reference
    )

    # limit(2).all() preserves the explicit zero-or-one
    # cardinality contract instead of silently masking an
    # impossible duplicate with first().
    matches = (
        db.query(
            AttributionContext
        )
        .filter(
            AttributionContext.journey_reference_hash
            == reference_hash
        )
        .limit(2)
        .all()
    )

    if len(matches) > 1:
        raise RuntimeError(
            "Journey-reference integrity failure: "
            "multiple AttributionContext rows share one digest."
        )

    if not matches:
        return JourneyReferenceDecision(
            classification=UNKNOWN_REFERENCE,
            allowed=False,
            reference_hash=reference_hash,
            reason="No canonical Attribution Context resolved.",
        )

    context = matches[0]

    authority_now = (
        now
        if now is not None
        else datetime.utcnow()
    )

    if (
        context.expires_at is not None
        and authority_now > context.expires_at
    ):
        return JourneyReferenceDecision(
            classification=EXPIRED,
            allowed=False,
            context=context,
            reference_hash=reference_hash,
            reason="Canonical Attribution Context is expired.",
        )

    if context.status not in ACTIVE_CONTEXT_STATUSES:
        return JourneyReferenceDecision(
            classification=INVALID_CONTEXT,
            allowed=False,
            context=context,
            reference_hash=reference_hash,
            reason=(
                "Canonical Attribution Context status does not "
                "permit v1 journey continuity."
            ),
        )

    return JourneyReferenceDecision(
        classification=ACTIVE,
        allowed=True,
        context=context,
        reference_hash=reference_hash,
        reason="Canonical journey continuity resolved.",
    )
