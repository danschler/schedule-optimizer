import streamlit as st

st.set_page_config(page_title="Schedule Optimizer", layout="wide")

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

# Navigation using st.navigation / st.Page
pages = {
    "Data Management": st.Page("src/ui/data_view.py", title="Data Management", icon="\U0001f4cb"),
    "Optimize": st.Page("src/ui/optimize_view.py", title="Optimize", icon="\u26a1"),
    "Schedule": st.Page("src/ui/schedule_view.py", title="Schedule", icon="\U0001f4c5"),
    "Dashboard": st.Page("src/ui/dashboard_view.py", title="Dashboard", icon="\U0001f4ca"),
}
pg = st.navigation(list(pages.values()))
pg.run()
