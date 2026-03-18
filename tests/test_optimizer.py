"""Tests for the CP-SAT schedule optimization engine."""

import pytest

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
from src.optimizer.constraints import ConstraintConfig
from src.optimizer.engine import ScheduleOptimizer
from src.optimizer.scoring import evaluate_schedule

# sample_data and solved_schedule fixtures provided by conftest.py


# ---------------------------------------------------------------------------
# Full solve tests
# ---------------------------------------------------------------------------

class TestFullSolve:
    def test_solve_returns_optimal_or_feasible(self, solved_schedule):
        assert solved_schedule.status in ("optimal", "feasible")

    def test_solve_has_assignments(self, solved_schedule, sample_data):
        # Should have at least one assignment per course session
        total_sessions = sum(c.sessions_per_week for c in sample_data.courses)
        assert len(solved_schedule.assignments) == total_sessions

    def test_zero_hard_constraint_violations(self, sample_data, solved_schedule):
        score = evaluate_schedule(sample_data, solved_schedule)
        assert score.feasible is True
        assert score.hard_score == 0.0

    def test_all_hard_evaluators_zero_violations(self, sample_data, solved_schedule):
        score = evaluate_schedule(sample_data, solved_schedule)
        hard_scores = [cs for cs in score.constraint_scores if cs.category == "hard"]
        for cs in hard_scores:
            assert cs.violations == 0, (
                f"Hard constraint '{cs.name}' has {cs.violations} violations: "
                f"{cs.details}"
            )


# ---------------------------------------------------------------------------
# Fixed course tests
# ---------------------------------------------------------------------------

class TestFixedCourses:
    def test_fixed_courses_at_correct_slots(self, sample_data, solved_schedule):
        fixed_courses = [c for c in sample_data.courses if c.is_fixed]
        assert len(fixed_courses) > 0, "Sample data should have fixed courses"

        assignment_map = {}
        for a in solved_schedule.assignments:
            assignment_map.setdefault(a.course_id, []).append(a)

        for course in fixed_courses:
            assigns = assignment_map.get(course.id, [])
            found = any(
                a.day == course.fixed_day and a.period == course.fixed_period
                for a in assigns
            )
            assert found, (
                f"Fixed course {course.name} ({course.id}) should be at "
                f"day={course.fixed_day}, period={course.fixed_period} "
                f"but assignments are: "
                f"{[(a.day, a.period) for a in assigns]}"
            )


# ---------------------------------------------------------------------------
# Infeasible scenario
# ---------------------------------------------------------------------------

class TestInfeasible:
    def test_infeasible_returns_infeasible_status(self):
        """Create an impossible scenario: one teacher, two courses at same time,
        one room, both courses fixed to the same slot."""
        teacher = Teacher(
            id="t1", name="Only Teacher", department="CS",
            subjects_can_teach=["math"],
            availability={0: [0, 1, 2, 3, 4, 5, 6, 7, 8]},
            max_hours_week=20, max_hours_day=6,
        )
        group1 = StudentGroup(id="sg1", name="G1", size=10)
        group2 = StudentGroup(id="sg2", name="G2", size=10)
        room = Room(
            id="r1", name="Only Room", building_id="b1", capacity=20,
            room_type=RoomType.LECTURE_HALL,
        )
        building = Building(id="b1", name="Main", travel_time_to={"b1": 0})

        # Two courses fixed to the exact same slot, same teacher, same room
        course1 = Course(
            id="c1", name="Course A", subject="math", department="CS",
            sessions_per_week=1, session_duration_slots=1,
            required_room_type=RoomType.LECTURE_HALL, student_group_id="sg1",
            eligible_teacher_ids=["t1"],
            is_fixed=True, fixed_day=0, fixed_period=0,
        )
        course2 = Course(
            id="c2", name="Course B", subject="math", department="CS",
            sessions_per_week=1, session_duration_slots=1,
            required_room_type=RoomType.LECTURE_HALL, student_group_id="sg2",
            eligible_teacher_ids=["t1"],
            is_fixed=True, fixed_day=0, fixed_period=0,
        )

        data = ScheduleData(
            teachers=[teacher],
            courses=[course1, course2],
            rooms=[room],
            buildings=[building],
            student_groups=[group1, group2],
        )
        optimizer = ScheduleOptimizer(data)
        result = optimizer.solve(time_limit=10)
        assert result.status == "infeasible"
