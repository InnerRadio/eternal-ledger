from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models import PartnerInquiry, PartnerInquiryCreate

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
