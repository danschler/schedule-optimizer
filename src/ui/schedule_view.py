"""Schedule View page - Weekly grid visualization using Plotly."""

import csv
import io

import streamlit as st
import plotly.graph_objects as go

from src.models.time_slot import DAY_SHORT, PERIOD_LABELS, LUNCH_PERIOD, PERIODS_PER_DAY
from src.ui.components import get_department_color, build_lookup_maps

st.title("Schedule View")

schedule = st.session_state.current_schedule
data = st.session_state.schedule_data

if schedule is None or not schedule.assignments:
    st.info("No schedule available. Go to the Optimize page to generate one.")
    st.stop()

teachers_map, courses_map, rooms_map, buildings_map, groups_map = build_lookup_maps(data)

# ── Sidebar filters ──────────────────────────────────────────────────────
st.sidebar.header("Filters")

filter_mode = st.sidebar.radio("View by", ["All", "Teacher", "Student Group", "Room"])

filtered_assignments = list(schedule.assignments)

if filter_mode == "Teacher":
    teacher_options = {t.id: t.name for t in data.teachers}
    selected_teacher = st.sidebar.selectbox(
        "Select Teacher",
        options=list(teacher_options.keys()),
        format_func=lambda x: teacher_options[x],
    )
    filtered_assignments = [a for a in filtered_assignments if a.teacher_id == selected_teacher]

elif filter_mode == "Student Group":
    group_options = {g.id: g.name for g in data.student_groups}
    selected_group = st.sidebar.selectbox(
        "Select Student Group",
        options=list(group_options.keys()),
        format_func=lambda x: group_options[x],
    )
    # Filter by courses belonging to the selected group
    group_course_ids = {c.id for c in data.courses if c.student_group_id == selected_group}
    filtered_assignments = [a for a in filtered_assignments if a.course_id in group_course_ids]

elif filter_mode == "Room":
    room_options = {r.id: r.name for r in data.rooms}
    selected_room = st.sidebar.selectbox(
        "Select Room",
        options=list(room_options.keys()),
        format_func=lambda x: room_options[x],
    )
    filtered_assignments = [a for a in filtered_assignments if a.room_id == selected_room]

st.write(f"Showing **{len(filtered_assignments)}** assignments")

# ── Build Plotly weekly grid ─────────────────────────────────────────────

fig = go.Figure()

# Grid dimensions
num_days = len(DAY_SHORT)
num_periods = PERIODS_PER_DAY

# Set up the layout
fig.update_layout(
    height=650,
    margin=dict(l=80, r=20, t=40, b=40),
    xaxis=dict(
        range=[-0.5, num_days - 0.5],
        tickvals=list(range(num_days)),
        ticktext=DAY_SHORT,
        side="top",
        fixedrange=True,
    ),
    yaxis=dict(
        range=[num_periods - 0.5, -0.5],  # Inverted so morning is at top
        tickvals=list(range(num_periods)),
        ticktext=PERIOD_LABELS,
        fixedrange=True,
    ),
    plot_bgcolor="white",
    showlegend=False,
)

# Draw grid lines
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

# Highlight lunch period row
fig.add_shape(
    type="rect",
    x0=-0.5, x1=num_days - 0.5,
    y0=LUNCH_PERIOD - 0.5, y1=LUNCH_PERIOD + 0.5,
    fillcolor="rgba(200, 200, 200, 0.3)",
    line=dict(width=0),
    layer="below",
)

# Draw assignments as colored rectangles
for a in filtered_assignments:
    course = courses_map.get(a.course_id)
    teacher = teachers_map.get(a.teacher_id)
    room = rooms_map.get(a.room_id)

    if not course:
        continue

    dept = course.department
    color = get_department_color(dept)
    duration = course.session_duration_slots

    course_name = course.name if course else a.course_id
    teacher_name = teacher.name.split()[-1] if teacher else a.teacher_id  # Last name
    room_name = room.name if room else a.room_id

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

    # Text annotation
    mid_y = a.period + (duration - 1) / 2
    # Truncate course name if too long
    display_name = course_name if len(course_name) <= 18 else course_name[:16] + ".."
    label = f"<b>{display_name}</b><br>{teacher_name}<br>{room_name}"

    fig.add_annotation(
        x=a.day, y=mid_y,
        text=label,
        showarrow=False,
        font=dict(size=9, color="white"),
        align="center",
    )

st.plotly_chart(fig, width="stretch")

# ── Department color legend ──────────────────────────────────────────────
from src.ui.components import DEPARTMENT_COLORS

legend_cols = st.columns(len(DEPARTMENT_COLORS))
for i, (dept, color) in enumerate(DEPARTMENT_COLORS.items()):
    with legend_cols[i]:
        st.markdown(
            f'<span style="background-color:{color};color:white;padding:2px 10px;'
            f'border-radius:4px;font-size:0.85em;">{dept}</span>',
            unsafe_allow_html=True,
        )

# ── Export to CSV ────────────────────────────────────────────────────────
st.divider()

buf = io.StringIO()
writer = csv.writer(buf)
writer.writerow(["Course", "Teacher", "Room", "Day", "Period", "Department"])
for a in filtered_assignments:
    course = courses_map.get(a.course_id)
    teacher = teachers_map.get(a.teacher_id)
    room = rooms_map.get(a.room_id)
    writer.writerow([
        course.name if course else a.course_id,
        teacher.name if teacher else a.teacher_id,
        room.name if room else a.room_id,
        DAY_SHORT[a.day] if a.day < len(DAY_SHORT) else a.day,
        PERIOD_LABELS[a.period] if a.period < len(PERIOD_LABELS) else a.period,
        course.department if course else "",
    ])

st.download_button(
    label="Export to CSV",
    data=buf.getvalue(),
    file_name="schedule.csv",
    mime="text/csv",
)
