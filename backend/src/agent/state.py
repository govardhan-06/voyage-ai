from typing import TypedDict, List, Optional, Annotated
from operator import add


def add_messages(left: list, right: list) -> list:
    """
    Custom message reducer that adds new messages and applies pruning.
    
    This replaces the simple 'add' operator to include memory management.
    """
    from src.agent.utils.memory import prune_messages, MAX_MESSAGES_PER_NODE
    
    # Combine messages
    combined = (left or []) + (right or [])
    
    # Apply pruning if we exceed limits
    if len(combined) > MAX_MESSAGES_PER_NODE:
        combined = prune_messages(combined)
    
    return combined


class AgentState(TypedDict):
    """Full state flowing through the LangGraph travel planning pipeline."""
    
    # User context (set by initializer)
    user_id: str
    user_preferences: dict
    current_date: str  # YYYY-MM-DD for LLM and date validation (departure/arrival must be >= this)
    
    # Conversation (with automatic pruning)
    messages: Annotated[list, add_messages]  # message list with memory management
    
    # Node 1: Intent + Slot Filling
    trip_request: dict           # structured slots extracted
    slots_complete: bool         # whether all required slots filled
    clarification_count: int     # number of clarification rounds
    
    # Node 2: Planning + Tools
    tool_plan: list              # tools to execute
    tool_results: dict           # results from tool execution
    trip_strategy: dict          # high-level strategy
    
    # Node 2.5: Flight Selection (human-in-the-loop)
    available_flights: list      # flight options from search
    selected_flight: dict        # user-chosen flight
    
    # Node 2.6: Hotel Selection (human-in-the-loop)
    available_hotels: list       # hotel options from search
    selected_hotel: dict         # user-chosen hotel
    
    # Selection tracking
    selection_step: str          # "" | "awaiting_flight" | "awaiting_hotel"
    
    # Node 3: Itinerary Generation
    itinerary: dict              # generated day-wise itinerary
    
    # Node 3.5: Review (human-in-the-loop)
    review_status: str           # "pending" | "approved" | "revision_requested"
    review_feedback: str         # user's revision notes (if any)
    
    # Node 4: Finalization
    trip_id: str                 # saved trip ID
    itinerary_version_id: str    # saved version ID
    
    # Routing
    current_node: str            # current node for conditional edges
