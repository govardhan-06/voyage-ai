"""Node 2.5: Flight Selection – Auto-select first option.

Extracts available flights from tool_results and auto-selects the first one.
If no flights are available (API error or no results),
this node uses a fallback assumption and continues.
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


async def flight_selection_node(state: dict) -> dict:
    """
    Extract available flights and auto-select the first option.
    No human-in-the-loop; graph continues to hotel_selection.
    """
    tool_results = state.get("tool_results", {})
    available_flights = _extract_flights_for_display(tool_results)
    
    # If no flights found, use assumption and continue
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
    
    # Auto-select the first flight and continue to hotel selection
    chosen = available_flights[0]
    airline = chosen.get("airline", "your flight")
    price = chosen.get("price_inr", 0)
    price_text = f" (₹{price:,.0f})" if price > 0 else ""
    
    return {
        "available_flights": available_flights,
        "selected_flight": chosen,
        "selection_step": "awaiting_hotel",
        "current_node": "hotel_selection",
        "messages": [{
            "role": "ai",
            "content": f"✅ I've selected {airline}{price_text} for you. Now let's pick your hotel!"
        }]
    }
