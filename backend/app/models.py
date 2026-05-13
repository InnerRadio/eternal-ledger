from pydantic import BaseModel


class MemorialCreate(BaseModel):
    companion_name: str
    years: str
    story: str
    archive_type: str = "Companion Memorial"
    project: str = "PurPaws"
