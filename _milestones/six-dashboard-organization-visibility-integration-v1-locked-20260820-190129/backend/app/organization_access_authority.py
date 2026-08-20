from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.app.models import (
    OrganizationMember,
    PartnerOrganization,
    User,
)


ROLE_ORDER = {
    "viewer": 10,
    "editor": 20,
    "manager": 30,
    "steward": 40,
    "owner": 50,
}


CAPABILITY_MINIMUM_ROLE = {
    "view_organization": "viewer",
    "edit_organization": "editor",
    "manage_campaigns": "manager",
    "administer_members": "steward",
}


SUPPORTED_CAPABILITIES = set(
    CAPABILITY_MINIMUM_ROLE.keys()
)


ADMIN_ACCOUNT_ROLES = {
    "admin",
    "super_admin",
}


@dataclass(frozen=True)
class OrganizationAccessDecision:
    allowed: bool
    capability: str
    reason: str
    user_id: int
    organization_id: int
    account_role: str | None
    membership_id: int | None
    membership_role: str | None
    membership_status: str | None


def _clean_role(value):
    return str(value or "").strip().lower()


def _validate_capability(capability: str):
    capability = str(capability or "").strip()

    if capability not in SUPPORTED_CAPABILITIES:
        raise ValueError(
            "Unsupported organization capability: "
            f"{capability!r}"
        )

    return capability


def _role_allows(
    role: str,
    capability: str,
):
    role = _clean_role(role)

    if role not in ROLE_ORDER:
        return False

    required_role = CAPABILITY_MINIMUM_ROLE[
        capability
    ]

    return (
        ROLE_ORDER[role]
        >=
        ROLE_ORDER[required_role]
    )


def get_active_organization_membership(
    db: Session,
    *,
    user_id: int,
    organization_id: int,
):
    return db.query(
        OrganizationMember
    ).filter(
        OrganizationMember.user_id == user_id,
        OrganizationMember.organization_id == organization_id,
        OrganizationMember.status == "active",
    ).first()


def evaluate_organization_access(
    db: Session,
    *,
    user_id: int,
    organization_id: int,
    capability: str,
):
    """
    Organization Access Enforcement Authority v1.

    Principles:

    - account admin / super_admin bypass remains explicit
    - non-admin users require active OrganizationMember
    - active membership alone is insufficient
    - OrganizationMember.role must authorize requested capability
    - unknown roles fail closed
    - relationship truth is not consulted here
    - publication authority is not granted here
    - communication permission is not granted here
    - commerce authority is not granted here
    - location authority is not granted here
    """

    capability = _validate_capability(
        capability
    )

    user = db.query(
        User
    ).filter(
        User.id == user_id
    ).first()

    if not user:
        return OrganizationAccessDecision(
            allowed=False,
            capability=capability,
            reason="user_not_found",
            user_id=user_id,
            organization_id=organization_id,
            account_role=None,
            membership_id=None,
            membership_role=None,
            membership_status=None,
        )

    organization = db.query(
        PartnerOrganization
    ).filter(
        PartnerOrganization.id == organization_id
    ).first()

    if not organization:
        return OrganizationAccessDecision(
            allowed=False,
            capability=capability,
            reason="organization_not_found",
            user_id=user_id,
            organization_id=organization_id,
            account_role=_clean_role(user.role),
            membership_id=None,
            membership_role=None,
            membership_status=None,
        )

    account_role = _clean_role(
        user.role
    )

    if account_role in ADMIN_ACCOUNT_ROLES:
        return OrganizationAccessDecision(
            allowed=True,
            capability=capability,
            reason="account_admin",
            user_id=user_id,
            organization_id=organization_id,
            account_role=account_role,
            membership_id=None,
            membership_role=None,
            membership_status=None,
        )

    membership = get_active_organization_membership(
        db,
        user_id=user_id,
        organization_id=organization_id,
    )

    if not membership:
        return OrganizationAccessDecision(
            allowed=False,
            capability=capability,
            reason="no_active_membership",
            user_id=user_id,
            organization_id=organization_id,
            account_role=account_role,
            membership_id=None,
            membership_role=None,
            membership_status=None,
        )

    membership_role = _clean_role(
        membership.role
    )

    if membership_role not in ROLE_ORDER:
        return OrganizationAccessDecision(
            allowed=False,
            capability=capability,
            reason="unsupported_membership_role",
            user_id=user_id,
            organization_id=organization_id,
            account_role=account_role,
            membership_id=membership.id,
            membership_role=membership_role,
            membership_status=membership.status,
        )

    if not _role_allows(
        membership_role,
        capability,
    ):
        return OrganizationAccessDecision(
            allowed=False,
            capability=capability,
            reason="insufficient_role",
            user_id=user_id,
            organization_id=organization_id,
            account_role=account_role,
            membership_id=membership.id,
            membership_role=membership_role,
            membership_status=membership.status,
        )

    return OrganizationAccessDecision(
        allowed=True,
        capability=capability,
        reason="membership_role_authorized",
        user_id=user_id,
        organization_id=organization_id,
        account_role=account_role,
        membership_id=membership.id,
        membership_role=membership_role,
        membership_status=membership.status,
    )
