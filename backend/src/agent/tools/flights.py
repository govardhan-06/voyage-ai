"""Real flight search using Amadeus Flight Offers Search API.

Results are cached in Redis for 15 minutes to reduce API calls.
All prices are returned in INR (Indian Rupees).
"""

import json
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from amadeus import Client, ResponseError

# Approximate USD/EUR to INR for display when API returns non-INR
CURRENCY_TO_INR = {"USD": 91.0, "EUR": 100.0, "INR": 1.0}
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from src.config import settings
from src.database import get_redis_client
from src.agent.utils.tracing import trace_tool_execution

FLIGHT_CACHE_TTL = 900  # 15 minutes


def _get_amadeus_client() -> Client:
    """Get an authenticated Amadeus client."""
    return Client(
        client_id=settings.AMADEUS_API_KEY,
        client_secret=settings.AMADEUS_API_SECRET,
    )


def _build_cache_key(origin, destination, departure_date, return_date, travelers) -> str:
    """Build a deterministic cache key."""
    raw = json.dumps({
        "fn": "search_flights",
        "o": origin, "d": destination,
        "dd": departure_date, "rd": return_date,
        "t": travelers
    }, sort_keys=True)
    h = hashlib.sha256(raw.encode()).hexdigest()[:16]
    return f"cache:flights:{h}"


def _cache_get(cache_key: str):
    """Try to get a cached result from Redis (sync-safe)."""
    try:
        redis = get_redis_client()
        if not redis:
            return None
        import asyncio
        import concurrent.futures

        async def _get():
            raw = await redis.get(cache_key)
            if raw:
                result = json.loads(raw)
                result["_cached"] = True
                return result
            return None

        try:
            loop = asyncio.get_running_loop()
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
            await redis.set(cache_key, json.dumps(data, default=str), ex=FLIGHT_CACHE_TTL)

        try:
            loop = asyncio.get_running_loop()
            asyncio.run_coroutine_threadsafe(_set(), loop)
        except RuntimeError:
            asyncio.run(_set())
        except Exception:
            pass
    except Exception:
        pass


class FlightSearchInput(BaseModel):
    """Input schema for flight search tool."""
    origin: str = Field(..., description="IATA airport/city code for departure (e.g., 'BOM', 'DEL', 'BLR')")
    destination: str = Field(..., description="IATA airport/city code for arrival (e.g., 'NRT', 'CDG', 'DPS')")
    departure_date: str = Field(..., description="Departure date in YYYY-MM-DD format")
    return_date: Optional[str] = Field(None, description="Optional return date in YYYY-MM-DD format for round-trip")
    travelers: int = Field(1, description="Number of adult travelers", ge=1, le=9)


@tool("search_flights", args_schema=FlightSearchInput)
@trace_tool_execution("search_flights")
def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: Optional[str] = None,
    travelers: int = 1
) -> dict:
    """
    Search for flight offers using the Amadeus Flight Offers Search API.
    Results are cached in Redis for 15 minutes. Prices in INR.
    
    Args:
        origin: IATA airport/city code (e.g., "BOM", "DEL", "BLR")
        destination: IATA airport/city code (e.g., "NRT", "CDG")
        departure_date: Date in YYYY-MM-DD format
        return_date: Optional return date in YYYY-MM-DD format
        travelers: Number of adult travelers
    
    Returns:
        dict with flight offers (prices in INR) or error information
    """
    # ── Check cache ──
    cache_key = _build_cache_key(origin, destination, departure_date, return_date, travelers)
    cached = _cache_get(cache_key)
    if cached:
        return cached
    
    # ── API call ──
    # Amadeus GET /v2/shopping/flight-offers: required = originLocationCode, destinationLocationCode, departureDate, adults
    # API rejects past dates; ensure departure and return are always in the future
    try:
        amadeus = _get_amadeus_client()
        
        origin_code = (origin or "").upper().strip()[:3]
        destination_code = (destination or "").upper().strip()[:3]
        if len(origin_code) != 3 or len(destination_code) != 3:
            return {
                "origin": origin,
                "destination": destination,
                "error": "Origin and destination must be 3-letter IATA codes (e.g. DEL, BOM).",
                "flights": [],
            }
        
        today = datetime.now().date()
        
        def parse_date(s):
            if not s:
                return None
            try:
                return datetime.strptime(s.strip()[:10], "%Y-%m-%d").date()
            except (ValueError, TypeError):
                return None
        
        dep_d = parse_date(departure_date)
        if dep_d is None:
            departure_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        elif dep_d < today:
            departure_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            departure_date = dep_d.strftime("%Y-%m-%d")
        
        ret_d = parse_date(return_date) if return_date else None
        if ret_d is not None:
            dep_d = parse_date(departure_date) or today
            if ret_d < today or ret_d < dep_d:
                return_date = (dep_d + timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                return_date = ret_d.strftime("%Y-%m-%d")
        
        adults_count = min(9, max(1, int(travelers)))
        params = {
            "originLocationCode": origin_code,
            "destinationLocationCode": destination_code,
            "departureDate": departure_date,
            "adults": adults_count,
        }
        if return_date:
            params["returnDate"] = return_date
        # Limit results; omit currencyCode to avoid invalid-parameter 400 in some environments
        params["max"] = 5
        
        response = amadeus.shopping.flight_offers_search.get(**params)
        
        # Parse the response into a cleaner format
        flights = []
        for offer in response.data:
            itineraries = []
            for itin in offer.get("itineraries", []):
                segments = []
                for seg in itin.get("segments", []):
                    segments.append({
                        "departure_airport": seg["departure"]["iataCode"],
                        "departure_time": seg["departure"].get("at", ""),
                        "arrival_airport": seg["arrival"]["iataCode"],
                        "arrival_time": seg["arrival"].get("at", ""),
                        "carrier": seg.get("carrierCode", ""),
                        "flight_number": f"{seg.get('carrierCode', '')}{seg.get('number', '')}",
                        "duration": seg.get("duration", ""),
                        "aircraft": seg.get("aircraft", {}).get("code", ""),
                    })
                itineraries.append({
                    "duration": itin.get("duration", ""),
                    "segments": segments,
                    "stops": len(segments) - 1,
                })
            
            price_info = offer.get("price", {})
            
            # Extract first segment info for display
            first_itin = itineraries[0] if itineraries else {}
            first_seg = first_itin.get("segments", [{}])[0] if first_itin else {}
            last_seg = first_itin.get("segments", [{}])[-1] if first_itin else {}
            
            try:
                price_total = float(price_info.get("grandTotal", 0))
            except (ValueError, TypeError):
                price_total = 0
            api_currency = (price_info.get("currency") or "USD").upper()
            rate = CURRENCY_TO_INR.get(api_currency, CURRENCY_TO_INR["USD"])
            price_inr = round(price_total * rate, 2)
            
            flights.append({
                "id": offer.get("id", ""),
                "price_total": price_info.get("grandTotal", ""),
                "price_inr": price_inr,
                "price_currency": "INR",
                "price_per_traveler": price_info.get("total", ""),
                "itineraries": itineraries,
                "booking_class": offer.get("travelerPricings", [{}])[0].get("fareDetailsBySegment", [{}])[0].get("cabin", "ECONOMY"),
                "seats_remaining": offer.get("numberOfBookableSeats", "N/A"),
                # Convenience fields for display
                "airline": first_seg.get("carrier", ""),
                "flight_number": first_seg.get("flight_number", ""),
                "departure_time": first_seg.get("departure_time", ""),
                "arrival_time": last_seg.get("arrival_time", ""),
                "duration": first_itin.get("duration", ""),
                "stops": first_itin.get("stops", 0),
            })
        
        result = {
            "origin": origin,
            "destination": destination,
            "departure_date": departure_date,
            "return_date": return_date,
            "travelers": travelers,
            "currency": "INR",
            "flights": flights,
            "total_results": len(flights),
        }
        
        # ── Store in cache ──
        _cache_set(cache_key, result)
        
        return result
    
    except ResponseError as e:
        return {
            "origin": origin,
            "destination": destination,
            "error": f"Amadeus API error: {str(e)}",
            "status_code": getattr(e.response, "status_code", None),
            "flights": [],
        }
    except Exception as e:
        return {
            "origin": origin,
            "destination": destination,
            "error": f"Flight search failed: {str(e)}",
            "flights": [],
        }
