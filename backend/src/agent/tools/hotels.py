"""Real hotel search using Amadeus Hotel Search API.

Results are cached in Redis for 30 minutes to reduce API calls.
All prices are in INR (Indian Rupees).
"""

import json
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from amadeus import Client, ResponseError
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from src.config import settings
from src.database import get_redis_client
from src.agent.utils.tracing import trace_tool_execution

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


class HotelSearchInput(BaseModel):
    """Input schema for hotel search tool."""
    city_code: str = Field(..., description="IATA city code for the destination (e.g., 'PAR', 'TYO', 'NYC')")
    checkin: Optional[str] = Field(None, description="Check-in date in YYYY-MM-DD format")
    checkout: Optional[str] = Field(None, description="Check-out date in YYYY-MM-DD format")
    guests: int = Field(1, description="Number of guests", ge=1, le=8)
    radius: int = Field(30, description="Search radius from city center", ge=1, le=300)
    radius_unit: str = Field("KM", description="Radius unit: 'KM' or 'MI'")


@tool("search_hotels", args_schema=HotelSearchInput)
@trace_tool_execution("search_hotels")
def search_hotels(
    city_code: str,
    checkin: Optional[str] = None,
    checkout: Optional[str] = None,
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
    # Amadeus v3: hotelIds = comma-separated string; checkInDate/checkOutDate required; adults string
    try:
        amadeus = _get_amadeus_client()
        
        city_code_upper = (city_code or "").upper().strip()[:3]
        if len(city_code_upper) != 3:
            return {
                "city_code": city_code,
                "error": "City code must be a 3-letter IATA code (e.g. PAR, TYO, NYC).",
                "hotels": [],
            }
        
        # Default dates if not provided; API requires future dates only
        today = datetime.now().date()
        
        def parse_date(s):
            if not s:
                return None
            try:
                return datetime.strptime(str(s).strip()[:10], "%Y-%m-%d").date()
            except (ValueError, TypeError):
                return None
        
        checkin_d = parse_date(checkin)
        if checkin_d is None or checkin_d < today:
            checkin_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            checkin_date = checkin_d.strftime("%Y-%m-%d")
        
        checkin_d = parse_date(checkin_date)
        checkout_d = parse_date(checkout)
        ci = checkin_d or (today + timedelta(days=1))
        if checkout_d is None:
            checkout_date = (ci + timedelta(days=3)).strftime("%Y-%m-%d")
        elif checkout_d < today or checkout_d <= ci:
            checkout_date = (ci + timedelta(days=3)).strftime("%Y-%m-%d")
        else:
            checkout_date = checkout_d.strftime("%Y-%m-%d")
        
        # ── Step 1: Get hotel IDs by city ──
        hotel_list_response = amadeus.reference_data.locations.hotels.by_city.get(
            cityCode=city_code_upper,
            radius=radius,
            radiusUnit=radius_unit,
        )
        
        if not hotel_list_response.data:
            return {
                "city_code": city_code_upper,
                "hotels": [],
                "total_results": 0,
                "message": "No hotels found for this city code.",
            }
        
        # Take top 5 hotel IDs; API expects comma-separated string
        hotel_id_list = [h.get("hotelId") or h.get("hotel_id") for h in hotel_list_response.data[:5]]
        hotel_id_list = [h for h in hotel_id_list if h]
        if not hotel_id_list:
            return {
                "city_code": city_code_upper,
                "hotels": [],
                "total_results": 0,
                "message": "No valid hotel IDs returned.",
            }
        hotel_ids_str = ",".join(str(h) for h in hotel_id_list)
        
        # ── Step 2: Get offers (v3 requires hotelIds, adults, checkInDate; checkOutDate often required) ──
        params = {
            "hotelIds": hotel_ids_str,
            "adults": str(min(8, max(1, int(guests)))),
            "checkInDate": checkin_date,
            "checkOutDate": checkout_date,
        }
        
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
                    "check_in": offer.get("checkInDate", checkin_date),
                    "check_out": offer.get("checkOutDate", checkout_date),
                    "price_total": price.get("total", ""),
                    "price_inr": price_total,
                    "price_currency": "INR",
                    "price_per_night": price.get("base", ""),
                    "price_per_night_inr": price_base,
                    "room_type": room.get("typeEstimated", {}).get("category", ""),
                    "bed_type": room.get("typeEstimated", {}).get("bedType", ""),
                    "description": room.get("description", {}).get("text", ""),
                })
            
            hotels.append({
                "hotel_id": hotel_info.get("hotelId", ""),
                "name": hotel_info.get("name", ""),
                "city_code": hotel_info.get("cityCode", city_code_upper),
                "latitude": hotel_info.get("latitude"),
                "longitude": hotel_info.get("longitude"),
                "offers": parsed_offers,
                # Convenience fields: use best (first) offer
                "best_price_inr": parsed_offers[0]["price_inr"] if parsed_offers else 0,
                "best_price_per_night_inr": parsed_offers[0]["price_per_night_inr"] if parsed_offers else 0,
                "room_type": parsed_offers[0]["room_type"] if parsed_offers else "",
                "bed_type": parsed_offers[0]["bed_type"] if parsed_offers else "",
                "check_in": checkin_date,
                "check_out": checkout_date,
            })
        
        result = {
            "city_code": city_code_upper,
            "checkin": checkin_date,
            "checkout": checkout_date,
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
