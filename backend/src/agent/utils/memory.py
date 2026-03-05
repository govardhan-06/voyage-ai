"""Memory management utilities for controlling message history and token usage."""

from typing import List, Dict, Any, Optional
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from src.config import settings


# Configuration for message limits
MAX_MESSAGES_PER_NODE = 20
MAX_TOTAL_MESSAGES = 50
PRESERVE_RECENT_MESSAGES = 5  # Always keep the most recent N messages


def _estimate_tokens(text: str) -> int:
    """Rough token estimation (1 token ≈ 4 characters for most models)."""
    return len(text) // 4


def _summarize_old_messages(messages: List[Dict[str, Any]]) -> str:
    """Create a summary of older conversation messages."""
    if not messages:
        return ""
    
    # Extract key information from old messages
    user_messages = [msg for msg in messages if msg.get("role") == "user"]
    ai_messages = [msg for msg in messages if msg.get("role") == "ai"]
    
    summary_parts = []
    
    if user_messages:
        user_content = " ".join([msg.get("content", "") for msg in user_messages[-3:]])  # Last 3 user messages
        summary_parts.append(f"Recent user requests: {user_content[:200]}...")
    
    if ai_messages:
        ai_content = " ".join([msg.get("content", "") for msg in ai_messages[-2:]])  # Last 2 AI responses
        summary_parts.append(f"Recent AI responses: {ai_content[:200]}...")
    
    return " | ".join(summary_parts)


def prune_messages(
    messages: List[Dict[str, Any]], 
    max_messages: Optional[int] = None,
    preserve_recent: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Prune message history to control memory usage.
    
    Strategy:
    1. Always preserve the most recent N messages
    2. Summarize older messages into a single context message
    3. Remove intermediate tool call messages that are no longer relevant
    
    Args:
        messages: List of message dictionaries
        max_messages: Maximum number of messages to keep (default: MAX_MESSAGES_PER_NODE)
        preserve_recent: Number of recent messages to always preserve
        
    Returns:
        Pruned list of messages
    """
    if not messages:
        return messages
    
    max_msgs = max_messages or MAX_MESSAGES_PER_NODE
    preserve_count = preserve_recent or PRESERVE_RECENT_MESSAGES
    
    # If we're under the limit, return as-is
    if len(messages) <= max_msgs:
        return messages
    
    # Split messages into old and recent
    recent_messages = messages[-preserve_count:]
    old_messages = messages[:-preserve_count]
    
    # Create summary of old messages
    summary = _summarize_old_messages(old_messages)
    
    # Create a summary message if we have old content
    pruned_messages = []
    if summary:
        pruned_messages.append({
            "role": "system",
            "content": f"[Previous conversation summary: {summary}]"
        })
    
    # Add recent messages
    pruned_messages.extend(recent_messages)
    
    return pruned_messages


def prune_tool_messages(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Remove intermediate tool call messages that are no longer needed.
    
    Keeps only:
    - The most recent tool calls and results
    - User messages
    - Final AI responses
    """
    if not messages:
        return messages
    
    pruned = []
    tool_call_count = 0
    
    # Process messages in reverse to keep recent tool calls
    for msg in reversed(messages):
        content = msg.get("content", "")
        role = msg.get("role", "")
        
        # Always keep user messages and final AI responses
        if role == "user":
            pruned.insert(0, msg)
        elif role == "ai" and not ("tool" in content.lower() or "round" in content.lower()):
            pruned.insert(0, msg)
        # Keep only recent tool-related messages
        elif "tool" in content.lower() or "round" in content.lower():
            if tool_call_count < 3:  # Keep last 3 tool interactions
                pruned.insert(0, msg)
                tool_call_count += 1
        else:
            pruned.insert(0, msg)
    
    return pruned


def optimize_state_messages(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Optimize the message history in the agent state to control memory usage.
    
    This function should be called between major nodes to prevent
    unlimited message growth.
    """
    messages = state.get("messages", [])
    
    if not messages or len(messages) <= MAX_MESSAGES_PER_NODE:
        return state
    
    # Apply pruning strategies
    pruned_messages = prune_messages(messages)
    pruned_messages = prune_tool_messages(pruned_messages)
    
    # Ensure we don't exceed the absolute maximum
    if len(pruned_messages) > MAX_TOTAL_MESSAGES:
        pruned_messages = pruned_messages[-MAX_TOTAL_MESSAGES:]
    
    # Update state with pruned messages
    optimized_state = state.copy()
    optimized_state["messages"] = pruned_messages
    
    return optimized_state


def get_context_summary(state: Dict[str, Any]) -> str:
    """
    Generate a concise summary of the current conversation context.
    
    Useful for providing context to LLMs without including full message history.
    """
    messages = state.get("messages", [])
    trip_request = state.get("trip_request", {})
    current_node = state.get("current_node", "unknown")
    
    summary_parts = []
    
    # Trip context
    if trip_request:
        destination = trip_request.get("destination", "unknown")
        duration = trip_request.get("duration_days", "unknown")
        travelers = trip_request.get("traveler_count", "unknown")
        summary_parts.append(f"Planning trip to {destination} for {duration} days, {travelers} travelers")
    
    # Current progress
    summary_parts.append(f"Current stage: {current_node}")
    
    # Recent conversation
    recent_user_msgs = [
        msg.get("content", "") 
        for msg in messages[-5:] 
        if msg.get("role") == "user"
    ]
    if recent_user_msgs:
        summary_parts.append(f"Recent user input: {recent_user_msgs[-1][:100]}...")
    
    return " | ".join(summary_parts)


class MessageWindow:
    """
    Sliding window for managing conversation messages with automatic pruning.
    """
    
    def __init__(self, max_size: int = MAX_MESSAGES_PER_NODE):
        self.max_size = max_size
        self.messages: List[Dict[str, Any]] = []
    
    def add_message(self, message: Dict[str, Any]) -> None:
        """Add a message to the window, pruning if necessary."""
        self.messages.append(message)
        
        if len(self.messages) > self.max_size:
            self._prune()
    
    def _prune(self) -> None:
        """Internal pruning logic."""
        self.messages = prune_messages(self.messages, self.max_size)
    
    def get_messages(self) -> List[Dict[str, Any]]:
        """Get current messages in the window."""
        return self.messages.copy()
    
    def clear(self) -> None:
        """Clear all messages."""
        self.messages = []
    
    def get_summary(self) -> str:
        """Get a summary of messages in the window."""
        return _summarize_old_messages(self.messages)