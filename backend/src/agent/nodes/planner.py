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
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from src.config import settings
from src.agent.schemas import PlannerLLMResponse
from src.agent.tools.flights import search_flights
from src.agent.tools.hotels import search_hotels

MAX_TOOL_ROUNDS = 10

# ── Tool registry — only whitelisted tools can be executed ──
TOOL_REGISTRY = {
    "search_flights": search_flights,
    "search_hotels": search_hotels,
}

PLANNER_SYSTEM_PROMPT = """You are the travel planner for Voyage AI. You plan trips by iteratively gathering data through tools.

## Trip Requirements
{trip_request}

## User Preferences
{user_preferences}

## Available Tools
You can call these backend tools to gather real data:

1. **search_flights**(origin, destination, departure_date, return_date, travelers)
   - origin: Use `origin_iata` from trip requirements (already resolved to IATA code)
   - destination: Use `destination_iata` from trip requirements (already resolved to IATA code)
   - departure_date: Use `start_date` from trip requirements (YYYY-MM-DD)
   - return_date: Use `end_date` from trip requirements (YYYY-MM-DD)
   - travelers: Use `traveler_count` from trip requirements

2. **search_hotels**(city_code, checkin, checkout, guests, radius, radius_unit)
   - city_code: Use `destination_iata` from trip requirements
   - checkin: Use `start_date` from trip requirements (YYYY-MM-DD)
   - checkout: Use `end_date` from trip requirements (YYYY-MM-DD)
   - guests: Use `traveler_count` from trip requirements

## How This Works
You are in an iterative loop. Each round you respond with a JSON object:

1. **If you need more data**: Set `stop: false` and provide `tool_requests` with the tools you want to call. You will receive the results in the next round.
2. **If you have all the data you need**: Set `stop: true`, leave `tool_requests` empty, and fill in your final strategy fields (summary, selected_cities, key_experiences, budget_allocation, cost_estimates, recommendations, warnings).

## Rules
- Use the IATA codes already provided in the trip requirements (`origin_iata`, `destination_iata`). Do NOT pass full city names to tools.
- Try to call search_flights and search_hotels to get real pricing data.
- **If a tool call fails or returns an error, do NOT retry it. Continue planning using your own knowledge and provide reasonable cost estimates based on your training data.** The plan must succeed even without tool data.
- You can call multiple tools in a single round.
- Refine your strategy as you receive more data. Each round should build on the last.
- Max {max_rounds} rounds — make efficient use of each one.
- Be specific and realistic with cost estimates.
- Do NOT generate the day-by-day itinerary — that's the next node's job.
- For attractions, restaurants, and local info, use your built-in knowledge.

## Response Schema (JSON)
{schema}
"""


def _get_llm():
    """Get the Gemini LLM instance."""
    return ChatGoogleGenerativeAI(
        model=settings.LLM_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0.2,
    )


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


def _parse_llm_response(response_text: str) -> PlannerLLMResponse:
    """Parse LLM response text into PlannerLLMResponse."""
    # Strip markdown code fences if present
    text = response_text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    
    data = json.loads(text)
    return PlannerLLMResponse(**data)


async def planner_node(state: dict) -> dict:
    """
    Iterative LLM ↔ Tool loop.
    
    The LLM decides which tools to call each round. Tool results are
    fed back. Loop ends when LLM sets stop=true or after MAX_TOOL_ROUNDS.
    
    Google Maps grounding runs natively inside the model for attractions/POI data.
    
    When re-entered after a review rejection, the planner sees the user's
    revision feedback and the previous strategy/itinerary, so it can
    make targeted adjustments.
    """
    trip_request = state.get("trip_request", {})
    user_preferences = state.get("user_preferences", {})
    review_feedback = state.get("review_feedback", "")
    previous_strategy = state.get("trip_strategy", {})
    previous_itinerary = state.get("itinerary", {})
    
    llm = _get_llm()
    schema_str = json.dumps(PlannerLLMResponse.model_json_schema(), indent=2)
    
    system_prompt = PLANNER_SYSTEM_PROMPT.format(
        trip_request=json.dumps(trip_request, indent=2, default=str),
        user_preferences=json.dumps(user_preferences, indent=2, default=str),
        max_rounds=MAX_TOOL_ROUNDS,
        schema=schema_str
    )
    
    # If this is a revision pass, add context about what the user wants changed
    if review_feedback and previous_strategy:
        system_prompt += f"""

## ⚠️ REVISION MODE
The user reviewed the previous itinerary and requested changes.

User's feedback: "{review_feedback}"

Previous strategy:
{json.dumps(previous_strategy, indent=2, default=str)}

Previous itinerary summary:
{json.dumps(previous_itinerary.get('summary', ''), default=str)}

IMPORTANT: Focus on addressing the user's feedback. You may call tools again if the feedback requires new data (e.g., different flights, hotels). Otherwise, update your strategy to reflect the requested changes and set stop=true.
"""
    
    # Conversation history for the planner loop (internal to this node)
    loop_messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content="Begin planning. Decide which tools to call first.")
    ]
    
    all_tool_results = {}  # accumulated across all rounds
    all_tool_calls = []    # log of every tool request
    final_strategy = None  # the last PlannerLLMResponse with stop=true
    
    for round_num in range(1, MAX_TOOL_ROUNDS + 1):
        # ── LLM turn ──
        response = await llm.ainvoke(loop_messages)
        response_text = response.content
        
        # Parse the response
        try:
            planner_response = _parse_llm_response(response_text)
        except (json.JSONDecodeError, Exception):
            # If parsing fails on a non-final round, ask LLM to retry
            if round_num < MAX_TOOL_ROUNDS:
                loop_messages.append(AIMessage(content=response_text))
                loop_messages.append(HumanMessage(
                    content="Your response was not valid JSON. Please respond with a valid JSON object matching the schema."
                ))
                continue
            else:
                # Last round — force stop with whatever we have
                break
        
        # Add LLM response to conversation
        loop_messages.append(AIMessage(content=response_text))
        
        # ── Check stop flag ──
        if planner_response.stop:
            final_strategy = planner_response
            break
        
        # ── Execute requested tools ──
        tool_requests = [tr.dict() if hasattr(tr, "dict") else tr for tr in planner_response.tool_requests]
        
        if not tool_requests:
            # LLM didn't request tools and didn't set stop — nudge it
            loop_messages.append(HumanMessage(
                content="You didn't request any tools and didn't set stop=true. Either call tools you need or set stop=true with your final strategy."
            ))
            continue
        
        all_tool_calls.extend(tool_requests)
        round_results = _execute_tools(tool_requests)
        
        # Merge into accumulated results (keyed by tool_name, later calls overwrite)
        for tool_name, result in round_results.items():
            if tool_name in all_tool_results:
                # If same tool called again, store as list
                if isinstance(all_tool_results[tool_name], list):
                    all_tool_results[tool_name].append(result)
                else:
                    all_tool_results[tool_name] = [all_tool_results[tool_name], result]
            else:
                all_tool_results[tool_name] = result
        
        # ── Feed results back to LLM ──
        tools_called = [r.get("tool_name", "") for r in tool_requests]
        
        # Check for errors in results
        has_errors = any(
            isinstance(v, dict) and "error" in v 
            for v in round_results.values()
        )
        error_note = ""
        if has_errors:
            error_note = (
                "\n\n⚠️ Some tools returned errors. Do NOT retry them. "
                "Use your own knowledge to estimate costs and details for the failed tools. "
                "Proceed with planning using whatever data you have."
            )
        
        feedback = (
            f"Round {round_num} complete. Tools called: {tools_called}\n\n"
            f"Results:\n{json.dumps(round_results, indent=2, default=str)}"
            f"{error_note}\n\n"
            f"Analyze these results. Then either:\n"
            f"- Call more tools if you need additional data (but do NOT retry failed tools)\n"
            f"- Set stop=true and provide your final strategy if you have enough info\n\n"
            f"Rounds remaining: {MAX_TOOL_ROUNDS - round_num}"
        )
        loop_messages.append(HumanMessage(content=feedback))
        
        # Save latest strategy in case we hit max rounds
        final_strategy = planner_response
    
    # ── Build final state update ──
    if final_strategy is None:
        # Fallback — no valid response was ever parsed
        final_strategy = PlannerLLMResponse(
            stop=True,
            summary=f"Trip to {trip_request.get('destination', 'destination')}",
            selected_cities=[trip_request.get("destination", "")],
            key_experiences=["Local food", "Cultural sites", "City exploration"],
            budget_allocation={"flights": 30, "hotels": 35, "activities": 20, "food": 10, "misc": 5},
            cost_estimates={"total": trip_request.get("budget_max", 2000)},
            recommendations=["Explore local food markets", "Visit cultural landmarks"],
        )
    
    strategy_dict = final_strategy.dict(exclude={"tool_requests", "stop"})
    
    return {
        "tool_plan": all_tool_calls,
        "tool_results": all_tool_results,
        "trip_strategy": strategy_dict,
        "current_node": "itinerary_gen",
        "messages": [{
            "role": "ai",
            "content": (
                f"Planning complete! I researched your trip across {len(all_tool_calls)} tool calls. "
                f"Now generating your day-by-day itinerary..."
            )
        }]
    }
