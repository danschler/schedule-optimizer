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
from src.models.time_slot import DAY_NAMES, DAY_SHORT, PERIOD_LABELS
from src.ui.components import format_availability

data: ScheduleData = st.session_state.schedule_data

st.title("Data Management")
st.caption("Add, edit, and manage all scheduling entities. Load sample data to get started quickly.")

# -- Flash messages --------------------------------------------------------
if "flash_message" in st.session_state and st.session_state.flash_message:
    msg_type, msg_text = st.session_state.flash_message
    if msg_type == "success":
        st.success(msg_text)
    elif msg_type == "error":
        st.error(msg_text)
    elif msg_type == "info":
        st.info(msg_text)
    st.session_state.flash_message = None


def flash(msg_type: str, msg_text: str):
    """Store a flash message and trigger rerun."""
    st.session_state.flash_message = (msg_type, msg_text)
    st.rerun()


# -- Summary metrics at top ------------------------------------------------
col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
col_m1.metric("Teachers", len(data.teachers))
col_m2.metric("Courses", len(data.courses))
col_m3.metric("Rooms", len(data.rooms))
col_m4.metric("Groups", len(data.student_groups))
col_m5.metric("Buildings", len(data.buildings))

# -- Empty state guidance --------------------------------------------------
if not data.courses and not data.teachers and not data.rooms:
    st.info(
        "**Getting started:** Generate sample data below, or upload your own JSON file. "
        "Then head to the **Optimize** page to create a schedule."
    )
    if st.button("Generate Sample Data", type="primary", key="empty_state_gen"):
        from src.data.generator import generate_sample_data
        st.session_state.schedule_data = generate_sample_data()
        st.session_state.current_schedule = None
        st.session_state.current_score = None
        flash("success", "Sample data generated!")

# -- Load / Save controls -------------------------------------------------
with st.expander("Import / Export / Generate", expanded=False):
    col_load, col_save, col_gen = st.columns(3)

    with col_load:
        uploaded = st.file_uploader("Load JSON", type=["json"], key="data_uploader")
        if uploaded is not None:
            try:
                raw = json.loads(uploaded.getvalue())
                st.session_state.schedule_data = ScheduleData.model_validate(raw)
                st.session_state.current_schedule = None
                st.session_state.current_score = None
                flash("success", "Data loaded successfully!")
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
        if st.button("Generate Sample Data", key="topbar_gen"):
            from src.data.generator import generate_sample_data
            st.session_state.schedule_data = generate_sample_data()
            st.session_state.current_schedule = None
            st.session_state.current_score = None
            flash("success", "Sample data generated!")

# Refresh reference after potential reload
data = st.session_state.schedule_data


# Helper: collect existing departments from teachers and courses
def _existing_departments() -> list[str]:
    depts: set[str] = set()
    for t in data.teachers:
        if t.department:
            depts.add(t.department)
    for c in data.courses:
        if c.department:
            depts.add(c.department)
    return sorted(depts)


# -- Tabs with counts -----------------------------------------------------
tab_teachers, tab_courses, tab_rooms, tab_groups, tab_buildings = st.tabs([
    f"Teachers ({len(data.teachers)})",
    f"Courses ({len(data.courses)})",
    f"Rooms ({len(data.rooms)})",
    f"Student Groups ({len(data.student_groups)})",
    f"Buildings ({len(data.buildings)})",
])

# =========================================================================
# TEACHERS
# =========================================================================
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
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No teachers loaded. Add one below or generate sample data.")

    col_add, col_del = st.columns(2)

    with col_add:
        with st.expander("Add Teacher"):
            with st.form("add_teacher", clear_on_submit=True):
                default_t_id = f"t{len(data.teachers)+1}"
                t_id = st.text_input("ID", value=default_t_id, placeholder="t16")
                t_name = st.text_input("Name", placeholder="Dr. Jane Doe")
                existing_depts = _existing_departments()
                dept_help = f"Existing: {', '.join(existing_depts)}" if existing_depts else ""
                t_dept = st.text_input("Department", placeholder="CS", help=dept_help)
                t_subjects = st.text_input("Subjects (comma-separated)", placeholder="programming, algorithms")
                c1, c2 = st.columns(2)
                with c1:
                    t_max_day = st.number_input("Max hours/day", 1, 9, 6)
                with c2:
                    t_max_week = st.number_input("Max hours/week", 1, 45, 20)
                t_avail_days = st.multiselect("Available days", options=list(range(5)),
                                              format_func=lambda d: ["Mon","Tue","Wed","Thu","Fri"][d],
                                              default=list(range(5)))
                t_pref_days_off = st.multiselect(
                    "Preferred days off", options=list(range(5)),
                    format_func=lambda d: DAY_NAMES[d],
                    key="teacher_pref_days_off"
                )
                t_pref_time_slots = st.multiselect(
                    "Preferred time slots", options=list(range(len(PERIOD_LABELS))),
                    format_func=lambda p: PERIOD_LABELS[p],
                    key="teacher_pref_time_slots"
                )
                if st.form_submit_button("Add Teacher", type="primary"):
                    if any(t.id == t_id for t in data.teachers):
                        st.error(f"Teacher with ID '{t_id}' already exists.")
                    else:
                        subjects = [s.strip() for s in t_subjects.split(",") if s.strip()]
                        avail = {d: list(range(9)) for d in t_avail_days}
                        teacher = Teacher(
                            id=t_id, name=t_name, department=t_dept,
                            subjects_can_teach=subjects, availability=avail,
                            max_hours_day=t_max_day, max_hours_week=t_max_week,
                            preferred_days_off=t_pref_days_off,
                            preferred_time_slots=t_pref_time_slots,
                        )
                        data.teachers.append(teacher)
                        flash("success", f"Added teacher '{t_name}'")

    with col_del:
        if data.teachers:
            with st.expander("Delete Teacher"):
                del_t = st.selectbox("Select teacher",
                                     options=[t.id for t in data.teachers],
                                     format_func=lambda tid: next((t.name for t in data.teachers if t.id == tid), tid),
                                     key="del_teacher")
                del_name = next((t.name for t in data.teachers if t.id == del_t), del_t)
                if st.button(f"Delete '{del_name}'", key="del_teacher_btn", type="primary"):
                    data.teachers = [t for t in data.teachers if t.id != del_t]
                    flash("success", f"Deleted teacher '{del_name}'.")

# =========================================================================
# COURSES
# =========================================================================
with tab_courses:
    if data.courses:
        rows = []
        for c in data.courses:
            rows.append({
                "ID": c.id,
                "Name": c.name,
                "Subject": c.subject,
                "Dept": c.department,
                "Sessions/Wk": c.sessions_per_week,
                "Duration": f"{c.session_duration_slots}h",
                "Room Type": c.required_room_type.value,
                "Group": c.student_group_id,
                "Fixed": "Yes" if c.is_fixed else "",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No courses loaded. Add one below or generate sample data.")

    col_add, col_del = st.columns(2)

    with col_add:
        with st.expander("Add Course"):
            with st.form("add_course", clear_on_submit=True):
                default_c_id = f"c{len(data.courses)+1}"
                c_id = st.text_input("ID", value=default_c_id, placeholder="c31")
                c_name = st.text_input("Name", placeholder="New Course")
                c_subject = st.text_input("Subject", placeholder="programming")
                existing_depts = _existing_departments()
                dept_help_c = f"Existing: {', '.join(existing_depts)}" if existing_depts else ""
                c_dept = st.text_input("Department", placeholder="CS", help=dept_help_c, key="course_dept")
                c1, c2 = st.columns(2)
                with c1:
                    c_sessions = st.number_input("Sessions per week", 1, 10, 1)
                with c2:
                    c_duration = st.number_input("Session duration (slots)", 1, 4, 1)
                c_room_type = st.selectbox("Room type", [rt.value for rt in RoomType])
                group_opts = [g.id for g in data.student_groups] if data.student_groups else [""]
                c_group = st.selectbox("Student group", group_opts,
                                       format_func=lambda gid: next((g.name for g in data.student_groups if g.id == gid), gid))
                teacher_opts = [t.id for t in data.teachers]
                c_teachers = st.multiselect("Eligible teachers", teacher_opts,
                                            format_func=lambda tid: next((t.name for t in data.teachers if t.id == tid), tid))
                c_is_fixed = st.checkbox("Fixed schedule", key="course_is_fixed")
                c_fixed_day = None
                c_fixed_period = None
                if c_is_fixed:
                    fc1, fc2 = st.columns(2)
                    with fc1:
                        c_fixed_day = st.selectbox(
                            "Fixed day", options=list(range(5)),
                            format_func=lambda d: DAY_NAMES[d], key="course_fixed_day"
                        )
                    with fc2:
                        c_fixed_period = st.selectbox(
                            "Fixed period", options=list(range(len(PERIOD_LABELS))),
                            format_func=lambda p: PERIOD_LABELS[p], key="course_fixed_period"
                        )

                if st.form_submit_button("Add Course", type="primary"):
                    if any(c.id == c_id for c in data.courses):
                        st.error(f"Course with ID '{c_id}' already exists.")
                    else:
                        course = Course(
                            id=c_id, name=c_name, subject=c_subject, department=c_dept,
                            sessions_per_week=c_sessions, session_duration_slots=c_duration,
                            required_room_type=RoomType(c_room_type), student_group_id=c_group,
                            eligible_teacher_ids=c_teachers,
                            is_fixed=c_is_fixed,
                            fixed_day=c_fixed_day if c_is_fixed else None,
                            fixed_period=c_fixed_period if c_is_fixed else None,
                        )
                        data.courses.append(course)
                        flash("success", f"Added course '{c_name}'")

    with col_del:
        if data.courses:
            with st.expander("Delete Course"):
                del_c = st.selectbox("Select course",
                                     options=[c.id for c in data.courses],
                                     format_func=lambda cid: next((c.name for c in data.courses if c.id == cid), cid),
                                     key="del_course")
                del_name = next((c.name for c in data.courses if c.id == del_c), del_c)
                if st.button(f"Delete '{del_name}'", key="del_course_btn", type="primary"):
                    data.courses = [c for c in data.courses if c.id != del_c]
                    flash("success", f"Deleted course '{del_name}'.")

# =========================================================================
# ROOMS
# =========================================================================
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
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No rooms loaded. Add one below or generate sample data.")

    col_add, col_del = st.columns(2)

    with col_add:
        with st.expander("Add Room"):
            with st.form("add_room", clear_on_submit=True):
                default_r_id = f"r{len(data.rooms)+1}"
                r_id = st.text_input("ID", value=default_r_id, placeholder="r13")
                r_name = st.text_input("Name", placeholder="LH-401")
                building_opts = [b.id for b in data.buildings] if data.buildings else [""]
                r_building = st.selectbox("Building", building_opts,
                                          format_func=lambda bid: next((b.name for b in data.buildings if b.id == bid), bid))
                c1, c2 = st.columns(2)
                with c1:
                    r_capacity = st.number_input("Capacity", 1, 500, 30)
                with c2:
                    r_type = st.selectbox("Room type", [rt.value for rt in RoomType], key="room_type_add")
                r_equipment = st.text_input("Equipment (comma-separated)", placeholder="projector, whiteboard")
                if st.form_submit_button("Add Room", type="primary"):
                    if any(r.id == r_id for r in data.rooms):
                        st.error(f"Room with ID '{r_id}' already exists.")
                    else:
                        equip = [e.strip() for e in r_equipment.split(",") if e.strip()]
                        room = Room(
                            id=r_id, name=r_name, building_id=r_building,
                            capacity=r_capacity, room_type=RoomType(r_type), equipment=equip,
                        )
                        data.rooms.append(room)
                        flash("success", f"Added room '{r_name}'")

    with col_del:
        if data.rooms:
            with st.expander("Delete Room"):
                del_r = st.selectbox("Select room",
                                     options=[r.id for r in data.rooms],
                                     format_func=lambda rid: next((r.name for r in data.rooms if r.id == rid), rid),
                                     key="del_room")
                del_name = next((r.name for r in data.rooms if r.id == del_r), del_r)
                if st.button(f"Delete '{del_name}'", key="del_room_btn", type="primary"):
                    data.rooms = [r for r in data.rooms if r.id != del_r]
                    flash("success", f"Deleted room '{del_name}'.")

# =========================================================================
# STUDENT GROUPS
# =========================================================================
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
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No student groups loaded. Add one below or generate sample data.")

    col_add, col_del = st.columns(2)

    with col_add:
        with st.expander("Add Student Group"):
            with st.form("add_group", clear_on_submit=True):
                default_g_id = f"sg{len(data.student_groups)+1}"
                g_id = st.text_input("ID", value=default_g_id, placeholder="sg9")
                g_name = st.text_input("Name", placeholder="CS-Y3")
                g_size = st.number_input("Size", 1, 500, 30)
                if st.form_submit_button("Add Student Group", type="primary"):
                    if any(g.id == g_id for g in data.student_groups):
                        st.error(f"Student group with ID '{g_id}' already exists.")
                    else:
                        group = StudentGroup(id=g_id, name=g_name, size=g_size)
                        data.student_groups.append(group)
                        flash("success", f"Added group '{g_name}'")

    with col_del:
        if data.student_groups:
            with st.expander("Delete Student Group"):
                del_g = st.selectbox("Select group",
                                     options=[g.id for g in data.student_groups],
                                     format_func=lambda gid: next((g.name for g in data.student_groups if g.id == gid), gid),
                                     key="del_group")
                del_name = next((g.name for g in data.student_groups if g.id == del_g), del_g)
                if st.button(f"Delete '{del_name}'", key="del_group_btn", type="primary"):
                    data.student_groups = [g for g in data.student_groups if g.id != del_g]
                    flash("success", f"Deleted group '{del_name}'.")

# =========================================================================
# BUILDINGS
# =========================================================================
with tab_buildings:
    if data.buildings:
        rows = []
        for b in data.buildings:
            travel = ", ".join(f"{k}: {v}min" for k, v in b.travel_time_to.items())
            rows.append({
                "ID": b.id,
                "Name": b.name,
                "Travel Times": travel if travel else "-",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No buildings loaded. Add one below or generate sample data.")

    col_add, col_del = st.columns(2)

    with col_add:
        with st.expander("Add Building"):
            with st.form("add_building", clear_on_submit=True):
                default_b_id = f"b{len(data.buildings)+1}"
                b_id = st.text_input("ID", value=default_b_id, placeholder="b4")
                b_name = st.text_input("Name", placeholder="Engineering")
                if st.form_submit_button("Add Building", type="primary"):
                    if any(b.id == b_id for b in data.buildings):
                        st.error(f"Building with ID '{b_id}' already exists.")
                    else:
                        building = Building(id=b_id, name=b_name)
                        data.buildings.append(building)
                        flash("success", f"Added building '{b_name}'")

    with col_del:
        if data.buildings:
            with st.expander("Delete Building"):
                del_b = st.selectbox("Select building",
                                     options=[b.id for b in data.buildings],
                                     format_func=lambda bid: next((b.name for b in data.buildings if b.id == bid), bid),
                                     key="del_building")
                del_name = next((b.name for b in data.buildings if b.id == del_b), del_b)
                if st.button(f"Delete '{del_name}'", key="del_building_btn", type="primary"):
                    data.buildings = [b for b in data.buildings if b.id != del_b]
                    flash("success", f"Deleted building '{del_name}'.")

# -- Forward navigation cue -----------------------------------------------
if data.courses and data.teachers and data.rooms:
    st.success("Data ready! Head to the **Optimize** page to generate a schedule.")
