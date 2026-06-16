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

from sqlalchemy import Column, Integer, String, Text, DateTime
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

    status = Column(String, default="draft")

    ipfs_cid = Column(String, nullable=True)
    xrpl_tx_hash = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


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
