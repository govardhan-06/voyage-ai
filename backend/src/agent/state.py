from typing import TypedDict, List, Optional, Annotated
from operator import add

class AgentState(TypedDict):
    """Full state flowing through the LangGraph travel planning pipeline."""
    
    # User context (set by initializer)
    user_id: str
    user_preferences: dict
    
    # Conversation
    messages: Annotated[list, add]  # append-only message list
    
    # Node 1: Intent + Slot Filling
    trip_request: dict           # structured slots extracted
    slots_complete: bool         # whether all required slots filled
    clarification_count: int     # number of clarification rounds
    
    # Node 2: Planning + Tools
    tool_plan: list              # tools to execute
    tool_results: dict           # results from tool execution
    trip_strategy: dict          # high-level strategy
    
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
