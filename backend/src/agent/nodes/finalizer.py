"""Node 4: Finalization – Save + Version.

No LLM. Saves the trip and itinerary version to MongoDB.
Handles versioning of itinerary.
"""

from datetime import datetime
from src.database import get_database


async def finalizer_node(state: dict) -> dict:
    """
    Save trip and itinerary to MongoDB. Version control.
    No LLM call — pure database operations.
    """
    db = get_database()
    user_id = state.get("user_id", "")
    trip_request = state.get("trip_request", {})
    itinerary = state.get("itinerary", {})
    trip_strategy = state.get("trip_strategy", {})
    
    now = datetime.utcnow()
    
    # ── Save Trip ──
    trip_doc = {
        "user_id": user_id,
        "title": itinerary.get("title", f"Trip to {trip_request.get('destination', 'Unknown')}"),
        "status": "planning",
        "created_at": now,
        "updated_at": now,
        "trip_constraints": {
            "destination": trip_request.get("destination", ""),
            "start_date": trip_request.get("start_date"),
            "end_date": trip_request.get("end_date"),
            "duration_days": trip_request.get("duration_days", 0),
            "budget": trip_request.get("budget_max", 0),
            "travel_group": trip_request.get("travel_group", "solo"),
            "traveler_count": trip_request.get("traveler_count", 1),
            "special_constraints": trip_request.get("constraints", [])
        },
        "current_version": 1,
        "final_itinerary_version": None
    }
    
    trip_result = await db.trips.insert_one(trip_doc)
    trip_id = str(trip_result.inserted_id)
    
    # ── Save Itinerary Version ──
    # Transform itinerary days to match the ItineraryVersion schema
    days_data = []
    for day in itinerary.get("days", []):
        activities_data = []
        for act in day.get("activities", []):
            activities_data.append({
                "time": act.get("time", ""),
                "title": act.get("title", ""),
                "description": act.get("description", ""),
                "location": {
                    "name": act.get("location_name", ""),
                    "address": act.get("location_address", ""),
                    "latitude": act.get("latitude"),
                    "longitude": act.get("longitude")
                },
                "cost_estimate": act.get("cost_estimate", 0),
                "tags": act.get("tags", [])
            })
        days_data.append({
            "day_number": day.get("day_number", 0),
            "date": day.get("date", ""),
            "activities": activities_data
        })
    
    version_doc = {
        "trip_id": trip_id,
        "version_number": 1,
        "created_at": now,
        "created_by": "ai",
        "change_summary": "Initial AI-generated itinerary",
        "itinerary": {
            "total_cost_estimate": itinerary.get("total_cost_estimate", 0),
            "currency": itinerary.get("currency", "USD"),
            "days": days_data
        }
    }
    
    version_result = await db.itinerary_versions.insert_one(version_doc)
    version_id = str(version_result.inserted_id)
    
    # ── Save Conversation ──
    messages = state.get("messages", [])
    conversation_doc = {
        "trip_id": trip_id,
        "user_id": user_id,
        "created_at": now,
        "messages": [
            {
                "role": msg.get("role", "ai") if isinstance(msg, dict) else "ai",
                "content": msg.get("content", "") if isinstance(msg, dict) else str(msg),
                "timestamp": now,
            }
            for msg in messages
        ]
    }
    await db.conversations.insert_one(conversation_doc)
    
    return {
        "trip_id": trip_id,
        "itinerary_version_id": version_id,
        "current_node": "done",
        "messages": [{
            "role": "ai",
            "content": f"Your trip has been saved! Trip ID: {trip_id}. You can view and refine your itinerary anytime."
        }]
    }
