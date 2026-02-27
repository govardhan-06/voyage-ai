"""Real flight search using Amadeus Flight Offers Search API.

Results are cached in Redis for 15 minutes to reduce API calls.
All prices are returned in INR (Indian Rupees).
"""

import json
import hashlib
from amadeus import Client, ResponseError
from src.config import settings
from src.database import get_redis_client

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


def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str = None,
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
    try:
        amadeus = _get_amadeus_client()
        
        params = {
            "originLocationCode": origin,
            "destinationLocationCode": destination,
            "departureDate": departure_date,
            "adults": travelers,
            "max": 5,
            "currencyCode": "INR",
        }
        
        if return_date:
            params["returnDate"] = return_date
        
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
            
            flights.append({
                "id": offer.get("id", ""),
                "price_total": price_info.get("grandTotal", ""),
                "price_inr": price_total,
                "price_currency": price_info.get("currency", "INR"),
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
