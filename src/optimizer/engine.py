"""CP-SAT based schedule optimization engine."""

from __future__ import annotations

import os
from collections import defaultdict

from ortools.sat.python import cp_model

from src.models.building import Building
from src.models.course import Course
from src.models.room import Room
from src.models.schedule import Schedule, ScheduleAssignment, ScheduleData
from src.models.student_group import StudentGroup
from src.models.teacher import Teacher
from src.models.time_slot import (
    DAYS,
    LUNCH_PERIOD,
    PERIODS_PER_DAY,
    slot_index,
    slot_to_day_period,
)

from .constraints import (
    ConstraintConfig,
    get_eligible_rooms,
    get_eligible_slots,
    get_eligible_teachers,
)


def _weight(value: float) -> int:
    """Convert a float weight to an integer for CP-SAT (multiply by 10)."""
    return int(round(value * 10))


class ScheduleOptimizer:
    """Core CP-SAT schedule optimizer.

    Creates boolean decision variables for every feasible
    (course, session, teacher, room, start_slot) combination, adds hard and
    soft constraints, then minimises the weighted sum of soft-constraint
    penalties.
    """

    def __init__(
        self,
        data: ScheduleData,
        config: ConstraintConfig | None = None,
    ) -> None:
        self.data = data
        self.config = config or ConstraintConfig()
        self.model = cp_model.CpModel()

        # (course_id, session_idx, teacher_id, room_id, start_slot) -> BoolVar
        self.variables: dict[tuple[str, int, str, str, int], cp_model.IntVar] = {}

        # Lookup dicts
        self.teachers_by_id: dict[str, Teacher] = {t.id: t for t in data.teachers}
        self.courses_by_id: dict[str, Course] = {c.id: c for c in data.courses}
        self.rooms_by_id: dict[str, Room] = {r.id: r for r in data.rooms}
        self.groups_by_id: dict[str, StudentGroup] = {
            g.id: g for g in data.student_groups
        }
        self.buildings_by_id: dict[str, Building] = {
            b.id: b for b in data.buildings
        }

        # course_id -> student_group_id
        self._course_group: dict[str, str] = {
            c.id: c.student_group_id for c in data.courses
        }
        # student_group_id -> list of course_ids
        self._group_courses: dict[str, list[str]] = defaultdict(list)
        for c in data.courses:
            self._group_courses[c.student_group_id].append(c.id)

        # Pre-computed variable indexes (populated in _create_variables)
        self._vars_by_course_session: dict[
            tuple[str, int], list[cp_model.IntVar]
        ] = defaultdict(list)
        self._vars_by_teacher_slot: dict[
            tuple[str, int], list[cp_model.IntVar]
        ] = defaultdict(list)
        self._vars_by_room_slot: dict[
            tuple[str, int], list[cp_model.IntVar]
        ] = defaultdict(list)
        self._vars_by_group_slot: dict[
            tuple[str, int], list[cp_model.IntVar]
        ] = defaultdict(list)
        self._vars_by_teacher_day: dict[
            tuple[str, int], list[tuple[cp_model.IntVar, int]]
        ] = defaultdict(list)
        self._vars_by_teacher_week: dict[
            str, list[tuple[cp_model.IntVar, int]]
        ] = defaultdict(list)
        self._vars_by_teacher_day_period: dict[
            tuple[str, int, int], list[cp_model.IntVar]
        ] = defaultdict(list)
        self._vars_by_group_day_period: dict[
            tuple[str, int, int], list[cp_model.IntVar]
        ] = defaultdict(list)
        self._vars_by_group_day_period_bldg: dict[
            tuple[str, int, int], list[tuple[str, cp_model.IntVar]]
        ] = defaultdict(list)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def solve(self, time_limit: int = 30, num_workers: int | None = None) -> Schedule:
        """Build and solve the CP-SAT model.

        Parameters
        ----------
        time_limit:
            Maximum solver time in seconds.
        num_workers:
            Number of parallel workers. Defaults to os.cpu_count() or 8.

        Returns
        -------
        Schedule with assignments on success, or status="infeasible".
        """
        self._create_variables()
        self._build_indexes()
        self._add_hard_constraints()
        penalties = self._add_soft_constraints()
        if penalties:
            self.model.Minimize(sum(penalties))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit
        solver.parameters.num_workers = num_workers or os.cpu_count() or 8

        status = solver.Solve(self.model)

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return self._extract_solution(solver, status)
        return Schedule(status="infeasible", objective_value=float("inf"))

    # ------------------------------------------------------------------
    # Variable creation
    # ------------------------------------------------------------------

    def _create_variables(self) -> None:
        """Create boolean decision variables with pre-filtering."""
        for course in self.data.courses:
            eligible_teachers = get_eligible_teachers(course, self.data.teachers)
            eligible_rooms = get_eligible_rooms(
                course, self.data.rooms, self.groups_by_id
            )
            for session_idx in range(course.sessions_per_week):
                for teacher in eligible_teachers:
                    eligible_slots = get_eligible_slots(
                        course, teacher, enforce_fixed=(session_idx == 0)
                    )
                    for room in eligible_rooms:
                        for slot in eligible_slots:
                            key = (
                                course.id,
                                session_idx,
                                teacher.id,
                                room.id,
                                slot,
                            )
                            name = (
                                f"c{course.id}_s{session_idx}"
                                f"_t{teacher.id}_r{room.id}_sl{slot}"
                            )
                            self.variables[key] = self.model.NewBoolVar(name)

    def _build_indexes(self) -> None:
        """Pre-compute lookup structures from variables for constraint methods."""
        for (cid, sidx, tid, rid, start_sl), var in self.variables.items():
            course = self.courses_by_id[cid]
            duration = course.session_duration_slots
            day, period = slot_to_day_period(start_sl)
            gid = self._course_group.get(cid)
            room = self.rooms_by_id[rid]

            # By course-session
            self._vars_by_course_session[(cid, sidx)].append(var)

            # By teacher/room/group occupied slots (expanded for duration)
            for d in range(duration):
                occupied_slot = start_sl + d
                occ_period = period + d
                self._vars_by_teacher_slot[(tid, occupied_slot)].append(var)
                self._vars_by_room_slot[(rid, occupied_slot)].append(var)
                if gid:
                    self._vars_by_group_slot[(gid, occupied_slot)].append(var)
                    self._vars_by_group_day_period[(gid, day, occ_period)].append(var)
                    self._vars_by_group_day_period_bldg[
                        (gid, day, occ_period)
                    ].append((room.building_id, var))
                self._vars_by_teacher_day_period[(tid, day, occ_period)].append(var)

            # By teacher-day and teacher-week (for hour limits)
            self._vars_by_teacher_day[(tid, day)].append((var, duration))
            self._vars_by_teacher_week[tid].append((var, duration))

    # ------------------------------------------------------------------
    # Hard constraints
    # ------------------------------------------------------------------

    def _add_hard_constraints(self) -> None:
        """Add all hard constraints to the model."""
        self._hc_exactly_one_assignment()
        self._hc_no_teacher_double_booking()
        self._hc_no_room_double_booking()
        self._hc_no_student_group_double_booking()
        self._hc_teacher_max_hours()
        self._hc_multi_session_ordering()

    # HC1 -- each (course, session) assigned exactly once
    def _hc_exactly_one_assignment(self) -> None:
        for var_list in self._vars_by_course_session.values():
            self.model.AddExactlyOne(var_list)

    # HC2 -- no teacher double-booking
    def _hc_no_teacher_double_booking(self) -> None:
        for var_list in self._vars_by_teacher_slot.values():
            if len(var_list) > 1:
                self.model.Add(sum(var_list) <= 1)

    # HC3 -- no room double-booking
    def _hc_no_room_double_booking(self) -> None:
        for var_list in self._vars_by_room_slot.values():
            if len(var_list) > 1:
                self.model.Add(sum(var_list) <= 1)

    # HC8 -- no student-group double-booking
    def _hc_no_student_group_double_booking(self) -> None:
        for var_list in self._vars_by_group_slot.values():
            if len(var_list) > 1:
                self.model.Add(sum(var_list) <= 1)

    # HC7 -- max teaching hours per day / per week
    def _hc_teacher_max_hours(self) -> None:
        for (tid, _day), entries in self._vars_by_teacher_day.items():
            teacher = self.teachers_by_id[tid]
            self.model.Add(
                sum(var * dur for var, dur in entries) <= teacher.max_hours_day
            )

        for tid, entries in self._vars_by_teacher_week.items():
            teacher = self.teachers_by_id[tid]
            self.model.Add(
                sum(var * dur for var, dur in entries) <= teacher.max_hours_week
            )

    # Symmetry breaking: session i must start before session i+1
    def _hc_multi_session_ordering(self) -> None:
        cs_vars: dict[tuple[str, int], list[tuple[int, cp_model.IntVar]]] = (
            defaultdict(list)
        )
        for (cid, sidx, _tid, _rid, start_sl), var in self.variables.items():
            cs_vars[(cid, sidx)].append((start_sl, var))

        courses_with_multi = [
            c for c in self.data.courses if c.sessions_per_week > 1
        ]
        for course in courses_with_multi:
            total_slots = DAYS * PERIODS_PER_DAY
            for sidx in range(course.sessions_per_week - 1):
                vars_a = cs_vars.get((course.id, sidx), [])
                vars_b = cs_vars.get((course.id, sidx + 1), [])
                if not vars_a or not vars_b:
                    continue

                slot_var_a = self.model.NewIntVar(0, total_slots - 1,
                                                  f"slot_{course.id}_{sidx}")
                slot_var_b = self.model.NewIntVar(0, total_slots - 1,
                                                  f"slot_{course.id}_{sidx+1}")
                self.model.Add(
                    slot_var_a == sum(sl * v for sl, v in vars_a)
                )
                self.model.Add(
                    slot_var_b == sum(sl * v for sl, v in vars_b)
                )
                self.model.Add(slot_var_a < slot_var_b)

    # ------------------------------------------------------------------
    # Soft constraints
    # ------------------------------------------------------------------

    def _add_soft_constraints(self) -> list[cp_model.IntVar]:
        """Add all soft constraints; return list of penalty IntVars."""
        penalties: list[cp_model.IntVar] = []
        penalties.extend(self._sc_student_gaps())
        penalties.extend(self._sc_teacher_gaps())
        penalties.extend(self._sc_building_travel())
        penalties.extend(self._sc_even_distribution())
        penalties.extend(self._sc_lunch_breaks())
        penalties.extend(self._sc_morning_core())
        penalties.extend(self._sc_no_same_subject_twice())
        penalties.extend(self._sc_teacher_day_off())
        penalties.extend(self._sc_back_to_back_limit())
        penalties.extend(self._sc_even_workload())
        return penalties

    # Shared helper for gap penalties (used by SC1 and SC2)
    def _build_gap_penalties(
        self,
        entity_day_period: dict[tuple[str, int, int], list[cp_model.IntVar]],
        entity_ids: list[str],
        w: int,
        prefix: str,
    ) -> list[cp_model.IntVar]:
        """Build gap penalties for a set of entities (groups or teachers).

        For each entity/day, penalise empty periods between the first and last
        occupied period.
        """
        penalties: list[cp_model.IntVar] = []
        for eid in entity_ids:
            for day in range(DAYS):
                occupied: dict[int, cp_model.IntVar] = {}
                for period in range(PERIODS_PER_DAY):
                    var_list = entity_day_period.get((eid, day, period))
                    if var_list:
                        occ = self.model.NewBoolVar(
                            f"{prefix}occ_{eid}_d{day}_p{period}"
                        )
                        self.model.AddMaxEquality(occ, var_list)
                        occupied[period] = occ

                if len(occupied) < 2:
                    continue

                sorted_periods = sorted(occupied.keys())
                for i in range(len(sorted_periods) - 1):
                    p_lo = sorted_periods[i]
                    p_hi = sorted_periods[i + 1]
                    for mid in range(p_lo + 1, p_hi):
                        if mid in occupied:
                            continue
                        pen = self.model.NewBoolVar(
                            f"{prefix}gap_{eid}_d{day}_{p_lo}_{mid}_{p_hi}"
                        )
                        self.model.AddBoolAnd(
                            [occupied[p_lo], occupied[p_hi]]
                        ).OnlyEnforceIf(pen)
                        self.model.AddBoolOr(
                            [occupied[p_lo].Not(), occupied[p_hi].Not()]
                        ).OnlyEnforceIf(pen.Not())
                        scaled = self.model.NewIntVar(
                            0, w, f"{prefix}gap_w_{eid}_d{day}_p{mid}"
                        )
                        self.model.Add(scaled == w * pen)
                        penalties.append(scaled)
        return penalties

    # SC1 -- student gaps
    def _sc_student_gaps(self) -> list[cp_model.IntVar]:
        w = _weight(self.config.student_gaps)
        if w == 0:
            return []
        return self._build_gap_penalties(
            self._vars_by_group_day_period,
            list(self.groups_by_id.keys()),
            w,
            "s",
        )

    # SC2 -- teacher gaps
    def _sc_teacher_gaps(self) -> list[cp_model.IntVar]:
        w = _weight(self.config.teacher_gaps)
        if w == 0:
            return []
        return self._build_gap_penalties(
            self._vars_by_teacher_day_period,
            list(self.teachers_by_id.keys()),
            w,
            "t",
        )

    # SC3 -- building travel: penalise consecutive slots in different buildings,
    #         weighted by actual travel time (matching scorer)
    def _sc_building_travel(self) -> list[cp_model.IntVar]:
        w = _weight(self.config.building_travel)
        if w == 0:
            return []
        penalties: list[cp_model.IntVar] = []
        pen_counter = 0

        for gid in self.groups_by_id:
            for day in range(DAYS):
                for period in range(PERIODS_PER_DAY - 1):
                    entries_a = self._vars_by_group_day_period_bldg.get(
                        (gid, day, period), []
                    )
                    entries_b = self._vars_by_group_day_period_bldg.get(
                        (gid, day, period + 1), []
                    )
                    if not entries_a or not entries_b:
                        continue
                    for bid_a, var_a in entries_a:
                        for bid_b, var_b in entries_b:
                            if bid_a == bid_b:
                                continue
                            # Look up actual travel time
                            bldg = self.buildings_by_id.get(bid_a)
                            travel = 1
                            if bldg:
                                travel = max(
                                    bldg.travel_time_to.get(bid_b, 1), 1
                                )
                            pen = self.model.NewBoolVar(
                                f"travel_{gid}_d{day}_p{period}_{bid_a}_{bid_b}"
                            )
                            self.model.AddBoolAnd([var_a, var_b]).OnlyEnforceIf(
                                pen
                            )
                            self.model.AddBoolOr(
                                [var_a.Not(), var_b.Not()]
                            ).OnlyEnforceIf(pen.Not())
                            scaled_w = w * travel
                            scaled = self.model.NewIntVar(
                                0, scaled_w,
                                f"travel_w_{gid}_d{day}_p{period}_{pen_counter}",
                            )
                            pen_counter += 1
                            self.model.Add(scaled == scaled_w * pen)
                            penalties.append(scaled)
        return penalties

    # SC4 -- even distribution of classes across days for each group
    def _sc_even_distribution(self) -> list[cp_model.IntVar]:
        w = _weight(self.config.even_distribution)
        if w == 0:
            return []
        penalties: list[cp_model.IntVar] = []

        for gid in self.groups_by_id:
            course_ids = set(self._group_courses.get(gid, []))
            if not course_ids:
                continue

            # Collect day loads from pre-computed index
            day_loads: dict[int, list[tuple[cp_model.IntVar, int]]] = defaultdict(list)
            for (cid, _sidx, _tid, _rid, start_sl), var in self.variables.items():
                if cid not in course_ids:
                    continue
                day, _ = slot_to_day_period(start_sl)
                dur = self.courses_by_id[cid].session_duration_slots
                day_loads[day].append((var, dur))

            if not day_loads:
                continue

            max_possible = sum(
                self.courses_by_id[cid].sessions_per_week
                * self.courses_by_id[cid].session_duration_slots
                for cid in course_ids
            )

            day_vars: list[cp_model.IntVar] = []
            for day in range(DAYS):
                dv = self.model.NewIntVar(
                    0, max_possible, f"dload_{gid}_d{day}"
                )
                entries = day_loads.get(day, [])
                if entries:
                    self.model.Add(
                        dv == sum(var * dur for var, dur in entries)
                    )
                else:
                    self.model.Add(dv == 0)
                day_vars.append(dv)

            max_load = self.model.NewIntVar(
                0, max_possible, f"maxload_{gid}"
            )
            min_load = self.model.NewIntVar(
                0, max_possible, f"minload_{gid}"
            )
            self.model.AddMaxEquality(max_load, day_vars)
            self.model.AddMinEquality(min_load, day_vars)

            spread = self.model.NewIntVar(
                0, max_possible, f"spread_{gid}"
            )
            self.model.Add(spread == max_load - min_load)

            excess = self.model.NewIntVar(
                0, max_possible, f"spread_exc_{gid}"
            )
            self.model.AddMaxEquality(
                excess, [spread - 1, self.model.NewConstant(0)]
            )

            pen = self.model.NewIntVar(
                0, w * max_possible, f"edist_pen_{gid}"
            )
            self.model.Add(pen == w * excess)
            penalties.append(pen)
        return penalties

    # SC5 -- lunch breaks: penalise assignments at LUNCH_PERIOD
    def _sc_lunch_breaks(self) -> list[cp_model.IntVar]:
        w = _weight(self.config.lunch_breaks)
        if w == 0:
            return []
        penalties: list[cp_model.IntVar] = []
        for (cid, _sidx, _tid, _rid, start_sl), var in self.variables.items():
            duration = self.courses_by_id[cid].session_duration_slots
            _day, period = slot_to_day_period(start_sl)
            occupies_lunch = any(
                (period + d) == LUNCH_PERIOD for d in range(duration)
            )
            if occupies_lunch:
                pen = self.model.NewIntVar(0, w, f"lunch_{cid}_{start_sl}")
                self.model.Add(pen == w * var)
                penalties.append(pen)
        return penalties

    # SC6 -- morning preference for core subjects (penalise afternoon slots)
    _CORE_KEYWORDS = frozenset({
        "math", "mathematics", "science", "physics", "chemistry",
        "biology", "language", "english", "literature", "history",
    })

    def _sc_morning_core(self) -> list[cp_model.IntVar]:
        w = _weight(self.config.morning_core)
        if w == 0:
            return []
        penalties: list[cp_model.IntVar] = []
        afternoon_start = 5  # period index 5 = 13:00
        for (cid, _sidx, _tid, _rid, start_sl), var in self.variables.items():
            course = self.courses_by_id[cid]
            if course.subject.lower() not in self._CORE_KEYWORDS:
                continue
            _day, period = slot_to_day_period(start_sl)
            if period >= afternoon_start:
                pen = self.model.NewIntVar(
                    0, w, f"morning_{cid}_{start_sl}"
                )
                self.model.Add(pen == w * var)
                penalties.append(pen)
        return penalties

    # SC7 -- no same subject twice in one day for a group
    def _sc_no_same_subject_twice(self) -> list[cp_model.IntVar]:
        w = _weight(self.config.no_same_subject_twice)
        if w == 0:
            return []
        penalties: list[cp_model.IntVar] = []

        gds: dict[tuple[str, int, str], list[cp_model.IntVar]] = defaultdict(list)
        for (cid, _sidx, _tid, _rid, start_sl), var in self.variables.items():
            course = self.courses_by_id[cid]
            gid = course.student_group_id
            day, _ = slot_to_day_period(start_sl)
            gds[(gid, day, course.subject)].append(var)

        for (gid, day, subj), var_list in gds.items():
            if len(var_list) <= 1:
                continue
            total = self.model.NewIntVar(
                0, len(var_list), f"subj_cnt_{gid}_d{day}_{subj}"
            )
            self.model.Add(total == sum(var_list))
            excess = self.model.NewIntVar(
                0, len(var_list), f"subj_exc_{gid}_d{day}_{subj}"
            )
            self.model.AddMaxEquality(excess, [total - 1, self.model.NewConstant(0)])
            pen = self.model.NewIntVar(
                0, w * len(var_list), f"subj_pen_{gid}_d{day}_{subj}"
            )
            self.model.Add(pen == w * excess)
            penalties.append(pen)
        return penalties

    # SC8 -- teacher preferred days off
    def _sc_teacher_day_off(self) -> list[cp_model.IntVar]:
        w = _weight(self.config.teacher_day_off)
        if w == 0:
            return []
        penalties: list[cp_model.IntVar] = []
        for (cid, _sidx, tid, _rid, start_sl), var in self.variables.items():
            teacher = self.teachers_by_id[tid]
            if not teacher.preferred_days_off:
                continue
            day, _ = slot_to_day_period(start_sl)
            if day in teacher.preferred_days_off:
                pen = self.model.NewIntVar(
                    0, w, f"dayoff_{tid}_d{day}_{cid}_{start_sl}"
                )
                self.model.Add(pen == w * var)
                penalties.append(pen)
        return penalties

    # SC9 -- back-to-back limit: penalise >3 consecutive teaching periods
    def _sc_back_to_back_limit(self) -> list[cp_model.IntVar]:
        w = _weight(self.config.back_to_back_limit)
        if w == 0:
            return []
        penalties: list[cp_model.IntVar] = []

        for tid in self.teachers_by_id:
            for day in range(DAYS):
                occupied: dict[int, cp_model.IntVar] = {}
                for period in range(PERIODS_PER_DAY):
                    var_list = self._vars_by_teacher_day_period.get(
                        (tid, day, period)
                    )
                    if var_list:
                        occ = self.model.NewBoolVar(
                            f"b2b_occ_{tid}_d{day}_p{period}"
                        )
                        self.model.AddMaxEquality(occ, var_list)
                        occupied[period] = occ

                # Sliding window of 4 consecutive periods
                for start_p in range(PERIODS_PER_DAY - 3):
                    window = [
                        occupied.get(start_p + k) for k in range(4)
                    ]
                    if any(v is None for v in window):
                        continue
                    pen = self.model.NewBoolVar(
                        f"b2b_{tid}_d{day}_p{start_p}"
                    )
                    self.model.AddBoolAnd(window).OnlyEnforceIf(pen)  # type: ignore[arg-type]
                    self.model.AddBoolOr(
                        [v.Not() for v in window]  # type: ignore[union-attr]
                    ).OnlyEnforceIf(pen.Not())
                    scaled = self.model.NewIntVar(
                        0, w, f"b2b_w_{tid}_d{day}_p{start_p}"
                    )
                    self.model.Add(scaled == w * pen)
                    penalties.append(scaled)
        return penalties

    # SC10 -- even workload: penalise per-teacher daily spread
    #         Only considers days with possible assignments (matching scorer).
    def _sc_even_workload(self) -> list[cp_model.IntVar]:
        w = _weight(self.config.even_workload)
        if w == 0:
            return []
        penalties: list[cp_model.IntVar] = []

        max_daily = max(
            (t.max_hours_day for t in self.data.teachers), default=9
        )

        for tid, teacher in self.teachers_by_id.items():
            # Only build day vars for days that have possible assignments
            active_day_vars: list[cp_model.IntVar] = []
            for day in range(DAYS):
                entries = self._vars_by_teacher_day.get((tid, day))
                if entries:
                    dv = self.model.NewIntVar(
                        0, max_daily, f"wload_{tid}_d{day}"
                    )
                    self.model.Add(
                        dv == sum(var * dur for var, dur in entries)
                    )
                    active_day_vars.append(dv)

            if len(active_day_vars) < 2:
                continue

            max_d = self.model.NewIntVar(0, max_daily, f"wload_max_{tid}")
            min_d = self.model.NewIntVar(0, max_daily, f"wload_min_{tid}")
            self.model.AddMaxEquality(max_d, active_day_vars)
            self.model.AddMinEquality(min_d, active_day_vars)

            spread = self.model.NewIntVar(0, max_daily, f"wload_spread_{tid}")
            self.model.Add(spread == max_d - min_d)

            # Allow spread of 1 for free (matching scorer)
            excess = self.model.NewIntVar(
                0, max_daily, f"wload_exc_{tid}"
            )
            self.model.AddMaxEquality(
                excess, [spread - 1, self.model.NewConstant(0)]
            )

            pen = self.model.NewIntVar(
                0, w * max_daily, f"wload_pen_{tid}"
            )
            self.model.Add(pen == w * excess)
            penalties.append(pen)
        return penalties

    # ------------------------------------------------------------------
    # Solution extraction
    # ------------------------------------------------------------------

    def _extract_solution(
        self,
        solver: cp_model.CpSolver,
        status: int,
    ) -> Schedule:
        """Extract assignments from a solved model."""
        status_str = "optimal" if status == cp_model.OPTIMAL else "feasible"
        assignments: list[ScheduleAssignment] = []

        for (cid, sidx, tid, rid, start_sl), var in self.variables.items():
            if solver.Value(var):
                day, period = slot_to_day_period(start_sl)
                assignments.append(
                    ScheduleAssignment(
                        course_id=cid,
                        session_index=sidx,
                        teacher_id=tid,
                        room_id=rid,
                        day=day,
                        period=period,
                    )
                )

        return Schedule(
            assignments=assignments,
            status=status_str,
            objective_value=solver.ObjectiveValue(),
        )
