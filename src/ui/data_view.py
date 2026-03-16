"""Data Management page - CRUD for all schedule entities."""

import json
import streamlit as st
import pandas as pd

from src.models.schedule import ScheduleData
from src.models.teacher import Teacher
from src.models.course import Course, RoomType
from src.models.room import Room
from src.models.building import Building
from src.models.student_group import StudentGroup
from src.ui.components import format_availability

data: ScheduleData = st.session_state.schedule_data

st.title("Data Management")

# ── Load / Save controls ─────────────────────────────────────────────────
col_load, col_save, col_gen = st.columns(3)

with col_load:
    uploaded = st.file_uploader("Load JSON", type=["json"], key="data_uploader")
    if uploaded is not None:
        try:
            raw = json.loads(uploaded.getvalue())
            st.session_state.schedule_data = ScheduleData.model_validate(raw)
            st.session_state.current_schedule = None
            st.session_state.current_score = None
            st.success("Data loaded successfully!")
            st.rerun()
        except Exception as e:
            st.error(f"Failed to load data: {e}")

with col_save:
    json_str = st.session_state.schedule_data.model_dump_json(indent=2)
    st.download_button(
        label="Download JSON",
        data=json_str,
        file_name="schedule_data.json",
        mime="application/json",
    )

with col_gen:
    if st.button("Generate Sample Data"):
        from src.data.generator import generate_sample_data
        st.session_state.schedule_data = generate_sample_data()
        st.session_state.current_schedule = None
        st.session_state.current_score = None
        st.success("Sample data generated!")
        st.rerun()

st.divider()

# Refresh reference after potential reload
data = st.session_state.schedule_data

# ── Tabs ──────────────────────────────────────────────────────────────────
tab_teachers, tab_courses, tab_rooms, tab_groups, tab_buildings = st.tabs(
    ["Teachers", "Courses", "Rooms", "Student Groups", "Buildings"]
)

# ═══════════════════════════════════════════════════════════════════════════
# TEACHERS
# ═══════════════════════════════════════════════════════════════════════════
with tab_teachers:
    if data.teachers:
        rows = []
        for t in data.teachers:
            rows.append({
                "ID": t.id,
                "Name": t.name,
                "Department": t.department,
                "Subjects": ", ".join(t.subjects_can_teach),
                "Availability": format_availability(t.availability),
                "Max Hrs/Day": t.max_hours_day,
                "Max Hrs/Week": t.max_hours_week,
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    else:
        st.info("No teachers loaded.")

    with st.expander("Add Teacher"):
        with st.form("add_teacher", clear_on_submit=True):
            t_id = st.text_input("ID", placeholder="t16")
            t_name = st.text_input("Name", placeholder="Dr. Jane Doe")
            t_dept = st.selectbox("Department", ["CS", "Math", "Physics", "Languages"])
            t_subjects = st.text_input("Subjects (comma-separated)", placeholder="programming, algorithms")
            t_max_day = st.number_input("Max hours/day", 1, 9, 6)
            t_max_week = st.number_input("Max hours/week", 1, 45, 20)
            t_avail_days = st.multiselect("Available days", options=list(range(5)),
                                          format_func=lambda d: ["Mon","Tue","Wed","Thu","Fri"][d],
                                          default=list(range(5)))
            if st.form_submit_button("Add Teacher"):
                subjects = [s.strip() for s in t_subjects.split(",") if s.strip()]
                avail = {d: list(range(9)) for d in t_avail_days}
                teacher = Teacher(
                    id=t_id, name=t_name, department=t_dept,
                    subjects_can_teach=subjects, availability=avail,
                    max_hours_day=t_max_day, max_hours_week=t_max_week,
                )
                data.teachers.append(teacher)
                st.success(f"Added teacher {t_name}")
                st.rerun()

    # Delete teacher
    if data.teachers:
        with st.expander("Delete Teacher"):
            del_t = st.selectbox("Select teacher to delete",
                                 options=[t.id for t in data.teachers],
                                 format_func=lambda tid: next((t.name for t in data.teachers if t.id == tid), tid),
                                 key="del_teacher")
            if st.button("Delete", key="del_teacher_btn"):
                data.teachers = [t for t in data.teachers if t.id != del_t]
                st.success("Teacher deleted.")
                st.rerun()

# ═══════════════════════════════════════════════════════════════════════════
# COURSES
# ═══════════════════════════════════════════════════════════════════════════
with tab_courses:
    if data.courses:
        rows = []
        for c in data.courses:
            rows.append({
                "ID": c.id,
                "Name": c.name,
                "Subject": c.subject,
                "Department": c.department,
                "Sessions/Week": c.sessions_per_week,
                "Duration (slots)": c.session_duration_slots,
                "Room Type": c.required_room_type.value,
                "Student Group": c.student_group_id,
                "Fixed": "Yes" if c.is_fixed else "No",
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    else:
        st.info("No courses loaded.")

    with st.expander("Add Course"):
        with st.form("add_course", clear_on_submit=True):
            c_id = st.text_input("ID", placeholder="c31")
            c_name = st.text_input("Name", placeholder="New Course")
            c_subject = st.text_input("Subject", placeholder="programming")
            c_dept = st.selectbox("Department", ["CS", "Math", "Physics", "Languages"], key="course_dept")
            c_sessions = st.number_input("Sessions per week", 1, 10, 1)
            c_duration = st.number_input("Session duration (slots)", 1, 4, 1)
            c_room_type = st.selectbox("Room type", [rt.value for rt in RoomType])
            group_opts = [g.id for g in data.student_groups] if data.student_groups else [""]
            c_group = st.selectbox("Student group", group_opts,
                                   format_func=lambda gid: next((g.name for g in data.student_groups if g.id == gid), gid))
            teacher_opts = [t.id for t in data.teachers]
            c_teachers = st.multiselect("Eligible teachers", teacher_opts,
                                        format_func=lambda tid: next((t.name for t in data.teachers if t.id == tid), tid))
            if st.form_submit_button("Add Course"):
                course = Course(
                    id=c_id, name=c_name, subject=c_subject, department=c_dept,
                    sessions_per_week=c_sessions, session_duration_slots=c_duration,
                    required_room_type=RoomType(c_room_type), student_group_id=c_group,
                    eligible_teacher_ids=c_teachers,
                )
                data.courses.append(course)
                st.success(f"Added course {c_name}")
                st.rerun()

    if data.courses:
        with st.expander("Delete Course"):
            del_c = st.selectbox("Select course to delete",
                                 options=[c.id for c in data.courses],
                                 format_func=lambda cid: next((c.name for c in data.courses if c.id == cid), cid),
                                 key="del_course")
            if st.button("Delete", key="del_course_btn"):
                data.courses = [c for c in data.courses if c.id != del_c]
                st.success("Course deleted.")
                st.rerun()

# ═══════════════════════════════════════════════════════════════════════════
# ROOMS
# ═══════════════════════════════════════════════════════════════════════════
with tab_rooms:
    if data.rooms:
        rows = []
        for r in data.rooms:
            bname = next((b.name for b in data.buildings if b.id == r.building_id), r.building_id)
            rows.append({
                "ID": r.id,
                "Name": r.name,
                "Building": bname,
                "Capacity": r.capacity,
                "Type": r.room_type.value,
                "Equipment": ", ".join(r.equipment) if r.equipment else "-",
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    else:
        st.info("No rooms loaded.")

    with st.expander("Add Room"):
        with st.form("add_room", clear_on_submit=True):
            r_id = st.text_input("ID", placeholder="r13")
            r_name = st.text_input("Name", placeholder="LH-401")
            building_opts = [b.id for b in data.buildings] if data.buildings else [""]
            r_building = st.selectbox("Building", building_opts,
                                      format_func=lambda bid: next((b.name for b in data.buildings if b.id == bid), bid))
            r_capacity = st.number_input("Capacity", 1, 500, 30)
            r_type = st.selectbox("Room type", [rt.value for rt in RoomType], key="room_type_add")
            r_equipment = st.text_input("Equipment (comma-separated)", placeholder="projector, whiteboard")
            if st.form_submit_button("Add Room"):
                equip = [e.strip() for e in r_equipment.split(",") if e.strip()]
                room = Room(
                    id=r_id, name=r_name, building_id=r_building,
                    capacity=r_capacity, room_type=RoomType(r_type), equipment=equip,
                )
                data.rooms.append(room)
                st.success(f"Added room {r_name}")
                st.rerun()

    if data.rooms:
        with st.expander("Delete Room"):
            del_r = st.selectbox("Select room to delete",
                                 options=[r.id for r in data.rooms],
                                 format_func=lambda rid: next((r.name for r in data.rooms if r.id == rid), rid),
                                 key="del_room")
            if st.button("Delete", key="del_room_btn"):
                data.rooms = [r for r in data.rooms if r.id != del_r]
                st.success("Room deleted.")
                st.rerun()

# ═══════════════════════════════════════════════════════════════════════════
# STUDENT GROUPS
# ═══════════════════════════════════════════════════════════════════════════
with tab_groups:
    if data.student_groups:
        rows = []
        for g in data.student_groups:
            rows.append({
                "ID": g.id,
                "Name": g.name,
                "Size": g.size,
                "Required Courses": len(g.required_course_ids),
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    else:
        st.info("No student groups loaded.")

    with st.expander("Add Student Group"):
        with st.form("add_group", clear_on_submit=True):
            g_id = st.text_input("ID", placeholder="sg9")
            g_name = st.text_input("Name", placeholder="CS-Y3")
            g_size = st.number_input("Size", 1, 500, 30)
            if st.form_submit_button("Add Student Group"):
                group = StudentGroup(id=g_id, name=g_name, size=g_size)
                data.student_groups.append(group)
                st.success(f"Added group {g_name}")
                st.rerun()

    if data.student_groups:
        with st.expander("Delete Student Group"):
            del_g = st.selectbox("Select group to delete",
                                 options=[g.id for g in data.student_groups],
                                 format_func=lambda gid: next((g.name for g in data.student_groups if g.id == gid), gid),
                                 key="del_group")
            if st.button("Delete", key="del_group_btn"):
                data.student_groups = [g for g in data.student_groups if g.id != del_g]
                st.success("Student group deleted.")
                st.rerun()

# ═══════════════════════════════════════════════════════════════════════════
# BUILDINGS
# ═══════════════════════════════════════════════════════════════════════════
with tab_buildings:
    if data.buildings:
        rows = []
        for b in data.buildings:
            travel = ", ".join(f"{k}: {v}min" for k, v in b.travel_time_to.items())
            rows.append({
                "ID": b.id,
                "Name": b.name,
                "Travel Times": travel,
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    else:
        st.info("No buildings loaded.")

    with st.expander("Add Building"):
        with st.form("add_building", clear_on_submit=True):
            b_id = st.text_input("ID", placeholder="b4")
            b_name = st.text_input("Name", placeholder="Engineering")
            if st.form_submit_button("Add Building"):
                building = Building(id=b_id, name=b_name)
                data.buildings.append(building)
                st.success(f"Added building {b_name}")
                st.rerun()

    if data.buildings:
        with st.expander("Delete Building"):
            del_b = st.selectbox("Select building to delete",
                                 options=[b.id for b in data.buildings],
                                 format_func=lambda bid: next((b.name for b in data.buildings if b.id == bid), bid),
                                 key="del_building")
            if st.button("Delete", key="del_building_btn"):
                data.buildings = [b for b in data.buildings if b.id != del_b]
                st.success("Building deleted.")
                st.rerun()

st.divider()
st.caption(
    f"Summary: {len(data.teachers)} teachers, {len(data.courses)} courses, "
    f"{len(data.rooms)} rooms, {len(data.student_groups)} groups, "
    f"{len(data.buildings)} buildings"
)
