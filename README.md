# Schedule Optimizer

A university/school course schedule optimizer powered by **Google OR-Tools CP-SAT** with an interactive **Streamlit** web UI. It assigns courses to teachers, rooms, and time slots while satisfying hard constraints and optimizing soft preferences.

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)

## Features

- **Constraint-based optimization** using CP-SAT solver with pre-filtered variable space (~10K variables from ~243K naive)
- **8 hard constraints**: no double-booking (teacher/room/student group), room capacity & type matching, teacher hour limits, fixed time slots
- **10 configurable soft constraints**: minimize gaps, even workload distribution, lunch breaks, building travel, morning preferences, and more
- **Interactive Streamlit UI** with 4 pages:
  - **Data** -- CRUD for teachers, courses, rooms, buildings, student groups with summary metrics, JSON import/export
  - **Optimize** -- constraint weight presets (Balanced / Student-focused / Teacher-focused / Minimal), grouped constraint sliders, solver controls
  - **Schedule** -- interactive Plotly weekly grid with hover tooltips, department color legend, filters by teacher/group/room/course, CSV export
  - **Dashboard** -- constraint satisfaction chart, side-by-side room utilization & teacher workload, actionable violation tips
- **Independent scoring system** that evaluates any schedule against all constraints with detailed violation reports
- **Sample dataset** included: 15 teachers, 30 courses, 12 rooms, 3 buildings, 8 student groups

## Quick Start

### Prerequisites

- Python 3.10 or higher
- pip

### Installation

```bash
# Clone the repository
git clone https://github.com/danschler/schedule-optimizer.git
cd schedule-optimizer

# Create a virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Generate Sample Data

The repository includes a pre-generated sample dataset in `data/sample_data.json`. To regenerate it:

```bash
python3 -c "from src.data.generator import generate_sample_data; from src.data.loader import save_data; save_data(generate_sample_data(), 'data/sample_data.json')"
```

### Launch the App

```bash
streamlit run app.py
```

The app opens at `http://localhost:8501`. Follow the workflow:

1. **Data** -- Review or modify the loaded data (sample data loads automatically). Summary metrics at the top show entity counts at a glance.
2. **Optimize** -- Pick a constraint preset or fine-tune individual weights, then click "Generate Schedule".
3. **Schedule** -- Browse the weekly timetable. Hover over blocks for full details. Filter by student group, teacher, room, or course. Export to CSV.
4. **Dashboard** -- Review constraint satisfaction, room utilization, teacher workload, and lunch conflicts side by side.

## Project Structure

```
schedule_optimizer/
├── app.py                          # Streamlit entry point
├── requirements.txt                # Python dependencies
├── data/
│   └── sample_data.json            # Sample dataset (auto-loaded)
├── src/
│   ├── models/                     # Pydantic data models
│   │   ├── teacher.py              # Teacher (availability, subjects, hours)
│   │   ├── course.py               # Course + RoomType enum
│   │   ├── room.py                 # Room (capacity, type, building)
│   │   ├── building.py             # Building (travel times)
│   │   ├── student_group.py        # Student group (size, courses)
│   │   ├── time_slot.py            # Time constants & helpers
│   │   └── schedule.py             # Assignment, Schedule, ScheduleData
│   ├── optimizer/
│   │   ├── engine.py               # CP-SAT model (~770 lines, core solver)
│   │   ├── constraints.py          # Constraint config & pre-filtering
│   │   └── scoring.py              # Post-solve evaluation & metrics
│   ├── data/
│   │   ├── loader.py               # JSON load/save
│   │   └── generator.py            # Sample data generation
│   └── ui/
│       ├── components.py           # Shared UI helpers (colors, lookups)
│       ├── data_view.py            # Entity CRUD forms
│       ├── optimize_view.py        # Solver controls & weights
│       ├── schedule_view.py        # Plotly weekly grid
│       └── dashboard_view.py       # Quality metrics & charts
└── tests/                          # 61 pytest tests
    ├── test_models.py
    ├── test_constraints.py
    ├── test_optimizer.py
    └── test_scoring.py
```

## How It Works

### Optimization Approach

The optimizer constructs a **Constraint Programming** model where each decision variable represents a possible `(course, session, teacher, room, time_slot)` assignment. **Pre-filtering** eliminates impossible combinations before variable creation:

- Only teachers who can teach the course's subject
- Only rooms matching the required type with sufficient capacity
- Only time slots where the teacher is available

This reduces the search space from ~243,000 to ~10,000 variables.

### Hard Constraints (must be satisfied)

| ID | Constraint | Description |
|----|-----------|-------------|
| HC1 | Assignment completeness | Each course session assigned exactly once |
| HC2 | Teacher no-conflict | No teacher teaches two courses at the same time |
| HC3 | Room no-conflict | No room hosts two courses at the same time |
| HC4 | Room capacity | Room capacity >= student group size |
| HC5 | Room type | Room type matches course requirement |
| HC6 | Fixed slots | Pinned courses stay at their designated time |
| HC7 | Teacher hours | Daily and weekly teaching hour limits respected |
| HC8 | Group no-conflict | No student group has two courses at the same time |

### Soft Constraints (optimized via weighted penalties)

| ID | Constraint | Default Weight | Description |
|----|-----------|---------------|-------------|
| SC1 | Student gaps | 3 | Minimize free periods between classes |
| SC2 | Teacher gaps | 2 | Minimize free periods in teacher schedules |
| SC3 | Building travel | 4 | Penalize cross-building consecutive classes |
| SC4 | Even distribution | 2 | Spread classes evenly across the week |
| SC5 | Lunch breaks | 5 | Keep the lunch period (12:00-13:00) free |
| SC6 | Morning core | 1 | Prefer morning slots for core subjects |
| SC7 | Same subject | 3 | Avoid same subject twice in one day per group |
| SC8 | Teacher day-off | 2 | Respect preferred days off |
| SC9 | Back-to-back | 3 | Limit consecutive teaching to 3 slots |
| SC10 | Even workload | 1 | Balance daily teaching hours per teacher |

All weights are configurable in the UI (0-10 scale). Setting a weight to 0 disables the constraint.

## Data Format

The app uses JSON for data storage. You can import/export data through the UI or edit JSON files directly.

### Example: Adding a Teacher (JSON)

```json
{
  "id": "t16",
  "name": "Dr. Jane Smith",
  "department": "CS",
  "subjects_can_teach": ["programming", "algorithms"],
  "availability": {
    "0": [0, 1, 2, 3, 4, 5, 6, 7, 8],
    "1": [0, 1, 2, 3, 4, 5, 6, 7, 8],
    "2": [0, 1, 2, 3, 4, 5, 6, 7, 8]
  },
  "max_hours_day": 6,
  "max_hours_week": 18,
  "preferred_days_off": [4],
  "preferred_time_slots": [0, 1, 2, 3]
}
```

**Availability** maps day indices (0=Monday through 4=Friday) to lists of available period indices (0-8, corresponding to 8:00-17:00 in one-hour slots).

### Time Slots

- **Days**: 0=Monday, 1=Tuesday, 2=Wednesday, 3=Thursday, 4=Friday
- **Periods**: 0=8:00-9:00, 1=9:00-10:00, ..., 4=12:00-13:00 (lunch), ..., 8=16:00-17:00
- **Lunch period**: Index 4 (12:00-13:00)

## Running Tests

```bash
source .venv/bin/activate
pytest tests/ -v
```

The test suite (61 tests) covers:
- **Model validation** -- Pydantic field constraints, JSON round-trips, time slot helpers
- **Pre-filtering** -- Room eligibility, slot eligibility, teacher eligibility
- **Optimizer** -- Full solve feasibility, fixed course placement, infeasible detection
- **Scoring** -- Constraint violation detection, multi-slot handling, custom weights

## Using the Optimizer Programmatically

```python
from src.data.generator import generate_sample_data
from src.optimizer.engine import ScheduleOptimizer
from src.optimizer.constraints import ConstraintConfig
from src.optimizer.scoring import evaluate_schedule

# Load or generate data
data = generate_sample_data()

# Configure constraint weights (optional)
config = ConstraintConfig(lunch_breaks=10.0, student_gaps=5.0)

# Solve (time_limit in seconds)
optimizer = ScheduleOptimizer(data, config)
schedule = optimizer.solve(time_limit=30)

print(f"Status: {schedule.status}")  # "optimal", "feasible", or "infeasible"
print(f"Assignments: {len(schedule.assignments)}")

# Evaluate the schedule
score = evaluate_schedule(data, schedule)
print(f"Feasible: {score.feasible}")
print(f"Hard violations: {score.hard_score}")
print(f"Soft penalties: {score.soft_score}")

# Inspect individual constraint results
for cs in score.constraint_scores:
    if cs.violations > 0:
        print(f"  {cs.name}: {cs.violations} violations")
        for detail in cs.details:
            print(f"    - {detail}")
```

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| ortools | >= 9.9 | CP-SAT constraint solver |
| streamlit | >= 1.35 | Web UI framework |
| plotly | >= 5.18 | Interactive charts |
| pydantic | >= 2.5 | Data validation & serialization |
| pytest | >= 8.0 | Testing |

## License

MIT
