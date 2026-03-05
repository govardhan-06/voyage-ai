"""Middleware utilities for state optimization between nodes."""

from typing import Dict, Any
from src.agent.utils.memory import optimize_state_messages, get_context_summary


def optimize_state_between_nodes(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Middleware function to optimize state between major agent nodes.
    
    This should be called at transition points to:
    1. Prune message history
    2. Clean up temporary data
    3. Optimize memory usage
    
    Args:
        state: Current agent state
        
    Returns:
        Optimized state
    """
    # Apply message pruning
    optimized_state = optimize_state_messages(state)
    
    # Add context summary for debugging/monitoring
    if optimized_state.get("messages"):
        context_summary = get_context_summary(optimized_state)
        # Store summary in state for potential use by nodes
        optimized_state["_context_summary"] = context_summary
    
    return optimized_state


def add_memory_management_to_node(node_func):
    """
    Decorator to add automatic memory management to agent nodes.
    
    This decorator:
    1. Optimizes state before node execution
    2. Ensures memory limits are respected
    3. Adds tracing metadata about memory usage
    """
    async def wrapper(state: Dict[str, Any]) -> Dict[str, Any]:
        # Optimize state before processing
        optimized_state = optimize_state_between_nodes(state)
        
        # Track memory metrics
        message_count_before = len(optimized_state.get("messages", []))
        
        # Execute the original node function
        result_state = await node_func(optimized_state)
        
        # Track memory metrics after
        message_count_after = len(result_state.get("messages", []))
        
        # Add memory metrics to result (for monitoring)
        result_state["_memory_metrics"] = {
            "messages_before": message_count_before,
            "messages_after": message_count_after,
            "node_name": result_state.get("current_node", "unknown")
        }
        
        return result_state
    
    return wrapper