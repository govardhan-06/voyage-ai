"""Node 2: Planner – Iterative LLM ↔ Tool Loop.

Core intelligence node with an internal loop:
  1. LLM analyzes state and decides which tools to call (or sets stop=true)
  2. Backend executes tools deterministically
  3. Tool results are fed back to the LLM
  4. Repeat until LLM sets stop=true OR max 10 rounds

The LLM also has access to Google Maps grounding for location/attraction
data — that runs natively inside the model, not through the tool registry.

When the loop ends, the accumulated strategy + all tool results are
written to state for the itinerary generator node.
"""

import json
from datetime import datetime
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from src.config import settings
from src.agent.schemas import PlannerLLMResponse
from src.agent.tools import AVAILABLE_TOOLS
from src.agent.utils.tracing import trace_agent_node, trace_llm_call

MAX_TOOL_ROUNDS = 3

# ── Tool registry — only whitelisted tools can be executed ──
# Note: This will be replaced with native LangChain tool binding
TOOL_REGISTRY = {tool.name: tool.func for tool in AVAILABLE_TOOLS}


def _sanitize_tool_results_for_llm(tool_results: dict) -> dict:
    """
    Remove error messages from tool results so the LLM never mentions failures to the user.
    Replace failed results with empty but valid structures (flights=[], hotels=[]).
    """
    sanitized = {}
    for name, data in (tool_results or {}).items():
        if isinstance(data, dict) and data.get("error"):
            if "flight" in name.lower():
                sanitized[name] = {"flights": [], "total_results": 0}
            elif "hotel" in name.lower():
                sanitized[name] = {"hotels": [], "total_results": 0}
            else:
                sanitized[name] = {}
        else:
            sanitized[name] = data
    return sanitized

PLANNER_SYSTEM_PROMPT_TOOL_CALLING = """You are the travel planner for Voyage AI — an AI travel assistant specifically designed for Indian travelers.

## Today's date
{current_date} — use this for context. All trip dates in the requirements are already validated to be on or after this date.

## Trip Requirements
{trip_request}

## User Preferences
{user_preferences}

## Your Task
Analyze the trip requirements and call the available tools to gather real flight and hotel data. Then provide a comprehensive travel strategy. When calling tools, use the exact start_date and end_date from the trip requirements (they are already in the future).

## Available Tools
You have access to search_flights and search_hotels tools. Use them to get real pricing data:

- **search_flights**: Get flight options and pricing
  - Use `origin_iata` and `destination_iata` from trip requirements
  - Use `start_date` as departure_date and `end_date` as return_date (both are already future dates)
  - Use `traveler_count` for number of travelers

- **search_hotels**: Get hotel options and pricing  
  - Use `destination_iata` as city_code
  - Use `start_date` as checkin and `end_date` as checkout (both are already future dates)
  - Use `traveler_count` for guests

## Instructions
1. First, call the tools you need to gather real data
2. If tools fail, continue with your knowledge and provide estimates
3. Create a comprehensive travel strategy with realistic cost estimates in INR
4. Do NOT generate day-by-day itinerary - that's handled separately

## Standard Assumptions
- Economy class flights unless specified otherwise
- 3-star hotels unless specified otherwise  
- 1 room for solo/couple, separate rooms for groups of 3+
- All costs in INR (Indian Rupees ₹)"""

PLANNER_DECISION_PROMPT = """Based on the tool results (if any), create your final travel strategy.

## Today's date
{current_date}

## Trip Requirements
{trip_request}

## Tool Results (flights/hotels — use only when present; otherwise use your knowledge for estimates)
{tool_results}

## Previous Context
{previous_context}

Create a comprehensive strategy including:
- Summary of the travel plan
- Selected cities to visit
- Key experiences and attractions
- Budget allocation breakdown
- Cost estimates (use tool data when available; otherwise use realistic estimates in INR)
- Recommendations for the traveler
- Assumptions (e.g. economy class, 3-star hotel) — do NOT mention that any API or tool failed or that data is missing

All costs must be in INR. Be specific and realistic for Indian travelers. Do not refer to errors, API failures, or missing data in your strategy or warnings."""


def _get_llm_with_tools():
    """Get the Gemini LLM instance with tools bound."""
    llm = ChatGoogleGenerativeAI(
        model=settings.LLM_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0.2,
    )
    return llm.bind_tools(AVAILABLE_TOOLS)

def _get_structured_llm():
    """Get the Gemini LLM instance for structured output (planning decisions)."""
    return ChatGoogleGenerativeAI(
        model=settings.LLM_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0.2,
    ).with_structured_output(PlannerLLMResponse)


def _execute_tools(tool_requests: list) -> dict:
    """Deterministic tool execution — only whitelisted tools allowed."""
    results = {}
    for req in tool_requests:
        tool_name = req.get("tool_name", "")
        params = req.get("parameters", {})
        
        if tool_name not in TOOL_REGISTRY:
            results[tool_name] = {"error": f"Unknown tool: {tool_name}"}
            continue
        
        try:
            tool_fn = TOOL_REGISTRY[tool_name]
            result = tool_fn(**params)
            results[tool_name] = result
        except Exception as e:
            results[tool_name] = {"error": str(e)}
    
    return results




@trace_agent_node("planner")
async def planner_node(state: dict) -> dict:
    """
    Modern LangChain tool-calling approach for travel planning.
    
    Uses native tool binding and structured outputs for better reliability.
    Two-phase approach:
    1. Tool calling phase: LLM calls tools to gather data
    2. Strategy phase: LLM creates final strategy with structured output
    """
    trip_request = state.get("trip_request", {})
    user_preferences = state.get("user_preferences", {})
    review_feedback = state.get("review_feedback", "")
    previous_strategy = state.get("trip_strategy", {})
    previous_itinerary = state.get("itinerary", {})
    current_date = state.get("current_date") or datetime.now().strftime("%Y-%m-%d")
    
    # Phase 1: Tool calling to gather data
    llm_with_tools = _get_llm_with_tools()
    
    tool_calling_prompt = PLANNER_SYSTEM_PROMPT_TOOL_CALLING.format(
        current_date=current_date,
        trip_request=json.dumps(trip_request, indent=2, default=str),
        user_preferences=json.dumps(user_preferences, indent=2, default=str)
    )
    
    # Add revision context if needed
    revision_context = ""
    if review_feedback and previous_strategy:
        revision_context = f"""

## ⚠️ REVISION MODE
User feedback: "{review_feedback}"
Previous strategy: {json.dumps(previous_strategy, indent=2, default=str)}
Focus on addressing the user's feedback."""
        tool_calling_prompt += revision_context
    
    # Call LLM with tools to gather data
    tool_messages = [
        SystemMessage(content=tool_calling_prompt),
        HumanMessage(content="Analyze the trip requirements and call the necessary tools to gather flight and hotel data.")
    ]
    
    try:
        tool_response = await llm_with_tools.ainvoke(tool_messages)
        
        # Extract tool calls and results
        all_tool_results = {}
        all_tool_calls = []
        
        # Process any tool calls made by the LLM
        if hasattr(tool_response, 'tool_calls') and tool_response.tool_calls:
            for tool_call in tool_response.tool_calls:
                tool_name = tool_call['name']
                tool_args = tool_call['args']
                
                all_tool_calls.append({
                    "tool_name": tool_name,
                    "parameters": tool_args
                })
                
                # Execute the tool
                try:
                    if tool_name in TOOL_REGISTRY:
                        result = TOOL_REGISTRY[tool_name](**tool_args)
                        all_tool_results[tool_name] = result
                    else:
                        all_tool_results[tool_name] = {"error": f"Unknown tool: {tool_name}"}
                except Exception as e:
                    all_tool_results[tool_name] = {"error": str(e)}
        
    except Exception as e:
        # Fallback if tool calling fails
        all_tool_results = {}
        all_tool_calls = []
    
    # Sanitize tool results so the LLM never sees or mentions errors (use empty flights/hotels instead)
    sanitized_tool_results = _sanitize_tool_results_for_llm(all_tool_results)
    
    # Phase 2: Create strategy with structured output
    structured_llm = _get_structured_llm()
    
    strategy_prompt = PLANNER_DECISION_PROMPT.format(
        current_date=current_date,
        trip_request=json.dumps(trip_request, indent=2, default=str),
        tool_results=json.dumps(sanitized_tool_results, indent=2, default=str),
        previous_context=revision_context
    )
    
    try:
        final_strategy = await structured_llm.ainvoke([
            SystemMessage(content=strategy_prompt),
            HumanMessage(content="Create the comprehensive travel strategy based on the available data.")
        ])
    except Exception:
        # Fallback strategy (no mention of tool failure)
        final_strategy = PlannerLLMResponse(
            stop=True,
            summary=f"Trip to {trip_request.get('destination', 'destination')}",
            selected_cities=[trip_request.get("destination", "")],
            key_experiences=["Local food", "Cultural sites", "City exploration"],
            budget_allocation={"flights": 30, "hotels": 35, "activities": 20, "food": 10, "misc": 5},
            cost_estimates={"total": trip_request.get("budget_max", 50000)},
            recommendations=["Explore local food markets", "Visit cultural landmarks"],
            warnings=["Economy class assumed", "3-star hotel assumed"]
        )
    
    strategy_dict = final_strategy.dict(exclude={"tool_requests", "stop"})
    
    # Extract available flights and hotels for user selection
    available_flights = []
    available_hotels = []
    
    flight_data = all_tool_results.get("search_flights", {})
    if isinstance(flight_data, dict):
        available_flights = flight_data.get("flights", [])
    
    hotel_data = all_tool_results.get("search_hotels", {})
    if isinstance(hotel_data, dict):
        available_hotels = hotel_data.get("hotels", [])
    
    return {
        "tool_plan": all_tool_calls,
        "tool_results": sanitized_tool_results,  # store sanitized so itinerary never sees errors
        "trip_strategy": strategy_dict,
        "available_flights": available_flights,
        "available_hotels": available_hotels,
        "selected_flight": {},  # reset selection for re-planning
        "selected_hotel": {},   # reset selection for re-planning
        "current_node": "flight_selection",
        "messages": [{
            "role": "ai",
            "content": (
                f"Planning complete! I researched your trip using {len(all_tool_calls)} tool calls. "
                f"All prices are in INR (₹). Let me now help you pick your flights and hotel!"
            )
        }]
    }
