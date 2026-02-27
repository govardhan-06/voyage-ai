"""Real hotel search using Amadeus Hotel Search API.

Results are cached in Redis for 30 minutes to reduce API calls.
All prices are in INR (Indian Rupees).
"""

import json
import hashlib
from amadeus import Client, ResponseError
from src.config import settings
from src.database import get_redis_client

HOTEL_CACHE_TTL = 1800  # 30 minutes


def _get_amadeus_client() -> Client:
    """Get an authenticated Amadeus client."""
    return Client(
        client_id=settings.AMADEUS_API_KEY,
        client_secret=settings.AMADEUS_API_SECRET,
    )


def _build_cache_key(city_code, checkin, checkout, guests, radius, radius_unit) -> str:
    """Build a deterministic cache key."""
    raw = json.dumps({
        "fn": "search_hotels",
        "c": city_code, "ci": checkin, "co": checkout,
        "g": guests, "r": radius, "ru": radius_unit
    }, sort_keys=True)
    h = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"cache:hotels:{h}"


def _cache_get(cache_key: str):
    """Try to get a cached result from Redis (sync-safe)."""
    try:
        redis = get_redis_client()
        if not redis:
            return None
        import asyncio

        async def _get():
            raw = await redis.get(cache_key)
            if raw:
                result = json.loads(raw)
                result["_cached"] = True
                return result
            return None

        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            future = asyncio.run_coroutine_threadsafe(_get(), loop)
            return future.result(timeout=2)
        except RuntimeError:
            return asyncio.run(_get())
    except Exception:
        return None


def _cache_set(cache_key: str, data: dict):
    """Store a result in Redis cache (sync-safe)."""
    try:
        redis = get_redis_client()
        if not redis:
            return
        import asyncio

        async def _set():
            await redis.set(cache_key, json.dumps(data, default=str), ex=HOTEL_CACHE_TTL)

        try:
            loop = asyncio.get_running_loop()
            asyncio.run_coroutine_threadsafe(_set(), loop)
        except RuntimeError:
            asyncio.run(_set())
        except Exception:
            pass
    except Exception:
        pass


def search_hotels(
    city_code: str,
    checkin: str = None,
    checkout: str = None,
    guests: int = 1,
    radius: int = 30,
    radius_unit: str = "KM",
) -> dict:
    """
    Search for hotels using the Amadeus Hotel List + Hotel Offers APIs.
    Results are cached in Redis for 30 minutes. Prices in INR.
    
    Two-step process:
      1. Hotel List API – find hotels by city code
      2. Hotel Offers API – get prices for those hotels
    
    Args:
        city_code: IATA city code (e.g., "PAR", "TYO", "NYC")
        checkin: Check-in date in YYYY-MM-DD format
        checkout: Check-out date in YYYY-MM-DD format
        guests: Number of guests
        radius: Search radius from city center
        radius_unit: "KM" or "MI"
    
    Returns:
        dict with hotel offers (prices in INR) or error information
    """
    # ── Check cache ──
    cache_key = _build_cache_key(city_code, checkin, checkout, guests, radius, radius_unit)
    cached = _cache_get(cache_key)
    if cached:
        return cached
    
    # ── API call ──
    try:
        amadeus = _get_amadeus_client()
        
        # ── Step 1: Get hotel IDs by city ──
        hotel_list_response = amadeus.reference_data.locations.hotels.by_city.get(
            cityCode=city_code,
            radius=radius,
            radiusUnit=radius_unit,
        )
        
        if not hotel_list_response.data:
            return {
                "city_code": city_code,
                "hotels": [],
                "total_results": 0,
                "message": "No hotels found for this city code.",
            }
        
        # Take top 5 hotel IDs
        hotel_ids = [h["hotelId"] for h in hotel_list_response.data[:5]]
        
        # ── Step 2: Get offers for those hotels ──
        params = {
            "hotelIds": hotel_ids,
            "adults": guests,
            "currency": "INR",
        }
        if checkin:
            params["checkInDate"] = checkin
        if checkout:
            params["checkOutDate"] = checkout
        
        offers_response = amadeus.shopping.hotel_offers_search.get(**params)
        
        # Parse the response
        hotels = []
        for hotel_offer in offers_response.data:
            hotel_info = hotel_offer.get("hotel", {})
            offers = hotel_offer.get("offers", [])
            
            parsed_offers = []
            for offer in offers[:3]:  # max 3 offers per hotel
                price = offer.get("price", {})
                room = offer.get("room", {})
                
                try:
                    price_total = float(price.get("total", 0))
                except (ValueError, TypeError):
                    price_total = 0
                
                try:
                    price_base = float(price.get("base", 0))
                except (ValueError, TypeError):
                    price_base = 0
                
                parsed_offers.append({
                    "offer_id": offer.get("id", ""),
                    "check_in": offer.get("checkInDate", checkin or ""),
                    "check_out": offer.get("checkOutDate", checkout or ""),
                    "price_total": price.get("total", ""),
                    "price_inr": price_total,
                    "price_currency": price.get("currency", "INR"),
                    "price_per_night": price.get("base", ""),
                    "price_per_night_inr": price_base,
                    "room_type": room.get("typeEstimated", {}).get("category", ""),
                    "bed_type": room.get("typeEstimated", {}).get("bedType", ""),
                    "description": room.get("description", {}).get("text", ""),
                })
            
            hotels.append({
                "hotel_id": hotel_info.get("hotelId", ""),
                "name": hotel_info.get("name", ""),
                "city_code": hotel_info.get("cityCode", city_code),
                "latitude": hotel_info.get("latitude"),
                "longitude": hotel_info.get("longitude"),
                "offers": parsed_offers,
                # Convenience fields: use best (first) offer
                "best_price_inr": parsed_offers[0]["price_inr"] if parsed_offers else 0,
                "best_price_per_night_inr": parsed_offers[0]["price_per_night_inr"] if parsed_offers else 0,
                "room_type": parsed_offers[0]["room_type"] if parsed_offers else "",
                "bed_type": parsed_offers[0]["bed_type"] if parsed_offers else "",
                "check_in": checkin or "",
                "check_out": checkout or "",
            })
        
        result = {
            "city_code": city_code,
            "checkin": checkin,
            "checkout": checkout,
            "guests": guests,
            "currency": "INR",
            "hotels": hotels,
            "total_results": len(hotels),
        }
        
        # ── Store in cache ──
        _cache_set(cache_key, result)
        
        return result
    
    except ResponseError as e:
        return {
            "city_code": city_code,
            "error": f"Amadeus API error: {str(e)}",
            "status_code": getattr(e.response, "status_code", None),
            "hotels": [],
        }
    except Exception as e:
        return {
            "city_code": city_code,
            "error": f"Hotel search failed: {str(e)}",
            "hotels": [],
        }
