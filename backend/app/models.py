from pydantic import BaseModel


class MemorialCreate(BaseModel):
    companion_name: str
    years: str
    story: str
    archive_type: str = "Companion Memorial"
    project: str = "PurPaws"

from sqlalchemy import Column, Integer, String, Text

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

    status = Column(
        String,
        default="draft"
    )
