"""Optimize page - Solver controls and constraint configuration."""

import streamlit as st

from src.optimizer.constraints import ConstraintConfig

st.title("Optimize Schedule")

data = st.session_state.schedule_data

if not data.courses:
    st.warning("No courses loaded. Go to Data Management to load or generate data first.")
    st.stop()

# ── Constraint weight configuration ──────────────────────────────────────
with st.expander("Constraint Weights", expanded=False):
    st.caption("Set weights for each soft constraint. Weight of 0 disables the constraint.")
    weights = st.session_state.constraint_weights

    CONSTRAINT_DESCRIPTIONS = {
        "student_gaps": "Student Gaps - Minimize free periods between classes for students",
        "teacher_gaps": "Teacher Gaps - Minimize free periods between classes for teachers",
        "building_travel": "Building Travel - Penalize consecutive classes in distant buildings",
        "even_distribution": "Even Distribution - Spread classes evenly across the week",
        "lunch_breaks": "Lunch Breaks - Ensure lunch period is free",
        "morning_core": "Morning Core - Prefer scheduling core courses in the morning",
        "no_same_subject_twice": "No Same Subject Twice - Avoid same subject twice in a day for a group",
        "teacher_day_off": "Teacher Day Off - Respect teacher preferred days off",
        "back_to_back_limit": "Back-to-Back Limit - Limit consecutive teaching hours",
        "even_workload": "Even Workload - Balance teaching hours across the week",
    }

    cols = st.columns(2)
    for i, (key, desc) in enumerate(CONSTRAINT_DESCRIPTIONS.items()):
        with cols[i % 2]:
            current = weights.get(key, 0.0)
            enabled = st.checkbox(f"Enable", value=current > 0, key=f"enable_{key}")
            if enabled:
                weights[key] = st.slider(desc, 0.0, 10.0, current if current > 0 else 3.0,
                                         step=0.5, key=f"weight_{key}")
            else:
                weights[key] = 0.0
                st.caption(f"~~{desc}~~ (disabled)")

    st.session_state.constraint_weights = weights

st.divider()

# ── Solver controls ──────────────────────────────────────────────────────
col1, col2 = st.columns([2, 1])

with col2:
    time_limit = st.slider("Time limit (seconds)", 5, 120, 30)

with col1:
    run_btn = st.button("Generate Schedule", type="primary", width="stretch")

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

    with st.spinner("Solving... this may take a while."):
        optimizer = ScheduleOptimizer(data, config)
        schedule = optimizer.solve(time_limit=time_limit)

    st.session_state.current_schedule = schedule

    # Display results
    st.divider()
    col_status, col_assign, col_obj = st.columns(3)
    with col_status:
        status_color = "green" if schedule.status == "optimal" else (
            "orange" if schedule.status == "feasible" else "red"
        )
        st.metric("Status", schedule.status.capitalize())
    with col_assign:
        st.metric("Assignments", len(schedule.assignments))
    with col_obj:
        st.metric("Objective Value", f"{schedule.objective_value:.2f}")

    if schedule.status in ("optimal", "feasible"):
        st.success(f"Schedule generated with {len(schedule.assignments)} assignments.")

        # Run scoring if available
        try:
            from src.optimizer.scoring import evaluate_schedule
            score = evaluate_schedule(data, schedule, st.session_state.constraint_weights)
            st.session_state.current_score = score
            st.info("Scoring complete. Check the Dashboard for detailed metrics.")
        except ImportError:
            st.warning(
                "Scoring module not available (src.optimizer.scoring). "
                "Dashboard metrics will be limited."
            )
        except Exception as e:
            st.warning(f"Scoring failed: {e}")
    else:
        st.error("Solver could not find a feasible schedule. Try adjusting constraints or data.")

# ── Show current schedule status ─────────────────────────────────────────
st.divider()
st.subheader("Current Schedule Status")

if st.session_state.current_schedule is not None:
    sched = st.session_state.current_schedule
    st.write(f"**Status:** {sched.status} | **Assignments:** {len(sched.assignments)} | "
             f"**Objective:** {sched.objective_value:.2f}")
else:
    st.info("No schedule generated yet. Click 'Generate Schedule' above.")
