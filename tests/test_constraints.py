"""Tests for constraint pre-filtering helpers and ConstraintConfig."""

import pytest

from src.models import Course, Room, RoomType, StudentGroup, Teacher
from src.models.time_slot import DAYS, PERIODS_PER_DAY, slot_index
from src.optimizer.constraints import (
    ConstraintConfig,
    get_eligible_rooms,
    get_eligible_slots,
    get_eligible_teachers,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def all_periods():
    return list(range(PERIODS_PER_DAY))


@pytest.fixture
def full_availability(all_periods):
    return {d: list(all_periods) for d in range(DAYS)}


@pytest.fixture
def teacher_full(full_availability):
    return Teacher(
        id="t1", name="Full-Time", department="CS",
        subjects_can_teach=["math", "programming"],
        availability=full_availability,
        max_hours_week=20, max_hours_day=6,
    )


@pytest.fixture
def teacher_limited():
    """Teacher available only on Mon/Wed, periods 0-3."""
    return Teacher(
        id="t2", name="Part-Time", department="CS",
        subjects_can_teach=["math"],
        availability={0: [0, 1, 2, 3], 2: [0, 1, 2, 3]},
        max_hours_week=12, max_hours_day=4,
    )


@pytest.fixture
def lecture_course():
    return Course(
        id="c1", name="Math 101", subject="math", department="Math",
        sessions_per_week=1, session_duration_slots=1,
        required_room_type=RoomType.LECTURE_HALL, student_group_id="sg1",
        eligible_teacher_ids=["t1", "t2"],
    )


@pytest.fixture
def lab_course():
    return Course(
        id="c2", name="Programming Lab", subject="programming", department="CS",
        sessions_per_week=1, session_duration_slots=2,
        required_room_type=RoomType.LAB, student_group_id="sg1",
        eligible_teacher_ids=["t1"],
    )


@pytest.fixture
def fixed_course():
    return Course(
        id="c3", name="Fixed Course", subject="math", department="Math",
        sessions_per_week=1, session_duration_slots=1,
        required_room_type=RoomType.LECTURE_HALL, student_group_id="sg1",
        eligible_teacher_ids=["t1"],
        is_fixed=True, fixed_day=0, fixed_period=2,
    )


@pytest.fixture
def rooms():
    return [
        Room(id="r1", name="LH-101", building_id="b1", capacity=50,
             room_type=RoomType.LECTURE_HALL),
        Room(id="r2", name="LAB-201", building_id="b2", capacity=40,
             room_type=RoomType.LAB),
        Room(id="r3", name="LH-102", building_id="b1", capacity=20,
             room_type=RoomType.LECTURE_HALL),
    ]


@pytest.fixture
def student_groups():
    return {
        "sg1": StudentGroup(id="sg1", name="CS-Y1", size=30),
    }


# ---------------------------------------------------------------------------
# get_eligible_rooms
# ---------------------------------------------------------------------------

class TestGetEligibleRooms:
    def test_filters_by_room_type(self, lecture_course, rooms, student_groups):
        eligible = get_eligible_rooms(lecture_course, rooms, student_groups)
        assert all(r.room_type == RoomType.LECTURE_HALL for r in eligible)

    def test_filters_by_capacity(self, lecture_course, rooms, student_groups):
        eligible = get_eligible_rooms(lecture_course, rooms, student_groups)
        group = student_groups["sg1"]
        assert all(r.capacity >= group.size for r in eligible)

    def test_excludes_small_rooms(self, lecture_course, rooms, student_groups):
        eligible = get_eligible_rooms(lecture_course, rooms, student_groups)
        eligible_ids = {r.id for r in eligible}
        # r3 has capacity 20 < group size 30
        assert "r3" not in eligible_ids

    def test_lab_course_gets_lab_rooms(self, lab_course, rooms, student_groups):
        eligible = get_eligible_rooms(lab_course, rooms, student_groups)
        assert len(eligible) == 1
        assert eligible[0].id == "r2"

    def test_no_matching_rooms_returns_empty(self, rooms, student_groups):
        course = Course(
            id="cx", name="X", subject="x", department="d",
            required_room_type=RoomType.AUDITORIUM,
            student_group_id="sg1",
        )
        eligible = get_eligible_rooms(course, rooms, student_groups)
        assert eligible == []


# ---------------------------------------------------------------------------
# get_eligible_slots
# ---------------------------------------------------------------------------

class TestGetEligibleSlots:
    def test_full_availability_single_slot(self, lecture_course, teacher_full):
        slots = get_eligible_slots(lecture_course, teacher_full)
        # Full-time teacher should have all 45 slots available
        assert len(slots) == DAYS * PERIODS_PER_DAY

    def test_limited_availability(self, lecture_course, teacher_limited):
        slots = get_eligible_slots(lecture_course, teacher_limited)
        # Mon periods 0-3 + Wed periods 0-3 = 8 slots
        assert len(slots) == 8

    def test_multi_slot_respects_duration(self, lab_course, teacher_full):
        slots = get_eligible_slots(lab_course, teacher_full)
        # 2-slot sessions: periods 0-7 possible (8 starts), on 5 days = 40
        assert len(slots) == DAYS * (PERIODS_PER_DAY - 1)

    def test_multi_slot_limited_teacher(self, lab_course, teacher_limited):
        slots = get_eligible_slots(lab_course, teacher_limited)
        # Mon: periods 0-3 available, 2-slot can start at 0,1,2 = 3 starts
        # Wed: same = 3 starts
        assert len(slots) == 6

    def test_fixed_course_returns_single_slot(self, fixed_course, teacher_full):
        slots = get_eligible_slots(fixed_course, teacher_full)
        assert len(slots) == 1
        assert slots[0] == slot_index(0, 2)

    def test_fixed_course_unavailable_teacher(self, fixed_course, teacher_limited):
        # teacher_limited is available Mon periods 0-3, fixed is Mon period 2
        slots = get_eligible_slots(fixed_course, teacher_limited)
        # Should be available since period 2 is in [0,1,2,3]
        assert len(slots) == 1

    def test_fixed_course_completely_unavailable(self):
        """Fixed course on a day the teacher is unavailable returns empty."""
        teacher = Teacher(
            id="t99", name="Unavailable", department="CS",
            subjects_can_teach=["math"],
            availability={1: [0, 1]},  # Only Tuesday
        )
        course = Course(
            id="cx", name="Fixed", subject="math", department="Math",
            student_group_id="sg1",
            is_fixed=True, fixed_day=0, fixed_period=0,  # Monday
        )
        assert get_eligible_slots(course, teacher) == []


# ---------------------------------------------------------------------------
# get_eligible_teachers
# ---------------------------------------------------------------------------

class TestGetEligibleTeachers:
    def test_filters_by_subject(self):
        teachers = [
            Teacher(id="t1", name="A", department="CS",
                    subjects_can_teach=["math", "cs"]),
            Teacher(id="t2", name="B", department="CS",
                    subjects_can_teach=["cs"]),
        ]
        course = Course(
            id="c1", name="Math", subject="math", department="d",
            student_group_id="sg1",
            eligible_teacher_ids=["t1", "t2"],
        )
        eligible = get_eligible_teachers(course, teachers)
        assert len(eligible) == 1
        assert eligible[0].id == "t1"

    def test_filters_by_eligible_ids(self):
        teachers = [
            Teacher(id="t1", name="A", department="CS",
                    subjects_can_teach=["math"]),
            Teacher(id="t2", name="B", department="CS",
                    subjects_can_teach=["math"]),
        ]
        course = Course(
            id="c1", name="Math", subject="math", department="d",
            student_group_id="sg1",
            eligible_teacher_ids=["t1"],
        )
        eligible = get_eligible_teachers(course, teachers)
        assert len(eligible) == 1
        assert eligible[0].id == "t1"

    def test_empty_eligible_ids_allows_any_matching_subject(self):
        teachers = [
            Teacher(id="t1", name="A", department="CS",
                    subjects_can_teach=["math"]),
            Teacher(id="t2", name="B", department="CS",
                    subjects_can_teach=["math"]),
        ]
        course = Course(
            id="c1", name="Math", subject="math", department="d",
            student_group_id="sg1",
            eligible_teacher_ids=[],
        )
        eligible = get_eligible_teachers(course, teachers)
        assert len(eligible) == 2

    def test_no_matching_teachers(self):
        teachers = [
            Teacher(id="t1", name="A", department="CS",
                    subjects_can_teach=["physics"]),
        ]
        course = Course(
            id="c1", name="Math", subject="math", department="d",
            student_group_id="sg1",
            eligible_teacher_ids=["t1"],
        )
        eligible = get_eligible_teachers(course, teachers)
        assert eligible == []


# ---------------------------------------------------------------------------
# ConstraintConfig
# ---------------------------------------------------------------------------

class TestConstraintConfig:
    def test_as_dict_returns_all_weights(self):
        config = ConstraintConfig()
        d = config.as_dict()
        assert "student_gaps" in d
        assert "lunch_breaks" in d
        assert len(d) == 10

    def test_from_dict_roundtrip(self):
        config = ConstraintConfig(student_gaps=5.0, lunch_breaks=10.0)
        d = config.as_dict()
        restored = ConstraintConfig.from_dict(d)
        assert restored.student_gaps == 5.0
        assert restored.lunch_breaks == 10.0

    def test_from_dict_ignores_unknown_keys(self):
        d = {"student_gaps": 7.0, "unknown_key": 99.0}
        config = ConstraintConfig.from_dict(d)
        assert config.student_gaps == 7.0
        # Other fields should have defaults
        assert config.lunch_breaks == 5.0

    def test_default_values(self):
        config = ConstraintConfig()
        assert config.student_gaps == 3.0
        assert config.teacher_gaps == 2.0
        assert config.building_travel == 4.0
