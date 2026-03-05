"""Node 0: Pre-Agent Initializer – No LLM.

Loads user preferences and saved constraints from MongoDB,
attaches all context to the initial agent state.
"""

from datetime import datetime
from src.database import get_database


def _today_iso() -> str:
    """Current date in YYYY-MM-DD for prompts and validation."""
    return datetime.now().strftime("%Y-%m-%d")


async def initializer_node(state: dict) -> dict:
    """
    Load user context from MongoDB and attach to state.
    No LLM call — pure data retrieval.
    """
    db = get_database()
    user_id = state.get("user_id")
    
    user_preferences = {}
    
    if user_id:
        from bson import ObjectId
        try:
            user = await db.users.find_one({"_id": ObjectId(user_id)})
            if user and "preferences" in user:
                user_preferences = user["preferences"]
        except Exception:
            pass  # If user not found, proceed with empty preferences
    
    return {
        "current_date": _today_iso(),
        "user_preferences": user_preferences,
        "trip_request": {},
        "slots_complete": False,
        "clarification_count": 0,
        "tool_plan": [],
        "tool_results": {},
        "trip_strategy": {},
        "itinerary": {},
        "trip_id": "",
        "itinerary_version_id": "",
        "current_node": "intent_slot"
    }
