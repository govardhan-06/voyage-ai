from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from src.models.user import PyObjectId

class MessageEntities(BaseModel):
    budget: Optional[float] = None
    destination: Optional[str] = None
    dates: Optional[Dict[str, datetime]] = None

class Message(BaseModel):
    role: str # "user | ai"
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    intent: Optional[str] = None
    entities: Optional[MessageEntities] = None

class Conversation(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    trip_id: Optional[PyObjectId] = None
    user_id: PyObjectId
    created_at: datetime = Field(default_factory=datetime.utcnow)
    messages: List[Message] = []

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
