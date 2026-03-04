"""Node 3: Itinerary Generation.

Converts strategy + insights into a clear, day-wise itinerary.
Includes the user-selected flight and hotel in the itinerary.
Single LLM call. No new reasoning, no tool calls.
"""

import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.config import settings
from src.agent.schemas import GeneratedItinerary


ITINERARY_SYSTEM_PROMPT = """You are an itinerary formatter for Voyage AI — designed for Indian travelers. Convert the travel strategy and insights into a beautiful, structured day-by-day itinerary.

Trip Requirements:
{trip_request}

Travel Strategy:
{strategy}

Tool Results (real data):
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
7. Use location data from tool results where available.
8. Do NOT invent new information — only use what's provided.
9. Include the selected flight and hotel details in the itinerary fields.
10. Add a list of assumptions made (e.g., "Economy class assumed", "3-star hotel assumed").
11. All amounts MUST be in INR (Indian Rupees ₹). No USD or other currencies.

Respond with JSON matching this schema:
{schema}
"""


def _get_llm():
    return ChatGoogleGenerativeAI(
        model=settings.LLM_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0.3,
    )


def _format_selection(selection: dict, label: str) -> str:
    """Format a flight or hotel selection for the prompt."""
    if not selection:
        return f"No {label} selected (use assumptions: economy class / 3-star hotel)."
    if selection.get("assumption"):
        return f"{label} (assumed): {selection.get('note', 'Standard option assumed.')}"
    return json.dumps(selection, indent=2, default=str)


async def itinerary_gen_node(state: dict) -> dict:
    """
    Generate a structured day-wise itinerary from strategy + insights + selections.
    Single LLM call — no new reasoning, no tool calls.
    """
    trip_request = state.get("trip_request", {})
    trip_strategy = state.get("trip_strategy", {})
    tool_results = state.get("tool_results", {})
    selected_flight = state.get("selected_flight", {})
    selected_hotel = state.get("selected_hotel", {})
    
    llm = _get_llm()
    
    schema_str = json.dumps(GeneratedItinerary.model_json_schema(), indent=2)
    prompt = ITINERARY_SYSTEM_PROMPT.format(
        trip_request=json.dumps(trip_request, indent=2, default=str),
        strategy=json.dumps(trip_strategy, indent=2, default=str),
        tool_results=json.dumps(tool_results, indent=2, default=str),
        selected_flight=_format_selection(selected_flight, "Flight"),
        selected_hotel=_format_selection(selected_hotel, "Hotel"),
        schema=schema_str
    )
    
    response = await llm.ainvoke([
        SystemMessage(content=prompt),
        HumanMessage(content="Generate the day-by-day itinerary in INR currency.")
    ])
    
    # Parse response
    try:
        response_text = response.content
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        itinerary_data = json.loads(response_text)
        # Always ensure currency is INR
        itinerary_data["currency"] = "INR"
        # Embed selected flight/hotel into itinerary
        if selected_flight:
            itinerary_data["selected_flight"] = selected_flight
        if selected_hotel:
            itinerary_data["selected_hotel"] = selected_hotel
        
        itinerary = GeneratedItinerary(**itinerary_data)
    except Exception as e:
        # Fallback: minimal itinerary
        itinerary = GeneratedItinerary(
            title=f"Trip to {trip_request.get('destination', 'Your Destination')}",
            total_cost_estimate=trip_request.get("budget_max", 50000),
            currency="INR",
            summary=f"A {trip_request.get('duration_days', 5)}-day trip to {trip_request.get('destination', 'your destination')}.",
            days=[],
            reasoning=[f"Error generating detailed itinerary: {str(e)}. Please try again."],
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
