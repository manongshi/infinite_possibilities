from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_url: str
    name: str
    group_name: str
    source_type: str
    format: str
    enabled: bool
    weight: int
    sort_order: int
    remark: str
    updated_at: datetime | None = None


class EnabledIn(BaseModel):
    enabled: bool


class ImportResult(BaseModel):
    created: int
    updated: int
    errors: list[str]
    sources: list[SourceOut]


class ImportUrlIn(BaseModel):
    url: str
