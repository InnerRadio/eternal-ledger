"""
PurPaws Platform Ranking Aggregation Seam v1

Purpose
-------

Compute platform-wide ranking truth once.

This module is the aggregation-truth authority for the current
creator, rescue, affiliate, and partner leaderboard scoring model.

It does NOT:

- project data for public exposure,
- determine organization access,
- grant permission,
- create OrganizationMember,
- establish canonical relationships,
- publish records,
- administer taxonomy,
- mutate scoring source records,
- write to the database.

Aggregation Truth != Public Projection.
"""

from sqlalchemy.orm import Session

from backend.app.models import (
    User,
    PartnerOrganization,
    OrganizationMember,
    Memorial,
    Contribution,
    MediaAsset,
    AffiliateCampaignEnrollment,
    AffiliateClick,
    AffiliateConversion,
    AffiliateCommission,
    AffiliateCampaign,
)


def _rank_records(records):
    """
    Return new ranked dictionaries ordered by descending score.

    Source dictionaries are not mutated.
    """

    ordered = sorted(
        records,
        key=lambda item: item.get("score", 0),
        reverse=True,
    )

    ranked_records = []

    for index, record in enumerate(ordered, 1):
        ranked_record = dict(record)
        ranked_record["rank"] = index
        ranked_records.append(ranked_record)

    return ranked_records


def build_platform_ranking_aggregation(
    db: Session,
):
    """
    Build platform-wide aggregation truth.

    Returns:
        summary
        leaderboards:
            creators
            rescues
            partners
            affiliates

    The returned records intentionally contain internal analytical
    identity and scoring components.

    Public consumers MUST pass records through the separately locked
    Public Aggregation Projection Seam before public exposure.
    """

    users = db.query(
        User
    ).all()

    organizations = db.query(
        PartnerOrganization
    ).filter(
        PartnerOrganization.status == "active"
    ).all()

    memberships = db.query(
        OrganizationMember
    ).filter(
        OrganizationMember.status == "active"
    ).all()

    memorials = db.query(
        Memorial
    ).all()

    contributions = db.query(
        Contribution
    ).all()

    media_assets = db.query(
        MediaAsset
    ).all()

    enrollments = db.query(
        AffiliateCampaignEnrollment
    ).all()

    clicks = db.query(
        AffiliateClick
    ).all()

    conversions = db.query(
        AffiliateConversion
    ).all()

    commissions = db.query(
        AffiliateCommission
    ).all()

    campaigns = db.query(
        AffiliateCampaign
    ).all()


    memberships_by_user_id = {}

    for membership in memberships:
        memberships_by_user_id.setdefault(
            membership.user_id,
            [],
        ).append(
            membership
        )


    organizations_by_id = {
        organization.id: organization
        for organization in organizations
    }


    memorials_by_user_id = {}

    for memorial in memorials:
        memorials_by_user_id.setdefault(
            memorial.created_by_user_id,
            [],
        ).append(
            memorial
        )


    contributions_by_user_id = {}

    for contribution in contributions:
        contributions_by_user_id.setdefault(
            contribution.created_by_user_id,
            [],
        ).append(
            contribution
        )


    media_by_user_id = {}

    for asset in media_assets:
        media_by_user_id.setdefault(
            asset.uploaded_by_user_id,
            [],
        ).append(
            asset
        )


    enrollments_by_user_id = {}

    for enrollment in enrollments:
        enrollments_by_user_id.setdefault(
            enrollment.user_id,
            [],
        ).append(
            enrollment
        )


    clicks_by_referral_code = {}

    for click in clicks:
        clicks_by_referral_code.setdefault(
            click.referral_code,
            [],
        ).append(
            click
        )


    conversions_by_referral_code = {}

    for conversion in conversions:
        conversions_by_referral_code.setdefault(
            conversion.referral_code,
            [],
        ).append(
            conversion
        )


    commissions_by_referral_code = {}

    for commission in commissions:
        commissions_by_referral_code.setdefault(
            commission.referral_code,
            [],
        ).append(
            commission
        )


    creator_rankings = []
    rescue_rankings = []
    affiliate_rankings = []


    for platform_user in users:
        role = (
            platform_user.role
            or "free"
        )

        user_memorials = memorials_by_user_id.get(
            platform_user.id,
            [],
        )

        user_contributions = contributions_by_user_id.get(
            platform_user.id,
            [],
        )

        user_media = media_by_user_id.get(
            platform_user.id,
            [],
        )

        user_enrollments = enrollments_by_user_id.get(
            platform_user.id,
            [],
        )

        user_clicks = clicks_by_referral_code.get(
            platform_user.referral_code,
            [],
        )

        user_conversions = conversions_by_referral_code.get(
            platform_user.referral_code,
            [],
        )

        user_commissions = commissions_by_referral_code.get(
            platform_user.referral_code,
            [],
        )

        user_memberships = memberships_by_user_id.get(
            platform_user.id,
            [],
        )

        user_commission_cents = sum(
            commission.amount_cents
            or 0
            for commission in user_commissions
        )

        active_orgs = [
            organizations_by_id.get(
                membership.organization_id
            )
            for membership in user_memberships
            if organizations_by_id.get(
                membership.organization_id
            )
        ]

        rescue_orgs = [
            organization
            for organization in active_orgs
            if "rescue" in (
                (
                    organization.organization_type
                    or ""
                ).lower()
            )
        ]


        creator_score = (
            len(user_clicks)
            + (
                len(user_conversions)
                * 10
            )
            + (
                len(user_enrollments)
                * 15
            )
            + (
                len(user_memorials)
                * 5
            )
            + (
                len(user_contributions)
                * 3
            )
            + (
                len(user_media)
                * 2
            )
            + (
                len(active_orgs)
                * 20
            )
            + int(
                user_commission_cents
                / 100
            )
        )


        rescue_score = (
            (
                len(rescue_orgs)
                * 30
            )
            + (
                len(
                    [
                        memorial
                        for memorial in user_memorials
                        if memorial.status
                        in [
                            "reviewed",
                            "approved",
                            "published",
                        ]
                    ]
                )
                * 20
            )
            + (
                len(
                    [
                        memorial
                        for memorial in user_memorials
                        if memorial.status
                        in [
                            "submitted",
                            "reviewed",
                            "approved",
                            "published",
                        ]
                    ]
                )
                * 10
            )
            + (
                len(
                    [
                        contribution
                        for contribution
                        in user_contributions
                        if contribution.status
                        in [
                            "submitted",
                            "reviewed",
                            "approved",
                            "published",
                        ]
                    ]
                )
                * 5
            )
            + (
                len(user_media)
                * 2
            )
            + (
                len(user_enrollments)
                * 15
            )
            + (
                len(user_conversions)
                * 10
            )
            + len(user_clicks)
            + int(
                user_commission_cents
                / 100
            )
        )


        affiliate_score = (
            len(user_clicks)
            + (
                len(user_conversions)
                * 10
            )
            + (
                len(user_enrollments)
                * 15
            )
            + int(
                user_commission_cents
                / 100
            )
        )


        creator_rankings.append(
            {
                "user_id":
                    platform_user.id,

                "email":
                    platform_user.email,

                "role":
                    role,

                "affiliate_id":
                    platform_user.affiliate_id,

                "referral_code":
                    platform_user.referral_code,

                "score":
                    creator_score,

                "components": {
                    "clicks":
                        len(user_clicks),

                    "conversions":
                        len(user_conversions),

                    "campaign_enrollments":
                        len(user_enrollments),

                    "memorials":
                        len(user_memorials),

                    "contributions":
                        len(
                            user_contributions
                        ),

                    "media_assets":
                        len(user_media),

                    "organizations":
                        len(active_orgs),

                    "commission_points":
                        int(
                            user_commission_cents
                            / 100
                        ),
                },
            }
        )


        rescue_rankings.append(
            {
                "user_id":
                    platform_user.id,

                "email":
                    platform_user.email,

                "role":
                    role,

                "affiliate_id":
                    platform_user.affiliate_id,

                "referral_code":
                    platform_user.referral_code,

                "score":
                    rescue_score,

                "components": {
                    "rescue_organizations":
                        len(rescue_orgs),

                    "memorials":
                        len(user_memorials),

                    "contributions":
                        len(
                            user_contributions
                        ),

                    "media_assets":
                        len(user_media),

                    "campaign_enrollments":
                        len(user_enrollments),

                    "conversions":
                        len(user_conversions),

                    "clicks":
                        len(user_clicks),

                    "commission_points":
                        int(
                            user_commission_cents
                            / 100
                        ),
                },
            }
        )


        affiliate_rankings.append(
            {
                "user_id":
                    platform_user.id,

                "email":
                    platform_user.email,

                "role":
                    role,

                "affiliate_id":
                    platform_user.affiliate_id,

                "referral_code":
                    platform_user.referral_code,

                "score":
                    affiliate_score,

                "components": {
                    "clicks":
                        len(user_clicks),

                    "conversions":
                        len(user_conversions),

                    "campaign_enrollments":
                        len(user_enrollments),

                    "commission_points":
                        int(
                            user_commission_cents
                            / 100
                        ),
                },
            }
        )


    partner_rankings = []

    memberships_by_org_id = {}

    for membership in memberships:
        memberships_by_org_id.setdefault(
            membership.organization_id,
            [],
        ).append(
            membership
        )


    campaigns_by_sponsor = {}

    for campaign in campaigns:
        campaigns_by_sponsor.setdefault(
            campaign.sponsor_name,
            [],
        ).append(
            campaign
        )


    enrollments_by_campaign = {}

    for enrollment in enrollments:
        enrollments_by_campaign.setdefault(
            enrollment.campaign_id,
            [],
        ).append(
            enrollment
        )


    clicks_by_campaign = {}

    for click in clicks:
        clicks_by_campaign.setdefault(
            click.campaign_id,
            [],
        ).append(
            click
        )


    for organization in organizations:
        org_campaigns = campaigns_by_sponsor.get(
            organization.organization_name,
            [],
        )

        org_campaign_ids = [
            campaign.campaign_id
            for campaign in org_campaigns
        ]

        org_enrollments = []
        org_clicks = []

        for campaign_id in org_campaign_ids:
            org_enrollments.extend(
                enrollments_by_campaign.get(
                    campaign_id,
                    [],
                )
            )

            org_clicks.extend(
                clicks_by_campaign.get(
                    campaign_id,
                    [],
                )
            )

        org_referral_codes = [
            enrollment.referral_code
            for enrollment in org_enrollments
            if enrollment.referral_code
        ]

        org_conversions = [
            conversion
            for conversion in conversions
            if conversion.referral_code
            in org_referral_codes
        ]

        org_commissions = [
            commission
            for commission in commissions
            if commission.referral_code
            in org_referral_codes
        ]

        org_memberships = memberships_by_org_id.get(
            organization.id,
            [],
        )

        creator_relationships = [
            membership
            for membership in org_memberships
            if "creator" in (
                (
                    membership.role
                    or ""
                ).lower()
            )
        ]

        rescue_relationships = [
            membership
            for membership in org_memberships
            if "rescue" in (
                (
                    membership.role
                    or ""
                ).lower()
            )
        ]

        org_commission_cents = sum(
            commission.amount_cents
            or 0
            for commission in org_commissions
        )

        partner_score = (
            40
            + (
                len(org_campaigns)
                * 25
            )
            + (
                len(org_enrollments)
                * 15
            )
            + (
                len(org_conversions)
                * 10
            )
            + len(org_clicks)
            + (
                len(
                    creator_relationships
                )
                * 20
            )
            + (
                len(
                    rescue_relationships
                )
                * 20
            )
            + int(
                org_commission_cents
                / 100
            )
        )

        partner_rankings.append(
            {
                "organization_id":
                    organization.id,

                "organization_name":
                    organization.organization_name,

                "organization_type":
                    organization.organization_type,

                "project":
                    organization.project,

                "score":
                    partner_score,

                "components": {
                    "campaigns":
                        len(org_campaigns),

                    "campaign_enrollments":
                        len(org_enrollments),

                    "conversions":
                        len(org_conversions),

                    "clicks":
                        len(org_clicks),

                    "creator_relationships":
                        len(
                            creator_relationships
                        ),

                    "rescue_relationships":
                        len(
                            rescue_relationships
                        ),

                    "commission_points":
                        int(
                            org_commission_cents
                            / 100
                        ),
                },
            }
        )


    creator_rankings = _rank_records(
        creator_rankings
    )

    rescue_rankings = _rank_records(
        rescue_rankings
    )

    affiliate_rankings = _rank_records(
        affiliate_rankings
    )

    partner_rankings = _rank_records(
        partner_rankings
    )


    return {
        "summary": {
            "users":
                len(users),

            "organizations":
                len(organizations),

            "campaigns":
                len(campaigns),

            "clicks":
                len(clicks),

            "conversions":
                len(conversions),

            "commissions":
                len(commissions),
        },

        "leaderboards": {
            "creators":
                creator_rankings,

            "rescues":
                rescue_rankings,

            "partners":
                partner_rankings,

            "affiliates":
                affiliate_rankings,
        },
    }
