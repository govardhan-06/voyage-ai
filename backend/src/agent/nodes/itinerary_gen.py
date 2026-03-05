"""Node 3: Itinerary Generation.

Converts strategy + insights into a clear, day-wise itinerary.
Includes the user-selected flight and hotel in the itinerary.
Single LLM call. No new reasoning, no tool calls.
"""

import json
from datetime import datetime
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.config import settings
from src.agent.schemas import GeneratedItinerary
from src.agent.utils.tracing import trace_agent_node, trace_llm_call


ITINERARY_SYSTEM_PROMPT = """You are an itinerary formatter for Voyage AI — designed for Indian travelers. Convert the travel strategy and insights into a beautiful, structured day-by-day itinerary.

Today's date (for context): {current_date}

Trip Requirements:
{trip_request}

Travel Strategy:
{strategy}

Available data (flights/hotels — use where present; otherwise use realistic estimates):
{tool_results}

Selected Flight:
{selected_flight}

Selected Hotel:
{selected_hotel}

Rules:
1. Generate a day-wise plan for each day of the trip.
2. Each day should have 3-5 activities with time slots.
3. Include cost estimates for each activity IN INR (₹). Do NOT use USD ($).
4. Provide a brief theme for each day (e.g., "Cultural Exploration", "Beach & Relaxation").
5. Include reasoning for major decisions.
6. Total cost should be realistic and within budget (in INR).
7. Use data from the strategy and tool results where available; where data is missing, use your knowledge and realistic estimates.
8. Do NOT mention that any API, tool, or search failed. Do NOT refer to "could not fetch", "error", or "data unavailable". Present the itinerary as normal with estimated costs where needed.
9. Include the selected flight and hotel details in the itinerary when available.
10. Assumptions list: only neutral items (e.g., "Economy class assumed", "3-star hotel assumed"). Never include errors or missing-data mentions.
11. All amounts MUST be in INR (Indian Rupees ₹). No USD or other currencies.

Respond with structured itinerary data.
"""


def _get_llm():
    return ChatGoogleGenerativeAI(
        model=settings.LLM_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0.3,
    ).with_structured_output(GeneratedItinerary)


def _sanitize_tool_results(tool_results: dict) -> dict:
    """Remove any error keys from tool results so the itinerary never mentions failures."""
    if not tool_results:
        return tool_results
    out = {}
    for name, data in tool_results.items():
        if isinstance(data, dict):
            out[name] = {k: v for k, v in data.items() if k != "error"}
        else:
            out[name] = data
    return out


def _format_selection(selection: dict, label: str) -> str:
    """Format a flight or hotel selection for the prompt."""
    if not selection:
        return f"No {label} selected (use assumptions: economy class / 3-star hotel)."
    if selection.get("assumption"):
        return f"{label} (assumed): {selection.get('note', 'Standard option assumed.')}"
    return json.dumps(selection, indent=2, default=str)


@trace_agent_node("itinerary_gen")
async def itinerary_gen_node(state: dict) -> dict:
    """
    Generate a structured day-wise itinerary from strategy + insights + selections.
    Single LLM call — no new reasoning, no tool calls.
    """
    trip_request = state.get("trip_request", {})
    trip_strategy = state.get("trip_strategy", {})
    tool_results = _sanitize_tool_results(state.get("tool_results", {}))
    selected_flight = state.get("selected_flight", {})
    selected_hotel = state.get("selected_hotel", {})
    current_date = state.get("current_date") or datetime.now().strftime("%Y-%m-%d")
    
    llm = _get_llm()
    
    prompt = ITINERARY_SYSTEM_PROMPT.format(
        current_date=current_date,
        trip_request=json.dumps(trip_request, indent=2, default=str),
        strategy=json.dumps(trip_strategy, indent=2, default=str),
        tool_results=json.dumps(tool_results, indent=2, default=str),
        selected_flight=_format_selection(selected_flight, "Flight"),
        selected_hotel=_format_selection(selected_hotel, "Hotel")
    )
    
    # Use structured output - no manual JSON parsing needed
    try:
        itinerary = await llm.ainvoke([
            SystemMessage(content=prompt),
            HumanMessage(content="Generate the day-by-day itinerary in INR currency.")
        ])
        
        # Always ensure currency is INR and embed selections
        itinerary.currency = "INR"
        if selected_flight:
            itinerary.selected_flight = selected_flight
        if selected_hotel:
            itinerary.selected_hotel = selected_hotel
            
    except Exception:
        # Fallback: minimal itinerary (do not expose errors to the user)
        itinerary = GeneratedItinerary(
            title=f"Trip to {trip_request.get('destination', 'Your Destination')}",
            total_cost_estimate=trip_request.get("budget_max", 50000),
            currency="INR",
            summary=f"A {trip_request.get('duration_days', 5)}-day trip to {trip_request.get('destination', 'your destination')}.",
            days=[],
            reasoning=[],
            selected_flight=selected_flight or None,
            selected_hotel=selected_hotel or None,
            assumptions=["Economy class flights assumed", "3-star hotel assumed"]
        )
    
    return {
        "itinerary": itinerary.dict(),
        "current_node": "review",
        "messages": [{
            "role": "ai",
            "content": (
                f"Your itinerary for {itinerary.title} is ready! "
                f"Total estimated cost: ₹{itinerary.total_cost_estimate:,.0f}."
            )
        }]
    }
