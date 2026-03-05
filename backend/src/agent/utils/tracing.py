"""LangSmith tracing utilities for enhanced observability."""

import functools
from typing import Any, Callable, Dict, Optional
from langsmith import traceable
from src.config import settings


def trace_agent_node(
    node_name: str,
    metadata: Optional[Dict[str, Any]] = None,
    tags: Optional[list] = None
):
    """
    Decorator to trace agent node execution with LangSmith.
    
    Args:
        node_name: Name of the agent node (e.g., "intent_slot", "planner")
        metadata: Additional metadata to include in the trace
        tags: Tags to categorize the trace
    """
    def decorator(func: Callable) -> Callable:
        if not settings.LANGSMITH_TRACING:
            return func
            
        @traceable(
            name=f"voyage_ai_{node_name}",
            metadata=metadata or {},
            tags=tags or ["voyage-ai", "agent-node", node_name]
        )
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract state information for tracing
            state = args[0] if args else kwargs.get('state', {})
            
            # Add context to trace metadata
            trace_metadata = {
                "node_name": node_name,
                "user_id": state.get("user_id", "unknown"),
                "current_node": state.get("current_node", "unknown"),
                **(metadata or {})
            }
            
            # Add trip context if available
            if trip_request := state.get("trip_request"):
                trace_metadata.update({
                    "destination": trip_request.get("destination"),
                    "duration_days": trip_request.get("duration_days"),
                    "traveler_count": trip_request.get("traveler_count")
                })
            
            # Execute the function with tracing context
            wrapper.langsmith_extra = {"metadata": trace_metadata}
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator


def trace_tool_execution(tool_name: str):
    """
    Decorator to trace tool execution with LangSmith.
    
    Args:
        tool_name: Name of the tool being executed
    """
    def decorator(func: Callable) -> Callable:
        if not settings.LANGSMITH_TRACING:
            return func
            
        @traceable(
            name=f"voyage_ai_tool_{tool_name}",
            tags=["voyage-ai", "tool", tool_name]
        )
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Add tool-specific metadata
            wrapper.langsmith_extra = {
                "metadata": {
                    "tool_name": tool_name,
                    "parameters": kwargs
                }
            }
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def trace_llm_call(model_name: str, operation: str):
    """
    Decorator to trace LLM calls with LangSmith.
    
    Args:
        model_name: Name of the LLM model being used
        operation: Type of operation (e.g., "slot_filling", "planning", "itinerary_generation")
    """
    def decorator(func: Callable) -> Callable:
        if not settings.LANGSMITH_TRACING:
            return func
            
        @traceable(
            name=f"voyage_ai_llm_{operation}",
            tags=["voyage-ai", "llm", model_name, operation]
        )
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            wrapper.langsmith_extra = {
                "metadata": {
                    "model_name": model_name,
                    "operation": operation,
                    "temperature": getattr(args[0], 'temperature', None) if args else None
                }
            }
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator