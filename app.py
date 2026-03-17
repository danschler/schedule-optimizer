import streamlit as st

st.set_page_config(
    page_title="Schedule Optimizer",
    page_icon="\U0001f393",
    layout="wide",
)

# Initialize session state
if "schedule_data" not in st.session_state:
    from src.data.loader import load_data
    import os
    if os.path.exists("data/sample_data.json"):
        st.session_state.schedule_data = load_data("data/sample_data.json")
    else:
        from src.models.schedule import ScheduleData
        st.session_state.schedule_data = ScheduleData()

if "current_schedule" not in st.session_state:
    st.session_state.current_schedule = None
if "current_score" not in st.session_state:
    st.session_state.current_score = None
if "constraint_weights" not in st.session_state:
    from src.optimizer.constraints import ConstraintConfig
    st.session_state.constraint_weights = ConstraintConfig().as_dict()

# Dynamic page icons based on state
_has_schedule = (
    st.session_state.current_schedule is not None
    and st.session_state.current_schedule.assignments
)

optimize_icon = "\u2705" if _has_schedule else "\u26a1"
schedule_icon = "\u2705" if _has_schedule else "\U0001f4c5"

# Navigation using st.navigation / st.Page
pages = {
    "Data": st.Page("src/ui/data_view.py", title="Data", icon="\U0001f4cb"),
    "Optimize": st.Page("src/ui/optimize_view.py", title="Optimize", icon=optimize_icon),
    "Schedule": st.Page("src/ui/schedule_view.py", title="Schedule", icon=schedule_icon),
    "Dashboard": st.Page("src/ui/dashboard_view.py", title="Dashboard", icon="\U0001f4ca"),
}
pg = st.navigation(list(pages.values()))
pg.run()
