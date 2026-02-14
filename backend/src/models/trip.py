from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from src.models.user import PyObjectId

class TripConstraints(BaseModel):
    destination: str
    start_date: date
    end_date: date
    duration_days: int
    budget: float
    travel_group: str # "solo | couple | family | friends"
    traveler_count: int
    special_constraints: List[str] = []

class Trip(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: PyObjectId
    title: str
    status: str # "planning | finalized | cancelled"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    trip_constraints: TripConstraints
    current_version: int = 1
    final_itinerary_version: Optional[int] = None

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat()
        }
