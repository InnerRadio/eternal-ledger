from pydantic import BaseModel


class MemorialCreate(BaseModel):
    companion_name: str
    years: str
    story: str
    archive_type: str = "Companion Memorial"
    project: str = "PurPaws"




class UserCreate(BaseModel):
    email: str
    password: str
    role: str = "admin"


class UserLogin(BaseModel):
    email: str
    password: str

class MemorialUpdate(BaseModel):
    companion_name: str | None = None
    years: str | None = None
    story: str | None = None
    archive_type: str | None = None
    project: str | None = None
    status: str | None = None

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


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    role = Column(String, default="admin")
    status = Column(String, default="active")
