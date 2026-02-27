from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date

# ── Node 1: Intent + Slot Filling ──

class SlotFillingResponse(BaseModel):
    """Structured output from the intent + slot filling node."""
    
    destination: Optional[str] = Field(None, description="Travel destination city or country")
    destination_iata: Optional[str] = Field(None, description="IATA airport/city code for destination (e.g. NRT, CDG, DPS)")
    origin: Optional[str] = Field(None, description="Departure city where the user is traveling from")
    origin_iata: Optional[str] = Field(None, description="IATA airport/city code for origin (e.g. BOM, DEL, BLR)")
    duration_days: Optional[int] = Field(None, description="Number of days for the trip")
    budget_min: Optional[float] = Field(None, description="Minimum budget in INR (Indian Rupees)")
    budget_max: Optional[float] = Field(None, description="Maximum budget in INR (Indian Rupees)")
    travel_group: Optional[str] = Field(None, description="solo, couple, family, or friends")
    traveler_count: Optional[int] = Field(None, description="Number of travelers")
    start_date: Optional[str] = Field(None, description="Trip start date (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="Trip end date (YYYY-MM-DD)")
    interests: List[str] = Field(default_factory=list, description="User interests like culture, adventure, food")
    constraints: List[str] = Field(default_factory=list, description="Special constraints like accessibility, dietary")
    
    follow_up_question: Optional[str] = Field(None, description="Question to ask user if slots are missing")
    is_complete: bool = Field(False, description="True if all required slots are filled")


# ── Node 2: Planning + Tools (Iterative Loop) ──

class ToolRequest(BaseModel):
    """A single tool the planner wants to invoke."""
    tool_name: str = Field(..., description="One of: search_flights, search_hotels, search_attractions, get_weather")
    parameters: dict = Field(default_factory=dict, description="Parameters for the tool")

class PlannerLLMResponse(BaseModel):
    """Response from the planner LLM on each iteration of the tool loop.
    
    The LLM returns this every round. It can request tools OR set stop=true
    to indicate it has gathered all necessary information.
    """
    
    # ── Loop control ──
    stop: bool = Field(False, description="Set to true when all needed info is gathered and planning is complete")
    reasoning: str = Field("", description="Brief reasoning for this round's decisions")
    
    # ── Tool requests (empty if stop=true) ──
    tool_requests: List[ToolRequest] = Field(default_factory=list, description="Tools to call this round. Empty if stop=true.")
    
    # ── Progressively built strategy (updated every round) ──
    summary: str = Field("", description="High-level travel strategy, refined each round")
    selected_cities: List[str] = Field(default_factory=list, description="Cities to visit in order")
    key_experiences: List[str] = Field(default_factory=list, description="Must-do experiences")
    budget_allocation: dict = Field(default_factory=dict, description="Budget split in INR: flights, hotels, activities, food, misc")
    cost_estimates: dict = Field(default_factory=dict, description="Estimated costs in INR from tool results: flights, hotels, activities, total")
    recommendations: List[str] = Field(default_factory=list, description="Top recommendations")
    warnings: List[str] = Field(default_factory=list, description="Important warnings or caveats")


# ── Node 2.5 / 2.6: Flight & Hotel Selection ──

class FlightSegment(BaseModel):
    """A single flight segment."""
    departure_airport: str = ""
    departure_time: str = ""
    arrival_airport: str = ""
    arrival_time: str = ""
    carrier: str = ""
    flight_number: str = ""
    duration: str = ""

class FlightOption(BaseModel):
    """A selectable flight option presented to the user."""
    index: int = Field(..., description="1-based index for user selection")
    flight_id: str = ""
    airline: str = ""
    flight_number: str = ""
    departure_time: str = ""
    arrival_time: str = ""
    duration: str = ""
    stops: int = 0
    price_inr: float = 0
    booking_class: str = "ECONOMY"
    seats_remaining: str = "N/A"

class HotelOption(BaseModel):
    """A selectable hotel option presented to the user."""
    index: int = Field(..., description="1-based index for user selection")
    hotel_id: str = ""
    name: str = ""
    city: str = ""
    price_per_night_inr: float = 0
    total_price_inr: float = 0
    room_type: str = ""
    bed_type: str = ""
    check_in: str = ""
    check_out: str = ""


# ── Node 3: Itinerary Generation ──

class ItineraryActivity(BaseModel):
    """A single activity in the itinerary."""
    time: str = Field(..., description="Time slot like '09:00 AM'")
    title: str = Field(..., description="Activity title")
    description: str = Field("", description="Brief description")
    location_name: str = Field(..., description="Location/venue name")
    location_address: Optional[str] = Field(None, description="Address")
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    cost_estimate: float = Field(0, description="Estimated cost in INR (Indian Rupees)")
    tags: List[str] = Field(default_factory=list, description="Tags like 'food', 'culture', 'adventure'")

class ItineraryDay(BaseModel):
    """A single day in the itinerary."""
    day_number: int
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    theme: str = Field("", description="Day theme like 'Cultural Exploration'")
    activities: List[ItineraryActivity]

class GeneratedItinerary(BaseModel):
    """Complete itinerary output from Node 3."""
    
    title: str = Field(..., description="Trip title")
    total_cost_estimate: float = Field(0, description="Total estimated cost in INR")
    currency: str = Field("INR", description="Currency code — always INR for Indian users")
    summary: str = Field("", description="Brief trip summary")
    days: List[ItineraryDay] = Field(default_factory=list)
    reasoning: List[str] = Field(default_factory=list, description="Key reasoning for major decisions")
    
    # Selected travel options (populated after human-in-the-loop selection)
    selected_flight: Optional[dict] = Field(None, description="User-selected flight details")
    selected_hotel: Optional[dict] = Field(None, description="User-selected hotel details")
    assumptions: List[str] = Field(default_factory=list, description="Assumptions made during planning (e.g., economy class)")
