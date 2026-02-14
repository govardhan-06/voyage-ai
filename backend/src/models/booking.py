from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from src.models.user import PyObjectId

class FlightLink(BaseModel):
    from_loc: str = Field(alias="from")
    to_loc: str = Field(alias="to")
    departure_date: datetime
    return_date: Optional[datetime] = None
    price: Optional[float] = None
    booking_links: Dict[str, str] # e.g. {"skyscanner": "url", "makemytrip": "url"}

class HotelLink(BaseModel):
    city: str
    checkin: datetime
    checkout: datetime
    price_per_night: Optional[float] = None
    booking_links: Dict[str, str] # e.g. {"agoda": "url", "booking": "url"}

class ActivityLink(BaseModel):
    name: str
    booking_link: str

class BookingLinks(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    trip_id: PyObjectId
    itinerary_version: int
    flights: List[FlightLink] = []
    hotels: List[HotelLink] = []
    activities: List[ActivityLink] = []

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
