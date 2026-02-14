"""Node 3: Itinerary Generation.

Converts strategy + insights into a clear, day-wise itinerary.
Single LLM call. No new reasoning, no tool calls.
"""

import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.config import settings
from src.agent.schemas import GeneratedItinerary


ITINERARY_SYSTEM_PROMPT = """You are an itinerary formatter for Voyage AI. Convert the travel strategy and insights into a beautiful, structured day-by-day itinerary.

Trip Requirements:
{trip_request}

Travel Strategy:
{strategy}

Travel Insights:
{insights}

Tool Results (real data):
{tool_results}

Rules:
1. Generate a day-wise plan for each day of the trip.
2. Each day should have 3-5 activities with time slots.
3. Include cost estimates for each activity.
4. Provide a brief theme for each day (e.g., "Cultural Exploration", "Beach & Relaxation").
5. Include reasoning for major decisions.
6. Total cost should be realistic and within budget.
7. Use location data from tool results where available.
8. Do NOT invent new information — only use what's provided.

Respond with JSON matching this schema:
{schema}
"""


def _get_llm():
    return ChatGoogleGenerativeAI(
        model=settings.LLM_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0.3,
    )


async def itinerary_gen_node(state: dict) -> dict:
    """
    Generate a structured day-wise itinerary from strategy + insights.
    Single LLM call — no new reasoning, no tool calls.
    """
    trip_request = state.get("trip_request", {})
    trip_strategy = state.get("trip_strategy", {})
    tool_results = state.get("tool_results", {})
    
    llm = _get_llm()
    
    schema_str = json.dumps(GeneratedItinerary.model_json_schema(), indent=2)
    prompt = ITINERARY_SYSTEM_PROMPT.format(
        trip_request=json.dumps(trip_request, indent=2, default=str),
        strategy=json.dumps(trip_strategy, indent=2, default=str),
        insights=json.dumps(trip_strategy, indent=2, default=str),
        tool_results=json.dumps(tool_results, indent=2, default=str),
        schema=schema_str
    )
    
    response = await llm.ainvoke([
        SystemMessage(content=prompt),
        HumanMessage(content="Generate the day-by-day itinerary.")
    ])
    
    # Parse response
    try:
        response_text = response.content
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        itinerary_data = json.loads(response_text)
        itinerary = GeneratedItinerary(**itinerary_data)
    except Exception as e:
        # Fallback: minimal itinerary
        itinerary = GeneratedItinerary(
            title=f"Trip to {trip_request.get('destination', 'Your Destination')}",
            total_cost_estimate=trip_request.get("budget_max", 2000),
            currency="USD",
            summary=f"A {trip_request.get('duration_days', 5)}-day trip to {trip_request.get('destination', 'your destination')}.",
            days=[],
            reasoning=[f"Error generating detailed itinerary: {str(e)}. Please try again."]
        )
    
    return {
        "itinerary": itinerary.dict(),
        "current_node": "finalizer",
        "messages": [{
            "role": "ai",
            "content": f"Your itinerary for {itinerary.title} is ready! Total estimated cost: {itinerary.currency} {itinerary.total_cost_estimate:.0f}."
        }]
    }
