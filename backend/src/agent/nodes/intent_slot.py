"""Node 1: Intent + Slot Filling.

Extracts structured trip requirements from the user's message.
Graph pauses BEFORE this node on clarification loops (via interrupt_before).
The API layer handles injecting the user's response into state before resuming.
"""

import json
from datetime import datetime, timedelta
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.config import settings
from src.agent.schemas import SlotFillingResponse
from src.agent.utils.tracing import trace_agent_node, trace_llm_call

MAX_CLARIFICATION_ROUNDS = 3

SLOT_FILLING_SYSTEM_PROMPT = """You are a travel planning assistant for Voyage AI. Your ONLY job is to extract structured trip requirements from the user's message.

Required information (slots):
1. destination - Where the user wants to go (city and/or country)
2. destination_iata - The IATA airport/city code for the destination. You MUST resolve this yourself based on the destination city. Examples: Tokyo → NRT, Paris → CDG, Bali → DPS, London → LHR, New York → JFK, Dubai → DXB, Singapore → SIN, Delhi → DEL, Mumbai → BOM, Bangkok → BKK.
3. origin - Where the user is traveling FROM (city). Ask if not mentioned.
4. origin_iata - The IATA airport/city code for the origin city. Resolve this yourself. Examples: New York → JFK, Delhi → DEL, Mumbai → BOM, Los Angeles → LAX, Chicago → ORD, San Francisco → SFO, Hyderabad → HYD, Bangalore → BLR, Chennai → MAA.
5. duration_days - How many days
6. budget_min / budget_max - Budget range in INR (Indian Rupees)
7. travel_group - solo, couple, family, or friends
8. traveler_count - Number of travelers
9. start_date - Trip start date (YYYY-MM-DD). If the user says "next month" or "in March", convert to an actual date using today's date as reference. The start_date MUST be on or after today ({current_date}).
10. interests - What they want to do (culture, adventure, food, shopping, nature, etc.)

Optional but helpful:
- end_date - Trip end date (auto-calculated from start_date + duration_days if not given). Must be after start_date.
- constraints - Special requirements (accessibility, dietary, etc.)

Today's date (use this for any relative dates like "next week", "in March"): {current_date}. Year: {current_year}.

Rules:
- Extract as much as possible from the user's message.
- When interpreting dates, today is {current_date}. All start_date and end_date values must be in the future (on or after today).
- ALWAYS resolve IATA codes when you know the origin or destination city. Use the nearest major international airport.
- If information is missing, set follow_up_question to ask about the MOST important missing slot.
- Prioritize asking for: destination, origin, start_date, duration_days, budget in that order.
- Keep follow-up questions concise and friendly (1-2 sentences max).
- Set is_complete to true ONLY when destination, origin, duration_days, start_date, and budget (at least max) are all filled.
- Do NOT generate itinerary or recommendations.
- Do NOT call tools.

User preferences from their profile (use as fallbacks):
{user_preferences}
"""


def _ensure_future_dates(slots: dict) -> dict:
    """Ensure start_date and end_date are never in the past. Uses today for comparison."""
    today = datetime.now().date()
    for key in ("start_date", "end_date"):
        val = slots.get(key)
        if not val:
            continue
        try:
            d = datetime.strptime(val, "%Y-%m-%d").date()
            if d < today:
                if key == "start_date":
                    slots["start_date"] = today.strftime("%Y-%m-%d")
                else:
                    # end_date: keep at least start_date
                    start_val = slots.get("start_date")
                    if start_val:
                        start_d = datetime.strptime(start_val, "%Y-%m-%d").date()
                        if start_d >= today:
                            slots["end_date"] = start_val
                        else:
                            slots["end_date"] = today.strftime("%Y-%m-%d")
                    else:
                        slots["end_date"] = today.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            pass
    # Recompute end_date from start_date + duration_days if we changed start_date
    _compute_end_date(slots)
    return slots


def _get_llm():
    return ChatGoogleGenerativeAI(
        model=settings.LLM_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0.1,
    ).with_structured_output(SlotFillingResponse)


def _merge_with_preferences(slots: dict, preferences: dict) -> dict:
    """Fill missing slots from user preferences."""
    if not slots.get("budget_max") and preferences.get("budget_range"):
        budget = preferences["budget_range"]
        if isinstance(budget, dict):
            slots["budget_min"] = slots.get("budget_min") or budget.get("min")
            slots["budget_max"] = slots.get("budget_max") or budget.get("max")
    
    if not slots.get("interests") and preferences.get("interests"):
        slots["interests"] = preferences["interests"]
    
    if not slots.get("travel_group") and preferences.get("travel_style"):
        styles = preferences["travel_style"]
        if isinstance(styles, list) and styles:
            style = styles[0].lower()
            if "solo" in style:
                slots["travel_group"] = "solo"
            elif "couple" in style or "romantic" in style:
                slots["travel_group"] = "couple"
            elif "family" in style:
                slots["travel_group"] = "family"
    
    return slots


def _compute_end_date(slots: dict) -> dict:
    """Auto-compute end_date from start_date + duration_days if not set."""
    if slots.get("start_date") and slots.get("duration_days") and not slots.get("end_date"):
        try:
            start = datetime.strptime(slots["start_date"], "%Y-%m-%d")
            end = start + timedelta(days=int(slots["duration_days"]))
            slots["end_date"] = end.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            pass
    return slots


def _check_completeness(slots: dict) -> bool:
    """Check if all required slots are filled."""
    required = ["destination", "duration_days", "start_date", "origin"]
    for field in required:
        if not slots.get(field):
            return False
    
    if not slots.get("budget_max"):
        return False
    
    if not slots.get("travel_group"):
        slots["travel_group"] = "solo"
    
    if not slots.get("traveler_count"):
        group_defaults = {"solo": 1, "couple": 2, "family": 4, "friends": 4}
        slots["traveler_count"] = group_defaults.get(slots["travel_group"], 2)
    
    # Auto-compute end_date
    _compute_end_date(slots)
    
    return True


@trace_agent_node("intent_slot")
async def intent_slot_node(state: dict) -> dict:
    """
    Extract trip requirements from user message.
    Uses LLM with structured output.
    
    When slots are incomplete, sets slots_complete=False so the graph
    pauses at the interrupt_before point on the next cycle.
    """
    messages = state.get("messages", [])
    user_preferences = state.get("user_preferences", {})
    clarification_count = state.get("clarification_count", 0)
    existing_slots = state.get("trip_request", {})
    current_date = state.get("current_date") or datetime.now().strftime("%Y-%m-%d")
    current_year = current_date[:4] if len(current_date) >= 4 else str(datetime.now().year)
    
    # Get the latest user message
    user_message = ""
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "user":
            user_message = msg.get("content", "")
            break
        elif isinstance(msg, HumanMessage):
            user_message = msg.content
            break
    
    if not user_message:
        return {
            "current_node": "intent_slot",
            "slots_complete": False,
            "messages": [{"role": "ai", "content": "Hi! I'd love to help you plan a trip. Where would you like to go?"}]
        }
    
    llm = _get_llm()
    
    system_prompt = SLOT_FILLING_SYSTEM_PROMPT.format(
        current_date=current_date,
        current_year=current_year,
        user_preferences=json.dumps(user_preferences, indent=2, default=str)
    )
    
    # Include existing slots context if we're in a clarification loop
    context = ""
    if existing_slots:
        context = f"\n\nSlots already collected:\n{json.dumps(existing_slots, indent=2, default=str)}\n\nPlease update/merge with any new information from the user's latest message."
    
    llm_messages = [
        SystemMessage(content=system_prompt + context),
        HumanMessage(content=user_message)
    ]
    
    # Use structured output - no manual JSON parsing needed
    try:
        slot_response = await llm.ainvoke(llm_messages)
    except Exception:
        slot_response = SlotFillingResponse(
            follow_up_question="I had trouble understanding that. Could you tell me where you'd like to go and for how long?",
            is_complete=False
        )
    
    # Merge new slots with existing
    new_slots = slot_response.dict(exclude={"follow_up_question", "is_complete"}, exclude_none=True)
    merged_slots = {**existing_slots, **{k: v for k, v in new_slots.items() if v}}
    
    # Try filling from preferences
    merged_slots = _merge_with_preferences(merged_slots, user_preferences)
    
    # Ensure start_date and end_date are never in the past (fixes Amadeus 400)
    merged_slots = _ensure_future_dates(merged_slots)
    
    # Check completeness
    is_complete = _check_completeness(merged_slots)
    
    # If max clarification rounds reached, force complete with defaults
    if clarification_count >= MAX_CLARIFICATION_ROUNDS and not is_complete:
        if not merged_slots.get("destination"):
            merged_slots["destination"] = "Tokyo, Japan"
        if not merged_slots.get("origin"):
            merged_slots["origin"] = "New York"
        if not merged_slots.get("duration_days"):
            merged_slots["duration_days"] = 5
        if not merged_slots.get("start_date"):
            # Default to 30 days from now
            merged_slots["start_date"] = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        if not merged_slots.get("budget_max"):
            merged_slots["budget_max"] = 2000
        if not merged_slots.get("travel_group"):
            merged_slots["travel_group"] = "solo"
        if not merged_slots.get("traveler_count"):
            merged_slots["traveler_count"] = 1
        _compute_end_date(merged_slots)
        is_complete = True
    
    result = {
        "trip_request": merged_slots,
        "slots_complete": is_complete,
        "clarification_count": clarification_count + 1,
        "current_node": "planner" if is_complete else "intent_slot",
    }
    
    if is_complete:
        result["messages"] = [{
            "role": "ai",
            "content": (
                f"Great! I have all the details I need. Let me plan your trip to "
                f"{merged_slots.get('destination', 'your destination')} "
                f"from {merged_slots.get('start_date', 'TBD')} to {merged_slots.get('end_date', 'TBD')}!"
            )
        }]
    else:
        follow_up = slot_response.follow_up_question or "Could you provide more details about your trip?"
        result["messages"] = [{
            "role": "ai",
            "content": follow_up
        }]
    
    return result
