"""Tests for Pydantic models, time slot helpers, and JSON roundtrip."""

import pytest
from pydantic import ValidationError

from src.models import (
    DAYS,
    PERIODS_PER_DAY,
    TOTAL_SLOTS,
    Building,
    Course,
    Room,
    RoomType,
    Schedule,
    ScheduleAssignment,
    ScheduleData,
    StudentGroup,
    Teacher,
    format_slot,
    slot_index,
    slot_to_day_period,
)


# ---------------------------------------------------------------------------
# Time slot helpers
# ---------------------------------------------------------------------------

class TestTimeSlotConstants:
    def test_total_slots_equals_days_times_periods(self):
        assert TOTAL_SLOTS == DAYS * PERIODS_PER_DAY

    def test_days_is_five(self):
        assert DAYS == 5

    def test_periods_per_day_is_nine(self):
        assert PERIODS_PER_DAY == 9


class TestSlotIndex:
    def test_slot_index_origin(self):
        assert slot_index(0, 0) == 0

    def test_slot_index_second_day_first_period(self):
        assert slot_index(1, 0) == PERIODS_PER_DAY

    def test_slot_index_last_slot(self):
        assert slot_index(DAYS - 1, PERIODS_PER_DAY - 1) == TOTAL_SLOTS - 1


class TestSlotToDayPeriod:
    def test_slot_zero(self):
        assert slot_to_day_period(0) == (0, 0)

    def test_slot_nine(self):
        assert slot_to_day_period(9) == (1, 0)

    def test_roundtrip(self):
        for s in range(TOTAL_SLOTS):
            day, period = slot_to_day_period(s)
            assert slot_index(day, period) == s


class TestFormatSlot:
    def test_format_slot_zero(self):
        formatted = format_slot(0)
        assert "Mon" in formatted
        assert "8:00" in formatted

    def test_format_slot_nine(self):
        formatted = format_slot(9)
        assert "Tue" in formatted
        assert "8:00" in formatted


# ---------------------------------------------------------------------------
# Pydantic validation
# ---------------------------------------------------------------------------

class TestRoomValidation:
    def test_reject_zero_capacity(self):
        with pytest.raises(ValidationError):
            Room(id="r1", name="Bad Room", building_id="b1", capacity=0)

    def test_reject_negative_capacity(self):
        with pytest.raises(ValidationError):
            Room(id="r1", name="Bad Room", building_id="b1", capacity=-5)

    def test_valid_room(self):
        room = Room(id="r1", name="Good Room", building_id="b1", capacity=30)
        assert room.capacity == 30


class TestCourseValidation:
    def test_reject_invalid_room_type(self):
        with pytest.raises(ValidationError):
            Course(
                id="c1", name="Bad", subject="x", department="d",
                required_room_type="nonexistent_type",
                student_group_id="sg1",
            )

    def test_reject_zero_sessions(self):
        with pytest.raises(ValidationError):
            Course(
                id="c1", name="Bad", subject="x", department="d",
                sessions_per_week=0,
                student_group_id="sg1",
            )

    def test_reject_zero_duration(self):
        with pytest.raises(ValidationError):
            Course(
                id="c1", name="Bad", subject="x", department="d",
                session_duration_slots=0,
                student_group_id="sg1",
            )

    def test_valid_course(self):
        course = Course(
            id="c1", name="Good", subject="math", department="Math",
            sessions_per_week=2, session_duration_slots=1,
            student_group_id="sg1",
        )
        assert course.required_room_type == RoomType.LECTURE_HALL


class TestStudentGroupValidation:
    def test_reject_zero_size(self):
        with pytest.raises(ValidationError):
            StudentGroup(id="sg1", name="Bad", size=0)

    def test_reject_negative_size(self):
        with pytest.raises(ValidationError):
            StudentGroup(id="sg1", name="Bad", size=-1)


class TestTeacherValidation:
    def test_reject_zero_max_hours_day(self):
        with pytest.raises(ValidationError):
            Teacher(
                id="t1", name="Bad", department="CS",
                max_hours_day=0,
            )

    def test_reject_zero_max_hours_week(self):
        with pytest.raises(ValidationError):
            Teacher(
                id="t1", name="Bad", department="CS",
                max_hours_week=0,
            )


# ---------------------------------------------------------------------------
# JSON roundtrip
# ---------------------------------------------------------------------------

class TestScheduleDataRoundtrip:
    def test_json_roundtrip(self):
        data = ScheduleData(
            teachers=[
                Teacher(id="t1", name="Alice", department="CS",
                        subjects_can_teach=["math"],
                        availability={0: [0, 1, 2]}),
            ],
            courses=[
                Course(id="c1", name="Math 101", subject="math",
                       department="Math", student_group_id="sg1"),
            ],
            rooms=[
                Room(id="r1", name="Room A", building_id="b1", capacity=30),
            ],
            buildings=[
                Building(id="b1", name="Main", travel_time_to={"b1": 0}),
            ],
            student_groups=[
                StudentGroup(id="sg1", name="Group 1", size=25,
                             required_course_ids=["c1"]),
            ],
        )

        json_str = data.model_dump_json()
        restored = ScheduleData.model_validate_json(json_str)

        assert len(restored.teachers) == 1
        assert restored.teachers[0].id == "t1"
        assert len(restored.courses) == 1
        assert restored.courses[0].id == "c1"
        assert len(restored.rooms) == 1
        assert restored.rooms[0].capacity == 30
        assert len(restored.buildings) == 1
        assert len(restored.student_groups) == 1
        assert restored.student_groups[0].size == 25

    def test_schedule_json_roundtrip(self):
        schedule = Schedule(
            assignments=[
                ScheduleAssignment(
                    course_id="c1", teacher_id="t1", room_id="r1",
                    day=0, period=0,
                ),
            ],
            status="optimal",
            objective_value=42.0,
        )
        json_str = schedule.model_dump_json()
        restored = Schedule.model_validate_json(json_str)
        assert restored.status == "optimal"
        assert len(restored.assignments) == 1
        assert restored.assignments[0].course_id == "c1"
        assert restored.objective_value == 42.0
