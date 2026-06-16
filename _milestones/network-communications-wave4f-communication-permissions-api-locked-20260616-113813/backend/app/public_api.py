from fastapi import APIRouter, Depends
from datetime import datetime
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import Memorial, MediaAsset, Contribution, MetricEvent, User, AffiliateCampaign, PartnerOrganization, AffiliateConversion, AffiliateClick, AffiliateCommission, AffiliateCampaignEnrollment, OrganizationMember, RescueProfile, RescueAnimal, PublicProfile, FounderProfile, ContactRelayMessage, CommunicationPermission
from backend.app.environment_themes import ENVIRONMENT_THEMES


def parse_client_event_at(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None

router = APIRouter(prefix="/public", tags=["Public API"])


@router.post("/metrics/track")
def public_track_metric_event(
    event_type: str,
    project: str = "PurPaws",
    source: str = "public",
    session_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
    campaign_id: str | None = None,
    organization_id: int | None = None,
    affiliate_id: str | None = None,
    referral_code: str | None = None,
    page_url: str | None = None,
    metadata_json: str | None = None,
    client_event_at: str | None = None,
    db: Session = Depends(get_db)
):
    event = MetricEvent(
        event_type=event_type,
        project=project,
        source=source,
        session_id=session_id,
        target_type=target_type,
        target_id=target_id,
        campaign_id=campaign_id,
        organization_id=organization_id,
        affiliate_id=affiliate_id,
        referral_code=referral_code,
        page_url=page_url,
        metadata_json=metadata_json,
        client_event_at=parse_client_event_at(client_event_at),
    )

    db.add(event)
    db.commit()
    db.refresh(event)

    return {
        "module": "Public Metrics",
        "status": "tracked",
        "record": {
            "id": event.id,
            "event_type": event.event_type,
            "project": event.project,
            "source": event.source,
            "session_id": event.session_id,
            "target_type": event.target_type,
            "target_id": event.target_id,
            "campaign_id": event.campaign_id,
            "organization_id": event.organization_id,
            "affiliate_id": event.affiliate_id,
            "referral_code": event.referral_code,
            "page_url": event.page_url,
            "metadata_json": event.metadata_json,
            "client_event_at": event.client_event_at,
            "created_at": event.created_at,
        }
    }


@router.post("/contact-relay")
def public_contact_relay(
    recipient_type: str,
    message: str,
    sender_name: str,
    sender_email: str | None = None,
    recipient_id: int | None = None,
    source_listing_type: str | None = None,
    source_listing_id: int | None = None,
    subject: str | None = None,
    project: str = "PurPaws",
    source_context: str = "public_directory",
    db: Session = Depends(get_db)
):
    allowed_recipient_types = [
        "founder",
        "creator",
        "rescue",
        "partner",
        "organization"
    ]

    if recipient_type not in allowed_recipient_types:
        return {
            "module": "Public Contact Relay",
            "status": "error",
            "message": "Unsupported recipient_type.",
            "allowed_recipient_types": allowed_recipient_types
        }

    clean_message = (message or "").strip()
    clean_sender_name = (sender_name or "").strip()

    if not clean_sender_name:
        return {
            "module": "Public Contact Relay",
            "status": "error",
            "message": "sender_name is required."
        }

    if not clean_message:
        return {
            "module": "Public Contact Relay",
            "status": "error",
            "message": "message is required."
        }

    effective_listing_type = source_listing_type or recipient_type
    effective_listing_id = source_listing_id or recipient_id

    permission = None

    if effective_listing_type and effective_listing_id:
        permission = db.query(CommunicationPermission).filter(
            CommunicationPermission.project == project,
            CommunicationPermission.listing_type == effective_listing_type,
            CommunicationPermission.listing_id == effective_listing_id,
            CommunicationPermission.status == "active"
        ).first()

    if permission and not bool(permission.allow_contact_relay):
        return {
            "module": "Public Contact Relay",
            "status": "blocked",
            "version": "network-communications-contact-relay-v1",
            "message": "Contact relay is disabled for this listing.",
            "permission": {
                "listing_type": permission.listing_type,
                "listing_id": permission.listing_id,
                "allow_contact_relay": permission.allow_contact_relay,
                "status": permission.status
            }
        }

    relay = ContactRelayMessage(
        project=project,
        source_context=source_context,
        source_listing_type=source_listing_type,
        source_listing_id=source_listing_id,
        recipient_type=recipient_type,
        recipient_id=recipient_id,
        sender_name=clean_sender_name,
        sender_email=sender_email,
        sender_user_id=None,
        subject=subject,
        message=clean_message,
        status="new",
        privacy_status="relay_protected"
    )

    db.add(relay)
    db.commit()
    db.refresh(relay)

    return {
        "module": "Public Contact Relay",
        "status": "received",
        "version": "network-communications-contact-relay-v1",
        "privacy": "Message stored in relay layer. Recipient private contact details are not exposed.",
        "record": {
            "id": relay.id,
            "project": relay.project,
            "recipient_type": relay.recipient_type,
            "recipient_id": relay.recipient_id,
            "source_context": relay.source_context,
            "source_listing_type": relay.source_listing_type,
            "source_listing_id": relay.source_listing_id,
            "subject": relay.subject,
            "status": relay.status,
            "privacy_status": relay.privacy_status,
            "permission_status": "allowed" if permission else "default_allowed",
            "created_at": relay.created_at
        }
    }


@router.post("/metrics/batch")
def public_track_metric_events_batch(
    events_json: str,
    db: Session = Depends(get_db)
):
    import json

    try:
        events_data = json.loads(events_json)
    except Exception:
        return {
            "module": "Public Metrics Batch",
            "status": "error",
            "message": "Invalid events_json payload."
        }

    if not isinstance(events_data, list):
        return {
            "module": "Public Metrics Batch",
            "status": "error",
            "message": "events_json must be a JSON list."
        }

    created = []

    for item in events_data:
        if not isinstance(item, dict):
            continue

        event_type = item.get("event_type")

        if not event_type:
            continue

        event = MetricEvent(
            event_type=event_type,
            project=item.get("project") or "PurPaws",
            source=item.get("source") or "public",
            session_id=item.get("session_id"),
            target_type=item.get("target_type"),
            target_id=item.get("target_id"),
            campaign_id=item.get("campaign_id"),
            organization_id=item.get("organization_id"),
            affiliate_id=item.get("affiliate_id"),
            referral_code=item.get("referral_code"),
            page_url=item.get("page_url"),
            metadata_json=item.get("metadata_json"),
            client_event_at=parse_client_event_at(item.get("client_event_at")),
        )

        db.add(event)
        created.append(event)

    db.commit()

    for event in created:
        db.refresh(event)

    return {
        "module": "Public Metrics Batch",
        "status": "tracked",
        "count": len(created),
        "records": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "project": event.project,
                "source": event.source,
                "session_id": event.session_id,
                "target_type": event.target_type,
                "target_id": event.target_id,
                "campaign_id": event.campaign_id,
                "organization_id": event.organization_id,
                "affiliate_id": event.affiliate_id,
                "referral_code": event.referral_code,
                "page_url": event.page_url,
                "metadata_json": event.metadata_json,
                "client_event_at": event.client_event_at,
                "created_at": event.created_at,
            }
            for event in created
        ]
    }


@router.get("/memorials")
def public_memorials(
    db: Session = Depends(get_db)
):
    memorials = db.query(Memorial).filter(
        Memorial.status == "published"
    ).all()

    records = []

    for memorial in memorials:
        media = db.query(MediaAsset).filter(
            MediaAsset.memorial_id == memorial.id,
            MediaAsset.status == "published"
        ).first()

        records.append({
            "id": memorial.id,
            "companion_name": memorial.companion_name,
            "years": memorial.years,
            "story": memorial.story,
            "archive_type": memorial.archive_type,
            "project": memorial.project,
            "status": memorial.status,
            "environment_theme": memorial.environment_theme,
            "atmosphere_intensity": memorial.atmosphere_intensity,
            "primary_media": media.file_path if media else None
        })

    return {
        "module": "Public Memorials",
        "status": "active",
        "count": len(records),
        "records": records
    }


@router.get("/memorials/{memorial_id}")
def public_memorial_detail(
    memorial_id: int,
    db: Session = Depends(get_db)
):
    memorial = db.query(Memorial).filter(
        Memorial.id == memorial_id,
        Memorial.status == "published"
    ).first()

    if not memorial:
        return {
            "module": "Public Memorial",
            "status": "error",
            "message": "Memorial not found."
        }

    return {
        "module": "Public Memorial",
        "status": "active",
        "record": {
            "id": memorial.id,
            "companion_name": memorial.companion_name,
            "years": memorial.years,
            "story": memorial.story,
            "archive_type": memorial.archive_type,
            "project": memorial.project,
            "status": memorial.status,
            "environment_theme": memorial.environment_theme,
            "atmosphere_intensity": memorial.atmosphere_intensity
        }
    }


@router.get("/memorials/{memorial_id}/media")
def public_memorial_media(
    memorial_id: int,
    db: Session = Depends(get_db)
):
    assets = db.query(MediaAsset).filter(
        MediaAsset.memorial_id == memorial_id,
        MediaAsset.status == "published"
    ).all()

    return {
        "module": "Public Memorial Media",
        "status": "active",
        "memorial_id": memorial_id,
        "count": len(assets),
        "records": [
            {
                "id": asset.id,
                "file_path": asset.file_path,
                "original_filename": asset.original_filename,
                "media_type": asset.media_type,
                "status": asset.status,
                "ipfs_cid": asset.ipfs_cid,
                "xrpl_tx_hash": asset.xrpl_tx_hash,
                "created_at": asset.created_at,
            }
            for asset in assets
        ]
    }


@router.get("/memorials/{memorial_id}/contributions")
def public_memorial_contributions(
    memorial_id: int,
    db: Session = Depends(get_db)
):
    contributions = db.query(Contribution).filter(
        Contribution.memorial_id == memorial_id,
        Contribution.status == "published"
    ).all()

    return {
        "module": "Public Contributions",
        "status": "active",
        "memorial_id": memorial_id,
        "count": len(contributions),
        "records": [
            {
                "id": contribution.id,
                "contributor_name": contribution.contributor_name,
                "contribution_type": contribution.contribution_type,
                "content": contribution.content,
                "media_asset_id": contribution.media_asset_id,
                "status": contribution.status,
                "ipfs_cid": contribution.ipfs_cid,
                "xrpl_tx_hash": contribution.xrpl_tx_hash,
                "created_at": contribution.created_at,
            }
            for contribution in contributions
        ]
    }


@router.get("/environment-themes")
def public_environment_themes():
    return {
        "module": "Environment Themes",
        "status": "active",
        "count": len(ENVIRONMENT_THEMES),
        "records": ENVIRONMENT_THEMES
    }


@router.get("/pulse")
def public_network_pulse(
    db: Session = Depends(get_db)
):
    memorial_count = db.query(Memorial).filter(
        Memorial.status == "published"
    ).count()

    media_count = db.query(MediaAsset).filter(
        MediaAsset.status == "published"
    ).count()

    contribution_count = db.query(Contribution).filter(
        Contribution.status == "published"
    ).count()

    users = db.query(User).all()

    organizations = db.query(PartnerOrganization).filter(
        PartnerOrganization.status == "active"
    ).all()

    opportunities = db.query(AffiliateCampaign).filter(
        AffiliateCampaign.status == "active"
    ).order_by(AffiliateCampaign.created_at.desc()).limit(6).all()

    creator_count = len([
        user for user in users
        if (user.role or "").lower() == "creator"
    ])

    rescue_count = len([
        user for user in users
        if (user.role or "").lower() == "rescue"
    ])

    affiliate_count = len([
        user for user in users
        if user.affiliate_id or user.referral_code
    ])

    rescue_organization_count = len([
        organization for organization in organizations
        if "rescue" in ((organization.organization_type or "").lower())
    ])

    opportunity_records = [
        {
            "id": opportunity.id,
            "campaign_id": opportunity.campaign_id,
            "label": "Opportunity",
            "title": opportunity.title,
            "description": opportunity.description,
            "project": opportunity.project,
            "sponsor_name": opportunity.sponsor_name,
            "opportunity_type": opportunity.campaign_type,
            "payout_type": opportunity.payout_type,
            "payout_amount_cents": opportunity.payout_amount_cents,
            "payout_percent": opportunity.payout_percent,
            "currency": opportunity.currency,
            "status": opportunity.status,
            "starts_at": opportunity.starts_at,
            "ends_at": opportunity.ends_at,
            "created_at": opportunity.created_at,
        }
        for opportunity in opportunities
    ]

    clicks = db.query(AffiliateClick).all()
    conversions = db.query(AffiliateConversion).all()
    commissions = db.query(AffiliateCommission).all()
    enrollments = db.query(AffiliateCampaignEnrollment).all()
    memberships = db.query(OrganizationMember, RescueProfile, RescueAnimal, PublicProfile).filter(
        OrganizationMember, RescueProfile, RescueAnimal, PublicProfile.status == "active"
    ).all()

    memorials_all = db.query(Memorial).all()
    contributions_all = db.query(Contribution).all()
    media_assets_all = db.query(MediaAsset).all()

    memberships_by_user_id = {}
    for membership in memberships:
        memberships_by_user_id.setdefault(membership.user_id, []).append(membership)

    memorials_by_user_id = {}
    for memorial in memorials_all:
        memorials_by_user_id.setdefault(memorial.created_by_user_id, []).append(memorial)

    contributions_by_user_id = {}
    for contribution in contributions_all:
        contributions_by_user_id.setdefault(contribution.created_by_user_id, []).append(contribution)

    media_by_user_id = {}
    for asset in media_assets_all:
        media_by_user_id.setdefault(asset.uploaded_by_user_id, []).append(asset)

    enrollments_by_user_id = {}
    for enrollment in enrollments:
        enrollments_by_user_id.setdefault(enrollment.user_id, []).append(enrollment)

    clicks_by_referral_code = {}
    for click in clicks:
        clicks_by_referral_code.setdefault(click.referral_code, []).append(click)

    conversions_by_referral_code = {}
    for conversion in conversions:
        conversions_by_referral_code.setdefault(conversion.referral_code, []).append(conversion)

    commissions_by_referral_code = {}
    for commission in commissions:
        commissions_by_referral_code.setdefault(commission.referral_code, []).append(commission)

    creator_rankings = []
    rescue_rankings = []
    affiliate_rankings = []

    for platform_user in users:
        role = platform_user.role or "free"
        user_memorials = memorials_by_user_id.get(platform_user.id, [])
        user_contributions = contributions_by_user_id.get(platform_user.id, [])
        user_media = media_by_user_id.get(platform_user.id, [])
        user_enrollments = enrollments_by_user_id.get(platform_user.id, [])
        user_clicks = clicks_by_referral_code.get(platform_user.referral_code, [])
        user_conversions = conversions_by_referral_code.get(platform_user.referral_code, [])
        user_commissions = commissions_by_referral_code.get(platform_user.referral_code, [])
        user_commission_cents = sum(
            commission.amount_cents or 0
            for commission in user_commissions
        )

        active_orgs = memberships_by_user_id.get(platform_user.id, [])

        rescue_orgs = [
            membership
            for membership in active_orgs
            if "rescue" in ((membership.role or "").lower())
        ]

        creator_score = (
            25
            + (len([m for m in user_memorials if m.status in ["reviewed", "approved", "published"]]) * 20)
            + (len([m for m in user_memorials if m.status in ["submitted", "reviewed", "approved", "published"]]) * 10)
            + (len([c for c in user_contributions if c.status in ["submitted", "reviewed", "approved", "published"]]) * 5)
            + (len(user_media) * 2)
            + (len(user_enrollments) * 15)
            + (len(user_conversions) * 10)
            + len(user_clicks)
            + int(user_commission_cents / 100)
        )

        rescue_score = (
            25
            + (len(rescue_orgs) * 40)
            + (len([m for m in user_memorials if m.status in ["reviewed", "approved", "published"]]) * 20)
            + (len([m for m in user_memorials if m.status in ["submitted", "reviewed", "approved", "published"]]) * 10)
            + (len([c for c in user_contributions if c.status in ["submitted", "reviewed", "approved", "published"]]) * 5)
            + (len(user_media) * 2)
            + (len(user_enrollments) * 15)
            + (len(user_conversions) * 10)
            + len(user_clicks)
            + int(user_commission_cents / 100)
        )

        affiliate_score = (
            len(user_clicks)
            + (len(user_conversions) * 10)
            + (len(user_enrollments) * 15)
            + int(user_commission_cents / 100)
        )

        public_label = platform_user.affiliate_id or "Community Member"

        creator_rankings.append({
            "label": public_label,
            "role": role,
            "score": creator_score,
        })

        rescue_rankings.append({
            "label": public_label,
            "role": role,
            "score": rescue_score,
        })

        affiliate_rankings.append({
            "label": public_label,
            "role": role,
            "score": affiliate_score,
        })

    campaigns_by_sponsor = {}
    for campaign in opportunities:
        campaigns_by_sponsor.setdefault(campaign.sponsor_name, []).append(campaign)

    memberships_by_org_id = {}
    for membership in memberships:
        memberships_by_org_id.setdefault(membership.organization_id, []).append(membership)

    enrollments_by_campaign = {}
    for enrollment in enrollments:
        enrollments_by_campaign.setdefault(enrollment.campaign_id, []).append(enrollment)

    clicks_by_campaign = {}
    for click in clicks:
        clicks_by_campaign.setdefault(click.campaign_id, []).append(click)

    partner_rankings = []

    for organization in organizations:
        org_campaigns = campaigns_by_sponsor.get(organization.organization_name, [])
        org_campaign_ids = [
            campaign.campaign_id
            for campaign in org_campaigns
        ]

        org_enrollments = []
        org_clicks = []

        for campaign_id in org_campaign_ids:
            org_enrollments.extend(enrollments_by_campaign.get(campaign_id, []))
            org_clicks.extend(clicks_by_campaign.get(campaign_id, []))

        org_referral_codes = [
            enrollment.referral_code
            for enrollment in org_enrollments
            if enrollment.referral_code
        ]

        org_conversions = [
            conversion
            for conversion in conversions
            if conversion.referral_code in org_referral_codes
        ]

        org_commissions = [
            commission
            for commission in commissions
            if commission.referral_code in org_referral_codes
        ]

        org_memberships = memberships_by_org_id.get(organization.id, [])

        creator_relationships = [
            membership
            for membership in org_memberships
            if "creator" in ((membership.role or "").lower())
        ]

        rescue_relationships = [
            membership
            for membership in org_memberships
            if "rescue" in ((membership.role or "").lower())
        ]

        org_commission_cents = sum(
            commission.amount_cents or 0
            for commission in org_commissions
        )

        partner_score = (
            40
            + (len(org_campaigns) * 25)
            + (len(org_enrollments) * 15)
            + (len(org_conversions) * 10)
            + len(org_clicks)
            + (len(creator_relationships) * 20)
            + (len(rescue_relationships) * 20)
            + int(org_commission_cents / 100)
        )

        partner_rankings.append({
            "label": organization.organization_name,
            "organization_type": organization.organization_type,
            "project": organization.project,
            "score": partner_score,
        })

    def top_public_record(records):
        if not records:
            return None

        ordered = sorted(
            records,
            key=lambda item: item.get("score", 0),
            reverse=True
        )

        record = dict(ordered[0])
        record["rank"] = 1
        return record

    leaderboard_highlights = {
        "top_creator": top_public_record(creator_rankings),
        "top_rescue": top_public_record(rescue_rankings),
        "top_partner": top_public_record(partner_rankings),
        "top_affiliate": top_public_record(affiliate_rankings),
        "privacy": "Public-safe highlights exclude email, user_id, referral_code, and internal organization_id."
    }

    featured_opportunity = opportunity_records[0] if opportunity_records else None

    return {
        "module": "PurPaws Network Pulse",
        "status": "active",
        "version": "v30b-public-network-pulse",
        "visibility": "public",
        "network": "PurPaws Continuity Network",
        "philosophy": "The Pulse Medallion is the public-facing heartbeat of the community.",

        "metrics": {
            "published_memorials": memorial_count,
            "published_media_assets": media_count,
            "published_contributions": contribution_count,

            "members": len(users),
            "organizations": len(organizations),
            "creators": creator_count,
            "rescues": rescue_count,
            "rescue_organizations": rescue_organization_count,
            "affiliates": affiliate_count,
            "active_opportunities": len(opportunity_records)
        },

        "continuity": {
            "memorials": memorial_count,
            "media_assets": media_count,
            "contributions": contribution_count
        },

        "community": {
            "members": len(users),
            "organizations": len(organizations),
            "creators": creator_count,
            "rescues": rescue_count,
            "rescue_organizations": rescue_organization_count,
            "affiliates": affiliate_count
        },

        "opportunities": {
            "label": "Opportunities",
            "description": "Public-facing campaigns and side-hustle paths available through the PurPaws network.",
            "count": len(opportunity_records),
            "featured": featured_opportunity,
            "records": opportunity_records
        },

        "leaderboard_highlights": leaderboard_highlights,

        "pulse_layers": [
            {
                "key": "continuity",
                "label": "Continuity Layer",
                "enabled": True,
                "locked": False
            },
            {
                "key": "community",
                "label": "Community Layer",
                "enabled": True,
                "locked": False
            },
            {
                "key": "opportunities",
                "label": "Opportunities",
                "enabled": bool(opportunity_records),
                "locked": not bool(opportunity_records),
                "reason": "Available when active public campaigns exist."
            },
            {
                "key": "leaderboard_highlights",
                "label": "Leaderboard Highlights",
                "enabled": True,
                "locked": False,
                "reason": "Public-safe leaderboard highlights are available."
            },
            {
                "key": "featured_creators",
                "label": "Featured Creators",
                "enabled": False,
                "locked": True,
                "reason": "Requires featured community curation."
            },
            {
                "key": "featured_rescues",
                "label": "Featured Rescues",
                "enabled": False,
                "locked": True,
                "reason": "Requires featured rescue curation."
            },
            {
                "key": "xrpl_verification",
                "label": "XRPL Verification",
                "enabled": False,
                "locked": True,
                "reason": "Future ledger verification pulse layer."
            }
        ],

        "systems": {
            "xrpl": "planned",
            "eternal_ledger": "active",
            "continuity_layer": "operational",
            "community_layer": "active",
            "opportunity_layer": "active" if opportunity_records else "waiting"
        },

        "coming_soon": [
            "Leaderboard Highlights",
            "Featured Creators",
            "Featured Rescues",
            "Featured Organizations",
            "XRPL Verification",
            "White Label Communities"
        ],

        "notes": [
            "This endpoint is public-safe and does not require account authentication.",
            "The legacy metrics object is preserved for compatibility with existing Pulse Medallion UI.",
            "AffiliateCampaign records are presented publicly as Opportunities."
        ]
    }


@router.get("/founders")
def public_founders(
    founder_type: str | None = None,
    founder_level: str | None = None,
    db: Session = Depends(get_db)
):
    query = db.query(FounderProfile).filter(
        FounderProfile.status == "active"
    )

    if founder_type:
        query = query.filter(FounderProfile.founder_type == founder_type)

    if founder_level:
        query = query.filter(FounderProfile.founder_level == founder_level)

    founders = query.order_by(
        FounderProfile.created_at.asc(),
        FounderProfile.id.asc()
    ).all()

    records = []

    for founder in founders:
        records.append({
            "id": founder.id,
            "type": "founder",
            "identity": {
                "user_id": founder.user_id,
            },
            "organization": {
                "organization_name": founder.organization_name,
            } if founder.organization_name else None,
            "profile": {
                "founder_type": founder.founder_type,
                "founder_level": founder.founder_level,
                "display_name": founder.display_name,
                "message": founder.message,
                "created_at": founder.created_at,
            },
            "metrics": {},
            "status": founder.status,
        })

    return {
        "module": "Public Founders",
        "status": "active",
        "version": "public-discovery-founders-v1",
        "privacy": "Public-safe founder records expose recognition details only and exclude email, referral_code, affiliate_id, security data, and private account details.",
        "filters": {
            "founder_type": founder_type,
            "founder_level": founder_level,
        },
        "count": len(records),
        "records": records
    }


@router.get("/directory")
def public_directory(
    listing_type: str | None = None,
    location: str | None = None,
    project: str | None = None,
    db: Session = Depends(get_db)
):
    records = []

    include_all = listing_type is None

    if include_all or listing_type == "founder":
        founders = db.query(FounderProfile).filter(
            FounderProfile.status == "active"
        ).order_by(
            FounderProfile.created_at.asc(),
            FounderProfile.id.asc()
        ).all()

        for founder in founders:
            if location and founder.organization_name != location:
                continue

            records.append({
                "id": f"founder-{founder.id}",
                "listing_id": founder.id,
                "listing_type": "founder",
                "source": "founder_profiles",
                "name": founder.display_name,
                "headline": founder.founder_level,
                "description": founder.message,
                "location": None,
                "project": "PurPaws",
                "website_url": None,
                "organization_name": founder.organization_name,
                "profile": {
                    "founder_type": founder.founder_type,
                    "founder_level": founder.founder_level,
                    "created_at": founder.created_at,
                },
                "metrics": {},
                "status": founder.status,
            })

    if include_all or listing_type == "creator":
        creators = db.query(User).filter(
            User.role == "creator",
            User.status == "active"
        ).order_by(User.id.asc()).all()

        for creator in creators:
            profile = db.query(PublicProfile).filter(
                PublicProfile.user_id == creator.id
            ).first()

            creator_location = profile.location if profile else None

            if location and creator_location != location:
                continue

            records.append({
                "id": f"creator-{creator.id}",
                "listing_id": creator.id,
                "listing_type": "creator",
                "source": "users_public_profiles",
                "name": profile.display_name if profile else None,
                "headline": profile.headline if profile else None,
                "description": profile.bio if profile else None,
                "location": creator_location,
                "project": "PurPaws",
                "website_url": profile.website_url if profile else None,
                "organization_name": None,
                "profile": {
                    "username": profile.username if profile else None,
                    "avatar_url": profile.avatar_url if profile else None,
                    "banner_url": profile.banner_url if profile else None,
                    "verification_status": profile.verification_status if profile else "pending",
                    "public_profile_status": profile.public_profile_status if profile else "missing",
                },
                "metrics": {},
                "status": creator.status,
            })

    if include_all or listing_type == "rescue":
        rescue_query = db.query(RescueProfile).filter(
            RescueProfile.status == "active"
        )

        if location:
            rescue_query = rescue_query.filter(RescueProfile.location == location)

        rescues = rescue_query.order_by(
            RescueProfile.organization_name.asc()
        ).all()

        for rescue in rescues:
            animals = db.query(RescueAnimal).filter(
                RescueAnimal.rescue_profile_id == rescue.id,
                RescueAnimal.adoption_status == "available"
            ).all()

            records.append({
                "id": f"rescue-{rescue.id}",
                "listing_id": rescue.id,
                "listing_type": "rescue",
                "source": "rescue_profiles",
                "name": rescue.organization_name,
                "headline": "Rescue Organization",
                "description": rescue.story,
                "location": rescue.location,
                "project": "PurPaws",
                "website_url": None,
                "organization_name": rescue.organization_name,
                "profile": {
                    "organization_type": "rescue",
                },
                "metrics": {
                    "available_animal_count": len(animals)
                },
                "status": rescue.status,
            })

    if include_all or listing_type in ["partner", "organization"]:
        partner_query = db.query(PartnerOrganization).filter(
            PartnerOrganization.status == "active"
        )

        if project:
            partner_query = partner_query.filter(PartnerOrganization.project == project)

        if location:
            partner_query = partner_query.filter(PartnerOrganization.location == location)

        partners = partner_query.order_by(
            PartnerOrganization.organization_name.asc()
        ).all()

        for partner in partners:
            active_members = db.query(OrganizationMember).filter(
                OrganizationMember.organization_id == partner.id,
                OrganizationMember.status == "active"
            ).all()

            effective_listing_type = "organization" if listing_type == "organization" else "partner"

            records.append({
                "id": f"{effective_listing_type}-{partner.id}",
                "listing_id": partner.id,
                "listing_type": effective_listing_type,
                "source": "partner_organizations",
                "name": partner.organization_name,
                "headline": partner.organization_type,
                "description": None,
                "location": partner.location,
                "project": partner.project,
                "website_url": partner.website_url,
                "organization_name": partner.organization_name,
                "profile": {
                    "organization_type": partner.organization_type,
                },
                "metrics": {
                    "active_member_count": len(active_members)
                },
                "status": partner.status,
            })

    return {
        "module": "Public Directory",
        "status": "active",
        "version": "public-discovery-directory-v1",
        "privacy": "Public-safe directory records aggregate discovery listings and exclude email, referral_code, affiliate_id, contact_email, security data, and private account details.",
        "filters": {
            "listing_type": listing_type,
            "location": location,
            "project": project,
        },
        "count": len(records),
        "records": records
    }


@router.get("/creators")
def public_creators(
    db: Session = Depends(get_db)
):
    creators = db.query(User).filter(
        User.role == "creator",
        User.status == "active"
    ).order_by(User.id.asc()).all()

    records = []

    for creator in creators:
        profile = db.query(PublicProfile).filter(
            PublicProfile.user_id == creator.id
        ).first()

        records.append({
            "id": creator.id,
            "type": "creator",
            "identity": {
                "affiliate_id": creator.affiliate_id,
                "username": profile.username if profile else None,
                "display_name": profile.display_name if profile else None,
                "role": creator.role,
                "public_profile_status": profile.public_profile_status if profile else "missing",
                "verification_status": profile.verification_status if profile else "pending",
            },
            "organization": None,
            "profile": {
                "headline": profile.headline if profile else None,
                "bio": profile.bio if profile else None,
                "website_url": profile.website_url if profile else None,
                "avatar_url": profile.avatar_url if profile else None,
                "banner_url": profile.banner_url if profile else None,
                "location": profile.location if profile else None,
            } if profile else None,
            "metrics": {},
            "status": creator.status,
        })

    return {
        "module": "Public Creators",
        "status": "active",
        "version": "public-discovery-creators-v1",
        "privacy": "Public-safe creator records exclude email, referral_code, user security data, and private account details.",
        "count": len(records),
        "records": records
    }


@router.get("/partners")
def public_partners(
    project: str | None = None,
    organization_type: str | None = None,
    db: Session = Depends(get_db)
):
    query = db.query(PartnerOrganization).filter(
        PartnerOrganization.status == "active"
    )

    if project:
        query = query.filter(PartnerOrganization.project == project)

    if organization_type:
        query = query.filter(PartnerOrganization.organization_type == organization_type)

    partners = query.order_by(
        PartnerOrganization.organization_name.asc()
    ).all()

    records = []

    for partner in partners:
        active_members = db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == partner.id,
            OrganizationMember.status == "active"
        ).all()

        records.append({
            "id": partner.id,
            "type": "partner",
            "identity": None,
            "organization": {
                "id": partner.id,
                "organization_name": partner.organization_name,
                "organization_type": partner.organization_type,
                "project": partner.project,
                "website_url": partner.website_url,
                "location": partner.location,
                "status": partner.status,
                "created_at": partner.created_at,
            },
            "profile": None,
            "metrics": {
                "active_member_count": len(active_members)
            },
            "status": partner.status,
        })

    return {
        "module": "Public Partners",
        "status": "active",
        "version": "public-discovery-partners-v1",
        "privacy": "Public-safe partner records exclude contact_name, contact_email, notes, and internal member details.",
        "filters": {
            "project": project,
            "organization_type": organization_type,
        },
        "count": len(records),
        "records": records
    }


@router.get("/rescues")
def public_rescues(
    location: str | None = None,
    db: Session = Depends(get_db)
):
    query = db.query(RescueProfile).filter(
        RescueProfile.status == "active"
    )

    if location:
        query = query.filter(RescueProfile.location == location)

    rescues = query.order_by(
        RescueProfile.organization_name.asc()
    ).all()

    records = []

    for rescue in rescues:
        animals = db.query(RescueAnimal).filter(
            RescueAnimal.rescue_profile_id == rescue.id,
            RescueAnimal.adoption_status == "available"
        ).all()

        records.append({
            "id": rescue.id,
            "type": "rescue",
            "identity": None,
            "organization": {
                "id": rescue.id,
                "organization_name": rescue.organization_name,
                "organization_type": "rescue",
                "project": "PurPaws",
                "website_url": None,
                "location": rescue.location,
                "status": rescue.status,
                "created_at": rescue.created_at,
            },
            "profile": {
                "story": rescue.story,
            },
            "metrics": {
                "available_animal_count": len(animals)
            },
            "status": rescue.status,
        })

    return {
        "module": "Public Rescues",
        "status": "active",
        "version": "public-discovery-rescues-v1",
        "privacy": "Public-safe rescue records exclude contact_email and private contact routing.",
        "filters": {
            "location": location,
        },
        "count": len(records),
        "records": records
    }


@router.get("/opportunities")
def public_opportunities(
    project: str | None = None,
    opportunity_type: str | None = None,
    db: Session = Depends(get_db)
):
    query = db.query(AffiliateCampaign).filter(
        AffiliateCampaign.status == "active"
    )

    if project:
        query = query.filter(AffiliateCampaign.project == project)

    if opportunity_type:
        query = query.filter(AffiliateCampaign.campaign_type == opportunity_type)

    opportunities = query.order_by(
        AffiliateCampaign.created_at.desc()
    ).all()

    records = []

    for opportunity in opportunities:
        records.append({
            "id": opportunity.id,
            "type": "opportunity",
            "identity": None,
            "organization": {
                "sponsor_name": opportunity.sponsor_name
            },
            "profile": None,
            "opportunity": {
                "id": opportunity.id,
                "campaign_id": opportunity.campaign_id,
                "title": opportunity.title,
                "description": opportunity.description,
                "project": opportunity.project,
                "opportunity_type": opportunity.campaign_type,
                "sponsor_name": opportunity.sponsor_name,
                "payout_type": opportunity.payout_type,
                "payout_amount_cents": opportunity.payout_amount_cents,
                "payout_percent": opportunity.payout_percent,
                "currency": opportunity.currency,
                "status": opportunity.status,
                "starts_at": opportunity.starts_at,
                "ends_at": opportunity.ends_at,
                "created_at": opportunity.created_at,
            },
            "metrics": {},
            "status": opportunity.status,
        })

    return {
        "module": "Public Opportunities",
        "status": "active",
        "version": "public-discovery-opportunities-v1",
        "privacy": "Public-safe opportunity records expose active campaign opportunities without private enrollments, referral codes, clicks, conversions, commissions, or user details.",
        "filters": {
            "project": project,
            "opportunity_type": opportunity_type,
        },
        "count": len(records),
        "records": records
    }


@router.get("/campaigns")
def public_campaigns(
    project: str | None = None,
    campaign_type: str | None = None,
    db: Session = Depends(get_db)
):
    query = db.query(AffiliateCampaign).filter(
        AffiliateCampaign.status == "active"
    )

    if project:
        query = query.filter(AffiliateCampaign.project == project)

    if campaign_type:
        query = query.filter(AffiliateCampaign.campaign_type == campaign_type)

    campaigns = query.order_by(
        AffiliateCampaign.created_at.desc()
    ).all()

    records = []

    for campaign in campaigns:
        records.append({
            "id": campaign.id,
            "type": "campaign",
            "identity": None,
            "organization": {
                "sponsor_name": campaign.sponsor_name
            },
            "profile": None,
            "campaign": {
                "id": campaign.id,
                "campaign_id": campaign.campaign_id,
                "title": campaign.title,
                "description": campaign.description,
                "project": campaign.project,
                "campaign_type": campaign.campaign_type,
                "sponsor_name": campaign.sponsor_name,
                "payout_type": campaign.payout_type,
                "payout_amount_cents": campaign.payout_amount_cents,
                "payout_percent": campaign.payout_percent,
                "currency": campaign.currency,
                "status": campaign.status,
                "starts_at": campaign.starts_at,
                "ends_at": campaign.ends_at,
                "created_at": campaign.created_at,
            },
            "metrics": {},
            "status": campaign.status,
        })

    return {
        "module": "Public Campaigns",
        "status": "active",
        "version": "public-discovery-campaigns-v1",
        "privacy": "Public-safe campaign records exclude private enrollments, clicks, conversions, commissions, referral codes, and user details.",
        "filters": {
            "project": project,
            "campaign_type": campaign_type,
        },
        "count": len(records),
        "records": records
    }


@router.get("/organizations")
def public_organizations(
    project: str | None = None,
    organization_type: str | None = None,
    db: Session = Depends(get_db)
):
    query = db.query(PartnerOrganization).filter(
        PartnerOrganization.status == "active"
    )

    if project:
        query = query.filter(PartnerOrganization.project == project)

    if organization_type:
        query = query.filter(PartnerOrganization.organization_type == organization_type)

    organizations = query.order_by(
        PartnerOrganization.organization_name.asc()
    ).all()

    records = []

    for organization in organizations:
        active_members = db.query(OrganizationMember, RescueProfile, RescueAnimal, PublicProfile).filter(
            OrganizationMember, RescueProfile, RescueAnimal, PublicProfile.organization_id == organization.id,
            OrganizationMember, RescueProfile, RescueAnimal, PublicProfile.status == "active"
        ).all()

        records.append({
            "id": organization.id,
            "type": "organization",
            "identity": None,
            "organization": {
                "id": organization.id,
                "organization_name": organization.organization_name,
                "organization_type": organization.organization_type,
                "project": organization.project,
                "website_url": organization.website_url,
                "location": organization.location,
                "status": organization.status,
                "created_at": organization.created_at,
            },
            "profile": None,
            "metrics": {
                "active_member_count": len(active_members)
            },
            "status": organization.status,
        })

    return {
        "module": "Public Organizations",
        "status": "active",
        "version": "public-discovery-organizations-v1",
        "privacy": "Public-safe organization records exclude contact_name, contact_email, notes, and internal member details.",
        "filters": {
            "project": project,
            "organization_type": organization_type,
        },
        "count": len(records),
        "records": records
    }


@router.get("/trails")
def public_trails(db: Session = Depends(get_db)):
    contributions = db.query(Contribution).filter(
        Contribution.status == "published"
    ).order_by(Contribution.created_at.desc()).limit(12).all()

    records = []

    for contribution in contributions:
        memorial = db.query(Memorial).filter(
            Memorial.id == contribution.memorial_id
        ).first()

        records.append({
            "id": contribution.id,
            "title": memorial.companion_name if memorial else "PurPaws Trail Note",
            "trail_type": contribution.contribution_type,
            "content": contribution.content,
            "memorial_id": contribution.memorial_id,
            "media_asset_id": contribution.media_asset_id,
            "status": contribution.status,
            "ipfs_cid": contribution.ipfs_cid,
            "xrpl_tx_hash": contribution.xrpl_tx_hash,
            "created_at": contribution.created_at,
        })

    return {
        "module": "PurPaws Trails",
        "status": "active",
        "count": len(records),
        "records": records
    }

