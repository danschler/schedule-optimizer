"""Schedule scoring and evaluation system.

Evaluates a schedule against hard and soft constraints, computing
a ScheduleScore with detailed violation information and utilization metrics.
"""

from collections import defaultdict
from dataclasses import dataclass, field

from src.models import (
    DAYS,
    DAY_NAMES,
    LUNCH_PERIOD,
    PERIODS_PER_DAY,
    TOTAL_SLOTS,
)
from src.models.schedule import Schedule, ScheduleAssignment, ScheduleData


# ---------------------------------------------------------------------------
# Result data classes
# ---------------------------------------------------------------------------

@dataclass
class ConstraintScore:
    name: str
    category: str  # "hard" or "soft"
    weight: float
    violations: int
    penalty: float
    details: list[str] = field(default_factory=list)


@dataclass
class ScheduleScore:
    hard_score: float
    soft_score: float
    total_score: float
    constraint_scores: list[ConstraintScore] = field(default_factory=list)
    feasible: bool = True
    utilization: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Default soft-constraint weights
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS: dict[str, float] = {
    "student_gaps": 3.0,
    "teacher_gaps": 2.0,
    "building_travel": 4.0,
    "even_distribution": 2.0,
    "lunch_breaks": 5.0,
    "morning_core": 1.0,
    "no_same_subject_twice": 3.0,
    "teacher_day_off": 2.0,
    "back_to_back_limit": 3.0,
    "even_workload": 1.0,
}


# ---------------------------------------------------------------------------
# Helper: occupied slots for an assignment
# ---------------------------------------------------------------------------

def _occupied_slots(a: ScheduleAssignment, courses_by_id: dict) -> list[tuple[int, int]]:
    """Return list of (day, period) tuples occupied by *a*."""
    course = courses_by_id.get(a.course_id)
    duration = course.session_duration_slots if course else 1
    return [(a.day, a.period + offset) for offset in range(duration)]


# ---------------------------------------------------------------------------
# Hard constraint evaluators
# ---------------------------------------------------------------------------

def _hc1_correct_assignments(data, schedule, courses_by_id, **_kw) -> ConstraintScore:
    """HC1: Each course has the correct number of assignments (sessions_per_week)."""
    counts: dict[str, int] = defaultdict(int)
    for a in schedule.assignments:
        counts[a.course_id] += 1

    violations = 0
    details: list[str] = []
    for course in data.courses:
        expected = course.sessions_per_week
        actual = counts.get(course.id, 0)
        if actual != expected:
            violations += 1
            details.append(
                f"Course {course.name} ({course.id}): expected {expected} "
                f"sessions, got {actual}"
            )

    return ConstraintScore(
        name="Correct assignment count",
        category="hard",
        weight=1.0,
        violations=violations,
        penalty=float(violations),
        details=details,
    )


def _hc2_teacher_conflict(data, schedule, courses_by_id, assignments_by_teacher, **_kw) -> ConstraintScore:
    """HC2: No teacher teaches two things at the same time slot."""
    violations = 0
    details: list[str] = []
    teachers_by_id = _kw.get("teachers_by_id", {})

    for tid, assigns in assignments_by_teacher.items():
        slot_map: dict[tuple[int, int], list[ScheduleAssignment]] = defaultdict(list)
        for a in assigns:
            for slot in _occupied_slots(a, courses_by_id):
                slot_map[slot].append(a)
        for slot, asgns in slot_map.items():
            if len(asgns) > 1:
                violations += len(asgns) - 1
                teacher = teachers_by_id.get(tid)
                tname = teacher.name if teacher else tid
                day_name = DAY_NAMES[slot[0]]
                details.append(
                    f"Teacher {tname} has {len(asgns)} classes at "
                    f"{day_name} period {slot[1]}"
                )

    return ConstraintScore(
        name="No teacher time conflict",
        category="hard",
        weight=1.0,
        violations=violations,
        penalty=float(violations),
        details=details,
    )


def _hc3_room_conflict(data, schedule, courses_by_id, assignments_by_room, **_kw) -> ConstraintScore:
    """HC3: No room double-booking."""
    violations = 0
    details: list[str] = []
    rooms_by_id = _kw.get("rooms_by_id", {})

    for rid, assigns in assignments_by_room.items():
        slot_map: dict[tuple[int, int], list[ScheduleAssignment]] = defaultdict(list)
        for a in assigns:
            for slot in _occupied_slots(a, courses_by_id):
                slot_map[slot].append(a)
        for slot, asgns in slot_map.items():
            if len(asgns) > 1:
                violations += len(asgns) - 1
                room = rooms_by_id.get(rid)
                rname = room.name if room else rid
                day_name = DAY_NAMES[slot[0]]
                details.append(
                    f"Room {rname} has {len(asgns)} bookings at "
                    f"{day_name} period {slot[1]}"
                )

    return ConstraintScore(
        name="No room double-booking",
        category="hard",
        weight=1.0,
        violations=violations,
        penalty=float(violations),
        details=details,
    )


def _hc4_room_capacity(data, schedule, courses_by_id, rooms_by_id, groups_by_id, **_kw) -> ConstraintScore:
    """HC4: Room capacity >= student group size."""
    violations = 0
    details: list[str] = []

    for a in schedule.assignments:
        room = rooms_by_id.get(a.room_id)
        course = courses_by_id.get(a.course_id)
        if not room or not course:
            continue
        group = groups_by_id.get(course.student_group_id)
        if not group:
            continue
        if room.capacity < group.size:
            violations += 1
            details.append(
                f"Room {room.name} (cap {room.capacity}) too small for "
                f"{group.name} (size {group.size}) in course {course.name}"
            )

    return ConstraintScore(
        name="Room capacity sufficient",
        category="hard",
        weight=1.0,
        violations=violations,
        penalty=float(violations),
        details=details,
    )


def _hc5_room_type(data, schedule, courses_by_id, rooms_by_id, **_kw) -> ConstraintScore:
    """HC5: Room type matches course requirement."""
    violations = 0
    details: list[str] = []

    for a in schedule.assignments:
        room = rooms_by_id.get(a.room_id)
        course = courses_by_id.get(a.course_id)
        if not room or not course:
            continue
        if room.room_type != course.required_room_type:
            violations += 1
            details.append(
                f"Course {course.name} requires {course.required_room_type.value} "
                f"but assigned to {room.name} ({room.room_type.value})"
            )

    return ConstraintScore(
        name="Room type matches requirement",
        category="hard",
        weight=1.0,
        violations=violations,
        penalty=float(violations),
        details=details,
    )


def _hc6_fixed_courses(data, schedule, courses_by_id, **_kw) -> ConstraintScore:
    """HC6: Fixed courses are at their fixed slot."""
    violations = 0
    details: list[str] = []

    assignment_map: dict[str, list[ScheduleAssignment]] = defaultdict(list)
    for a in schedule.assignments:
        assignment_map[a.course_id].append(a)

    for course in data.courses:
        if not course.is_fixed:
            continue
        assigns = assignment_map.get(course.id, [])
        found = any(
            a.day == course.fixed_day and a.period == course.fixed_period
            for a in assigns
        )
        if not found:
            violations += 1
            details.append(
                f"Fixed course {course.name} should be at "
                f"{DAY_NAMES[course.fixed_day]} period {course.fixed_period} "
                f"but is not"
            )

    return ConstraintScore(
        name="Fixed courses at fixed slots",
        category="hard",
        weight=1.0,
        violations=violations,
        penalty=float(violations),
        details=details,
    )


def _hc7_teacher_hours(data, schedule, courses_by_id, assignments_by_teacher, teachers_by_id, **_kw) -> ConstraintScore:
    """HC7: Teacher max hours/day and /week."""
    violations = 0
    details: list[str] = []

    for tid, assigns in assignments_by_teacher.items():
        teacher = teachers_by_id.get(tid)
        if not teacher:
            continue

        # Count slots per day and total
        day_slots: dict[int, int] = defaultdict(int)
        total_slots = 0
        for a in assigns:
            duration = courses_by_id.get(a.course_id)
            dur = duration.session_duration_slots if duration else 1
            day_slots[a.day] += dur
            total_slots += dur

        for day, count in day_slots.items():
            if count > teacher.max_hours_day:
                violations += 1
                details.append(
                    f"Teacher {teacher.name} has {count} hours on "
                    f"{DAY_NAMES[day]} (max {teacher.max_hours_day})"
                )

        if total_slots > teacher.max_hours_week:
            violations += 1
            details.append(
                f"Teacher {teacher.name} has {total_slots} hours/week "
                f"(max {teacher.max_hours_week})"
            )

    return ConstraintScore(
        name="Teacher hour limits",
        category="hard",
        weight=1.0,
        violations=violations,
        penalty=float(violations),
        details=details,
    )


def _hc8_group_conflict(data, schedule, courses_by_id, assignments_by_group, groups_by_id, **_kw) -> ConstraintScore:
    """HC8: No student group has two courses at the same time."""
    violations = 0
    details: list[str] = []

    for gid, assigns in assignments_by_group.items():
        slot_map: dict[tuple[int, int], list[ScheduleAssignment]] = defaultdict(list)
        for a in assigns:
            for slot in _occupied_slots(a, courses_by_id):
                slot_map[slot].append(a)
        for slot, asgns in slot_map.items():
            if len(asgns) > 1:
                violations += len(asgns) - 1
                group = groups_by_id.get(gid)
                gname = group.name if group else gid
                day_name = DAY_NAMES[slot[0]]
                details.append(
                    f"Group {gname} has {len(asgns)} classes at "
                    f"{day_name} period {slot[1]}"
                )

    return ConstraintScore(
        name="No student group time conflict",
        category="hard",
        weight=1.0,
        violations=violations,
        penalty=float(violations),
        details=details,
    )


# ---------------------------------------------------------------------------
# Soft constraint evaluators
# ---------------------------------------------------------------------------

def _count_gaps(periods: list[int]) -> int:
    """Count gap periods between first and last occupied period in a sorted list."""
    if len(periods) < 2:
        return 0
    periods_sorted = sorted(periods)
    total_span = periods_sorted[-1] - periods_sorted[0] + 1
    return total_span - len(periods_sorted)


def _sc1_student_gaps(data, schedule, courses_by_id, assignments_by_group, groups_by_id, weight, **_kw) -> ConstraintScore:
    """SC1: Minimise gaps in each student group's daily timetable."""
    violations = 0
    details: list[str] = []

    for gid, assigns in assignments_by_group.items():
        day_periods: dict[int, set[int]] = defaultdict(set)
        for a in assigns:
            for day, period in _occupied_slots(a, courses_by_id):
                day_periods[day].add(period)

        group = groups_by_id.get(gid)
        gname = group.name if group else gid
        for day in range(DAYS):
            periods = day_periods.get(day)
            if not periods:
                continue
            gaps = _count_gaps(list(periods))
            if gaps > 0:
                violations += gaps
                details.append(
                    f"Group {gname} has {gaps} gap(s) on {DAY_NAMES[day]}"
                )

    return ConstraintScore(
        name="Student gaps",
        category="soft",
        weight=weight,
        violations=violations,
        penalty=violations * weight,
        details=details,
    )


def _sc2_teacher_gaps(data, schedule, courses_by_id, assignments_by_teacher, teachers_by_id, weight, **_kw) -> ConstraintScore:
    """SC2: Minimise gaps in each teacher's daily timetable."""
    violations = 0
    details: list[str] = []

    for tid, assigns in assignments_by_teacher.items():
        day_periods: dict[int, set[int]] = defaultdict(set)
        for a in assigns:
            for day, period in _occupied_slots(a, courses_by_id):
                day_periods[day].add(period)

        teacher = teachers_by_id.get(tid)
        tname = teacher.name if teacher else tid
        for day in range(DAYS):
            periods = day_periods.get(day)
            if not periods:
                continue
            gaps = _count_gaps(list(periods))
            if gaps > 0:
                violations += gaps
                details.append(
                    f"Teacher {tname} has {gaps} gap(s) on {DAY_NAMES[day]}"
                )

    return ConstraintScore(
        name="Teacher gaps",
        category="soft",
        weight=weight,
        violations=violations,
        penalty=violations * weight,
        details=details,
    )


def _sc3_building_travel(data, schedule, courses_by_id, assignments_by_group, rooms_by_id, buildings_by_id, groups_by_id, weight, **_kw) -> ConstraintScore:
    """SC3: Penalise cross-building consecutive assignments, weighted by travel time."""
    violations = 0
    details: list[str] = []

    for gid, assigns in assignments_by_group.items():
        # Build (day, period) -> assignment, accounting for duration
        slot_to_assign: dict[tuple[int, int], ScheduleAssignment] = {}
        for a in assigns:
            for slot in _occupied_slots(a, courses_by_id):
                slot_to_assign[slot] = a

        group = groups_by_id.get(gid)
        gname = group.name if group else gid

        for day in range(DAYS):
            # Find all periods with assignments on this day
            day_assigns: list[tuple[int, ScheduleAssignment]] = []
            for period in range(PERIODS_PER_DAY):
                a = slot_to_assign.get((day, period))
                if a:
                    day_assigns.append((period, a))

            # Check consecutive slots for building changes
            for i in range(len(day_assigns) - 1):
                p1, a1 = day_assigns[i]
                p2, a2 = day_assigns[i + 1]
                # Only check truly consecutive periods
                if p2 != p1 + 1:
                    continue
                # Same assignment spanning multiple slots is fine
                if a1 is a2:
                    continue
                r1 = rooms_by_id.get(a1.room_id)
                r2 = rooms_by_id.get(a2.room_id)
                if not r1 or not r2:
                    continue
                if r1.building_id == r2.building_id:
                    continue
                b1 = buildings_by_id.get(r1.building_id)
                travel = 0
                if b1:
                    travel = b1.travel_time_to.get(r2.building_id, 0)
                violations += max(travel, 1)
                details.append(
                    f"Group {gname} travels between buildings on "
                    f"{DAY_NAMES[day]} period {p1}->{p2} "
                    f"(travel {travel} min)"
                )

    return ConstraintScore(
        name="Building travel",
        category="soft",
        weight=weight,
        violations=violations,
        penalty=violations * weight,
        details=details,
    )


def _sc4_even_distribution(data, schedule, courses_by_id, assignments_by_group, groups_by_id, weight, **_kw) -> ConstraintScore:
    """SC4: Penalise uneven daily class counts per group (max - min)."""
    violations = 0
    details: list[str] = []

    for gid, assigns in assignments_by_group.items():
        day_counts: dict[int, int] = defaultdict(int)
        for a in assigns:
            course = courses_by_id.get(a.course_id)
            dur = course.session_duration_slots if course else 1
            day_counts[a.day] += dur

        # Include days with zero classes
        counts = [day_counts.get(d, 0) for d in range(DAYS)]
        spread = max(counts) - min(counts)
        if spread > 1:
            penalty_amount = spread - 1  # allow spread of 1 for free
            violations += penalty_amount
            group = groups_by_id.get(gid)
            gname = group.name if group else gid
            details.append(
                f"Group {gname} daily class counts {counts} (spread {spread})"
            )

    return ConstraintScore(
        name="Even daily distribution",
        category="soft",
        weight=weight,
        violations=violations,
        penalty=violations * weight,
        details=details,
    )


def _sc5_lunch_breaks(data, schedule, courses_by_id, weight, **_kw) -> ConstraintScore:
    """SC5: Penalise assignments during LUNCH_PERIOD."""
    violations = 0
    details: list[str] = []
    groups_by_id = _kw.get("groups_by_id", {})

    for a in schedule.assignments:
        occupied = _occupied_slots(a, courses_by_id)
        for day, period in occupied:
            if period == LUNCH_PERIOD:
                violations += 1
                course = courses_by_id.get(a.course_id)
                cname = course.name if course else a.course_id
                details.append(
                    f"Course {cname} scheduled during lunch on "
                    f"{DAY_NAMES[day]}"
                )

    return ConstraintScore(
        name="Lunch breaks",
        category="soft",
        weight=weight,
        violations=violations,
        penalty=violations * weight,
        details=details,
    )


def _sc6_morning_core(data, schedule, courses_by_id, weight, **_kw) -> ConstraintScore:
    """SC6: Penalise core subjects in the afternoon (period >= 5)."""
    # Treat subjects like math, science, language as core (heuristic: first 3 unique subjects)
    # A more robust approach: consider any subject tagged 'core'. Here we simply check period.
    violations = 0
    details: list[str] = []

    # Gather the set of subjects marked as core.  Since the model has no
    # explicit `is_core` flag we rely on a simple heuristic: a subject is
    # "core" if its name is in a well-known set.  Callers can override by
    # adding a `core_subjects` key in the weights dict, but the spec just
    # says "core subject" so we treat the first subjects we find or use a
    # simple fallback: any subject whose name is alphabetically in the first
    # half.  Better: just penalise *all* afternoon assignments lightly -- but
    # the spec says "core subject afternoon assignments".
    #
    # Pragmatic choice: treat every subject as potentially core and let the
    # weight handle severity.  The caller can zero-out the weight if they
    # don't want this constraint.
    CORE_KEYWORDS = {"math", "mathematics", "science", "physics", "chemistry",
                     "biology", "language", "english", "literature", "history"}

    for a in schedule.assignments:
        course = courses_by_id.get(a.course_id)
        if not course:
            continue
        if course.subject.lower() not in CORE_KEYWORDS:
            continue
        for day, period in _occupied_slots(a, courses_by_id):
            if period >= 5:
                violations += 1
                details.append(
                    f"Core course {course.name} ({course.subject}) in afternoon "
                    f"on {DAY_NAMES[day]} period {period}"
                )

    return ConstraintScore(
        name="Morning core subjects",
        category="soft",
        weight=weight,
        violations=violations,
        penalty=violations * weight,
        details=details,
    )


def _sc7_no_same_subject_twice(data, schedule, courses_by_id, assignments_by_group, groups_by_id, weight, **_kw) -> ConstraintScore:
    """SC7: Penalise days where a group has the same subject twice."""
    violations = 0
    details: list[str] = []

    for gid, assigns in assignments_by_group.items():
        day_subjects: dict[int, list[str]] = defaultdict(list)
        for a in assigns:
            course = courses_by_id.get(a.course_id)
            if course:
                day_subjects[a.day].append(course.subject)

        group = groups_by_id.get(gid)
        gname = group.name if group else gid
        for day, subjects in day_subjects.items():
            seen: dict[str, int] = defaultdict(int)
            for s in subjects:
                seen[s] += 1
            for s, count in seen.items():
                if count > 1:
                    violations += count - 1
                    details.append(
                        f"Group {gname} has {s} {count} times on "
                        f"{DAY_NAMES[day]}"
                    )

    return ConstraintScore(
        name="No same subject twice per day",
        category="soft",
        weight=weight,
        violations=violations,
        penalty=violations * weight,
        details=details,
    )


def _sc8_teacher_day_off(data, schedule, courses_by_id, assignments_by_teacher, teachers_by_id, weight, **_kw) -> ConstraintScore:
    """SC8: Penalise assignments on a teacher's preferred days off."""
    violations = 0
    details: list[str] = []

    for tid, assigns in assignments_by_teacher.items():
        teacher = teachers_by_id.get(tid)
        if not teacher or not teacher.preferred_days_off:
            continue
        off_set = set(teacher.preferred_days_off)
        for a in assigns:
            if a.day in off_set:
                violations += 1
                details.append(
                    f"Teacher {teacher.name} assigned on preferred day off "
                    f"{DAY_NAMES[a.day]}"
                )

    return ConstraintScore(
        name="Teacher preferred days off",
        category="soft",
        weight=weight,
        violations=violations,
        penalty=violations * weight,
        details=details,
    )


def _sc9_back_to_back_limit(data, schedule, courses_by_id, assignments_by_teacher, teachers_by_id, weight, **_kw) -> ConstraintScore:
    """SC9: Penalise windows where a teacher has >3 consecutive teaching slots."""
    violations = 0
    details: list[str] = []
    max_consecutive = 3

    for tid, assigns in assignments_by_teacher.items():
        teacher = teachers_by_id.get(tid)
        tname = teacher.name if teacher else tid

        day_periods: dict[int, set[int]] = defaultdict(set)
        for a in assigns:
            for day, period in _occupied_slots(a, courses_by_id):
                day_periods[day].add(period)

        for day in range(DAYS):
            periods = day_periods.get(day)
            if not periods:
                continue
            sorted_periods = sorted(periods)
            # Find consecutive runs
            run_length = 1
            for i in range(1, len(sorted_periods)):
                if sorted_periods[i] == sorted_periods[i - 1] + 1:
                    run_length += 1
                else:
                    if run_length > max_consecutive:
                        excess = run_length - max_consecutive
                        violations += excess
                        details.append(
                            f"Teacher {tname} has {run_length} consecutive "
                            f"slots on {DAY_NAMES[day]}"
                        )
                    run_length = 1
            # Check final run
            if run_length > max_consecutive:
                excess = run_length - max_consecutive
                violations += excess
                details.append(
                    f"Teacher {tname} has {run_length} consecutive "
                    f"slots on {DAY_NAMES[day]}"
                )

    return ConstraintScore(
        name="Back-to-back teaching limit",
        category="soft",
        weight=weight,
        violations=violations,
        penalty=violations * weight,
        details=details,
    )


def _sc10_even_workload(data, schedule, courses_by_id, assignments_by_teacher, teachers_by_id, weight, **_kw) -> ConstraintScore:
    """SC10: Penalise uneven daily workload across all teachers."""
    violations = 0
    details: list[str] = []

    for tid, assigns in assignments_by_teacher.items():
        teacher = teachers_by_id.get(tid)
        tname = teacher.name if teacher else tid

        day_counts: dict[int, int] = defaultdict(int)
        for a in assigns:
            course = courses_by_id.get(a.course_id)
            dur = course.session_duration_slots if course else 1
            day_counts[a.day] += dur

        # Only consider days the teacher actually works
        if not day_counts:
            continue
        counts = list(day_counts.values())
        spread = max(counts) - min(counts)
        if spread > 1:
            penalty_amount = spread - 1
            violations += penalty_amount
            details.append(
                f"Teacher {tname} daily workload spread {spread} "
                f"(counts: {dict(day_counts)})"
            )

    return ConstraintScore(
        name="Even teacher workload",
        category="soft",
        weight=weight,
        violations=violations,
        penalty=violations * weight,
        details=details,
    )


# ---------------------------------------------------------------------------
# Main evaluation entry point
# ---------------------------------------------------------------------------

def evaluate_schedule(
    data: ScheduleData,
    schedule: Schedule,
    weights: dict[str, float] | None = None,
) -> ScheduleScore:
    """Evaluate a schedule against all constraints and compute metrics.

    Parameters
    ----------
    data : ScheduleData
        The input data (teachers, courses, rooms, buildings, student groups).
    schedule : Schedule
        The schedule to evaluate.
    weights : dict[str, float] | None
        Optional soft-constraint weight overrides.  Keys should match
        ``DEFAULT_WEIGHTS``.  Missing keys fall back to defaults.

    Returns
    -------
    ScheduleScore
        Aggregated hard/soft scores, per-constraint details, feasibility
        flag, and utilization metrics.
    """

    # Merge weights
    w = dict(DEFAULT_WEIGHTS)
    if weights:
        w.update(weights)

    # ---- 1. Build lookup dicts ----
    teachers_by_id = {t.id: t for t in data.teachers}
    courses_by_id = {c.id: c for c in data.courses}
    rooms_by_id = {r.id: r for r in data.rooms}
    buildings_by_id = {b.id: b for b in data.buildings}
    groups_by_id = {g.id: g for g in data.student_groups}

    # ---- 2. Build helper structures ----
    assignments_by_teacher: dict[str, list[ScheduleAssignment]] = defaultdict(list)
    assignments_by_room: dict[str, list[ScheduleAssignment]] = defaultdict(list)
    assignments_by_group: dict[str, list[ScheduleAssignment]] = defaultdict(list)
    assignments_by_slot: dict[tuple[int, int], list[ScheduleAssignment]] = defaultdict(list)

    for a in schedule.assignments:
        assignments_by_teacher[a.teacher_id].append(a)
        assignments_by_room[a.room_id].append(a)

        course = courses_by_id.get(a.course_id)
        if course:
            assignments_by_group[course.student_group_id].append(a)

        for slot in _occupied_slots(a, courses_by_id):
            assignments_by_slot[slot].append(a)

    # Common kwargs passed to every evaluator
    ctx = dict(
        data=data,
        schedule=schedule,
        courses_by_id=courses_by_id,
        teachers_by_id=teachers_by_id,
        rooms_by_id=rooms_by_id,
        buildings_by_id=buildings_by_id,
        groups_by_id=groups_by_id,
        assignments_by_teacher=assignments_by_teacher,
        assignments_by_room=assignments_by_room,
        assignments_by_group=assignments_by_group,
        assignments_by_slot=assignments_by_slot,
    )

    # ---- 3. Evaluate hard constraints ----
    hard_evaluators = [
        _hc1_correct_assignments,
        _hc2_teacher_conflict,
        _hc3_room_conflict,
        _hc4_room_capacity,
        _hc5_room_type,
        _hc6_fixed_courses,
        _hc7_teacher_hours,
        _hc8_group_conflict,
    ]

    constraint_scores: list[ConstraintScore] = []
    hard_score = 0.0
    for fn in hard_evaluators:
        cs = fn(**ctx)
        constraint_scores.append(cs)
        hard_score += cs.penalty

    # ---- 4. Evaluate soft constraints ----
    soft_evaluators = [
        ("student_gaps", _sc1_student_gaps),
        ("teacher_gaps", _sc2_teacher_gaps),
        ("building_travel", _sc3_building_travel),
        ("even_distribution", _sc4_even_distribution),
        ("lunch_breaks", _sc5_lunch_breaks),
        ("morning_core", _sc6_morning_core),
        ("no_same_subject_twice", _sc7_no_same_subject_twice),
        ("teacher_day_off", _sc8_teacher_day_off),
        ("back_to_back_limit", _sc9_back_to_back_limit),
        ("even_workload", _sc10_even_workload),
    ]

    soft_score = 0.0
    for key, fn in soft_evaluators:
        cs = fn(weight=w[key], **ctx)
        constraint_scores.append(cs)
        soft_score += cs.penalty

    # ---- 5. Utilization metrics ----
    num_rooms = len(data.rooms)
    total_assigned_room_slots = 0
    for a in schedule.assignments:
        course = courses_by_id.get(a.course_id)
        dur = course.session_duration_slots if course else 1
        total_assigned_room_slots += dur

    room_utilization_pct = 0.0
    if num_rooms > 0 and TOTAL_SLOTS > 0:
        room_utilization_pct = (
            total_assigned_room_slots / (num_rooms * TOTAL_SLOTS) * 100
        )

    teacher_utilizations: dict[str, float] = {}
    for teacher in data.teachers:
        assigns = assignments_by_teacher.get(teacher.id, [])
        total_slots = 0
        for a in assigns:
            course = courses_by_id.get(a.course_id)
            dur = course.session_duration_slots if course else 1
            total_slots += dur
        if teacher.max_hours_week > 0:
            teacher_utilizations[teacher.id] = total_slots / teacher.max_hours_week * 100
        else:
            teacher_utilizations[teacher.id] = 0.0

    avg_teacher_utilization_pct = 0.0
    if teacher_utilizations:
        avg_teacher_utilization_pct = sum(teacher_utilizations.values()) / len(
            teacher_utilizations
        )

    utilization = {
        "room_utilization_pct": round(room_utilization_pct, 2),
        "teacher_utilizations": {
            tid: round(v, 2) for tid, v in teacher_utilizations.items()
        },
        "avg_teacher_utilization_pct": round(avg_teacher_utilization_pct, 2),
    }

    total_score = hard_score + soft_score
    feasible = hard_score == 0.0

    return ScheduleScore(
        hard_score=hard_score,
        soft_score=soft_score,
        total_score=total_score,
        constraint_scores=constraint_scores,
        feasible=feasible,
        utilization=utilization,
    )
