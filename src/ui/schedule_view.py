"""Schedule View page - Weekly grid visualization using Plotly."""

import csv
import io
from collections import defaultdict

import streamlit as st
import plotly.graph_objects as go

from src.models.time_slot import DAY_SHORT, PERIOD_LABELS, LUNCH_PERIOD, PERIODS_PER_DAY
from src.ui.components import get_department_color, build_lookup_maps, DEFAULT_COLOR

st.title("Schedule View")
st.caption("Interactive weekly timetable. Hover over any block for details.")

schedule = st.session_state.current_schedule
data = st.session_state.schedule_data

if schedule is None or not schedule.assignments:
    st.info(
        "No schedule available yet. "
        "Go to the **Optimize** page to generate one."
    )
    st.stop()

teachers_map, courses_map, rooms_map, buildings_map, groups_map = build_lookup_maps(data)

# -- Department color legend (above chart) ---------------------------------
departments_in_data = sorted({c.department for c in data.courses if c.department})
if departments_in_data:
    from src.ui.components import DEPARTMENT_COLORS
    legend_html_parts = []
    for dept in departments_in_data:
        color = DEPARTMENT_COLORS.get(dept, DEFAULT_COLOR)
        legend_html_parts.append(
            f'<span style="background-color:{color};color:white;padding:2px 10px;'
            f'border-radius:4px;font-size:0.85em;margin-right:8px;">{dept}</span>'
        )
    st.markdown(" ".join(legend_html_parts), unsafe_allow_html=True)

# -- Filters ---------------------------------------------------------------
filter_col1, filter_col2 = st.columns([1, 2])

with filter_col1:
    filter_mode = st.radio(
        "View by",
        ["All", "Student Group", "Teacher", "Room", "Course"],
        horizontal=True,
    )

filtered_assignments = list(schedule.assignments)

with filter_col2:
    if filter_mode == "Teacher":
        teacher_options = {t.id: t.name for t in data.teachers}
        selected_teacher = st.selectbox(
            "Select Teacher",
            options=list(teacher_options.keys()),
            format_func=lambda x: teacher_options[x],
        )
        filtered_assignments = [a for a in filtered_assignments if a.teacher_id == selected_teacher]

    elif filter_mode == "Student Group":
        group_options = {g.id: g.name for g in data.student_groups}
        selected_group = st.selectbox(
            "Select Student Group",
            options=list(group_options.keys()),
            format_func=lambda x: group_options[x],
        )
        group_course_ids = {c.id for c in data.courses if c.student_group_id == selected_group}
        filtered_assignments = [a for a in filtered_assignments if a.course_id in group_course_ids]

    elif filter_mode == "Room":
        room_options = {r.id: r.name for r in data.rooms}
        selected_room = st.selectbox(
            "Select Room",
            options=list(room_options.keys()),
            format_func=lambda x: room_options[x],
        )
        filtered_assignments = [a for a in filtered_assignments if a.room_id == selected_room]

    elif filter_mode == "Course":
        course_options = {c.id: c.name for c in data.courses}
        selected_course = st.selectbox(
            "Select Course",
            options=list(course_options.keys()),
            format_func=lambda x: course_options[x],
        )
        filtered_assignments = [a for a in filtered_assignments if a.course_id == selected_course]

# Overlap warning for "All" view
if filter_mode == "All":
    slot_counts: dict[tuple[int, int], int] = defaultdict(int)
    for a in filtered_assignments:
        course = courses_map.get(a.course_id)
        duration = course.session_duration_slots if course else 1
        for p in range(a.period, a.period + duration):
            slot_counts[(a.day, p)] += 1
    if any(v > 1 for v in slot_counts.values()):
        st.warning(
            "Multiple assignments overlap in the **All** view. "
            "Use the filters above for a clearer per-group/teacher/room view."
        )

st.caption(f"Showing **{len(filtered_assignments)}** assignment(s)")

# -- Build Plotly weekly grid ----------------------------------------------
fig = go.Figure()

num_days = len(DAY_SHORT)
num_periods = PERIODS_PER_DAY

# Layout
fig.update_layout(
    height=680,
    margin=dict(l=80, r=20, t=40, b=40),
    xaxis=dict(
        range=[-0.5, num_days - 0.5],
        tickvals=list(range(num_days)),
        ticktext=DAY_SHORT,
        side="top",
        fixedrange=True,
    ),
    yaxis=dict(
        range=[num_periods - 0.5, -0.5],
        tickvals=list(range(num_periods)),
        ticktext=PERIOD_LABELS,
        fixedrange=True,
    ),
    plot_bgcolor="white",
    showlegend=False,
    hoverlabel=dict(bgcolor="white", font_size=12),
)

# Grid lines
for d in range(num_days + 1):
    fig.add_shape(
        type="line", x0=d - 0.5, x1=d - 0.5, y0=-0.5, y1=num_periods - 0.5,
        line=dict(color="#E0E0E0", width=1),
    )
for p in range(num_periods + 1):
    fig.add_shape(
        type="line", x0=-0.5, x1=num_days - 0.5, y0=p - 0.5, y1=p - 0.5,
        line=dict(color="#E0E0E0", width=1),
    )

# Highlight lunch period
fig.add_shape(
    type="rect",
    x0=-0.5, x1=num_days - 0.5,
    y0=LUNCH_PERIOD - 0.5, y1=LUNCH_PERIOD + 0.5,
    fillcolor="rgba(200, 200, 200, 0.2)",
    line=dict(width=0),
    layer="below",
)
# Lunch label
fig.add_annotation(
    x=num_days - 0.5, y=LUNCH_PERIOD,
    text="lunch",
    showarrow=False,
    font=dict(size=9, color="#999"),
    xanchor="right",
    xshift=-4,
)

# Draw assignments as colored rectangles with hover tooltips
for a in filtered_assignments:
    course = courses_map.get(a.course_id)
    teacher = teachers_map.get(a.teacher_id)
    room = rooms_map.get(a.room_id)

    if not course:
        continue

    dept = course.department
    color = get_department_color(dept)
    duration = course.session_duration_slots

    course_name = course.name
    teacher_name = teacher.name if teacher else a.teacher_id
    teacher_last = teacher.name.split()[-1] if teacher else a.teacher_id
    room_name = room.name if room else a.room_id
    group = groups_map.get(course.student_group_id)
    group_name = group.name if group else course.student_group_id

    day_str = DAY_SHORT[a.day] if a.day < len(DAY_SHORT) else f"Day {a.day}"
    period_str = PERIOD_LABELS[a.period] if a.period < len(PERIOD_LABELS) else f"P{a.period}"

    x0 = a.day - 0.45
    x1 = a.day + 0.45
    y0 = a.period - 0.45
    y1 = a.period + duration - 0.55

    # Colored rectangle
    fig.add_shape(
        type="rect", x0=x0, x1=x1, y0=y0, y1=y1,
        fillcolor=color, opacity=0.75,
        line=dict(color=color, width=1),
        layer="above",
    )

    # Hover tooltip via invisible scatter point
    mid_y = a.period + (duration - 1) / 2
    hover_text = (
        f"<b>{course_name}</b><br>"
        f"Teacher: {teacher_name}<br>"
        f"Room: {room_name}<br>"
        f"Group: {group_name}<br>"
        f"Time: {day_str} {period_str}<br>"
        f"Duration: {duration}h | Dept: {dept}"
    )
    fig.add_trace(go.Scatter(
        x=[a.day], y=[mid_y],
        mode="markers",
        marker=dict(size=max(20, duration * 15), opacity=0),
        hoverinfo="text",
        hovertext=hover_text,
        showlegend=False,
    ))

    # Text label on the block
    display_name = course_name if len(course_name) <= 18 else course_name[:16] + ".."
    label = f"<b>{display_name}</b><br>{teacher_last}<br>{room_name}"

    fig.add_annotation(
        x=a.day, y=mid_y,
        text=label,
        showarrow=False,
        font=dict(size=10, color="white"),
        align="center",
    )

st.plotly_chart(fig, use_container_width=True)

# -- Export to CSV ---------------------------------------------------------
buf = io.StringIO()
writer = csv.writer(buf)
writer.writerow(["Course", "Teacher", "Room", "Day", "Period", "Duration", "Department", "Group"])
for a in filtered_assignments:
    course = courses_map.get(a.course_id)
    teacher = teachers_map.get(a.teacher_id)
    room = rooms_map.get(a.room_id)
    group = groups_map.get(course.student_group_id) if course else None
    duration = course.session_duration_slots if course else 1
    writer.writerow([
        course.name if course else a.course_id,
        teacher.name if teacher else a.teacher_id,
        room.name if room else a.room_id,
        DAY_SHORT[a.day] if a.day < len(DAY_SHORT) else a.day,
        PERIOD_LABELS[a.period] if a.period < len(PERIOD_LABELS) else a.period,
        f"{duration}h",
        course.department if course else "",
        group.name if group else "",
    ])

st.download_button(
    label="Export to CSV",
    data=buf.getvalue(),
    file_name="schedule.csv",
    mime="text/csv",
)
