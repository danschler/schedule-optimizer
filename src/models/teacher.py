"""Teacher model."""

from pydantic import BaseModel, Field


class Teacher(BaseModel):
    id: str
    name: str
    department: str
    subjects_can_teach: list[str] = Field(default_factory=list)
    availability: dict[int, list[int]] = Field(
        default_factory=dict,
        description="Day index -> list of available period indices"
    )
    max_hours_day: int = Field(default=6, ge=1)
    max_hours_week: int = Field(default=20, ge=1)
    preferred_days_off: list[int] = Field(default_factory=list)
    preferred_time_slots: list[int] = Field(
        default_factory=list,
        description="List of preferred period indices (0-8)"
    )
