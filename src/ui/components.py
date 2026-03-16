"""Shared UI helper functions and constants for the Streamlit interface."""

from src.models.time_slot import DAY_NAMES, DAY_SHORT, PERIOD_LABELS, PERIODS_PER_DAY

# Department color map
DEPARTMENT_COLORS = {
    "CS": "#4CAF50",
    "Math": "#2196F3",
    "Physics": "#FF9800",
    "Languages": "#9C27B0",
}

# Fallback color for unknown departments
DEFAULT_COLOR = "#607D8B"


def get_department_color(department: str) -> str:
    """Return the color associated with a department."""
    return DEPARTMENT_COLORS.get(department, DEFAULT_COLOR)


def format_availability(availability: dict[int, list[int]]) -> str:
    """Format a teacher's availability dict into a human-readable string."""
    if not availability:
        return "No availability set"

    available_days = sorted(availability.keys())
    # Check if available all 5 days
    if available_days == list(range(5)):
        return "Available Mon-Fri"

    day_names = [DAY_SHORT[d] for d in available_days if d < len(DAY_SHORT)]
    return f"Available {', '.join(day_names)}"


def format_assignment_info(
    course_name: str,
    teacher_name: str,
    room_name: str,
    day: int,
    period: int,
) -> str:
    """Format assignment details for display."""
    day_str = DAY_SHORT[day] if day < len(DAY_SHORT) else f"Day {day}"
    period_str = PERIOD_LABELS[period] if period < len(PERIOD_LABELS) else f"Period {period}"
    return f"{course_name} | {teacher_name} | {room_name} | {day_str} {period_str}"


def build_lookup_maps(schedule_data):
    """Build id->entity lookup dicts from schedule_data for quick access."""
    teachers = {t.id: t for t in schedule_data.teachers}
    courses = {c.id: c for c in schedule_data.courses}
    rooms = {r.id: r for r in schedule_data.rooms}
    buildings = {b.id: b for b in schedule_data.buildings}
    groups = {g.id: g for g in schedule_data.student_groups}
    return teachers, courses, rooms, buildings, groups
