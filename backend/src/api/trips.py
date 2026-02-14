"""Trip planning API endpoints – Session-based chat with human-in-the-loop.

Uses LangGraph's interrupt_before + MemorySaver for two pause points:
1. After intent_slot (when slots incomplete → graph ends, API detects & prompts user)
2. Before review node (interrupt_before → graph pauses with draft itinerary)
"""

import uuid
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Body, Query, HTTPException, status
from bson import ObjectId
from src.database import get_database
from src.agent.graph import travel_graph

router = APIRouter()


# ── List endpoints with time-range filters ──

@router.get("/user/{user_id}")
async def list_user_trips(
    user_id: str,
    from_date: Optional[str] = Query(None, description="Start of date range (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="End of date range (YYYY-MM-DD)"),
    trip_status: Optional[str] = Query(None, description="Filter by status: planning, finalized, cancelled"),
    skip: int = Query(0, ge=0, description="Number of results to skip (pagination)"),
    limit: int = Query(20, ge=1, le=100, description="Max results to return"),
):
    """List all trips for a user, with optional date-range and status filters."""
    db = get_database()
    
    query: dict = {"user_id": user_id}
    
    # Time-range filter on created_at
    if from_date or to_date:
        date_filter: dict = {}
        if from_date:
            try:
                date_filter["$gte"] = datetime.strptime(from_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail="from_date must be YYYY-MM-DD")
        if to_date:
            try:
                date_filter["$lte"] = datetime.strptime(to_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            except ValueError:
                raise HTTPException(status_code=400, detail="to_date must be YYYY-MM-DD")
        query["created_at"] = date_filter
    
    # Status filter
    if trip_status:
        query["status"] = trip_status
    
    cursor = db.trips.find(query).sort("created_at", -1).skip(skip).limit(limit)
    trips = []
    async for trip in cursor:
        trip["_id"] = str(trip["_id"])
        trips.append(trip)
    
    # Get total count for pagination metadata
    total = await db.trips.count_documents(query)
    
    return {
        "trips": trips,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/user/{user_id}/itineraries")
async def list_user_itineraries(
    user_id: str,
    from_date: Optional[str] = Query(None, description="Start of date range (YYYY-MM-DD)"),
    to_date: Optional[str] = Query(None, description="End of date range (YYYY-MM-DD)"),
    skip: int = Query(0, ge=0, description="Number of results to skip (pagination)"),
    limit: int = Query(20, ge=1, le=100, description="Max results to return"),
):
    """List all itinerary versions across all trips for a user, with optional date-range filter."""
    db = get_database()
    
    # First, get all trip_ids for this user
    trip_cursor = db.trips.find({"user_id": user_id}, {"_id": 1})
    trip_ids = []
    async for trip in trip_cursor:
        trip_ids.append(str(trip["_id"]))
    
    if not trip_ids:
        return {
            "itineraries": [],
            "total": 0,
            "skip": skip,
            "limit": limit,
        }
    
    query: dict = {"trip_id": {"$in": trip_ids}}
    
    # Time-range filter on created_at
    if from_date or to_date:
        date_filter: dict = {}
        if from_date:
            try:
                date_filter["$gte"] = datetime.strptime(from_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(status_code=400, detail="from_date must be YYYY-MM-DD")
        if to_date:
            try:
                date_filter["$lte"] = datetime.strptime(to_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            except ValueError:
                raise HTTPException(status_code=400, detail="to_date must be YYYY-MM-DD")
        query["created_at"] = date_filter
    
    cursor = db.itinerary_versions.find(query).sort("created_at", -1).skip(skip).limit(limit)
    itineraries = []
    async for itinerary in cursor:
        itinerary["_id"] = str(itinerary["_id"])
        itineraries.append(itinerary)
    
    total = await db.itinerary_versions.count_documents(query)
    
    return {
        "itineraries": itineraries,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


def _get_latest_ai_message(state: dict) -> str:
    """Extract the latest AI message from state."""
    messages = state.get("messages", [])
    for msg in reversed(messages):
        if isinstance(msg, dict) and msg.get("role") == "ai":
            return msg.get("content", "")
    return "Your trip has been planned!"


@router.post("/chat")
async def chat(
    user_id: str = Body(..., description="User ID"),
    message: str = Body(..., description="User's message"),
    thread_id: str = Body(None, description="Thread ID for continuing a session (null for new)")
):
    """
    Session-based trip planning chat endpoint.
    
    Flow:
    1. No thread_id → starts a new planning session
    2. With thread_id → examines current graph state and:
       a. If clarifying → adds user message to state, re-runs intent_slot
       b. If reviewing → updates review_status/feedback, resumes graph
       c. If complete → returns final data
    
    Response status:
    - "clarifying" → agent needs more info, show message + input
    - "planning"   → planner + itinerary gen are running
    - "reviewing"  → draft itinerary ready for user review
    - "complete"   → trip finalized, itinerary ready
    """
    
    # Generate or use provided thread_id
    if not thread_id:
        thread_id = str(uuid.uuid4())
        is_new_session = True
    else:
        is_new_session = False
    
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        if is_new_session:
            # ── New session: Initialize and invoke the graph ──
            initial_state = {
                "user_id": user_id,
                "user_preferences": {},
                "messages": [{"role": "user", "content": message}],
                "trip_request": {},
                "slots_complete": False,
                "clarification_count": 0,
                "tool_plan": [],
                "tool_results": {},
                "trip_strategy": {},
                "itinerary": {},
                "review_status": "",
                "review_feedback": "",
                "trip_id": "",
                "itinerary_version_id": "",
                "current_node": "initializer"
            }
            
            result = await travel_graph.ainvoke(initial_state, config=config)
        else:
            # ── Resume session: Check where the graph is paused ──
            state_snapshot = await travel_graph.aget_state(config)
            current_state = state_snapshot.values
            next_nodes = state_snapshot.next  # tuple of next node names
            
            if next_nodes and "review" in next_nodes:
                # Graph is paused before the REVIEW node
                # User is responding to the draft itinerary
                response_lower = message.strip().lower()
                
                if response_lower in ("approve", "yes", "looks good", "confirm", "ok", "lgtm", "perfect"):
                    # User approved — update state and resume
                    await travel_graph.aupdate_state(
                        config,
                        {
                            "review_status": "approved",
                            "review_feedback": "",
                            "messages": [{"role": "user", "content": message}]
                        }
                    )
                else:
                    # User wants revision — update state with feedback and resume
                    await travel_graph.aupdate_state(
                        config,
                        {
                            "review_status": "revision_requested",
                            "review_feedback": message,
                            "messages": [{"role": "user", "content": message}]
                        }
                    )
                
                # Resume execution from the review node
                result = await travel_graph.ainvoke(None, config=config)
            
            else:
                # Graph ended after intent_slot (clarification needed)
                # OR graph completed but user is sending a follow-up
                
                # Update the state with the new user message and re-run
                await travel_graph.aupdate_state(
                    config,
                    {
                        "messages": [{"role": "user", "content": message}],
                    },
                    as_node="initializer"  # Re-enter from initializer so it flows to intent_slot
                )
                
                # Resume graph
                result = await travel_graph.ainvoke(None, config=config)
        
        # ── Determine response based on final state ──
        state_snapshot = await travel_graph.aget_state(config)
        final_state = state_snapshot.values
        next_nodes = state_snapshot.next
        
        # Check if graph is paused before review (draft ready)
        if next_nodes and "review" in next_nodes:
            return {
                "status": "reviewing",
                "thread_id": thread_id,
                "message": (
                    f"Here's your draft itinerary for "
                    f"{final_state.get('trip_request', {}).get('destination', 'your trip')}! "
                    f"Review it below and reply 'approve' to finalize, "
                    f"or tell me what you'd like to change."
                ),
                "data": {
                    "itinerary": final_state.get("itinerary", {}),
                    "trip_request": final_state.get("trip_request", {}),
                    "trip_strategy": final_state.get("trip_strategy", {}),
                }
            }
        
        # Check if slots are still incomplete (clarification needed)
        if not final_state.get("slots_complete", False):
            return {
                "status": "clarifying",
                "thread_id": thread_id,
                "message": _get_latest_ai_message(final_state),
                "data": {
                    "slots_collected": final_state.get("trip_request", {}),
                }
            }
        
        # Check if the trip was finalized
        if final_state.get("trip_id"):
            return {
                "status": "complete",
                "thread_id": thread_id,
                "message": _get_latest_ai_message(final_state),
                "data": {
                    "trip_id": final_state.get("trip_id", ""),
                    "itinerary_version_id": final_state.get("itinerary_version_id", ""),
                    "itinerary": final_state.get("itinerary", {}),
                    "trip_request": final_state.get("trip_request", {}),
                }
            }
        
        # Fallback: graph is still running or in an unknown state
        return {
            "status": "planning",
            "thread_id": thread_id,
            "message": _get_latest_ai_message(final_state),
            "data": {
                "trip_request": final_state.get("trip_request", {}),
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Trip planning failed: {str(e)}"
        )


# ── Read-only endpoints ──

@router.get("/{trip_id}")
async def get_trip(trip_id: str):
    """Get trip details by ID."""
    db = get_database()
    
    try:
        trip = await db.trips.find_one({"_id": ObjectId(trip_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid trip ID")
    
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    trip["_id"] = str(trip["_id"])
    return trip


@router.get("/{trip_id}/itinerary")
async def get_trip_itinerary(trip_id: str):
    """Get the latest itinerary version for a trip."""
    db = get_database()
    
    version = await db.itinerary_versions.find_one(
        {"trip_id": trip_id},
        sort=[("version_number", -1)]
    )
    
    if not version:
        raise HTTPException(status_code=404, detail="No itinerary found for this trip")
    
    version["_id"] = str(version["_id"])
    return version


@router.get("/{trip_id}/conversations")
async def get_trip_conversations(trip_id: str):
    """Get conversation history for a trip."""
    db = get_database()
    
    conversation = await db.conversations.find_one({"trip_id": trip_id})
    
    if not conversation:
        raise HTTPException(status_code=404, detail="No conversation found for this trip")
    
    conversation["_id"] = str(conversation["_id"])
    return conversation
