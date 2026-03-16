"""Constraint configuration and pre-filtering helpers for the schedule optimizer."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.models.course import Course, RoomType
from src.models.room import Room
from src.models.student_group import StudentGroup
from src.models.teacher import Teacher
from src.models.time_slot import DAYS, PERIODS_PER_DAY, slot_index


@dataclass
class ConstraintConfig:
    """Configuration for soft constraint weights."""

    student_gaps: float = 3.0
    teacher_gaps: float = 2.0
    building_travel: float = 4.0
    even_distribution: float = 2.0
    lunch_breaks: float = 5.0
    morning_core: float = 1.0
    no_same_subject_twice: float = 3.0
    teacher_day_off: float = 2.0
    back_to_back_limit: float = 3.0
    even_workload: float = 1.0

    def as_dict(self) -> dict[str, float]:
        """Return all weights as a dictionary."""
        return {
            "student_gaps": self.student_gaps,
            "teacher_gaps": self.teacher_gaps,
            "building_travel": self.building_travel,
            "even_distribution": self.even_distribution,
            "lunch_breaks": self.lunch_breaks,
            "morning_core": self.morning_core,
            "no_same_subject_twice": self.no_same_subject_twice,
            "teacher_day_off": self.teacher_day_off,
            "back_to_back_limit": self.back_to_back_limit,
            "even_workload": self.even_workload,
        }

    @classmethod
    def from_dict(cls, d: dict[str, float]) -> ConstraintConfig:
        """Create a ConstraintConfig from a dictionary, ignoring unknown keys."""
        known_fields = {
            "student_gaps", "teacher_gaps", "building_travel",
            "even_distribution", "lunch_breaks", "morning_core",
            "no_same_subject_twice", "teacher_day_off",
            "back_to_back_limit", "even_workload",
        }
        filtered = {k: v for k, v in d.items() if k in known_fields}
        return cls(**filtered)


# ---------------------------------------------------------------------------
# Pre-filtering helpers
# ---------------------------------------------------------------------------

def get_eligible_rooms(
    course: Course,
    rooms: list[Room],
    student_groups: dict[str, StudentGroup],
) -> list[Room]:
    """Filter rooms by room_type match and capacity >= group size."""
    group = student_groups.get(course.student_group_id)
    min_capacity = group.size if group else 0
    return [
        r for r in rooms
        if r.room_type == course.required_room_type and r.capacity >= min_capacity
    ]


def get_eligible_slots(
    course: Course,
    teacher: Teacher,
    days: int = DAYS,
    periods_per_day: int = PERIODS_PER_DAY,
) -> list[int]:
    """Filter slot indices where teacher is available and course fits.

    For multi-slot sessions (duration > 1), the returned slot is the *start*
    slot. All consecutive slots (start .. start + duration - 1) must be on the
    same day and the teacher must be available for every one of them.

    If the course is fixed to a specific day/period, only that single slot is
    returned (provided the teacher is available).
    """
    duration = course.session_duration_slots

    # If course is fixed, return only the fixed slot (if teacher available)
    if course.is_fixed and course.fixed_day is not None and course.fixed_period is not None:
        day = course.fixed_day
        period = course.fixed_period
        available_periods = set(teacher.availability.get(day, []))
        # Check all periods the session would occupy
        for dp in range(duration):
            p = period + dp
            if p >= periods_per_day or p not in available_periods:
                return []
        return [slot_index(day, period)]

    eligible: list[int] = []
    for day in range(days):
        available_periods = set(teacher.availability.get(day, []))
        for period in range(periods_per_day):
            # Check that all slots the session occupies fit in the same day
            # and the teacher is available for each
            if period + duration > periods_per_day:
                continue
            all_available = True
            for dp in range(duration):
                if (period + dp) not in available_periods:
                    all_available = False
                    break
            if all_available:
                eligible.append(slot_index(day, period))
    return eligible


def get_eligible_teachers(
    course: Course,
    teachers: list[Teacher],
) -> list[Teacher]:
    """Filter teachers whose subjects_can_teach includes course.subject
    and who are in eligible_teacher_ids."""
    eligible_ids = set(course.eligible_teacher_ids) if course.eligible_teacher_ids else None
    result: list[Teacher] = []
    for t in teachers:
        if eligible_ids is not None and t.id not in eligible_ids:
            continue
        if course.subject in t.subjects_can_teach:
            result.append(t)
    return result
