"""Node 2.6: Hotel Selection – Auto-select first option.

Extracts available hotels from tool_results and auto-selects the first one.
If no hotels are available (API error or no results),
this node uses a fallback assumption and continues.
"""

from src.agent.state import AgentState


# Standard assumptions shown to users
HOTEL_ASSUMPTION = {
    "name": "Best available hotel (3-star equivalent)",
    "room_type": "Standard Room",
    "bed_type": "Double",
    "price_per_night_inr": 0,
    "best_price_inr": 0,
    "assumption": True,
    "note": "Hotel details assumed (3-star, standard room). Book separately via preferred portal.",
}


def _extract_hotels_for_display(tool_results: dict) -> list:
    """Extract and format hotel options from tool_results."""
    hotel_data = tool_results.get("search_hotels", {})
    
    # Handle case where tool was called multiple times (stored as list)
    if isinstance(hotel_data, list):
        hotel_data = hotel_data[-1]  # use most recent result
    
    hotels = hotel_data.get("hotels", []) if isinstance(hotel_data, dict) else []
    
    # Format for display
    display_hotels = []
    for i, h in enumerate(hotels[:5], 1):
        best_price = h.get("best_price_inr", 0) or h.get("best_price_per_night_inr", 0) * max(1, 1)
        per_night = h.get("best_price_per_night_inr", 0)
        
        display_hotels.append({
            "index": i,
            "hotel_id": h.get("hotel_id", ""),
            "name": h.get("name", f"Hotel {i}"),
            "city": h.get("city_code", ""),
            "price_inr": best_price,
            "price_per_night_inr": per_night,
            "room_type": h.get("room_type", "Standard Room"),
            "bed_type": h.get("bed_type", ""),
            "check_in": h.get("check_in", ""),
            "check_out": h.get("check_out", ""),
            "latitude": h.get("latitude"),
            "longitude": h.get("longitude"),
        })
    
    return display_hotels


async def hotel_selection_node(state: dict) -> dict:
    """
    Extract available hotels and auto-select the first option.
    No human-in-the-loop; graph continues to itinerary_gen.
    """
    tool_results = state.get("tool_results", {})
    available_hotels = _extract_hotels_for_display(tool_results)
    
    # If no hotels found, use assumption and continue
    if not available_hotels:
        return {
            "available_hotels": [],
            "selected_hotel": HOTEL_ASSUMPTION,
            "selection_step": "",
            "current_node": "itinerary_gen",
            "messages": [{
                "role": "ai",
                "content": (
                    "🏨 Hotel search didn't return real-time results right now. "
                    "I'll assume a 3-star standard room for cost estimation. "
                    "You can book directly via Booking.com, MakeMyTrip, or your preferred portal. "
                    "Now I'll generate your personalized itinerary! 🗺️"
                )
            }]
        }
    
    # Auto-select the first hotel and continue to itinerary generation
    chosen = available_hotels[0]
    hotel_name = chosen.get("name", "your hotel")
    price = chosen.get("price_inr", 0)
    price_text = f" (₹{price:,.0f} total)" if price > 0 else ""
    
    return {
        "available_hotels": available_hotels,
        "selected_hotel": chosen,
        "selection_step": "",
        "current_node": "itinerary_gen",
        "messages": [{
            "role": "ai",
            "content": (
                f"✅ I've selected {hotel_name}{price_text} for you. "
                "Now I'll generate your personalized day-by-day itinerary including your flight and hotel! 🗺️"
            )
        }]
    }
