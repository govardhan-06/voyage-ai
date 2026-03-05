"""LangGraph assembly – Human-in-the-Loop with Checkpointing.

Uses interrupt_before only for review (draft itinerary approval).
Flight and hotel selection auto-pick the first option (no pause).

Graph flow:
  initializer → intent_slot → (loop via interrupt | proceed)
    → planner → flight_selection → hotel_selection
    → itinerary_gen → review → (approve → finalizer | revise → planner)
    → finalizer → END
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from src.agent.state import AgentState
from src.agent.nodes.initializer import initializer_node
from src.agent.nodes.intent_slot import intent_slot_node
from src.agent.nodes.planner import planner_node
from src.agent.nodes.flight_selection import flight_selection_node
from src.agent.nodes.hotel_selection import hotel_selection_node
from src.agent.nodes.itinerary_gen import itinerary_gen_node
from src.agent.nodes.review import review_node
from src.agent.nodes.finalizer import finalizer_node
from src.agent.utils.middleware import optimize_state_between_nodes


def _route_after_intent_slot(state: dict) -> str:
    """
    After intent_slot:
    - If slots complete → planner
    - If not complete → END (graph pauses; API will update state + resume)
    """
    if state.get("slots_complete", False):
        return "planner"
    # When slots are incomplete, we go to END so the graph stops.
    # The API detects this via state.next and handles the clarification loop.
    return "__end__"


def _route_after_review(state: dict) -> str:
    """
    After review:
    - If approved → finalizer
    - If revision requested → back to planner
    """
    if state.get("review_status") == "approved":
        return "finalizer"
    return "planner"


async def memory_optimizer_node(state: dict) -> dict:
    """
    Memory optimization node to prune messages between major transitions.
    
    This lightweight node optimizes state without changing the core logic.
    """
    optimized_state = optimize_state_between_nodes(state)
    
    # Don't change the current_node - just pass through with optimized state
    return optimized_state


def build_travel_graph():
    """Build and compile the LangGraph travel planning graph with checkpointing."""
    
    graph = StateGraph(AgentState)
    
    # Add nodes
    graph.add_node("initializer", initializer_node)
    graph.add_node("intent_slot", intent_slot_node)
    graph.add_node("memory_optimizer_1", memory_optimizer_node)  # After slot filling
    graph.add_node("planner", planner_node)
    graph.add_node("flight_selection", flight_selection_node)
    graph.add_node("hotel_selection", hotel_selection_node)
    graph.add_node("memory_optimizer_2", memory_optimizer_node)  # After selections
    graph.add_node("itinerary_gen", itinerary_gen_node)
    graph.add_node("review", review_node)
    graph.add_node("finalizer", finalizer_node)
    
    # Set entry point
    graph.set_entry_point("initializer")
    
    # Edges
    graph.add_edge("initializer", "intent_slot")
    
    # intent_slot → memory_optimizer_1 → planner (complete) or → END (needs clarification)
    graph.add_conditional_edges(
        "intent_slot",
        _route_after_intent_slot,
        {
            "__end__": END,
            "planner": "memory_optimizer_1"
        }
    )
    
    # Memory optimization before planning
    graph.add_edge("memory_optimizer_1", "planner")
    
    # planner → flight_selection → hotel_selection → memory_optimizer_2 → itinerary_gen
    graph.add_edge("planner", "flight_selection")
    graph.add_edge("flight_selection", "hotel_selection")
    graph.add_edge("hotel_selection", "memory_optimizer_2")
    graph.add_edge("memory_optimizer_2", "itinerary_gen")
    graph.add_edge("itinerary_gen", "review")
    
    # review → finalizer (approved) or → memory_optimizer_1 → planner (revision)
    graph.add_conditional_edges(
        "review",
        _route_after_review,
        {
            "finalizer": "finalizer",
            "planner": "memory_optimizer_1"  # Optimize memory before re-planning
        }
    )
    
    graph.add_edge("finalizer", END)
    
    # Compile with checkpointer + interrupt only before review (itinerary approval)
    checkpointer = MemorySaver()
    return graph.compile(
        checkpointer=checkpointer,
        interrupt_before=["review"]
    )


# Pre-compiled graph instance
travel_graph = build_travel_graph()
