"""Room model."""

from pydantic import BaseModel, Field
from .course import RoomType


class Room(BaseModel):
    id: str
    name: str
    building_id: str
    capacity: int = Field(ge=1)
    room_type: RoomType = RoomType.LECTURE_HALL
    equipment: list[str] = Field(default_factory=list)
