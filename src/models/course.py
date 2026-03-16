"""Course model and RoomType enum."""

from enum import Enum
from pydantic import BaseModel, Field, model_validator


class RoomType(str, Enum):
    LECTURE_HALL = "lecture_hall"
    LAB = "lab"
    SEMINAR = "seminar"
    COMPUTER_LAB = "computer_lab"
    AUDITORIUM = "auditorium"


class Course(BaseModel):
    id: str
    name: str
    subject: str
    department: str
    sessions_per_week: int = Field(default=1, ge=1)
    session_duration_slots: int = Field(default=1, ge=1)
    required_room_type: RoomType = RoomType.LECTURE_HALL
    student_group_id: str
    eligible_teacher_ids: list[str] = Field(default_factory=list)
    is_fixed: bool = False
    fixed_day: int | None = Field(default=None, ge=0, le=4)
    fixed_period: int | None = Field(default=None, ge=0, le=8)

    @model_validator(mode="after")
    def check_fixed_fields(self):
        if self.is_fixed and (self.fixed_day is None or self.fixed_period is None):
            raise ValueError(
                "fixed_day and fixed_period must be set when is_fixed is True"
            )
        return self
