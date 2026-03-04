"""LangGraph assembly – ReAct agent for planning, HITL for itinerary review only.

Planning uses create_react_agent (tool-calling ReAct loop). Interrupt only before
review for user to approve or request changes. Flight and hotel are auto-selected.

Graph flow:
  initializer → intent_slot → (loop via interrupt | proceed)
    → react_planner → flight_selection → hotel_selection
    → itinerary_gen → review → (approve → finalizer | revise → react_planner)
    → finalizer → END
"""

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from src.agent.state import AgentState
from src.agent.nodes.initializer import initializer_node
from src.agent.nodes.intent_slot import intent_slot_node
from src.agent.nodes.react_planner import react_planner_node
from src.agent.nodes.flight_selection import flight_selection_node
from src.agent.nodes.hotel_selection import hotel_selection_node
from src.agent.nodes.itinerary_gen import itinerary_gen_node
from src.agent.nodes.review import review_node
from src.agent.nodes.finalizer import finalizer_node


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


def build_travel_graph():
    """Build and compile the LangGraph travel planning graph with checkpointing."""
    
    graph = StateGraph(AgentState)
    
    # Add nodes
    graph.add_node("initializer", initializer_node)
    graph.add_node("intent_slot", intent_slot_node)
    graph.add_node("react_planner", react_planner_node)
    graph.add_node("flight_selection", flight_selection_node)
    graph.add_node("hotel_selection", hotel_selection_node)
    graph.add_node("itinerary_gen", itinerary_gen_node)
    graph.add_node("review", review_node)
    graph.add_node("finalizer", finalizer_node)
    
    # Set entry point
    graph.set_entry_point("initializer")
    
    # Edges
    graph.add_edge("initializer", "intent_slot")
    
    # intent_slot → react_planner (complete) or → END (needs clarification)
    graph.add_conditional_edges(
        "intent_slot",
        _route_after_intent_slot,
        {
            "__end__": END,
            "planner": "react_planner"
        }
    )
    
    # react_planner → flight_selection → hotel_selection → itinerary_gen
    graph.add_edge("react_planner", "flight_selection")
    graph.add_edge("flight_selection", "hotel_selection")
    graph.add_edge("hotel_selection", "itinerary_gen")
    graph.add_edge("itinerary_gen", "review")
    
    # review → finalizer (approved) or → react_planner (revision)
    graph.add_conditional_edges(
        "review",
        _route_after_review,
        {
            "finalizer": "finalizer",
            "planner": "react_planner"
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
