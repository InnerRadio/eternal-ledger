from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import PartnerInquiry, PartnerInquiryCreate, Memorial, MemorialCreate

router = APIRouter(tags=["Partner Inquiries"])


@router.post("/public/partner-inquiry")
def public_partner_inquiry(
    inquiry: PartnerInquiryCreate,
    db: Session = Depends(get_db)
):
    record = PartnerInquiry(
        name=inquiry.name,
        email=inquiry.email,
        interest_type=inquiry.interest_type,
        organization=inquiry.organization,
        message=inquiry.message,
        status="new"
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return {
        "module": "Partner Inquiry",
        "status": "submitted",
        "record": {
            "id": record.id,
            "name": record.name,
            "email": record.email,
            "interest_type": record.interest_type,
            "status": record.status,
            "created_at": record.created_at
        }
    }



@router.post("/public/memorial-intake")
def public_memorial_intake(
    memorial_data: MemorialCreate,
    db: Session = Depends(get_db)
):
    memorial = Memorial(
        companion_name=memorial_data.companion_name,
        years=memorial_data.years,
        story=memorial_data.story,
        archive_type=memorial_data.archive_type,
        project=memorial_data.project,
        environment_theme=memorial_data.environment_theme,
        atmosphere_intensity=memorial_data.atmosphere_intensity,
        status="draft"
    )

    db.add(memorial)
    db.commit()
    db.refresh(memorial)

    return {
        "module": "Public Memorial Intake",
        "status": "submitted_for_review",
        "record": {
            "id": memorial.id,
            "companion_name": memorial.companion_name,
            "years": memorial.years,
            "archive_type": memorial.archive_type,
            "project": memorial.project,
            "environment_theme": memorial.environment_theme,
            "atmosphere_intensity": memorial.atmosphere_intensity,
            "status": memorial.status,
            "created": True
        }
    }
