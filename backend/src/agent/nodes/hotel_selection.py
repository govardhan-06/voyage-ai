"""Node 2.6: Hotel Selection – auto-select first option (no HITL).

Picks the first available hotel from tool_results, or uses an assumption if none.
Flow continues straight to itinerary_gen.
"""

HOTEL_ASSUMPTION = {
    "name": "Best available hotel (3-star equivalent)",
    "room_type": "Standard Room",
    "bed_type": "Double",
    "price_per_night_inr": 0,
    "best_price_inr": 0,
    "price_inr": 0,
    "assumption": True,
    "note": "Hotel details assumed (3-star, standard room). Book separately via preferred portal.",
}


def _extract_hotels_for_display(tool_results: dict) -> list:
    """Extract and format hotel options from tool_results."""
    hotel_data = tool_results.get("search_hotels", {})
    if isinstance(hotel_data, list):
        hotel_data = hotel_data[-1] if hotel_data else {}
    hotels = hotel_data.get("hotels", []) if isinstance(hotel_data, dict) else []
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
            "best_price_inr": best_price,
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
    """Auto-select first hotel (or assumption) and continue to itinerary generation."""
    tool_results = state.get("tool_results", {})
    available_hotels = _extract_hotels_for_display(tool_results)

    if not available_hotels:
        return {
            "available_hotels": [],
            "selected_hotel": HOTEL_ASSUMPTION,
            "selection_step": "",
            "current_node": "itinerary_gen",
            "messages": [{
                "role": "ai",
                "content": (
                    "🏨 Hotel search didn't return results right now. "
                    "I'll assume a 3-star standard room for cost estimation. "
                    "Generating your day-by-day itinerary…"
                )
            }]
        }

    # Auto-select first hotel
    chosen = available_hotels[0]
    price_text = f" (₹{chosen.get('price_inr', 0):,.0f} total)" if chosen.get("price_inr", 0) > 0 else ""
    return {
        "available_hotels": available_hotels,
        "selected_hotel": chosen,
        "selection_step": "",
        "current_node": "itinerary_gen",
        "messages": [{
            "role": "ai",
            "content": f"✅ Selected hotel: {chosen.get('name', '')}{price_text}. Generating your itinerary…"
        }]
    }
