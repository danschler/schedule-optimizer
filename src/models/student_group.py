"""Student group model."""

from pydantic import BaseModel, Field


class StudentGroup(BaseModel):
    id: str
    name: str
    size: int = Field(ge=1)
    required_course_ids: list[str] = Field(default_factory=list)
