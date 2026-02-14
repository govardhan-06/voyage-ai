from fastapi import APIRouter, Depends, Body, HTTPException, status
from src.auth.dependencies import get_current_user
from src.models.user import UserInDB, UserPreferences, UserResponse
from src.database import get_database
from datetime import datetime
from bson import ObjectId

router = APIRouter()

@router.get("/me", response_model=UserResponse)
async def read_users_me(current_user: UserInDB = Depends(get_current_user)):
    return current_user

@router.get("/me/preferences", response_model=UserPreferences)
async def read_user_preferences(current_user: UserInDB = Depends(get_current_user)):
    return current_user.preferences

@router.patch("/me/preferences", response_model=UserPreferences)
async def update_user_preferences(
    preferences: UserPreferences = Body(...),
    current_user: UserInDB = Depends(get_current_user)
):
    db = get_database()
    
    # Get current preferences as a dict
    current_prefs_dict = current_user.preferences.dict() if current_user.preferences else {}
    
    # Get only the fields the user actually sent (exclude_unset=True)
    new_prefs_dict = preferences.dict(exclude_unset=True)
    
    # Convert nested Pydantic models (like BudgetRange) to dicts properly
    # exclude_unset doesn't recurse into nested models, so BudgetRange 
    # may include None defaults. Clean those out.
    def clean_none_in_nested(d):
        """Remove None values from nested dicts (handles BudgetRange, etc.)."""
        cleaned = {}
        for k, v in d.items():
            if isinstance(v, dict):
                nested = {nk: nv for nk, nv in v.items() if nv is not None}
                if nested:  # only include if there's at least one non-None value
                    cleaned[k] = nested
            else:
                cleaned[k] = v
        return cleaned
    
    new_prefs_dict = clean_none_in_nested(new_prefs_dict)
    
    # Deep merge: new values overwrite current, nested dicts are merged
    def deep_update(original, update):
        for key, value in update.items():
            if isinstance(value, dict) and key in original and isinstance(original[key], dict):
                deep_update(original[key], value)
            else:
                original[key] = value
        return original
    
    updated_prefs_dict = deep_update(current_prefs_dict, new_prefs_dict)
    
    # Validate through Pydantic
    validated_prefs = UserPreferences(**updated_prefs_dict)
    
    # Build MongoDB filter — handle both string and ObjectId
    user_id = current_user.id
    try:
        filter_id = ObjectId(user_id)
    except Exception:
        filter_id = user_id
    
    result = await db.users.update_one(
        {"_id": filter_id},
        {
            "$set": {
                "preferences": validated_prefs.dict(),
                "updated_at": datetime.utcnow()
            }
        }
    )
    
    if result.modified_count == 0:
        # Might be a string vs ObjectId mismatch — try the other form
        alt_id = str(user_id) if isinstance(filter_id, ObjectId) else user_id
        await db.users.update_one(
            {"_id": alt_id},
            {
                "$set": {
                    "preferences": validated_prefs.dict(),
                    "updated_at": datetime.utcnow()
                }
            }
        )
    
    return validated_prefs
