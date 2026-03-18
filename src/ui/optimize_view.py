"""Optimize page - Solver controls and constraint configuration."""

import streamlit as st

from src.optimizer.constraints import ConstraintConfig

st.title("Optimize Schedule")
st.caption("Configure constraint priorities, then run the solver to generate an optimized timetable.")

data = st.session_state.schedule_data

# -- Pre-optimization validation -------------------------------------------
missing = []
if not data.teachers:
    missing.append("teachers")
if not data.courses:
    missing.append("courses")
if not data.rooms:
    missing.append("rooms")
if not data.student_groups:
    missing.append("student groups")
if not data.buildings:
    missing.append("buildings")

if missing:
    st.error(
        f"Missing data: **{', '.join(missing)}**. "
        "Go to the **Data** page to add them first."
    )
    st.stop()

# -- Presets ---------------------------------------------------------------
PRESETS = {
    "Balanced (default)": ConstraintConfig().as_dict(),
    "Student-focused": {
        "student_gaps": 8.0, "teacher_gaps": 1.0, "building_travel": 4.0,
        "even_distribution": 5.0, "lunch_breaks": 7.0, "morning_core": 3.0,
        "no_same_subject_twice": 6.0, "teacher_day_off": 1.0,
        "back_to_back_limit": 1.0, "even_workload": 0.0,
    },
    "Teacher-focused": {
        "student_gaps": 1.0, "teacher_gaps": 7.0, "building_travel": 5.0,
        "even_distribution": 2.0, "lunch_breaks": 5.0, "morning_core": 1.0,
        "no_same_subject_twice": 2.0, "teacher_day_off": 8.0,
        "back_to_back_limit": 7.0, "even_workload": 6.0,
    },
    "Minimal (hard constraints only)": {
        "student_gaps": 0.0, "teacher_gaps": 0.0, "building_travel": 0.0,
        "even_distribution": 0.0, "lunch_breaks": 0.0, "morning_core": 0.0,
        "no_same_subject_twice": 0.0, "teacher_day_off": 0.0,
        "back_to_back_limit": 0.0, "even_workload": 0.0,
    },
}

preset_col, spacer = st.columns([2, 3])
with preset_col:
    selected_preset = st.selectbox(
        "Load preset",
        options=list(PRESETS.keys()),
        key="preset_selector",
        help="Presets adjust all soft constraint weights at once. You can fine-tune after loading.",
    )
    if st.button("Apply Preset", key="apply_preset"):
        st.session_state.constraint_weights = dict(PRESETS[selected_preset])
        st.rerun()

# -- Constraint weight configuration ---------------------------------------
weights = st.session_state.constraint_weights

# Group constraints by category for clarity
CONSTRAINT_GROUPS = {
    "Student Experience": {
        "student_gaps": "Minimize gaps between classes",
        "no_same_subject_twice": "Avoid same subject twice per day",
        "lunch_breaks": "Keep lunch period free",
        "morning_core": "Core courses in morning slots",
    },
    "Teacher Preferences": {
        "teacher_gaps": "Minimize gaps between classes",
        "teacher_day_off": "Respect preferred days off",
        "back_to_back_limit": "Limit consecutive teaching",
        "even_workload": "Balance hours across the week",
    },
    "Logistics": {
        "building_travel": "Penalize building changes",
        "even_distribution": "Spread classes evenly",
    },
}

with st.expander("Constraint Weights", expanded=True):
    st.caption("Adjust weights for each soft constraint (0 = disabled, higher = more important).")

    for group_name, constraints in CONSTRAINT_GROUPS.items():
        st.markdown(f"**{group_name}**")
        cols = st.columns(2)
        for i, (key, description) in enumerate(constraints.items()):
            with cols[i % 2]:
                current = weights.get(key, 0.0)
                weights[key] = st.slider(
                    description,
                    0.0, 10.0,
                    current,
                    step=0.5,
                    key=f"weight_{key}",
                    help=f"Weight for '{key}' constraint. Set to 0 to disable.",
                )

    st.session_state.constraint_weights = weights

st.divider()

# -- Solver controls -------------------------------------------------------
col1, col2 = st.columns([3, 1])

with col2:
    time_limit = st.slider("Time limit (sec)", 5, 120, 30, help="Maximum time the solver will spend searching.")

with col1:
    run_btn = st.button("Generate Schedule", type="primary", use_container_width=True)

if run_btn:
    try:
        from src.optimizer.engine import ScheduleOptimizer
    except ImportError:
        st.error(
            "Could not import ScheduleOptimizer from src.optimizer.engine. "
            "Make sure the optimizer engine module is implemented."
        )
        st.stop()

    config = ConstraintConfig.from_dict(st.session_state.constraint_weights)

    # Validate referential integrity before solving
    ref_errors = data.validate_references()
    if ref_errors:
        st.error("**Data validation errors** (fix on the Data page):")
        for err in ref_errors:
            st.caption(f"  - {err}")
        st.stop()

    with st.spinner(f"Solving with {time_limit}s time limit..."):
        optimizer = ScheduleOptimizer(data, config)
        schedule = optimizer.solve(time_limit=time_limit)

    st.session_state.current_schedule = schedule

    # Display results
    st.divider()
    col_status, col_assign, col_obj = st.columns(3)
    with col_status:
        st.metric("Status", schedule.status.capitalize())
    with col_assign:
        st.metric("Assignments", len(schedule.assignments))
    with col_obj:
        st.metric("Objective Value", f"{schedule.objective_value:.2f}",
                   help="Weighted sum of soft constraint penalties. Lower = better. 0 = perfect.")

    if schedule.status in ("optimal", "feasible"):
        st.success(f"Schedule generated with {len(schedule.assignments)} assignments.")

        # Run scoring
        try:
            from src.optimizer.scoring import evaluate_schedule
            score = evaluate_schedule(data, schedule, st.session_state.constraint_weights)
            st.session_state.current_score = score
            st.info("Check the **Schedule** page to view the timetable, or **Dashboard** for analytics.")
        except ImportError:
            st.warning("Scoring module not available. Dashboard metrics will be limited.")
        except Exception as e:
            st.warning(f"Scoring failed: {e}")
    else:
        st.error(
            "Solver could not find a feasible schedule. "
            "Try reducing constraint weights, increasing the time limit, or adjusting your data."
        )

# -- Current state ---------------------------------------------------------
if not run_btn:
    if st.session_state.current_schedule is not None:
        st.success(
            "A schedule is loaded. View it on the **Schedule** page or re-generate above."
        )
    else:
        st.info("Configure weights above and click **Generate Schedule** to begin.")
