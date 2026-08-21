from pydantic import BaseModel


class MemorialCreate(BaseModel):
    companion_name: str
    years: str
    story: str
    archive_type: str = "Companion Memorial"
    project: str = "PurPaws"
    environment_theme: str | None = "forest-night"
    atmosphere_intensity: float | None = 0.65






class MediaAssetCreate(BaseModel):
    memorial_id: int | None = None
    file_path: str
    original_filename: str | None = None
    media_type: str
    status: str = "draft"


class ContributionCreate(BaseModel):
    memorial_id: int
    contributor_name: str | None = None
    contribution_type: str = "memory"
    content: str
    media_asset_id: int | None = None
    status: str = "draft"

class UserCreate(BaseModel):
    email: str
    password: str
    role: str = "free"
    referring_affiliate_id: int | None = None
    referral_code: str | None = None




class PartnerInquiryCreate(BaseModel):
    name: str
    email: str
    interest_type: str = "affiliate"
    organization: str | None = None
    message: str | None = None

class UserLogin(BaseModel):
    email: str
    password: str

class MemorialUpdate(BaseModel):
    companion_name: str | None = None
    years: str | None = None
    story: str | None = None
    archive_type: str | None = None
    project: str | None = None
    environment_theme: str | None = None
    atmosphere_intensity: float | None = None
    status: str | None = None

from sqlalchemy import Column, Integer, String, Text, DateTime, UniqueConstraint
from datetime import datetime

from backend.app.database import Base


class Memorial(Base):
    __tablename__ = "memorials"

    id = Column(Integer, primary_key=True, index=True)

    companion_name = Column(String, nullable=False)
    years = Column(String, nullable=False)

    story = Column(Text, nullable=False)

    archive_type = Column(
        String,
        default="Companion Memorial"
    )

    project = Column(
        String,
        default="PurPaws"
    )

    environment_theme = Column(
        String,
        default="forest-night"
    )

    atmosphere_intensity = Column(
        String,
        default="0.65"
    )

    status = Column(
        String,
        default="draft"
    )

    created_by_user_id = Column(Integer, nullable=True)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    role = Column(String, default="admin")
    status = Column(String, default="active")

    affiliate_id = Column(String, unique=True, index=True, nullable=True)
    referral_code = Column(String, unique=True, index=True, nullable=True)
    referring_affiliate_id = Column(Integer, nullable=True)



class CanonicalizationProvenance(Base):
    __tablename__ = "canonicalization_provenance"

    id = Column(Integer, primary_key=True, index=True)

    source_type = Column(String, nullable=False)
    source_id = Column(Integer, nullable=False)

    target_type = Column(String, nullable=False)
    target_id = Column(Integer, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=True)


class OrganizationMember(Base):
    __tablename__ = "organization_members"

    id = Column(Integer, primary_key=True, index=True)

    organization_id = Column(Integer, nullable=False)
    user_id = Column(Integer, nullable=False)

    role = Column(String, default="viewer")
    status = Column(String, default="active")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PublicProfile(Base):
    __tablename__ = "public_profiles"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, unique=True, index=True, nullable=False)

    username = Column(String, unique=True, index=True, nullable=True)
    display_name = Column(String, nullable=True)

    headline = Column(String, nullable=True)
    bio = Column(Text, nullable=True)

    website_url = Column(String, nullable=True)
    avatar_url = Column(String, nullable=True)
    banner_url = Column(String, nullable=True)

    location = Column(String, nullable=True)

    public_profile_status = Column(String, default="pending")
    verification_status = Column(String, default="pending")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=True)



class MetricEvent(Base):
    __tablename__ = "metric_events"

    id = Column(Integer, primary_key=True, index=True)

    event_type = Column(String, nullable=False)

    project = Column(String, default="PurPaws")
    source = Column(String, default="public")

    actor_user_id = Column(Integer, nullable=True)
    session_id = Column(String, nullable=True)

    target_type = Column(String, nullable=True)
    target_id = Column(String, nullable=True)

    campaign_id = Column(String, nullable=True)
    organization_id = Column(Integer, nullable=True)

    affiliate_id = Column(String, nullable=True)
    referral_code = Column(String, nullable=True)

    page_url = Column(String, nullable=True)
    metadata_json = Column(Text, nullable=True)

    client_event_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, nullable=True)
    user_email = Column(String, nullable=True)
    user_role = Column(String, nullable=True)

    action = Column(String, nullable=False)
    target_type = Column(String, nullable=True)
    target_id = Column(Integer, nullable=True)

    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id = Column(Integer, primary_key=True, index=True)

    memorial_id = Column(Integer, nullable=True)

    file_path = Column(String, nullable=False)
    original_filename = Column(String, nullable=True)
    media_type = Column(String, nullable=False)

    status = Column(String, default="draft")
    uploaded_by_user_id = Column(Integer, nullable=True)

    file_size_bytes = Column(Integer, default=0)

    ipfs_cid = Column(String, nullable=True)
    xrpl_tx_hash = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Contribution(Base):
    __tablename__ = "contributions"

    id = Column(Integer, primary_key=True, index=True)

    memorial_id = Column(Integer, nullable=False)
    contributor_name = Column(String, nullable=True)

    contribution_type = Column(String, default="memory")
    content = Column(Text, nullable=False)

    media_asset_id = Column(Integer, nullable=True)

    created_by_user_id = Column(Integer, nullable=True)

    status = Column(String, default="draft")

    ipfs_cid = Column(String, nullable=True)
    xrpl_tx_hash = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AttributionContext(Base):
    __tablename__ = "attribution_contexts"

    id = Column(Integer, primary_key=True, index=True)

    status = Column(
        String,
        default="inbound",
        nullable=False,
    )

    campaign_id = Column(
        String,
        nullable=True,
    )

    referring_user_id = Column(
        Integer,
        nullable=True,
    )

    referring_affiliate_id = Column(
        String,
        nullable=True,
    )

    referring_referral_code = Column(
        String,
        nullable=True,
    )

    participant_user_id = Column(
        Integer,
        nullable=True,
    )

    participant_affiliate_id = Column(
        String,
        nullable=True,
    )

    participant_referral_code = Column(
        String,
        nullable=True,
    )

    enrollment_id = Column(
        Integer,
        nullable=True,
    )

    evidence_source_type = Column(
        String,
        nullable=True,
    )

    evidence_source_id = Column(
        Integer,
        nullable=True,
    )

    evidence_reference = Column(
        Text,
        nullable=True,
    )

    journey_reference_hash = Column(
        String,
        nullable=False,
        unique=True,
        index=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at = Column(
        DateTime,
        nullable=True,
    )

    identified_at = Column(
        DateTime,
        nullable=True,
    )

    participated_at = Column(
        DateTime,
        nullable=True,
    )

    expires_at = Column(
        DateTime,
        nullable=True,
    )


class AffiliateCampaign(Base):
    __tablename__ = "affiliate_campaigns"

    id = Column(Integer, primary_key=True, index=True)

    campaign_id = Column(String, unique=True, index=True, nullable=False)

    project = Column(String, default="PurPaws")
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)

    campaign_type = Column(String, default="general")
    sponsor_name = Column(String, nullable=True)

    payout_type = Column(String, default="flat")
    payout_amount_cents = Column(Integer, default=0)
    payout_percent = Column(String, nullable=True)
    currency = Column(String, default="CAD")

    status = Column(String, default="active")

    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)



class AffiliateCampaignEnrollment(Base):
    __tablename__ = "affiliate_campaign_enrollments"

    id = Column(Integer, primary_key=True, index=True)

    campaign_id = Column(String, nullable=False)

    affiliate_id = Column(String, nullable=True)
    referral_code = Column(String, nullable=True)
    user_id = Column(Integer, nullable=True)

    status = Column(String, default="active")

    joined_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AffiliateClick(Base):
    __tablename__ = "affiliate_clicks"

    id = Column(Integer, primary_key=True, index=True)

    affiliate_id = Column(String, nullable=True)
    referral_code = Column(String, nullable=True)

    campaign_id = Column(String, nullable=True)
    ad_id = Column(String, nullable=True)

    source_url = Column(String, nullable=True)
    destination_url = Column(String, nullable=True)

    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AffiliateConversion(Base):
    __tablename__ = "affiliate_conversions"

    id = Column(Integer, primary_key=True, index=True)

    affiliate_id = Column(String, nullable=True)
    referral_code = Column(String, nullable=True)

    conversion_type = Column(String, default="signup")
    target_type = Column(String, nullable=True)
    target_id = Column(Integer, nullable=True)

    status = Column(String, default="pending")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)



class AffiliateCommission(Base):
    __tablename__ = "affiliate_commissions"

    id = Column(Integer, primary_key=True, index=True)

    conversion_id = Column(Integer, nullable=True)

    affiliate_id = Column(String, nullable=True)
    referral_code = Column(String, nullable=True)

    project = Column(String, default="PurPaws")
    commission_type = Column(String, default="signup")

    amount_cents = Column(Integer, default=0)
    currency = Column(String, default="CAD")

    status = Column(String, default="pending")

    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)




class PartnerTaxonomyCategory(Base):
    __tablename__ = "partner_taxonomy_categories"

    id = Column(Integer, primary_key=True, index=True)

    parent_id = Column(Integer, nullable=True)

    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, index=True)

    description = Column(Text, nullable=True)

    taxonomy_type = Column(String, default="partner")
    project = Column(String, default="PurPaws")

    status = Column(String, default="active")
    sort_order = Column(Integer, default=100)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, nullable=True)



class PartnerTaxonomyAssignment(Base):
    __tablename__ = "partner_taxonomy_assignments"

    id = Column(Integer, primary_key=True, index=True)

    partner_organization_id = Column(Integer, nullable=False)
    taxonomy_category_id = Column(Integer, nullable=False)

    assignment_context = Column(String, default="organization")
    campaign_id = Column(Integer, nullable=True)

    project = Column(String, default="PurPaws")

    status = Column(String, default="active")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, nullable=True)



class PartnerCampaign(Base):
    __tablename__ = "partner_campaigns"

    id = Column(Integer, primary_key=True, index=True)

    partner_organization_id = Column(Integer, nullable=False)

    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, index=True)

    headline = Column(String, nullable=True)
    description = Column(Text, nullable=True)

    campaign_type = Column(String, default="affiliate_promotion")

    project = Column(String, default="PurPaws")

    landing_url = Column(String, nullable=True)
    asset_url = Column(String, nullable=True)

    budget_cents = Column(Integer, default=0)
    currency = Column(String, default="CAD")

    status = Column(String, default="draft")

    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, nullable=True)


class CanonicalPublication(Base):
    __tablename__ = "canonical_publications"

    id = Column(Integer, primary_key=True, index=True)

    target_type = Column(String, nullable=False)
    target_id = Column(Integer, nullable=False)

    publication_status = Column(
        String,
        default="unpublished",
        nullable=False,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    updated_at = Column(
        DateTime,
        nullable=True,
    )


class CanonicalRelationship(Base):
    __tablename__ = "canonical_relationships"

    id = Column(Integer, primary_key=True, index=True)

    source_type = Column(String, nullable=False)
    source_id = Column(Integer, nullable=False)

    target_type = Column(String, nullable=False)
    target_id = Column(Integer, nullable=False)

    relationship_type = Column(String, nullable=False)
    relationship_basis = Column(String, nullable=False)
    relationship_status = Column(
        String,
        default="pending",
        nullable=False,
    )

    scope = Column(String, nullable=True)

    evidence_source_type = Column(String, nullable=False)
    evidence_source_id = Column(Integer, nullable=True)
    evidence_reference = Column(Text, nullable=True)
    evidence_notes = Column(Text, nullable=True)

    effective_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at = Column(
        DateTime,
        nullable=True,
    )


class CanonicalContext(Base):
    __tablename__ = "canonical_contexts"

    __table_args__ = (
        UniqueConstraint(
            "subject_type",
            "subject_id",
            "context_type",
            "context_key",
            "evidence_source_type",
            "evidence_source_id",
            name="uq_canonical_context_evidence",
        ),
    )

    id = Column(Integer, primary_key=True)

    subject_type = Column(
        String,
        nullable=False,
    )

    subject_id = Column(
        Integer,
        nullable=False,
    )

    context_type = Column(
        String,
        nullable=False,
    )

    context_key = Column(
        String,
        nullable=False,
    )

    context_value = Column(
        Text,
        nullable=True,
    )

    context_status = Column(
        String,
        nullable=False,
        default="pending",
    )

    scope = Column(
        String,
        nullable=True,
    )

    evidence_source_type = Column(
        String,
        nullable=False,
    )

    evidence_source_id = Column(
        Integer,
        nullable=True,
    )

    evidence_reference = Column(
        Text,
        nullable=True,
    )

    evidence_notes = Column(
        Text,
        nullable=True,
    )

    effective_at = Column(
        DateTime,
        nullable=True,
    )

    expires_at = Column(
        DateTime,
        nullable=True,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at = Column(
        DateTime,
        nullable=True,
    )



class CanonicalOrganizationResolutionReview(Base):
    """
    Canonical Organization Resolution Review v1

    Append-only historical review judgment about whether an observed
    source resolves to an explicitly identified canonical target.

    This record is NOT canonicalization provenance, relationship authority,
    permission authority, publication authority, or reconciliation authority.
    """

    __tablename__ = "canonical_organization_resolution_reviews"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    source_type = Column(
        String,
        nullable=False,
    )

    source_id = Column(
        Integer,
        nullable=False,
    )

    target_type = Column(
        String,
        nullable=False,
    )

    target_id = Column(
        Integer,
        nullable=False,
    )

    decision = Column(
        String,
        nullable=False,
    )

    basis = Column(
        Text,
        nullable=False,
    )

    evidence_summary = Column(
        Text,
        nullable=True,
    )

    reviewer_user_id = Column(
        Integer,
        nullable=False,
    )

    reviewed_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at = Column(
        DateTime,
        nullable=True,
    )


class FCISHumanReview(Base):
    """
    FCIS Human Review Record v1

    Durable current-state human judgment about one canonical
    Need ↔ Offer context pair.

    This record is NOT canonical truth and does NOT authorize
    action, relationship creation, publication, or outreach.
    """

    __tablename__ = "fcis_human_reviews"

    __table_args__ = (
        UniqueConstraint(
            "need_context_id",
            "offer_context_id",
            name="uq_fcis_human_review_context_pair",
        ),
    )

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    need_context_id = Column(
        Integer,
        nullable=False,
    )

    offer_context_id = Column(
        Integer,
        nullable=False,
    )

    surfaced_card_id = Column(
        String,
        nullable=False,
    )

    disposition = Column(
        String,
        nullable=False,
        default="new",
    )

    reviewer_user_id = Column(
        Integer,
        nullable=False,
    )

    reviewer_email = Column(
        String,
        nullable=False,
    )

    reviewer_role = Column(
        String,
        nullable=False,
    )

    reviewer_note = Column(
        Text,
        nullable=True,
    )

    reviewed_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    updated_at = Column(
        DateTime,
        nullable=True,
    )


class PartnerOrganization(Base):
    __tablename__ = "partner_organizations"

    id = Column(Integer, primary_key=True, index=True)

    organization_name = Column(String, nullable=False)
    organization_type = Column(String, default="other")

    project = Column(String, default="PurPaws")

    contact_name = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)

    website_url = Column(String, nullable=True)
    location = Column(String, nullable=True)

    status = Column(String, default="active")

    notes = Column(Text, nullable=True)

    declared_activity_nature = Column(String, nullable=True)
    activity_nature = Column(String, nullable=True)

    eligibility_status = Column(String, default="unclassified")
    eligibility_basis = Column(String, nullable=True)

    eligibility_review_source = Column(String, nullable=True)
    eligibility_review_reference = Column(Text, nullable=True)
    eligibility_review_notes = Column(Text, nullable=True)
    eligibility_reviewed_at = Column(DateTime, nullable=True)

    commerce_requirement = Column(String, default="unclassified")
    commerce_status = Column(String, default="unclassified")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class PartnerInquiry(Base):
    __tablename__ = "partner_inquiries"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)
    email = Column(String, nullable=False)

    interest_type = Column(String, default="affiliate")

    organization = Column(String, nullable=True)

    message = Column(Text, nullable=True)

    status = Column(String, default="new")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class AccountSecurityEvent(Base):
    __tablename__ = "account_security_events"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, nullable=True)
    email = Column(String, nullable=True)

    event_type = Column(String, nullable=False)
    status = Column(String, nullable=False)

    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class NginxSecurityEvent(Base):
    __tablename__ = "nginx_security_events"

    id = Column(Integer, primary_key=True, index=True)

    remote_ip = Column(String, nullable=True)
    request_method = Column(String, nullable=True)
    request_path = Column(Text, nullable=True)
    status_code = Column(Integer, nullable=True)

    user_agent = Column(Text, nullable=True)
    referer = Column(Text, nullable=True)

    country = Column(String, nullable=True)
    source = Column(String, default="nginx")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class NginxSecurityAlert(Base):
    __tablename__ = "nginx_security_alerts"

    id = Column(Integer, primary_key=True, index=True)

    severity = Column(String, nullable=False)
    alert_type = Column(String, nullable=False)
    message = Column(Text, nullable=False)

    remote_ip = Column(String, nullable=True)
    request_path = Column(Text, nullable=True)

    value = Column(Integer, nullable=True)
    threshold = Column(Integer, nullable=True)

    status = Column(String, default="open")
    source = Column(String, default="nginx_alerts_v5")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)


class NginxSecurityActivation(Base):
    __tablename__ = "nginx_security_activations"

    id = Column(Integer, primary_key=True, index=True)

    domain = Column(String, nullable=False)
    config_path = Column(Text, nullable=False)
    include_path = Column(Text, nullable=False)

    status = Column(String, default="active")
    notes = Column(Text, nullable=True)

    activated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class NginxAlertSuppression(Base):
    __tablename__ = "nginx_alert_suppressions"

    id = Column(Integer, primary_key=True, index=True)

    alert_type = Column(String, nullable=True)
    request_path = Column(Text, nullable=True)
    remote_ip = Column(String, nullable=True)

    status = Column(String, default="active")
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class NginxSecurityIncident(Base):
    __tablename__ = "nginx_security_incidents"

    id = Column(Integer, primary_key=True, index=True)

    alert_type = Column(String, nullable=False)
    severity = Column(String, nullable=False)

    status = Column(String, default="open")

    occurrences = Column(Integer, default=0)
    first_seen = Column(DateTime, nullable=True)
    last_seen = Column(DateTime, nullable=True)

    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)


class RescueProfile(Base):
    __tablename__ = "rescue_profiles"

    id = Column(Integer, primary_key=True, index=True)

    organization_name = Column(String, nullable=False)
    location = Column(String, nullable=True)
    contact_email = Column(String, nullable=True)

    story = Column(Text, nullable=True)

    status = Column(String, default="active")

    created_at = Column(DateTime, default=datetime.utcnow)


class RescueAnimal(Base):
    __tablename__ = "rescue_animals"

    id = Column(Integer, primary_key=True, index=True)

    rescue_profile_id = Column(Integer, nullable=True)

    animal_name = Column(String, nullable=False)

    species = Column(String, default="dog")

    story = Column(Text, nullable=True)

    adoption_status = Column(String, default="available")

    created_at = Column(DateTime, default=datetime.utcnow)


class FounderProfile(Base):
    __tablename__ = "founder_profiles"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, nullable=True)

    founder_type = Column(String, default="member")
    founder_level = Column(String, default="Founding Member")

    display_name = Column(String, nullable=False)
    organization_name = Column(String, nullable=True)

    message = Column(Text, nullable=True)

    status = Column(String, default="active")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class ContactRelayMessage(Base):
    __tablename__ = "contact_relay_messages"

    id = Column(Integer, primary_key=True, index=True)

    project = Column(String, default="PurPaws")

    source_context = Column(String, default="public_directory")
    source_listing_type = Column(String, nullable=True)
    source_listing_id = Column(Integer, nullable=True)

    recipient_type = Column(String, nullable=False)
    recipient_id = Column(Integer, nullable=True)

    sender_name = Column(String, nullable=False)
    sender_email = Column(String, nullable=True)
    sender_user_id = Column(Integer, nullable=True)

    subject = Column(String, nullable=True)
    message = Column(Text, nullable=False)

    status = Column(String, default="new")
    privacy_status = Column(String, default="relay_protected")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)


class CommunicationPermission(Base):
    __tablename__ = "communication_permissions"

    id = Column(Integer, primary_key=True, index=True)

    project = Column(String, default="PurPaws")

    listing_type = Column(String, nullable=False)
    listing_id = Column(Integer, nullable=True)

    allow_contact_relay = Column(Integer, default=1)

    allow_founder_inquiries = Column(Integer, default=1)
    allow_creator_inquiries = Column(Integer, default=1)
    allow_rescue_inquiries = Column(Integer, default=1)
    allow_partner_inquiries = Column(Integer, default=1)
    allow_organization_inquiries = Column(Integer, default=1)

    auto_accept = Column(Integer, default=0)

    status = Column(String, default="active")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=True)

class OnboardingRecord(Base):
    __tablename__ = "onboarding_records"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, nullable=True)

    path = Column(String, nullable=False)

    display_name = Column(String, nullable=True)
    email = Column(String, nullable=True)

    payload_json = Column(Text, nullable=True)

    status = Column(String, default="started")

    verification_status = Column(String, default="pending")
    verification_token = Column(String, nullable=True)
    verification_sent_at = Column(DateTime, nullable=True)
    verified_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=True)

