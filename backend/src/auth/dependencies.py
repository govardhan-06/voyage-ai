from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from src.config import settings
from src.database import get_database
from src.models.user import UserInDB, PyObjectId
from bson import ObjectId

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)

async def get_current_user(token: str = Depends(oauth2_scheme)) -> UserInDB:
    # TEMPORARY: Bypass authentication for testing
    db = get_database()
    user = await db.users.find_one({})
    if user:
        return UserInDB(**user)
        
    # Original Auth Logic (Commented Out)
    # credentials_exception = HTTPException(
    #     status_code=status.HTTP_401_UNAUTHORIZED,
    #     detail="Could not validate credentials",
    #     headers={"WWW-Authenticate": "Bearer"},
    # )
    # try:
    #     payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    #     user_id: str = payload.get("sub")
    #     if user_id is None:
    #         raise credentials_exception
    # except JWTError:
    #     raise credentials_exception
    
    # db = get_database()
    # user = await db.users.find_one({"_id": ObjectId(user_id)})
    # if user is None:
    #     raise credentials_exception
        
    # return UserInDB(**user)
    raise HTTPException(status_code=404, detail="No users found for bypass mode")
