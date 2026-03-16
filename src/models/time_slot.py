"""Time slot constants and helper functions."""

DAYS = 5  # Monday through Friday
PERIODS_PER_DAY = 9  # 8:00 - 16:00 (9 one-hour periods)
LUNCH_PERIOD = 4  # 12:00 - 13:00
TOTAL_SLOTS = DAYS * PERIODS_PER_DAY

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
DAY_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri"]

PERIOD_LABELS = [
    "8:00-9:00", "9:00-10:00", "10:00-11:00", "11:00-12:00",
    "12:00-13:00", "13:00-14:00", "14:00-15:00", "15:00-16:00", "16:00-17:00"
]


def slot_index(day: int, period: int) -> int:
    """Convert (day, period) to flat slot index."""
    return day * PERIODS_PER_DAY + period


def slot_to_day_period(slot: int) -> tuple[int, int]:
    """Convert flat slot index to (day, period)."""
    return divmod(slot, PERIODS_PER_DAY)


def format_slot(slot: int) -> str:
    """Format a slot index as a human-readable string."""
    day, period = slot_to_day_period(slot)
    return f"{DAY_SHORT[day]} {PERIOD_LABELS[period]}"
