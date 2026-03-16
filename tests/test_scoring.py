"""Tests for the schedule scoring and evaluation system."""

import pytest

from src.data.generator import generate_sample_data
from src.models import (
    Building,
    Course,
    Room,
    RoomType,
    Schedule,
    ScheduleAssignment,
    ScheduleData,
    StudentGroup,
    Teacher,
)
from src.optimizer.engine import ScheduleOptimizer
from src.optimizer.scoring import evaluate_schedule


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sample_data():
    return generate_sample_data()


@pytest.fixture(scope="module")
def solved_schedule(sample_data):
    optimizer = ScheduleOptimizer(sample_data)
    return optimizer.solve(time_limit=60)


def _make_simple_data():
    """Create minimal valid data for hand-crafted schedule tests."""
    teacher1 = Teacher(
        id="t1", name="Teacher A", department="CS",
        subjects_can_teach=["math", "cs"],
        availability={d: list(range(9)) for d in range(5)},
        max_hours_week=20, max_hours_day=6,
    )
    teacher2 = Teacher(
        id="t2", name="Teacher B", department="CS",
        subjects_can_teach=["math", "cs"],
        availability={d: list(range(9)) for d in range(5)},
        max_hours_week=20, max_hours_day=6,
    )
    group = StudentGroup(id="sg1", name="Group 1", size=20)
    group2 = StudentGroup(id="sg2", name="Group 2", size=20)
    room1 = Room(id="r1", name="Room A", building_id="b1", capacity=30,
                 room_type=RoomType.LECTURE_HALL)
    room2 = Room(id="r2", name="Room B", building_id="b1", capacity=30,
                 room_type=RoomType.LECTURE_HALL)
    building = Building(id="b1", name="Main", travel_time_to={"b1": 0})

    course1 = Course(
        id="c1", name="Math 101", subject="math", department="CS",
        sessions_per_week=1, session_duration_slots=1,
        required_room_type=RoomType.LECTURE_HALL, student_group_id="sg1",
        eligible_teacher_ids=["t1", "t2"],
    )
    course2 = Course(
        id="c2", name="CS 101", subject="cs", department="CS",
        sessions_per_week=1, session_duration_slots=1,
        required_room_type=RoomType.LECTURE_HALL, student_group_id="sg2",
        eligible_teacher_ids=["t1", "t2"],
    )

    return ScheduleData(
        teachers=[teacher1, teacher2],
        courses=[course1, course2],
        rooms=[room1, room2],
        buildings=[building],
        student_groups=[group, group2],
    )


def _make_multi_slot_data():
    """Create data with a 2-slot course for multi-slot testing."""
    teacher = Teacher(
        id="t1", name="Teacher A", department="CS",
        subjects_can_teach=["math"],
        availability={d: list(range(9)) for d in range(5)},
        max_hours_week=20, max_hours_day=6,
    )
    group = StudentGroup(id="sg1", name="Group 1", size=20)
    room = Room(id="r1", name="Room A", building_id="b1", capacity=30,
                room_type=RoomType.LECTURE_HALL)
    building = Building(id="b1", name="Main", travel_time_to={"b1": 0})

    course = Course(
        id="c1", name="Math Lab", subject="math", department="CS",
        sessions_per_week=1, session_duration_slots=2,
        required_room_type=RoomType.LECTURE_HALL, student_group_id="sg1",
        eligible_teacher_ids=["t1"],
    )

    return ScheduleData(
        teachers=[teacher],
        courses=[course],
        rooms=[room],
        buildings=[building],
        student_groups=[group],
    )


# ---------------------------------------------------------------------------
# Tests on solved sample data
# ---------------------------------------------------------------------------

class TestEvaluateSolvedSchedule:
    def test_feasible_true(self, sample_data, solved_schedule):
        score = evaluate_schedule(sample_data, solved_schedule)
        assert score.feasible is True

    def test_hard_score_zero(self, sample_data, solved_schedule):
        score = evaluate_schedule(sample_data, solved_schedule)
        assert score.hard_score == 0.0

    def test_all_hard_evaluators_zero(self, sample_data, solved_schedule):
        score = evaluate_schedule(sample_data, solved_schedule)
        hard_scores = [cs for cs in score.constraint_scores if cs.category == "hard"]
        assert len(hard_scores) == 8  # 8 hard constraint evaluators
        for cs in hard_scores:
            assert cs.violations == 0, (
                f"{cs.name}: {cs.violations} violations - {cs.details}"
            )

    def test_utilization_present(self, sample_data, solved_schedule):
        score = evaluate_schedule(sample_data, solved_schedule)
        assert "room_utilization_pct" in score.utilization
        assert "avg_teacher_utilization_pct" in score.utilization
        assert score.utilization["room_utilization_pct"] > 0

    def test_total_score_equals_hard_plus_soft(self, sample_data, solved_schedule):
        score = evaluate_schedule(sample_data, solved_schedule)
        assert score.total_score == pytest.approx(
            score.hard_score + score.soft_score
        )


# ---------------------------------------------------------------------------
# Hand-crafted violation tests
# ---------------------------------------------------------------------------

class TestTeacherDoubleBooking:
    def test_teacher_conflict_detected(self):
        """Same teacher assigned to two courses at same day/period."""
        data = _make_simple_data()
        # Both courses assigned to t1, day 0, period 0 - teacher conflict
        schedule = Schedule(
            assignments=[
                ScheduleAssignment(
                    course_id="c1", teacher_id="t1", room_id="r1",
                    day=0, period=0,
                ),
                ScheduleAssignment(
                    course_id="c2", teacher_id="t1", room_id="r2",
                    day=0, period=0,
                ),
            ],
            status="test",
        )
        score = evaluate_schedule(data, schedule)
        assert score.feasible is False
        assert score.hard_score > 0

        # Find the teacher conflict constraint specifically
        teacher_conflict = next(
            cs for cs in score.constraint_scores
            if cs.name == "No teacher time conflict"
        )
        assert teacher_conflict.violations > 0


class TestRoomDoubleBooking:
    def test_room_conflict_detected(self):
        """Two courses assigned to same room at same day/period."""
        data = _make_simple_data()
        schedule = Schedule(
            assignments=[
                ScheduleAssignment(
                    course_id="c1", teacher_id="t1", room_id="r1",
                    day=0, period=0,
                ),
                ScheduleAssignment(
                    course_id="c2", teacher_id="t2", room_id="r1",
                    day=0, period=0,
                ),
            ],
            status="test",
        )
        score = evaluate_schedule(data, schedule)
        assert score.feasible is False

        room_conflict = next(
            cs for cs in score.constraint_scores
            if cs.name == "No room double-booking"
        )
        assert room_conflict.violations > 0


class TestValidHandCraftedSchedule:
    def test_no_violations_with_valid_schedule(self):
        """No conflicts when courses are at different slots."""
        data = _make_simple_data()
        schedule = Schedule(
            assignments=[
                ScheduleAssignment(
                    course_id="c1", teacher_id="t1", room_id="r1",
                    day=0, period=0,
                ),
                ScheduleAssignment(
                    course_id="c2", teacher_id="t2", room_id="r2",
                    day=0, period=1,
                ),
            ],
            status="test",
        )
        score = evaluate_schedule(data, schedule)
        hard_scores = [cs for cs in score.constraint_scores if cs.category == "hard"]
        for cs in hard_scores:
            assert cs.violations == 0, (
                f"{cs.name}: {cs.violations} violations - {cs.details}"
            )
        assert score.feasible is True


class TestMultiSlotConflict:
    def test_multi_slot_teacher_conflict(self):
        """A 2-slot session at period 0 should conflict with a 1-slot at period 1
        if assigned to the same teacher."""
        data = _make_multi_slot_data()
        # Add a second 1-slot course for the conflict
        extra_course = Course(
            id="c2", name="Quick Math", subject="math", department="CS",
            sessions_per_week=1, session_duration_slots=1,
            required_room_type=RoomType.LECTURE_HALL, student_group_id="sg1",
            eligible_teacher_ids=["t1"],
        )
        data.courses.append(extra_course)

        # c1 is 2-slot starting at period 0 (occupies 0 and 1)
        # c2 is 1-slot at period 1 -- overlaps with c1's second slot
        schedule = Schedule(
            assignments=[
                ScheduleAssignment(
                    course_id="c1", teacher_id="t1", room_id="r1",
                    day=0, period=0,
                ),
                ScheduleAssignment(
                    course_id="c2", teacher_id="t1", room_id="r1",
                    day=0, period=1,
                ),
            ],
            status="test",
        )
        score = evaluate_schedule(data, schedule)
        assert score.feasible is False

        teacher_conflict = next(
            cs for cs in score.constraint_scores
            if cs.name == "No teacher time conflict"
        )
        assert teacher_conflict.violations > 0


class TestMissingAssignment:
    def test_wrong_assignment_count_detected(self):
        """A course with sessions_per_week=1 but 0 assignments is a violation."""
        data = _make_simple_data()
        # Only assign c1, skip c2 entirely
        schedule = Schedule(
            assignments=[
                ScheduleAssignment(
                    course_id="c1", teacher_id="t1", room_id="r1",
                    day=0, period=0,
                ),
            ],
            status="test",
        )
        score = evaluate_schedule(data, schedule)
        assert score.feasible is False

        correct_count = next(
            cs for cs in score.constraint_scores
            if cs.name == "Correct assignment count"
        )
        assert correct_count.violations > 0


class TestCustomWeights:
    def test_custom_weights_affect_soft_score(self, sample_data, solved_schedule):
        score_default = evaluate_schedule(sample_data, solved_schedule)
        score_zeroed = evaluate_schedule(
            sample_data, solved_schedule,
            weights={k: 0.0 for k in [
                "student_gaps", "teacher_gaps", "building_travel",
                "even_distribution", "lunch_breaks", "morning_core",
                "no_same_subject_twice", "teacher_day_off",
                "back_to_back_limit", "even_workload",
            ]},
        )
        assert score_zeroed.soft_score == 0.0
        # Hard score should be unchanged
        assert score_zeroed.hard_score == score_default.hard_score
