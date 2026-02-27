"""Node 2.6: Hotel Selection – Human-in-the-Loop.

Presents available hotels from tool_results to the user.
The graph pauses (interrupt_before) so the user can pick a hotel.
When resumed, validates the selection and stores it in state.

If no hotels are available (API error or no results),
this node auto-selects a fallback assumption and continues.
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


def _format_hotel_message(hotels: list, trip_request: dict) -> str:
    """Format the hotel selection message for the user."""
    destination = trip_request.get("destination", "your destination")
    checkin = trip_request.get("start_date", "")
    checkout = trip_request.get("end_date", "")
    
    date_range = ""
    if checkin and checkout:
        date_range = f" ({checkin} to {checkout})"
    
    lines = [
        f"🏨 **Here are hotel options in {destination}**{date_range}:",
        "",
        "Please choose your preferred hotel by replying with the number (1, 2, 3...):",
        "",
    ]
    
    for h in hotels:
        price_text = f"₹{h['price_inr']:,.0f} total" if h["price_inr"] > 0 else "Price on request"
        per_night_text = f" (₹{h['price_per_night_inr']:,.0f}/night)" if h["price_per_night_inr"] > 0 else ""
        room_text = h["room_type"] if h["room_type"] else "Standard Room"
        bed_text = f" | {h['bed_type']}" if h["bed_type"] else ""
        
        lines.append(
            f"**{h['index']}.** {h['name']}\n"
            f"   🛏️ {room_text}{bed_text} | 💰 {price_text}{per_night_text}"
        )
        lines.append("")
    
    lines.append("💡 *Assumption: 3-star or equivalent hotel recommended. Mention 'luxury' or 'budget' if you have a preference.*")
    
    return "\n".join(lines)


async def hotel_selection_node(state: dict) -> dict:
    """
    Present hotel options to the user and wait for selection.
    
    First run: format and return hotel options. Graph pauses (interrupt_before).
    After resume: the API has already set selected_hotel in state via aupdate_state.
    This node just acknowledges and routes forward.
    """
    selected_hotel = state.get("selected_hotel", {})
    
    # If a hotel is already selected (resumed after pause), route forward
    if selected_hotel:
        hotel_name = selected_hotel.get("name", "your hotel")
        price = selected_hotel.get("price_inr", 0)
        price_text = f" (₹{price:,.0f} total)" if price > 0 else ""
        return {
            "selection_step": "",
            "current_node": "itinerary_gen",
            "messages": [{
                "role": "ai",
                "content": (
                    f"✅ Hotel selected: {hotel_name}{price_text}. "
                    "Now I'll generate your personalized day-by-day itinerary including your flight and hotel! 🗺️"
                )
            }]
        }
    
    # ── First run: extract and present available hotels ──
    tool_results = state.get("tool_results", {})
    trip_request = state.get("trip_request", {})
    
    available_hotels = _extract_hotels_for_display(tool_results)
    
    # If no hotels found, use assumption and skip selection
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
    
    # Present options — graph will pause here via interrupt_before
    message = _format_hotel_message(available_hotels, trip_request)
    
    return {
        "available_hotels": available_hotels,
        "selection_step": "awaiting_hotel",
        "current_node": "hotel_selection",
        "messages": [{"role": "ai", "content": message}]
    }
