"""LangChain tools registry for Voyage AI agent."""

from .flights import search_flights
from .hotels import search_hotels

# Export all available tools for LangChain binding
AVAILABLE_TOOLS = [
    search_flights,
    search_hotels,
]

__all__ = ["AVAILABLE_TOOLS", "search_flights", "search_hotels"]