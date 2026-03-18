"""Shared fixtures for the test suite."""

import pytest

from src.data.generator import generate_sample_data
from src.optimizer.engine import ScheduleOptimizer


@pytest.fixture(scope="session")
def sample_data():
    """Generate sample data once for the entire test session."""
    return generate_sample_data()


@pytest.fixture(scope="session")
def solved_schedule(sample_data):
    """Solve sample data once for the entire test session."""
    optimizer = ScheduleOptimizer(sample_data)
    return optimizer.solve(time_limit=60)
