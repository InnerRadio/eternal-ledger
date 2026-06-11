from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import AffiliateClick, AffiliateConversion, AffiliateCommission, AffiliateCampaign, AffiliateCampaignEnrollment, PartnerOrganization, OrganizationMember, User
from backend.app.cms.security import require_roles

router = APIRouter(prefix="/cms/affiliates", tags=["CMS Affiliates"])


ORGANIZATION_MEMBER_ROLES = [
    "owner",
    "manager",
    "analyst",
    "viewer",
]

ORGANIZATION_MEMBER_STATUSES = [
    "invited",
    "active",
    "suspended",
    "removed",
]


def serialize_organization_member(member: OrganizationMember):
    return {
        "id": member.id,
        "organization_id": member.organization_id,
        "user_id": member.user_id,
        "role": member.role,
        "status": member.status,
        "created_at": member.created_at,
    }


ORGANIZATION_STATUSES = [
    "active",
    "pending_review",
    "paused",
    "archived",
]


def serialize_partner_organization(org: PartnerOrganization):
    return {
        "id": org.id,
        "organization_name": org.organization_name,
        "organization_type": org.organization_type,
        "project": org.project,
        "contact_name": org.contact_name,
        "contact_email": org.contact_email,
        "website_url": org.website_url,
        "location": org.location,
        "status": org.status,
        "notes": org.notes,
        "created_at": org.created_at,
    }


def change_partner_organization_status(
    organization_id: int,
    status: str,
    db: Session
):
    if status not in ORGANIZATION_STATUSES:
        return {
            "module": "CMS Partner Organizations",
            "status": "error",
            "message": "Invalid organization status.",
            "allowed_statuses": ORGANIZATION_STATUSES,
        }

    org = db.query(PartnerOrganization).filter(
        PartnerOrganization.id == organization_id
    ).first()

    if not org:
        return {
            "module": "CMS Partner Organizations",
            "status": "error",
            "message": "Organization not found.",
        }

    org.status = status

    db.commit()
    db.refresh(org)

    return {
        "module": "CMS Partner Organizations",
        "status": "updated",
        "record": serialize_partner_organization(org)
    }


ENROLLMENT_STATUSES = [
    "active",
    "paused",
    "removed",
]


def serialize_campaign_enrollment(enrollment: AffiliateCampaignEnrollment):
    return {
        "id": enrollment.id,
        "campaign_id": enrollment.campaign_id,
        "affiliate_id": enrollment.affiliate_id,
        "referral_code": enrollment.referral_code,
        "user_id": enrollment.user_id,
        "status": enrollment.status,
        "joined_at": enrollment.joined_at,
    }


def change_campaign_enrollment_status(
    enrollment_id: int,
    status: str,
    db: Session
):
    if status not in ENROLLMENT_STATUSES:
        return {
            "module": "CMS Affiliate Campaign Enrollments",
            "status": "error",
            "message": "Invalid enrollment status.",
            "allowed_statuses": ENROLLMENT_STATUSES,
        }

    enrollment = db.query(AffiliateCampaignEnrollment).filter(
        AffiliateCampaignEnrollment.id == enrollment_id
    ).first()

    if not enrollment:
        return {
            "module": "CMS Affiliate Campaign Enrollments",
            "status": "error",
            "message": "Enrollment not found.",
        }

    enrollment.status = status

    db.commit()
    db.refresh(enrollment)

    return {
        "module": "CMS Affiliate Campaign Enrollments",
        "status": "updated",
        "record": serialize_campaign_enrollment(enrollment)
    }


CAMPAIGN_STATUSES = [
    "draft",
    "active",
    "paused",
    "ended",
    "archived",
]


def serialize_campaign(campaign: AffiliateCampaign):
    return {
        "id": campaign.id,
        "campaign_id": campaign.campaign_id,
        "project": campaign.project,
        "title": campaign.title,
        "description": campaign.description,
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
    }


def change_campaign_status(
    campaign_id: str,
    status: str,
    db: Session
):
    if status not in CAMPAIGN_STATUSES:
        return {
            "module": "CMS Affiliate Campaigns",
            "status": "error",
            "message": "Invalid campaign status.",
            "allowed_statuses": CAMPAIGN_STATUSES,
        }

    campaign = db.query(AffiliateCampaign).filter(
        AffiliateCampaign.campaign_id == campaign_id
    ).first()

    if not campaign:
        return {
            "module": "CMS Affiliate Campaigns",
            "status": "error",
            "message": "Campaign not found.",
        }

    campaign.status = status

    db.commit()
    db.refresh(campaign)

    return {
        "module": "CMS Affiliate Campaigns",
        "status": "updated",
        "record": serialize_campaign(campaign)
    }


COMMISSION_STATUSES = [
    "pending",
    "approved",
    "payable",
    "paid",
    "cancelled",
    "void",
]


def serialize_commission(commission: AffiliateCommission):
    return {
        "id": commission.id,
        "conversion_id": commission.conversion_id,
        "affiliate_id": commission.affiliate_id,
        "referral_code": commission.referral_code,
        "project": commission.project,
        "commission_type": commission.commission_type,
        "amount_cents": commission.amount_cents,
        "currency": commission.currency,
        "status": commission.status,
        "notes": commission.notes,
        "created_at": commission.created_at,
    }


def change_commission_status(
    commission_id: int,
    status: str,
    db: Session
):
    if status not in COMMISSION_STATUSES:
        return {
            "module": "CMS Affiliate Commissions",
            "status": "error",
            "message": "Invalid commission status.",
            "allowed_statuses": COMMISSION_STATUSES,
        }

    commission = db.query(AffiliateCommission).filter(
        AffiliateCommission.id == commission_id
    ).first()

    if not commission:
        return {
            "module": "CMS Affiliate Commissions",
            "status": "error",
            "message": "Commission not found.",
        }

    commission.status = status

    db.commit()
    db.refresh(commission)

    return {
        "module": "CMS Affiliate Commissions",
        "status": "updated",
        "record": serialize_commission(commission)
    }


@router.get("/organizations/{organization_id}/members")
def list_organization_members(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    members = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == organization_id
    ).order_by(OrganizationMember.id.desc()).all()

    return {
        "module": "CMS Organization Members",
        "status": "active",
        "organization_id": organization_id,
        "count": len(members),
        "records": [
            serialize_organization_member(member)
            for member in members
        ]
    }


@router.post("/organizations/{organization_id}/members/add")
def add_organization_member(
    organization_id: int,
    user_id: int,
    role: str = "viewer",
    status: str = "active",
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    if role not in ORGANIZATION_MEMBER_ROLES:
        return {
            "module": "CMS Organization Members",
            "status": "error",
            "message": "Invalid organization member role.",
            "allowed_roles": ORGANIZATION_MEMBER_ROLES,
        }

    if status not in ORGANIZATION_MEMBER_STATUSES:
        return {
            "module": "CMS Organization Members",
            "status": "error",
            "message": "Invalid organization member status.",
            "allowed_statuses": ORGANIZATION_MEMBER_STATUSES,
        }

    org = db.query(PartnerOrganization).filter(
        PartnerOrganization.id == organization_id
    ).first()

    if not org:
        return {
            "module": "CMS Organization Members",
            "status": "error",
            "message": "Organization not found.",
        }

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return {
            "module": "CMS Organization Members",
            "status": "error",
            "message": "User not found.",
        }

    existing = db.query(OrganizationMember).filter(
        OrganizationMember.organization_id == organization_id,
        OrganizationMember.user_id == user_id
    ).first()

    if existing:
        return {
            "module": "CMS Organization Members",
            "status": "error",
            "message": "User is already attached to this organization.",
            "record": serialize_organization_member(existing),
        }

    member = OrganizationMember(
        organization_id=organization_id,
        user_id=user_id,
        role=role,
        status=status
    )

    db.add(member)
    db.commit()
    db.refresh(member)

    return {
        "module": "CMS Organization Members",
        "status": "created",
        "record": serialize_organization_member(member)
    }


@router.get("/organizations")
def list_partner_organizations(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    orgs = db.query(PartnerOrganization).order_by(
        PartnerOrganization.created_at.desc()
    ).all()

    return {
        "module": "CMS Partner Organizations",
        "status": "active",
        "count": len(orgs),
        "records": [
            serialize_partner_organization(org)
            for org in orgs
        ]
    }


@router.post("/organizations/create")
def create_partner_organization(
    organization_name: str,
    organization_type: str = "other",
    project: str = "PurPaws",
    contact_name: str | None = None,
    contact_email: str | None = None,
    website_url: str | None = None,
    location: str | None = None,
    status: str = "active",
    notes: str | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    if status not in ORGANIZATION_STATUSES:
        return {
            "module": "CMS Partner Organizations",
            "status": "error",
            "message": "Invalid organization status.",
            "allowed_statuses": ORGANIZATION_STATUSES,
        }

    org = PartnerOrganization(
        organization_name=organization_name,
        organization_type=organization_type,
        project=project,
        contact_name=contact_name,
        contact_email=contact_email,
        website_url=website_url,
        location=location,
        status=status,
        notes=notes
    )

    db.add(org)
    db.commit()
    db.refresh(org)

    return {
        "module": "CMS Partner Organizations",
        "status": "created",
        "record": serialize_partner_organization(org)
    }


@router.post("/organizations/{organization_id}/active")
def activate_partner_organization(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    return change_partner_organization_status(
        organization_id=organization_id,
        status="active",
        db=db
    )


@router.post("/organizations/{organization_id}/pending-review")
def pending_review_partner_organization(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    return change_partner_organization_status(
        organization_id=organization_id,
        status="pending_review",
        db=db
    )


@router.post("/organizations/{organization_id}/pause")
def pause_partner_organization(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    return change_partner_organization_status(
        organization_id=organization_id,
        status="paused",
        db=db
    )


@router.post("/organizations/{organization_id}/archive")
def archive_partner_organization(
    organization_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    return change_partner_organization_status(
        organization_id=organization_id,
        status="archived",
        db=db
    )


@router.get("/enrollments")
def list_affiliate_campaign_enrollments(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    enrollments = db.query(AffiliateCampaignEnrollment).order_by(
        AffiliateCampaignEnrollment.joined_at.desc()
    ).all()

    return {
        "module": "CMS Affiliate Campaign Enrollments",
        "status": "active",
        "count": len(enrollments),
        "records": [
            serialize_campaign_enrollment(enrollment)
            for enrollment in enrollments
        ]
    }


@router.post("/enrollments/create")
def create_affiliate_campaign_enrollment(
    campaign_id: str,
    affiliate_id: str | None = None,
    referral_code: str | None = None,
    user_id: int | None = None,
    status: str = "active",
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    if status not in ENROLLMENT_STATUSES:
        return {
            "module": "CMS Affiliate Campaign Enrollments",
            "status": "error",
            "message": "Invalid enrollment status.",
            "allowed_statuses": ENROLLMENT_STATUSES,
        }

    campaign = db.query(AffiliateCampaign).filter(
        AffiliateCampaign.campaign_id == campaign_id
    ).first()

    if not campaign:
        return {
            "module": "CMS Affiliate Campaign Enrollments",
            "status": "error",
            "message": "Campaign not found.",
        }

    existing = db.query(AffiliateCampaignEnrollment).filter(
        AffiliateCampaignEnrollment.campaign_id == campaign_id,
        AffiliateCampaignEnrollment.referral_code == referral_code
    ).first()

    if existing:
        return {
            "module": "CMS Affiliate Campaign Enrollments",
            "status": "error",
            "message": "Affiliate is already enrolled in this campaign.",
            "record": serialize_campaign_enrollment(existing),
        }

    enrollment = AffiliateCampaignEnrollment(
        campaign_id=campaign_id,
        affiliate_id=affiliate_id,
        referral_code=referral_code,
        user_id=user_id,
        status=status
    )

    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)

    return {
        "module": "CMS Affiliate Campaign Enrollments",
        "status": "created",
        "record": serialize_campaign_enrollment(enrollment)
    }


@router.post("/enrollments/{enrollment_id}/active")
def activate_affiliate_campaign_enrollment(
    enrollment_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    return change_campaign_enrollment_status(
        enrollment_id=enrollment_id,
        status="active",
        db=db
    )


@router.post("/enrollments/{enrollment_id}/pause")
def pause_affiliate_campaign_enrollment(
    enrollment_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    return change_campaign_enrollment_status(
        enrollment_id=enrollment_id,
        status="paused",
        db=db
    )


@router.post("/enrollments/{enrollment_id}/remove")
def remove_affiliate_campaign_enrollment(
    enrollment_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    return change_campaign_enrollment_status(
        enrollment_id=enrollment_id,
        status="removed",
        db=db
    )


@router.get("/campaigns")
def list_affiliate_campaigns(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    campaigns = db.query(AffiliateCampaign).order_by(
        AffiliateCampaign.created_at.desc()
    ).all()

    return {
        "module": "CMS Affiliate Campaigns",
        "status": "active",
        "count": len(campaigns),
        "records": [
            serialize_campaign(campaign)
            for campaign in campaigns
        ]
    }


@router.post("/campaigns/create")
def create_affiliate_campaign(
    campaign_id: str,
    title: str,
    project: str = "PurPaws",
    description: str | None = None,
    campaign_type: str = "general",
    sponsor_name: str | None = None,
    payout_type: str = "flat",
    payout_amount_cents: int = 0,
    payout_percent: str | None = None,
    currency: str = "CAD",
    status: str = "active",
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    if status not in CAMPAIGN_STATUSES:
        return {
            "module": "CMS Affiliate Campaigns",
            "status": "error",
            "message": "Invalid campaign status.",
            "allowed_statuses": CAMPAIGN_STATUSES,
        }

    existing = db.query(AffiliateCampaign).filter(
        AffiliateCampaign.campaign_id == campaign_id
    ).first()

    if existing:
        return {
            "module": "CMS Affiliate Campaigns",
            "status": "error",
            "message": "Campaign already exists.",
            "record": serialize_campaign(existing)
        }

    campaign = AffiliateCampaign(
        campaign_id=campaign_id,
        project=project,
        title=title,
        description=description,
        campaign_type=campaign_type,
        sponsor_name=sponsor_name,
        payout_type=payout_type,
        payout_amount_cents=payout_amount_cents,
        payout_percent=payout_percent,
        currency=currency,
        status=status
    )

    db.add(campaign)
    db.commit()
    db.refresh(campaign)

    return {
        "module": "CMS Affiliate Campaigns",
        "status": "created",
        "record": serialize_campaign(campaign)
    }


@router.post("/campaigns/{campaign_id}/active")
def activate_affiliate_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    return change_campaign_status(
        campaign_id=campaign_id,
        status="active",
        db=db
    )


@router.post("/campaigns/{campaign_id}/pause")
def pause_affiliate_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    return change_campaign_status(
        campaign_id=campaign_id,
        status="paused",
        db=db
    )


@router.post("/campaigns/{campaign_id}/end")
def end_affiliate_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    return change_campaign_status(
        campaign_id=campaign_id,
        status="ended",
        db=db
    )


@router.post("/campaigns/{campaign_id}/archive")
def archive_affiliate_campaign(
    campaign_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    return change_campaign_status(
        campaign_id=campaign_id,
        status="archived",
        db=db
    )


@router.get("/commissions")
def list_affiliate_commissions(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    commissions = db.query(AffiliateCommission).order_by(
        AffiliateCommission.created_at.desc()
    ).all()

    return {
        "module": "CMS Affiliate Commissions",
        "status": "active",
        "count": len(commissions),
        "records": [
            serialize_commission(commission)
            for commission in commissions
        ]
    }


@router.post("/commissions/create")
def create_affiliate_commission(
    conversion_id: int | None = None,
    affiliate_id: str | None = None,
    referral_code: str | None = None,
    project: str = "PurPaws",
    commission_type: str = "signup",
    amount_cents: int = 0,
    currency: str = "CAD",
    status: str = "pending",
    notes: str | None = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    if status not in COMMISSION_STATUSES:
        return {
            "module": "CMS Affiliate Commissions",
            "status": "error",
            "message": "Invalid commission status.",
            "allowed_statuses": COMMISSION_STATUSES,
        }

    commission = AffiliateCommission(
        conversion_id=conversion_id,
        affiliate_id=affiliate_id,
        referral_code=referral_code,
        project=project,
        commission_type=commission_type,
        amount_cents=amount_cents,
        currency=currency,
        status=status,
        notes=notes
    )

    db.add(commission)
    db.commit()
    db.refresh(commission)

    return {
        "module": "CMS Affiliate Commissions",
        "status": "created",
        "record": serialize_commission(commission)
    }


@router.post("/commissions/{commission_id}/approve")
def approve_affiliate_commission(
    commission_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    return change_commission_status(
        commission_id=commission_id,
        status="approved",
        db=db
    )


@router.post("/commissions/{commission_id}/payable")
def payable_affiliate_commission(
    commission_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    return change_commission_status(
        commission_id=commission_id,
        status="payable",
        db=db
    )


@router.post("/commissions/{commission_id}/paid")
def paid_affiliate_commission(
    commission_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    return change_commission_status(
        commission_id=commission_id,
        status="paid",
        db=db
    )


@router.post("/commissions/{commission_id}/void")
def void_affiliate_commission(
    commission_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    return change_commission_status(
        commission_id=commission_id,
        status="void",
        db=db
    )


@router.get("/clicks")
def list_affiliate_clicks(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    clicks = db.query(AffiliateClick).order_by(AffiliateClick.created_at.desc()).all()

    return {
        "module": "CMS Affiliates",
        "status": "active",
        "count": len(clicks),
        "records": [
            {
                "id": click.id,
                "affiliate_id": click.affiliate_id,
                "referral_code": click.referral_code,
                "campaign_id": click.campaign_id,
                "ad_id": click.ad_id,
                "source_url": click.source_url,
                "destination_url": click.destination_url,
                "ip_address": click.ip_address,
                "user_agent": click.user_agent,
                "created_at": click.created_at,
            }
            for click in clicks
        ]
    }


@router.get("/conversions")
def list_affiliate_conversions(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer"))
):
    conversions = db.query(AffiliateConversion).order_by(AffiliateConversion.created_at.desc()).all()

    return {
        "module": "CMS Affiliate Conversions",
        "status": "active",
        "count": len(conversions),
        "records": [
            {
                "id": conversion.id,
                "affiliate_id": conversion.affiliate_id,
                "referral_code": conversion.referral_code,
                "conversion_type": conversion.conversion_type,
                "target_type": conversion.target_type,
                "target_id": conversion.target_id,
                "status": conversion.status,
                "created_at": conversion.created_at,
            }
            for conversion in conversions
        ]
    }


@router.post("/track-click")
def track_affiliate_click(
    request: Request,
    affiliate_id: str | None = None,
    referral_code: str | None = None,
    campaign_id: str | None = None,
    ad_id: str | None = None,
    destination_url: str | None = None,
    db: Session = Depends(get_db)
):
    click = AffiliateClick(
        affiliate_id=affiliate_id,
        referral_code=referral_code,
        campaign_id=campaign_id,
        ad_id=ad_id,
        source_url=str(request.headers.get("referer") or ""),
        destination_url=destination_url,
        ip_address=request.client.host if request.client else None,
        user_agent=str(request.headers.get("user-agent") or ""),
    )

    db.add(click)
    db.commit()
    db.refresh(click)

    return {
        "module": "Affiliate Tracking",
        "status": "tracked",
        "record": {
            "id": click.id,
            "affiliate_id": click.affiliate_id,
            "referral_code": click.referral_code,
            "campaign_id": click.campaign_id,
            "ad_id": click.ad_id,
            "destination_url": click.destination_url,
            "created_at": click.created_at,
        }
    }


@router.get("/partner-inquiries")
def list_partner_inquiries(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    from backend.app.models import PartnerInquiry

    inquiries = db.query(PartnerInquiry)\
        .order_by(PartnerInquiry.created_at.desc())\
        .all()

    return {
        "module": "Partner Inquiries",
        "status": "active",
        "count": len(inquiries),
        "records": [
            {
                "id": inquiry.id,
                "name": inquiry.name,
                "email": inquiry.email,
                "interest_type": inquiry.interest_type,
                "organization": inquiry.organization,
                "message": inquiry.message,
                "status": inquiry.status,
                "created_at": inquiry.created_at
            }
            for inquiry in inquiries
        ]
    }


@router.post("/partner-inquiries/{inquiry_id}/status")
def update_partner_inquiry_status(
    inquiry_id: int,
    status: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    from backend.app.models import PartnerInquiry

    inquiry = db.query(PartnerInquiry)\
        .filter(PartnerInquiry.id == inquiry_id)\
        .first()

    if not inquiry:
        return {
            "status": "error",
            "message": "Inquiry not found"
        }

    inquiry.status = status

    if status in ["approved", "partner", "affiliate", "sponsor"]:
        conversion = AffiliateConversion(
            affiliate_id=None,
            referral_code=None,
            conversion_type=f"partner_inquiry_{status}",
            target_type="partner_inquiry",
            target_id=inquiry.id,
            status="approved"
        )

        db.add(conversion)

    db.commit()
    db.refresh(inquiry)

    return {
        "module": "Partner Inquiry Status",
        "status": "updated",
        "record": {
            "id": inquiry.id,
            "name": inquiry.name,
            "email": inquiry.email,
            "interest_type": inquiry.interest_type,
            "status": inquiry.status,
            "updated": True
        }
    }


@router.post("/conversions/log")
def log_affiliate_conversion(
    affiliate_id: str | None = None,
    referral_code: str | None = None,
    conversion_type: str = "partner_inquiry",
    target_type: str | None = None,
    target_id: int | None = None,
    status: str = "pending",
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_roles("super_admin", "admin", "developer", "reviewer"))
):
    conversion = AffiliateConversion(
        affiliate_id=affiliate_id,
        referral_code=referral_code,
        conversion_type=conversion_type,
        target_type=target_type,
        target_id=target_id,
        status=status
    )

    db.add(conversion)
    db.commit()
    db.refresh(conversion)

    return {
        "module": "Affiliate Conversion",
        "status": "logged",
        "record": {
            "id": conversion.id,
            "affiliate_id": conversion.affiliate_id,
            "referral_code": conversion.referral_code,
            "conversion_type": conversion.conversion_type,
            "target_type": conversion.target_type,
            "target_id": conversion.target_id,
            "status": conversion.status,
            "created_at": conversion.created_at
        }
    }
