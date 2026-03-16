"""Dashboard page - Quality metrics and constraint analysis."""

from collections import defaultdict

import streamlit as st
import plotly.graph_objects as go

from src.models.time_slot import DAY_SHORT, PERIODS_PER_DAY, LUNCH_PERIOD
from src.ui.components import build_lookup_maps

st.title("Dashboard")

schedule = st.session_state.current_schedule
score = st.session_state.current_score
data = st.session_state.schedule_data

if schedule is None or not schedule.assignments:
    st.info("No schedule available. Go to the Optimize page to generate one first.")
    st.stop()

teachers_map, courses_map, rooms_map, buildings_map, groups_map = build_lookup_maps(data)

# ═══════════════════════════════════════════════════════════════════════════
# KEY METRICS
# ═══════════════════════════════════════════════════════════════════════════
st.subheader("Key Metrics")

col1, col2, col3, col4 = st.columns(4)

is_feasible = schedule.status in ("optimal", "feasible")
with col1:
    st.metric("Feasibility", "Feasible" if is_feasible else "Infeasible")
    if is_feasible:
        st.success("OK")
    else:
        st.error("Issues detected")

with col2:
    st.metric("Total Assignments", len(schedule.assignments))

with col3:
    st.metric("Objective Value", f"{schedule.objective_value:.2f}")

with col4:
    st.metric("Solver Status", schedule.status.capitalize())

st.divider()

# ═══════════════════════════════════════════════════════════════════════════
# CONSTRAINT SATISFACTION (from ScheduleScore object)
# ═══════════════════════════════════════════════════════════════════════════
st.subheader("Constraint Satisfaction")

if score is not None and hasattr(score, "constraint_scores"):
    constraint_names = []
    penalties = []
    colors = []
    categories = []

    for cs in score.constraint_scores:
        constraint_names.append(cs.name)
        penalties.append(cs.penalty)
        categories.append(cs.category)
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
    st.plotly_chart(fig_constraints, width="stretch")

    # Score summary
    col_h, col_s, col_t = st.columns(3)
    with col_h:
        st.metric("Hard Score", f"{score.hard_score:.1f}")
    with col_s:
        st.metric("Soft Score", f"{score.soft_score:.1f}")
    with col_t:
        st.metric("Total Score", f"{score.total_score:.1f}")

    # Expandable violation details
    with st.expander("Violation Details"):
        for cs in score.constraint_scores:
            if cs.violations > 0:
                icon = "!!!" if cs.category == "hard" else "!"
                st.warning(f"**[{cs.category.upper()}] {cs.name}**: "
                          f"{cs.violations} violation(s), penalty = {cs.penalty:.2f}")
                for detail in cs.details[:5]:
                    st.caption(f"  - {detail}")
            else:
                st.success(f"**{cs.name}**: no violations")
else:
    st.info(
        "Detailed scoring not available. "
        "Re-run the optimizer to see constraint details."
    )

st.divider()

# ═══════════════════════════════════════════════════════════════════════════
# ROOM UTILIZATION
# ═══════════════════════════════════════════════════════════════════════════
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
    col_u1, col_u2 = st.columns(2)
    with col_u1:
        st.metric("Rooms Used", f"{len(used_rooms)} / {len(data.rooms)}")
    with col_u2:
        st.metric("Avg Utilization", f"{avg_util:.1f}%")

    for r in data.rooms:
        used = room_usage.get(r.id, 0)
        pct = (used / total_available_slots) if total_available_slots > 0 else 0
        if used > 0:
            st.progress(min(pct, 1.0), text=f"{r.name}: {pct*100:.1f}% ({used}/{total_available_slots} slots)")
else:
    st.info("No room usage data.")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════
# TEACHER WORKLOAD
# ═══════════════════════════════════════════════════════════════════════════
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
            t_names.append(t.name)
            t_hours.append(hours)
            t_max.append(t.max_hours_week)

    bar_colors = [
        "#f44336" if h > m else "#FF9800" if h > m * 0.8 else "#4CAF50"
        for h, m in zip(t_hours, t_max)
    ]

    fig_workload = go.Figure()
    fig_workload.add_trace(go.Bar(
        x=t_names, y=t_hours,
        name="Assigned Hours",
        marker_color=bar_colors,
        text=[f"{h}h" for h in t_hours],
        textposition="auto",
    ))
    fig_workload.add_trace(go.Scatter(
        x=t_names, y=t_max,
        name="Max Hours/Week",
        mode="markers",
        marker=dict(symbol="line-ew-open", size=15, color="black", line=dict(width=2)),
    ))
    fig_workload.update_layout(
        height=400,
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis_title="Hours",
        barmode="group",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig_workload, width="stretch")
else:
    st.info("No teacher workload data.")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════
# QUICK STATS
# ═══════════════════════════════════════════════════════════════════════════
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
    st.metric("Lunch Conflicts", lunch_conflicts)
    if lunch_conflicts == 0:
        st.success("No classes during lunch period")
    else:
        st.warning(f"{lunch_conflicts} class(es) overlap with lunch (period {LUNCH_PERIOD})")

with col_s2:
    st.write("**Assignments by Department**")
    for dept, count in sorted(dept_counts.items()):
        st.write(f"- {dept}: {count}")
