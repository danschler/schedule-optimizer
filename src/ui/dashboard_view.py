"""Dashboard page - Quality metrics and constraint analysis."""

from collections import defaultdict

import streamlit as st
import plotly.graph_objects as go

from src.models.time_slot import DAY_SHORT, PERIODS_PER_DAY, LUNCH_PERIOD
from src.ui.components import build_lookup_maps

st.title("Dashboard")
st.caption("Quality metrics, constraint analysis, and resource utilization for the current schedule.")

schedule = st.session_state.current_schedule
score = st.session_state.current_score
data = st.session_state.schedule_data

if schedule is None or not schedule.assignments:
    st.info(
        "No schedule available yet. "
        "Go to the **Optimize** page to generate one, then return here."
    )
    st.stop()

teachers_map, courses_map, rooms_map, buildings_map, groups_map = build_lookup_maps(data)

# =========================================================================
# KEY METRICS
# =========================================================================
is_feasible = schedule.status in ("optimal", "feasible")

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Status", schedule.status.capitalize())
with col2:
    st.metric("Feasibility", "Feasible" if is_feasible else "INFEASIBLE")
with col3:
    st.metric("Assignments", len(schedule.assignments))
with col4:
    st.metric("Objective", f"{schedule.objective_value:.1f}",
              help="Lower = better. Weighted sum of soft constraint penalties.")

if not is_feasible:
    st.error("The schedule has hard constraint violations. Review the details below.")

st.divider()

# =========================================================================
# CONSTRAINT SATISFACTION
# =========================================================================
st.subheader("Constraint Satisfaction")

if score is not None and hasattr(score, "constraint_scores"):
    # Score summary
    col_h, col_s, col_t = st.columns(3)
    with col_h:
        hard_ok = score.hard_score == 0
        st.metric("Hard Score", f"{score.hard_score:.1f}",
                   help="Must be 0 for a valid schedule.",
                   delta="OK" if hard_ok else "violations",
                   delta_color="normal" if hard_ok else "inverse")
    with col_s:
        st.metric("Soft Score", f"{score.soft_score:.1f}",
                   help="Lower = better. Measures preference violations.")
    with col_t:
        st.metric("Total Score", f"{score.total_score:.1f}")

    # Hard violations - surface prominently
    hard_violations = [
        cs for cs in score.constraint_scores
        if cs.category == "hard" and cs.violations > 0
    ]
    if hard_violations:
        for cs in hard_violations:
            st.error(
                f"**{cs.name}**: {cs.violations} violation(s), penalty = {cs.penalty:.2f}"
            )

    # Bar chart
    constraint_names = []
    penalties = []
    colors = []

    for cs in score.constraint_scores:
        constraint_names.append(cs.name)
        penalties.append(cs.penalty)
        if cs.category == "hard":
            colors.append("#4CAF50" if cs.penalty == 0 else "#f44336")
        else:
            colors.append("#4CAF50" if cs.penalty == 0 else "#f44336" if cs.penalty > 10 else "#FF9800")

    fig_constraints = go.Figure(go.Bar(
        x=penalties,
        y=constraint_names,
        orientation="h",
        marker_color=colors,
        text=[f"{p:.1f}" for p in penalties],
        textposition="auto",
    ))
    fig_constraints.update_layout(
        height=max(300, len(constraint_names) * 35),
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis_title="Penalty",
        yaxis=dict(autorange="reversed"),
    )
    st.plotly_chart(fig_constraints, use_container_width=True)

    # Actionable hint mapping
    _VIOLATION_HINTS: dict[str, str] = {
        "teacher_conflict": "Add more teachers or adjust availability windows.",
        "room_conflict": "Add more rooms or reduce session durations.",
        "student_group_conflict": "Check for overlapping required courses across groups.",
        "teacher_availability": "Expand teacher availability on the Data page.",
        "room_capacity": "Assign courses to larger rooms or reduce group sizes.",
        "teacher_gaps": "Increase the 'Teacher Gaps' weight on Optimize page.",
        "teacher_max_hours": "Reduce course load or raise teacher max-hours.",
        "lunch_conflict": "Increase the 'Lunch Breaks' weight on Optimize page.",
        "consecutive_classes": "Increase the 'Back-to-Back Limit' weight.",
        "building_change": "Increase the 'Building Travel' weight.",
    }

    # Violation details
    violations_exist = any(cs.violations > 0 for cs in score.constraint_scores)
    with st.expander("Violation Details", expanded=bool(hard_violations)):
        if not violations_exist:
            st.success("No violations detected across all constraints.")
        else:
            for cs in score.constraint_scores:
                if cs.violations > 0:
                    severity = "error" if cs.category == "hard" else "warning"
                    getattr(st, severity)(
                        f"**[{cs.category.upper()}] {cs.name}**: "
                        f"{cs.violations} violation(s), penalty = {cs.penalty:.2f}"
                    )
                    for detail in cs.details[:5]:
                        st.caption(f"  - {detail}")
                    if len(cs.details) > 5:
                        st.caption(f"  ... and {len(cs.details) - 5} more")
                    hint_key = cs.name.lower().replace(" ", "_")
                    hint = _VIOLATION_HINTS.get(hint_key)
                    if hint:
                        st.info(f"**Tip:** {hint}")
else:
    st.info("Detailed scoring not available. Re-run the optimizer to see constraint details.")

st.divider()

# =========================================================================
# RESOURCE UTILIZATION (side by side)
# =========================================================================
col_rooms, col_teachers = st.columns(2)

# -- Room Utilization ------------------------------------------------------
with col_rooms:
    st.subheader("Room Utilization")

    total_available_slots = len(DAY_SHORT) * PERIODS_PER_DAY
    room_usage = defaultdict(int)
    for a in schedule.assignments:
        course = courses_map.get(a.course_id)
        duration = course.session_duration_slots if course else 1
        room_usage[a.room_id] += duration

    if room_usage:
        room_names = []
        utilizations = []
        for r in data.rooms:
            used = room_usage.get(r.id, 0)
            pct = (used / total_available_slots) * 100 if total_available_slots > 0 else 0
            room_names.append(r.name)
            utilizations.append(round(pct, 1))

        used_rooms = [r for r in data.rooms if room_usage.get(r.id, 0) > 0]
        avg_util = sum(utilizations) / len(utilizations) if utilizations else 0

        mc1, mc2 = st.columns(2)
        mc1.metric("Used", f"{len(used_rooms)} / {len(data.rooms)}")
        mc2.metric("Avg", f"{avg_util:.0f}%")

        sorted_pairs = sorted(zip(room_names, utilizations), key=lambda x: x[1], reverse=True)
        sorted_names = [p[0] for p in sorted_pairs]
        sorted_utils = [p[1] for p in sorted_pairs]

        bar_colors = []
        for u in sorted_utils:
            if u == 0:
                bar_colors.append("#9E9E9E")
            elif u < 70:
                bar_colors.append("#4CAF50")
            elif u <= 90:
                bar_colors.append("#FF9800")
            else:
                bar_colors.append("#f44336")

        fig_rooms = go.Figure(go.Bar(
            x=sorted_utils, y=sorted_names, orientation="h",
            marker_color=bar_colors,
            text=[f"{u:.0f}%" for u in sorted_utils],
            textposition="auto",
        ))
        fig_rooms.update_layout(
            height=max(250, len(sorted_names) * 28),
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis_title="Utilization %",
            xaxis=dict(range=[0, 105]),
            yaxis=dict(autorange="reversed"),
        )
        st.plotly_chart(fig_rooms, use_container_width=True)
    else:
        st.info("No room usage data.")

# -- Teacher Workload ------------------------------------------------------
with col_teachers:
    st.subheader("Teacher Workload")

    teacher_hours = defaultdict(int)
    for a in schedule.assignments:
        course = courses_map.get(a.course_id)
        duration = course.session_duration_slots if course else 1
        teacher_hours[a.teacher_id] += duration

    if teacher_hours:
        t_names = []
        t_hours = []
        t_max = []
        for t in data.teachers:
            hours = teacher_hours.get(t.id, 0)
            if hours > 0:
                t_names.append(t.name.split()[-1])  # Last name for compact display
                t_hours.append(hours)
                t_max.append(t.max_hours_week)

        bar_colors = [
            "#f44336" if h > m else "#FF9800" if h > m * 0.8 else "#4CAF50"
            for h, m in zip(t_hours, t_max)
        ]

        fig_workload = go.Figure()
        fig_workload.add_trace(go.Bar(
            x=t_names, y=t_hours,
            name="Assigned",
            marker_color=bar_colors,
            text=[f"{h}h" for h in t_hours],
            textposition="auto",
        ))
        fig_workload.add_trace(go.Scatter(
            x=t_names, y=t_max,
            name="Max/Week",
            mode="markers",
            marker=dict(symbol="line-ew-open", size=15, color="black", line=dict(width=2)),
        ))
        fig_workload.update_layout(
            height=max(300, 400),
            margin=dict(l=10, r=10, t=10, b=10),
            yaxis_title="Hours",
            barmode="group",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig_workload, use_container_width=True)
    else:
        st.info("No teacher workload data.")

st.divider()

# =========================================================================
# QUICK STATS
# =========================================================================
st.subheader("Quick Stats")

lunch_conflicts = 0
for a in schedule.assignments:
    course = courses_map.get(a.course_id)
    duration = course.session_duration_slots if course else 1
    for slot in range(a.period, a.period + duration):
        if slot == LUNCH_PERIOD:
            lunch_conflicts += 1
            break

dept_counts = defaultdict(int)
for a in schedule.assignments:
    course = courses_map.get(a.course_id)
    if course:
        dept_counts[course.department] += 1

col_s1, col_s2 = st.columns(2)
with col_s1:
    st.metric("Lunch Conflicts", lunch_conflicts,
              help=f"Number of classes overlapping with lunch period ({PERIOD_LABELS[LUNCH_PERIOD]})")
    if lunch_conflicts == 0:
        st.success("No classes during lunch")
    else:
        st.warning(f"{lunch_conflicts} class(es) overlap with lunch")

with col_s2:
    st.markdown("**Assignments by Department**")
    if dept_counts:
        from src.ui.components import get_department_color
        dept_labels = list(dept_counts.keys())
        dept_values = [dept_counts[d] for d in dept_labels]
        dept_colors = [get_department_color(d) for d in dept_labels]

        fig_dept = go.Figure(go.Pie(
            labels=dept_labels,
            values=dept_values,
            marker=dict(colors=dept_colors),
            hole=0.4,
            textinfo="label+value",
        ))
        fig_dept.update_layout(
            height=260,
            margin=dict(l=10, r=10, t=10, b=10),
            showlegend=False,
        )
        st.plotly_chart(fig_dept, use_container_width=True)
    else:
        st.caption("No department data.")
