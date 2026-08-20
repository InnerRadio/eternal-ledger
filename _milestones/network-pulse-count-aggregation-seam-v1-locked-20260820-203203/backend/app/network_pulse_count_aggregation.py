"""
PurPaws Network Pulse Count Aggregation Seam v1

Purpose
-------

Compute the canonical public-safe Network Pulse count truth.

Network Pulse
= network size + community activity.

This module does NOT compute leaderboard rank or score.

It does NOT:
- determine organization access,
- grant membership authority,
- grant relationship authority,
- publish records,
- manage campaigns,
- administer taxonomy,
- mutate database records,
- return featured records or discovery cards.

NETWORK PULSE != LEADERBOARD.
"""

from sqlalchemy.orm import Session

from backend.app.models import (
    User,
    PartnerOrganization,
    Memorial,
    Contribution,
    MediaAsset,
    AffiliateCampaign,
)


def build_network_pulse_counts(
    db: Session,
):
    """
    Return the canonical public-safe Network Pulse count contract.

    network:
        members
        organizations
        creators
        rescues
        rescue_organizations
        affiliates

    activity:
        memorials
        media_assets
        contributions
        active_opportunities
    """

    users = db.query(
        User
    ).all()

    organizations = db.query(
        PartnerOrganization
    ).filter(
        PartnerOrganization.status == "active"
    ).all()

    memorials = db.query(
        Memorial
    ).filter(
        Memorial.status == "published"
    ).all()

    contributions = db.query(
        Contribution
    ).filter(
        Contribution.status == "published"
    ).all()

    media_assets = db.query(
        MediaAsset
    ).filter(
        MediaAsset.status == "published"
    ).all()

    active_campaigns = db.query(
        AffiliateCampaign
    ).filter(
        AffiliateCampaign.status == "active"
    ).all()


    members = len(
        users
    )


    creators = len(
        [
            user
            for user in users
            if (
                (
                    user.role
                    or ""
                ).lower()
                == "creator"
            )
        ]
    )


    rescues = len(
        [
            user
            for user in users
            if (
                (
                    user.role
                    or ""
                ).lower()
                == "rescue"
            )
        ]
    )


    affiliates = len(
        [
            user
            for user in users
            if (
                user.affiliate_id
                or
                user.referral_code
            )
        ]
    )


    rescue_organizations = len(
        [
            organization
            for organization in organizations
            if (
                "rescue"
                in (
                    (
                        organization.organization_type
                        or ""
                    ).lower()
                )
            )
        ]
    )


    return {
        "network": {
            "members":
                members,

            "organizations":
                len(
                    organizations
                ),

            "creators":
                creators,

            "rescues":
                rescues,

            "rescue_organizations":
                rescue_organizations,

            "affiliates":
                affiliates,
        },

        "activity": {
            "memorials":
                len(
                    memorials
                ),

            "media_assets":
                len(
                    media_assets
                ),

            "contributions":
                len(
                    contributions
                ),

            "active_opportunities":
                len(
                    active_campaigns
                ),
        },
    }
