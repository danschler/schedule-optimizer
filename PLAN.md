# Schedule Optimizer - Implementation Plan

## Overview

A school/university schedule optimizer using Google OR-Tools CP-SAT solver with a Streamlit UI.

## Tech Stack

- **Python 3.10+** with OR-Tools CP-SAT solver
- **Streamlit** for the web UI
- **Plotly** for interactive schedule visualization
- **Pydantic v2** for data validation
- **pytest** for testing

## Architecture

```
app.py                     # Streamlit entry point
src/
  models/                  # Pydantic data models (Teacher, Course, Room, etc.)
  optimizer/
    engine.py              # CP-SAT model construction & solving
    constraints.py         # Constraint config & pre-filtering helpers
    scoring.py             # Post-solve schedule evaluation
  data/
    loader.py              # JSON I/O
    generator.py           # Sample data generation
  ui/
    schedule_view.py       # Weekly grid (Plotly)
    data_view.py           # Entity CRUD forms
    optimize_view.py       # Solver controls
    dashboard_view.py      # Quality metrics
    components.py          # Shared UI helpers
```

## Optimization Approach

- **Decision variables**: Boolean `x[course, session, teacher, room, slot]`
- **Pre-filtering** reduces variables from ~243K to ~10K
- **Hard constraints**: Assignment completeness, no double-booking, capacity, max hours
- **Soft constraints**: Minimize gaps, even distribution, lunch breaks, travel, etc.
- **Objective**: Minimize weighted sum of soft constraint violations

## Implementation Status

- [x] Phase 1: Data models + sample data
- [x] Phase 2: Core optimizer (CP-SAT engine)
- [x] Phase 3: Scoring system
- [x] Phase 4: Streamlit UI
- [x] Phase 5: Testing

## Running

```bash
# Install dependencies
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Generate sample data
python3 -c "from src.data.generator import generate_sample_data; from src.data.loader import save_data; save_data(generate_sample_data(), 'data/sample_data.json')"

# Launch UI
streamlit run app.py

# Run tests
pytest tests/ -v
```
