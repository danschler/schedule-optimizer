"""Schedule models for optimizer output."""

from pydantic import BaseModel, Field
from .teacher import Teacher
from .course import Course
from .room import Room
from .building import Building
from .student_group import StudentGroup


class ScheduleAssignment(BaseModel):
    course_id: str
    teacher_id: str
    room_id: str
    day: int
    period: int


class Schedule(BaseModel):
    assignments: list[ScheduleAssignment] = Field(default_factory=list)
    status: str = "unsolved"
    objective_value: float = 0.0


class ScheduleData(BaseModel):
    teachers: list[Teacher] = Field(default_factory=list)
    courses: list[Course] = Field(default_factory=list)
    rooms: list[Room] = Field(default_factory=list)
    buildings: list[Building] = Field(default_factory=list)
    student_groups: list[StudentGroup] = Field(default_factory=list)
