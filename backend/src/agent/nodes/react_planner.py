"""ReAct planner node – uses LangGraph create_react_agent for tool-calling planning.

Replaces the custom planner node with a ReAct agent that reasons and calls
search_flights / search_hotels. After the agent finishes, we extract tool results
from messages and run a single strategy-extraction LLM call to produce trip_strategy
for the rest of the graph. HITL for itinerary review remains in the outer graph.
"""

import json
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from src.config import settings
from src.agent.tools.langchain_tools import get_react_agent_tools

from langgraph.prebuilt import create_react_agent

REACT_SYSTEM = """You are the travel planner for Voyage AI — an AI travel assistant for Indian travelers.

Your job is to plan a trip using the tools available to you:

1. **search_flights**(origin, destination, departure_date, return_date, travelers)
   Use IATA codes from the trip requirements (origin_iata, destination_iata). Dates in YYYY-MM-DD.

2. **search_hotels**(city_code, checkin, checkout, guests, radius, radius_unit)
   Use destination_iata as city_code. Use start_date/end_date for checkin/checkout.

Call these tools to get real flight and hotel data. Then summarize your plan: key experiences,
budget allocation (flights, hotels, activities, food in INR), cost estimates from the tool results,
and any warnings. All amounts must be in INR (Indian Rupees). Do not use USD.
When you have called the tools and have enough information, provide your final trip strategy in plain text.
"""

STRATEGY_EXTRACT_PROMPT = """Based on the travel planning conversation and tool results below, output a single JSON object with these exact keys (no extra keys):
- summary (string): one-paragraph trip strategy
- selected_cities (array of strings)
- key_experiences (array of strings)
- budget_allocation (object: flights, hotels, activities, food, misc — numbers that sum to 100)
- cost_estimates (object: flights, hotels, activities, total — numbers in INR)
- recommendations (array of strings)
- warnings (array of strings)

Use the tool results for real costs. All money in INR.

Conversation / agent output:
{agent_output}

Tool results (use for cost_estimates):
{tool_results_json}

Respond with only the JSON object, no markdown.
"""


def _get_llm():
    return ChatGoogleGenerativeAI(
        model=settings.LLM_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0.2,
    )


def _extract_tool_results_from_messages(messages: list) -> tuple[dict, list]:
    """Extract tool_results dict and tool_plan list from agent messages.
    Pairs tool_calls from AIMessage with ToolMessages in order.
    Returns (tool_results, tool_plan). tool_results keys are tool names.
    """
    tool_plan = []
    pending_calls = []  # list of (tool_name, args)
    tool_results = {}
    for msg in messages:
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            for tc in msg.tool_calls:
                name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "")
                args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
                tool_plan.append({"tool_name": name, "parameters": args})
                pending_calls.append(name)
        if isinstance(msg, ToolMessage):
            content = getattr(msg, "content", "") or ""
            if isinstance(content, str) and content.strip().startswith("{"):
                try:
                    data = json.loads(content)
                except json.JSONDecodeError:
                    data = {"raw": content}
            else:
                data = {"raw": str(content)}
            # Match to next pending tool call in order
            if pending_calls:
                tool_name = pending_calls.pop(0)
                tool_results[tool_name] = data
    return tool_results, tool_plan


def _extract_agent_final_text(messages: list) -> str:
    """Get the last AI message content that is not a tool call (final reasoning/summary)."""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and getattr(msg, "content", None):
            content = msg.content
            if content and (not getattr(msg, "tool_calls", None) or not msg.tool_calls):
                return content if isinstance(content, str) else str(content)
    return ""


def _parse_strategy_response(text: str) -> dict:
    """Parse strategy JSON from LLM response."""
    text = text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    data = json.loads(text)
    return {
        "summary": data.get("summary", ""),
        "selected_cities": data.get("selected_cities", []),
        "key_experiences": data.get("key_experiences", []),
        "budget_allocation": data.get("budget_allocation", {}),
        "cost_estimates": data.get("cost_estimates", {}),
        "recommendations": data.get("recommendations", []),
        "warnings": data.get("warnings", []),
    }


def _available_flights_and_hotels(tool_results: dict) -> tuple[list, list]:
    """Get available_flights and available_hotels from tool_results for downstream nodes."""
    flights = []
    flight_data = tool_results.get("search_flights", {})
    if isinstance(flight_data, dict) and "flights" in flight_data:
        flights = flight_data["flights"]
    elif isinstance(flight_data, list) and flight_data:
        last = flight_data[-1] if isinstance(flight_data[-1], dict) else {}
        flights = last.get("flights", [])

    hotels = []
    hotel_data = tool_results.get("search_hotels", {})
    if isinstance(hotel_data, dict) and "hotels" in hotel_data:
        hotels = hotel_data["hotels"]
    elif isinstance(hotel_data, list) and hotel_data:
        last = hotel_data[-1] if isinstance(hotel_data[-1], dict) else {}
        hotels = last.get("hotels", [])
    return flights, hotels


async def react_planner_node(state: dict) -> dict:
    """
    Run a ReAct agent with search_flights and search_hotels, then extract
    tool_results and trip_strategy for the rest of the graph.
    """
    if create_react_agent is None:
        # Fallback: delegate to the original planner node behavior via a simple strategy
        from src.agent.nodes.planner import planner_node
        return await planner_node(state)

    trip_request = state.get("trip_request", {}) or {}
    user_preferences = state.get("user_preferences", {}) or {}
    review_feedback = state.get("review_feedback", "")
    previous_strategy = state.get("trip_strategy", {})
    previous_itinerary = state.get("itinerary", {})

    tools = get_react_agent_tools()
    llm = _get_llm()
    react_graph = create_react_agent(llm, tools)

    system_content = REACT_SYSTEM + "\n\n## Trip Requirements\n" + json.dumps(trip_request, indent=2, default=str)
    if user_preferences:
        system_content += "\n\n## User Preferences\n" + json.dumps(user_preferences, indent=2, default=str)
    if review_feedback and previous_strategy:
        system_content += f"\n\n## Revision requested\nUser feedback: {review_feedback}\n\nPrevious strategy:\n" + json.dumps(previous_strategy, indent=2, default=str)

    user_content = (
        "Plan this trip. Call search_flights and search_hotels with the IATA codes and dates from the trip requirements, "
        "then summarize your strategy and cost estimates in INR."
    )

    # Build messages in LangChain format
    initial_messages = [
        SystemMessage(content=system_content),
        HumanMessage(content=user_content),
    ]

    # Invoke ReAct agent (run until it stops calling tools)
    config = {"configurable": {}}
    agent_state = await react_graph.ainvoke(
        {"messages": initial_messages},
        config=config,
    )
    messages_out = agent_state.get("messages", [])

    # Extract tool results and plan from agent messages
    tool_results, tool_plan = _extract_tool_results_from_messages(messages_out)
    agent_final_text = _extract_agent_final_text(messages_out)

    # Strategy extraction: one LLM call to get structured trip_strategy
    strategy_dict = {
        "summary": f"Trip to {trip_request.get('destination', 'destination')}",
        "selected_cities": [trip_request.get("destination", "")],
        "key_experiences": [],
        "budget_allocation": {"flights": 30, "hotels": 35, "activities": 20, "food": 10, "misc": 5},
        "cost_estimates": {"total": trip_request.get("budget_max", 50000)},
        "recommendations": [],
        "warnings": ["Economy class assumed", "3-star hotel assumed"],
    }
    if agent_final_text or tool_results:
        try:
            extract_llm = _get_llm()
            prompt = STRATEGY_EXTRACT_PROMPT.format(
                agent_output=agent_final_text or "(no summary)",
                tool_results_json=json.dumps(tool_results, indent=2, default=str),
            )
            response = await extract_llm.ainvoke([HumanMessage(content=prompt)])
            content = getattr(response, "content", str(response))
            if isinstance(content, list):
                text = "".join(
                    p.get("text", "") if isinstance(p, dict) else str(p) for p in content
                )
            else:
                text = content if isinstance(content, str) else str(content)
            strategy_dict = _parse_strategy_response(text)
        except Exception:
            pass

    available_flights, available_hotels = _available_flights_and_hotels(tool_results)

    return {
        "tool_plan": tool_plan,
        "tool_results": tool_results,
        "trip_strategy": strategy_dict,
        "available_flights": available_flights,
        "available_hotels": available_hotels,
        "selected_flight": {},
        "selected_hotel": {},
        "current_node": "flight_selection",
        "messages": [{
            "role": "ai",
            "content": (
                f"Planning complete using ReAct agent ({len(tool_plan)} tool calls). "
                f"All prices in INR (₹). Picking your flight and hotel next."
            )
        }],
    }
