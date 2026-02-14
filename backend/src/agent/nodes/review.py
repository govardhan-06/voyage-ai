"""Node 3.5: Review – Human-in-the-Loop Itinerary Approval.

The graph pauses BEFORE this node (via interrupt_before in graph.compile).
The API layer reads the state (which has the draft itinerary) and presents
it to the user. When the user responds:
  - "approve" → API updates state with review_status="approved" and resumes
  - anything else → API updates state with review_feedback and resumes

This node then reads the state and routes accordingly.
"""


async def review_node(state: dict) -> dict:
    """
    Process the user's review decision.
    
    The graph was paused BEFORE this node. The API layer already updated
    the state with review_status and review_feedback before resuming.
    
    Routes:
      - review_status == "approved" → finalizer
      - review_status == "revision_requested" → planner
    """
    review_status = state.get("review_status", "")
    review_feedback = state.get("review_feedback", "")
    trip_request = state.get("trip_request", {})
    
    if review_status == "approved":
        return {
            "current_node": "finalizer",
            "messages": [{
                "role": "ai",
                "content": "Itinerary approved! Saving your trip now..."
            }]
        }
    else:
        # Revision requested — route back to planner
        return {
            "review_status": "revision_requested",
            "review_feedback": review_feedback,
            "current_node": "planner",
            "messages": [{
                "role": "ai",
                "content": f"Got it! I'll re-plan based on your feedback and generate an updated itinerary."
            }]
        }
