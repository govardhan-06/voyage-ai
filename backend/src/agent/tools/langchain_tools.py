"""LangChain tool wrappers for the ReAct agent.

Exposes search_flights and search_hotels as tools the create_react_agent can invoke.
"""

from langchain_core.tools import tool
from src.agent.tools.flights import search_flights as _search_flights
from src.agent.tools.hotels import search_hotels as _search_hotels


@tool
def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str = None,
    travelers: int = 1,
) -> dict:
    """Search for flight offers. Use IATA airport/city codes (e.g. DEL, BOM, NRT).
    Dates in YYYY-MM-DD. Returns prices in INR (Indian Rupees)."""
    return _search_flights(
        origin=origin,
        destination=destination,
        departure_date=departure_date,
        return_date=return_date,
        travelers=travelers,
    )


@tool
def search_hotels(
    city_code: str,
    checkin: str = None,
    checkout: str = None,
    guests: int = 1,
    radius: int = 30,
    radius_unit: str = "KM",
) -> dict:
    """Search for hotels by IATA city code (e.g. PAR, TYO). Dates in YYYY-MM-DD.
    Returns prices in INR (Indian Rupees)."""
    return _search_hotels(
        city_code=city_code,
        checkin=checkin,
        checkout=checkout,
        guests=guests,
        radius=radius,
        radius_unit=radius_unit,
    )


def get_react_agent_tools():
    """Return the list of tools for create_react_agent."""
    return [search_flights, search_hotels]
