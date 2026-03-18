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
    session_index: int = 0


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

    def validate_references(self) -> list[str]:
        """Check referential integrity across entities.

        Returns a list of human-readable error messages. An empty list means
        all references are valid.
        """
        errors: list[str] = []
        teacher_ids = {t.id for t in self.teachers}
        course_ids = {c.id for c in self.courses}
        room_ids = {r.id for r in self.rooms}
        building_ids = {b.id for b in self.buildings}
        group_ids = {g.id for g in self.student_groups}

        for course in self.courses:
            if course.student_group_id not in group_ids:
                errors.append(
                    f"Course '{course.name}' references unknown student group "
                    f"'{course.student_group_id}'"
                )
            for tid in course.eligible_teacher_ids:
                if tid not in teacher_ids:
                    errors.append(
                        f"Course '{course.name}' references unknown teacher '{tid}'"
                    )

        for room in self.rooms:
            if room.building_id not in building_ids:
                errors.append(
                    f"Room '{room.name}' references unknown building "
                    f"'{room.building_id}'"
                )

        for group in self.student_groups:
            for cid in group.required_course_ids:
                if cid not in course_ids:
                    errors.append(
                        f"Student group '{group.name}' references unknown "
                        f"course '{cid}'"
                    )

        return errors
