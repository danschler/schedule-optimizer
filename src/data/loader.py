"""JSON I/O for schedule data and schedule results."""

from pathlib import Path

from src.models import Schedule, ScheduleData


def load_data(filepath: str) -> ScheduleData:
    """Load schedule input data from a JSON file."""
    text = Path(filepath).read_text(encoding="utf-8")
    return ScheduleData.model_validate_json(text)


def save_data(data: ScheduleData, filepath: str) -> None:
    """Save schedule input data to a JSON file."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data.model_dump_json(indent=2), encoding="utf-8")


def load_schedule(filepath: str) -> Schedule:
    """Load a schedule result from a JSON file."""
    text = Path(filepath).read_text(encoding="utf-8")
    return Schedule.model_validate_json(text)


def save_schedule(schedule: Schedule, filepath: str) -> None:
    """Save a schedule result to a JSON file."""
    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(schedule.model_dump_json(indent=2), encoding="utf-8")
