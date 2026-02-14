from fastapi import APIRouter, HTTPException, status, Depends, Body
from fastapi.security import OAuth2PasswordBearer
from src.models.user import UserCreate, UserResponse, UserInDB
from src.database import get_database
from src.auth.utils import get_password_hash, verify_password, create_access_token
from datetime import datetime
from typing import Any

router = APIRouter()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

@router.post("/register", response_model=UserResponse)
async def register(user: UserCreate = Body(...)):
    db = get_database()
    existing_user = await db.users.find_one({"email": user.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    user_dict = user.dict()
    password_hash = get_password_hash(user_dict.pop("password"))
    
    new_user = UserInDB(
        **user_dict,
        password_hash=password_hash,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    
    new_user_dict = new_user.dict(by_alias=True, exclude={"id"})
    result = await db.users.insert_one(new_user_dict)
    
    created_user = await db.users.find_one({"_id": result.inserted_id})
    return UserResponse(**created_user)

@router.post("/login")
async def login(email: str = Body(...), password: str = Body(...)):
    db = get_database()
    user = await db.users.find_one({"email": email})
    
    if not user or not verify_password(password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    
    access_token = create_access_token(user["_id"])
    return {
        "access_token": access_token, 
        "token_type": "bearer",
        "user_id": str(user["_id"])
    }
