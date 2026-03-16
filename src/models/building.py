"""Building model with travel times."""

from pydantic import BaseModel, Field


class Building(BaseModel):
    id: str
    name: str
    travel_time_to: dict[str, int] = Field(
        default_factory=dict,
        description="Building ID -> travel time in minutes"
    )
