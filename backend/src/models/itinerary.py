from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date
from src.models.user import PyObjectId

class Location(BaseModel):
    name: str
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class Activity(BaseModel):
    time: str
    title: str
    description: Optional[str] = None
    location: Location
    cost_estimate: Optional[float] = 0
    tags: List[str] = []

class DayItinerary(BaseModel):
    day_number: int
    date: date
    activities: List[Activity]

class ItineraryDetail(BaseModel):
    total_cost_estimate: float
    currency: str
    days: List[DayItinerary]

class ItineraryVersion(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    trip_id: PyObjectId
    version_number: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str # "ai | user"
    change_summary: Optional[str] = None
    itinerary: ItineraryDetail

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat()
        }
