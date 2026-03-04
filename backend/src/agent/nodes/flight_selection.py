"""Node 2.5: Flight Selection – auto-select first option (no HITL).

Picks the first available flight from tool_results, or uses an assumption if none.
Flow continues straight to hotel_selection.
"""

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
    if isinstance(flight_data, list):
        flight_data = flight_data[-1] if flight_data else {}
    flights = flight_data.get("flights", []) if isinstance(flight_data, dict) else []
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


async def flight_selection_node(state: dict) -> dict:
    """Auto-select first flight (or assumption) and continue to hotel selection."""
    tool_results = state.get("tool_results", {})
    trip_request = state.get("trip_request", {})
    available_flights = _extract_flights_for_display(tool_results)

    if not available_flights:
        return {
            "available_flights": [],
            "selected_flight": FLIGHT_ASSUMPTION,
            "selection_step": "awaiting_hotel",
            "current_node": "hotel_selection",
            "messages": [{
                "role": "ai",
                "content": (
                    "✈️ Flight search didn't return results right now. "
                    "I'll assume economy class for cost estimation. "
                    "Selecting your hotel next…"
                )
            }]
        }

    # Auto-select first flight
    chosen = available_flights[0]
    origin = trip_request.get("origin", "your city")
    destination = trip_request.get("destination", "your destination")
    price_text = f" (₹{chosen['price_inr']:,.0f})" if chosen.get("price_inr", 0) > 0 else ""
    return {
        "available_flights": available_flights,
        "selected_flight": chosen,
        "selection_step": "awaiting_hotel",
        "current_node": "hotel_selection",
        "messages": [{
            "role": "ai",
            "content": f"✅ Selected flight: {chosen.get('airline', '')} {chosen.get('flight_number', '')}{price_text}. Selecting your hotel…"
        }]
    }
