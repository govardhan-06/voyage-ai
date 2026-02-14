"""Real hotel search using Amadeus Hotel Search API.

Results are cached in Redis for 30 minutes to reduce API calls.
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
    """Try to get a cached result from Redis."""
    try:
        redis = get_redis_client()
        if not redis:
            return None
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            future = asyncio.run_coroutine_threadsafe(redis.get(cache_key), loop)
            cached = future.result(timeout=2)
        except RuntimeError:
            cached = asyncio.run(redis.get(cache_key))
        
        if cached:
            result = json.loads(cached)
            result["_cached"] = True
            return result
    except Exception:
        pass
    return None


def _cache_set(cache_key: str, data: dict):
    """Store a result in Redis cache."""
    try:
        redis = get_redis_client()
        if not redis:
            return
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            asyncio.run_coroutine_threadsafe(
                redis.set(cache_key, json.dumps(data, default=str), ex=HOTEL_CACHE_TTL),
                loop
            )
        except RuntimeError:
            asyncio.run(redis.set(cache_key, json.dumps(data, default=str), ex=HOTEL_CACHE_TTL))
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
    Results are cached in Redis for 30 minutes.
    
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
        dict with hotel offers or error information
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
                parsed_offers.append({
                    "offer_id": offer.get("id", ""),
                    "check_in": offer.get("checkInDate", ""),
                    "check_out": offer.get("checkOutDate", ""),
                    "price_total": price.get("total", ""),
                    "price_currency": price.get("currency", "USD"),
                    "price_per_night": price.get("base", ""),
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
            })
        
        result = {
            "city_code": city_code,
            "checkin": checkin,
            "checkout": checkout,
            "guests": guests,
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
        }
    except Exception as e:
        return {
            "city_code": city_code,
            "error": f"Hotel search failed: {str(e)}",
        }
