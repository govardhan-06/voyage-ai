from pydantic import BaseModel, EmailStr, Field, BeforeValidator
from typing import Optional, List, Annotated
from datetime import datetime

# Helper for ObjectId
PyObjectId = Annotated[str, BeforeValidator(str)]

class BudgetRange(BaseModel):
    min: Optional[float] = None
    max: Optional[float] = None

class UserPreferences(BaseModel):
    budget_range: Optional[BudgetRange] = None
    travel_style: Optional[List[str]] = []
    interests: Optional[List[str]] = []
    preferred_climate: Optional[List[str]] = []
    preferred_destinations: Optional[List[str]] = []
    accommodation_type: Optional[List[str]] = []
    food_preferences: Optional[List[str]] = []
    activity_preferences: Optional[List[str]] = []
    risk_tolerance: Optional[str] = None

class UserMetadata(BaseModel):
    last_login: Optional[datetime] = None
    total_trips: Optional[int] = 0

class UserBase(BaseModel):
    email: EmailStr
    name: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserInDB(UserBase):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    password_hash: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    preferences: Optional[UserPreferences] = Field(default_factory=UserPreferences)
    metadata: Optional[UserMetadata] = Field(default_factory=UserMetadata)

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class UserResponse(UserBase):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    created_at: datetime
    updated_at: datetime
    preferences: Optional[UserPreferences] = None
    metadata: Optional[UserMetadata] = None

    class Config:
        populate_by_name = True
