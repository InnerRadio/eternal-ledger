from sqlalchemy.orm import Session

from backend.app.models import (
    OrganizationMember,
    PartnerOrganization,
)

from backend.app.organization_access_authority import (
    evaluate_organization_access,
)


def get_visible_organization_memberships(
    db: Session,
    *,
    user_id: int,
):
    """
    Dashboard Organization Visibility Seam v1.

    Returns only active OrganizationMember records whose role is
    authorized for the view_organization capability.

    This helper governs visibility only.

    It does not grant:
    - edit_organization
    - manage_campaigns
    - administer_members
    - publication authority
    - taxonomy authority
    - commerce authority
    - communication permission
    - location authority
    """

    memberships = db.query(
        OrganizationMember
    ).filter(
        OrganizationMember.user_id == user_id,
        OrganizationMember.status == "active",
    ).all()

    visible = []

    for membership in memberships:
        decision = evaluate_organization_access(
            db,
            user_id=user_id,
            organization_id=membership.organization_id,
            capability="view_organization",
        )

        if decision.allowed:
            visible.append(
                membership
            )

    return visible


def get_visible_organizations(
    db: Session,
    *,
    user_id: int,
):
    """
    Returns:

        memberships
        organizations
        membership_by_org_id

    for organizations visible through view_organization.
    """

    memberships = get_visible_organization_memberships(
        db,
        user_id=user_id,
    )

    organization_ids = [
        membership.organization_id
        for membership in memberships
    ]

    organizations = (
        db.query(
            PartnerOrganization
        ).filter(
            PartnerOrganization.id.in_(
                organization_ids
            )
        ).all()
        if organization_ids
        else []
    )

    membership_by_org_id = {
        membership.organization_id: membership
        for membership in memberships
    }

    return {
        "memberships": memberships,
        "organizations": organizations,
        "membership_by_org_id": membership_by_org_id,
    }
