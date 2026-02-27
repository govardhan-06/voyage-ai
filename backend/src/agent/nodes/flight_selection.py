"""Node 2.5: Flight Selection – Human-in-the-Loop.

Presents available flights from tool_results to the user.
The graph pauses (interrupt_before) so the user can pick a flight.
When resumed, validates the selection and stores it in state.

If no flights are available (API error or no results),
this node auto-selects a fallback assumption and continues.
"""

from src.agent.state import AgentState


# Standard assumptions shown to users
FLIGHT_ASSUMPTION = {
    "airline": "Best available airline",
    "flight_number": "TBD",
    "booking_class": "ECONOMY",
    "price_inr": 0,
    "assumption": True,
    "note": "Flight details assumed (economy class). Book separately via preferred airline.",
}


def _extract_flights_for_display(tool_results: dict) -> list:
    """Extract and format flight options from tool_results."""
    flight_data = tool_results.get("search_flights", {})
    
    # Handle case where tool was called multiple times (stored as list)
    if isinstance(flight_data, list):
        flight_data = flight_data[-1]  # use most recent result
    
    flights = flight_data.get("flights", []) if isinstance(flight_data, dict) else []
    
    # Format for display
    display_flights = []
    for i, f in enumerate(flights[:5], 1):
        itins = f.get("itineraries", [])
        first_itin = itins[0] if itins else {}
        segments = first_itin.get("segments", [])
        first_seg = segments[0] if segments else {}
        last_seg = segments[-1] if segments else {}
        
        display_flights.append({
            "index": i,
            "flight_id": f.get("id", ""),
            "airline": f.get("airline", first_seg.get("carrier", "Unknown Airline")),
            "flight_number": f.get("flight_number", first_seg.get("flight_number", "N/A")),
            "departure_time": f.get("departure_time", first_seg.get("departure_time", "")),
            "arrival_time": f.get("arrival_time", last_seg.get("arrival_time", "")),
            "duration": f.get("duration", first_itin.get("duration", "")),
            "stops": f.get("stops", first_itin.get("stops", 0)),
            "price_inr": f.get("price_inr", 0),
            "booking_class": f.get("booking_class", "ECONOMY"),
            "seats_remaining": f.get("seats_remaining", "N/A"),
        })
    
    return display_flights


def _format_flight_message(flights: list, trip_request: dict) -> str:
    """Format the flight selection message for the user."""
    origin = trip_request.get("origin", "your city")
    destination = trip_request.get("destination", "your destination")
    departure_date = trip_request.get("start_date", "")
    
    lines = [
        f"✈️ **Great! I found {len(flights)} flight options** from {origin} to {destination}",
        f"{'on ' + departure_date if departure_date else ''}.",
        "",
        "Please choose your preferred flight by replying with the number (1, 2, 3...):",
        "",
    ]
    
    for f in flights:
        stops_text = "Non-stop" if f["stops"] == 0 else f"{f['stops']} stop(s)"
        price_text = f"₹{f['price_inr']:,.0f}" if f["price_inr"] > 0 else "Price on request"
        dep_time = f["departure_time"][:16].replace("T", " ") if f["departure_time"] else "TBD"
        arr_time = f["arrival_time"][:16].replace("T", " ") if f["arrival_time"] else "TBD"
        
        lines.append(
            f"**{f['index']}.** {f['airline']} {f['flight_number']} | {f['booking_class']} | "
            f"{stops_text} | {price_text}\n"
            f"   🕐 Departs: {dep_time} → Arrives: {arr_time} | Duration: {f['duration']}"
        )
        lines.append("")
    
    lines.append("💡 *Assumption: Economy class selected by default. Mention 'business class' if you'd prefer an upgrade.*")
    
    return "\n".join(lines)


async def flight_selection_node(state: dict) -> dict:
    """
    Present flight options to the user and wait for selection.
    
    First run: format and return flight options. Graph pauses (interrupt_before).
    After resume: the API has already set selected_flight in state via aupdate_state.
    This node just acknowledges and routes forward.
    """
    selected_flight = state.get("selected_flight", {})
    
    # If a flight is already selected (resumed after pause), just route forward
    if selected_flight:
        airline = selected_flight.get("airline", "your flight")
        price = selected_flight.get("price_inr", 0)
        price_text = f" (₹{price:,.0f})" if price > 0 else ""
        return {
            "selection_step": "awaiting_hotel",
            "current_node": "hotel_selection",
            "messages": [{
                "role": "ai",
                "content": f"✅ Flight selected: {airline}{price_text}. Now let's pick your hotel!"
            }]
        }
    
    # ── First run: extract and present available flights ──
    tool_results = state.get("tool_results", {})
    trip_request = state.get("trip_request", {})
    
    available_flights = _extract_flights_for_display(tool_results)
    
    # If no flights found, use assumption and skip selection
    if not available_flights:
        return {
            "available_flights": [],
            "selected_flight": FLIGHT_ASSUMPTION,
            "selection_step": "awaiting_hotel",
            "current_node": "hotel_selection",
            "messages": [{
                "role": "ai",
                "content": (
                    "✈️ Flight search didn't return real-time results right now. "
                    "I'll assume economy class flights for cost estimation. "
                    "You can book directly via your preferred airline or travel portal. "
                    "Now let's pick your hotel!"
                )
            }]
        }
    
    # Present options — graph will pause here via interrupt_before
    message = _format_flight_message(available_flights, trip_request)
    
    return {
        "available_flights": available_flights,
        "selection_step": "awaiting_flight",
        "current_node": "flight_selection",
        "messages": [{"role": "ai", "content": message}]
    }
