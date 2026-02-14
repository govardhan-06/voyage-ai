"""Real flight search using Amadeus Flight Offers Search API.

Results are cached in Redis for 15 minutes to reduce API calls.
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


def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str = None,
    travelers: int = 1
) -> dict:
    """
    Search for flight offers using the Amadeus Flight Offers Search API.
    Results are cached in Redis for 15 minutes.
    
    Args:
        origin: IATA airport/city code (e.g., "JFK", "DEL")
        destination: IATA airport/city code (e.g., "NRT", "CDG")
        departure_date: Date in YYYY-MM-DD format
        return_date: Optional return date in YYYY-MM-DD format
        travelers: Number of adult travelers
    
    Returns:
        dict with flight offers or error information
    """
    # ── Check cache ──
    cache_key = _build_cache_key(origin, destination, departure_date, return_date, travelers)
    try:
        redis = get_redis_client()
        if redis:
            import asyncio
            try:
                loop = asyncio.get_running_loop()
                # Use a sync-compatible approach — run_coroutine_threadsafe
                import concurrent.futures
                future = asyncio.run_coroutine_threadsafe(redis.get(cache_key), loop)
                cached = future.result(timeout=2)
                if cached:
                    result = json.loads(cached)
                    result["_cached"] = True
                    return result
            except RuntimeError:
                # No running loop — use asyncio.run
                cached = asyncio.run(redis.get(cache_key))
                if cached:
                    result = json.loads(cached)
                    result["_cached"] = True
                    return result
            except Exception:
                pass
    except Exception:
        pass
    
    # ── API call ──
    try:
        amadeus = _get_amadeus_client()
        
        params = {
            "originLocationCode": origin,
            "destinationLocationCode": destination,
            "departureDate": departure_date,
            "adults": travelers,
            "max": 5,
            "currencyCode": "USD",
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
            flights.append({
                "id": offer.get("id", ""),
                "price_total": price_info.get("grandTotal", ""),
                "price_currency": price_info.get("currency", "USD"),
                "price_per_traveler": price_info.get("total", ""),
                "itineraries": itineraries,
                "booking_class": offer.get("travelerPricings", [{}])[0].get("fareDetailsBySegment", [{}])[0].get("cabin", "ECONOMY"),
                "seats_remaining": offer.get("numberOfBookableSeats", "N/A"),
            })
        
        result = {
            "origin": origin,
            "destination": destination,
            "departure_date": departure_date,
            "return_date": return_date,
            "travelers": travelers,
            "flights": flights,
            "total_results": len(flights),
        }
        
        # ── Store in cache ──
        try:
            if redis:
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    asyncio.run_coroutine_threadsafe(
                        redis.set(cache_key, json.dumps(result, default=str), ex=FLIGHT_CACHE_TTL),
                        loop
                    )
                except RuntimeError:
                    asyncio.run(redis.set(cache_key, json.dumps(result, default=str), ex=FLIGHT_CACHE_TTL))
                except Exception:
                    pass
        except Exception:
            pass
        
        return result
    
    except ResponseError as e:
        return {
            "origin": origin,
            "destination": destination,
            "error": f"Amadeus API error: {str(e)}",
            "status_code": getattr(e.response, "status_code", None),
        }
    except Exception as e:
        return {
            "origin": origin,
            "destination": destination,
            "error": f"Flight search failed: {str(e)}",
        }
