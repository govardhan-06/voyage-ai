"""Trip planning API – Session-based chat with HITL only for itinerary review.

Interrupt before review: user approves or requests changes. Flight/hotel are auto-selected.
"""

import uuid
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Body, Query, HTTPException, status
from fastapi.responses import JSONResponse
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
    Session-based trip planning chat. HITL only at review (approve/revise itinerary).
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
                "available_flights": [],
                "available_hotels": [],
                "selected_flight": {},
                "selected_hotel": {},
                "selection_step": "",
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
                response_lower = message.strip().lower()
                
                if response_lower in ("approve", "yes", "looks good", "confirm", "ok", "lgtm", "perfect", "approved"):
                    await travel_graph.aupdate_state(
                        config,
                        {
                            "review_status": "approved",
                            "review_feedback": "",
                            "messages": [{"role": "user", "content": message}]
                        }
                    )
                else:
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
                # OR graph completed but user is sending a follow-up.
                # Re-enter directly at intent_slot — NOT initializer — to
                # avoid the initializer wiping already-collected slot data.
                await travel_graph.aupdate_state(
                    config,
                    {
                        "messages": [{"role": "user", "content": message}],
                    },
                    as_node="intent_slot"
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
                    "selected_flight": final_state.get("selected_flight", {}),
                    "selected_hotel": final_state.get("selected_hotel", {}),
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
                    "selected_flight": final_state.get("selected_flight", {}),
                    "selected_hotel": final_state.get("selected_hotel", {}),
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


# ── Export Endpoint ──

@router.get("/{trip_id}/export")
async def export_itinerary(
    trip_id: str,
    format: str = Query("json", description="Export format: 'json' or 'text'")
):
    """
    Export a finalized itinerary.
    
    Returns a structured export of the trip including:
    - Trip metadata (destination, dates, travelers)
    - Selected flight details
    - Selected hotel details
    - Day-by-day itinerary with activities
    - Cost breakdown in INR
    
    Query params:
    - format=json (default): Returns structured JSON
    - format=text: Returns a human-readable plain text version
    """
    db = get_database()
    
    # Fetch trip
    try:
        trip = await db.trips.find_one({"_id": ObjectId(trip_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid trip ID")
    
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    # Fetch latest itinerary version
    version = await db.itinerary_versions.find_one(
        {"trip_id": trip_id},
        sort=[("version_number", -1)]
    )
    
    if not version:
        raise HTTPException(status_code=404, detail="No itinerary found for this trip")
    
    itinerary = version.get("itinerary", {})
    constraints = trip.get("trip_constraints", {})
    selected_flight = trip.get("selected_flight") or itinerary.get("selected_flight") or {}
    selected_hotel = trip.get("selected_hotel") or itinerary.get("selected_hotel") or {}
    
    # ── Build cost breakdown ──
    days = itinerary.get("days", [])
    day_costs = []
    total_activity_cost = 0
    for day in days:
        day_cost = sum(act.get("cost_estimate", 0) for act in day.get("activities", []))
        day_costs.append({"day": day.get("day_number"), "date": day.get("date"), "cost_inr": day_cost})
        total_activity_cost += day_cost
    
    flight_cost = selected_flight.get("price_inr", 0) if not selected_flight.get("assumption") else 0
    hotel_cost = selected_hotel.get("price_inr", 0) or selected_hotel.get("best_price_inr", 0) if not selected_hotel.get("assumption") else 0
    grand_total = itinerary.get("total_cost_estimate", total_activity_cost + flight_cost + hotel_cost)
    
    if format == "text":
        # ── Plain text export ──
        lines = [
            "=" * 60,
            f"  VOYAGE AI – TRIP ITINERARY",
            "=" * 60,
            f"  Trip: {trip.get('title', 'Your Trip')}",
            f"  Destination: {constraints.get('destination', 'N/A')}",
            f"  From: {constraints.get('origin', 'N/A')}",
            f"  Dates: {constraints.get('start_date', 'N/A')} to {constraints.get('end_date', 'N/A')}",
            f"  Duration: {constraints.get('duration_days', 'N/A')} days",
            f"  Travelers: {constraints.get('traveler_count', 1)} ({constraints.get('travel_group', 'solo')})",
            f"  Currency: INR (₹)",
            "",
        ]
        
        # Flight section
        if selected_flight and not selected_flight.get("assumption"):
            lines += [
                "✈️  FLIGHT DETAILS",
                "-" * 40,
                f"  Airline: {selected_flight.get('airline', 'N/A')} {selected_flight.get('flight_number', '')}",
                f"  Class: {selected_flight.get('booking_class', 'ECONOMY')}",
                f"  Departure: {selected_flight.get('departure_time', 'N/A')}",
                f"  Arrival: {selected_flight.get('arrival_time', 'N/A')}",
                f"  Duration: {selected_flight.get('duration', 'N/A')}",
                f"  Stops: {selected_flight.get('stops', 0)}",
                f"  Price: ₹{flight_cost:,.0f}",
                "",
            ]
        else:
            lines += [
                "✈️  FLIGHT DETAILS",
                "-" * 40,
                "  ⚠️  Economy class assumed – please book via your preferred airline.",
                "",
            ]
        
        # Hotel section
        if selected_hotel and not selected_hotel.get("assumption"):
            lines += [
                "🏨  HOTEL DETAILS",
                "-" * 40,
                f"  Name: {selected_hotel.get('name', 'N/A')}",
                f"  Room: {selected_hotel.get('room_type', 'Standard')} | {selected_hotel.get('bed_type', '')}",
                f"  Check-in: {selected_hotel.get('check_in', 'N/A')}",
                f"  Check-out: {selected_hotel.get('check_out', 'N/A')}",
                f"  Total Price: ₹{hotel_cost:,.0f}",
                "",
            ]
        else:
            lines += [
                "🏨  HOTEL DETAILS",
                "-" * 40,
                "  ⚠️  3-star hotel assumed – please book via MakeMyTrip, Booking.com, etc.",
                "",
            ]
        
        # Day-by-day itinerary
        lines += [
            "📅  DAY-BY-DAY ITINERARY",
            "=" * 60,
        ]
        
        for day in days:
            lines += [
                f"\n  Day {day.get('day_number')} – {day.get('date', '')}  |  Theme: {day.get('theme', '')}",
                "-" * 40,
            ]
            for act in day.get("activities", []):
                cost_str = f"  [₹{act.get('cost_estimate', 0):,.0f}]" if act.get("cost_estimate", 0) > 0 else ""
                loc = act.get("location", {})
                loc_name = loc.get("name", "") if isinstance(loc, dict) else act.get("location_name", "")
                lines.append(f"  {act.get('time', '')}  {act.get('title', '')}{cost_str}")
                if loc_name:
                    lines.append(f"           📍 {loc_name}")
                if act.get("description"):
                    lines.append(f"           {act.get('description')}")
        
        # Cost summary
        lines += [
            "",
            "💰  COST SUMMARY (INR)",
            "=" * 60,
        ]
        for dc in day_costs:
            lines.append(f"  Day {dc['day']} ({dc['date']}): ₹{dc['cost_inr']:,.0f}")
        
        if flight_cost > 0:
            lines.append(f"  Flights: ₹{flight_cost:,.0f}")
        if hotel_cost > 0:
            lines.append(f"  Hotel: ₹{hotel_cost:,.0f}")
        lines += [
            "-" * 40,
            f"  TOTAL ESTIMATE: ₹{grand_total:,.0f}",
            "",
        ]
        
        # Assumptions
        assumptions = itinerary.get("assumptions", [])
        if assumptions:
            lines += ["⚠️  ASSUMPTIONS MADE", "-" * 40]
            for a in assumptions:
                lines.append(f"  • {a}")
            lines.append("")
        
        lines += [
            "=" * 60,
            "  Generated by Voyage AI – Your AI Travel Companion",
            "=" * 60,
        ]
        
        text_content = "\n".join(lines)
        return JSONResponse(
            content={"text": text_content},
            headers={"Content-Disposition": f'attachment; filename="itinerary_{trip_id}.txt"'},
        )
    
    # ── JSON export (default) ──
    export_data = {
        "export_info": {
            "generated_at": datetime.utcnow().isoformat(),
            "trip_id": trip_id,
            "version": version.get("version_number", 1),
            "currency": "INR",
        },
        "trip": {
            "title": trip.get("title", ""),
            "destination": constraints.get("destination", ""),
            "origin": constraints.get("origin", ""),
            "start_date": constraints.get("start_date", ""),
            "end_date": constraints.get("end_date", ""),
            "duration_days": constraints.get("duration_days", 0),
            "travel_group": constraints.get("travel_group", ""),
            "traveler_count": constraints.get("traveler_count", 1),
            "budget_inr": constraints.get("budget", 0),
        },
        "selected_flight": selected_flight,
        "selected_hotel": selected_hotel,
        "itinerary": {
            "title": itinerary.get("title", ""),
            "summary": itinerary.get("summary", ""),
            "currency": "INR",
            "assumptions": itinerary.get("assumptions", []),
            "days": days,
        },
        "cost_summary": {
            "currency": "INR",
            "flight_cost_inr": flight_cost,
            "hotel_cost_inr": hotel_cost,
            "activity_cost_inr": total_activity_cost,
            "total_estimate_inr": grand_total,
            "daily_breakdown": day_costs,
        },
    }
    
    return JSONResponse(
        content=export_data,
        headers={"Content-Disposition": f'attachment; filename="itinerary_{trip_id}.json"'},
    )
