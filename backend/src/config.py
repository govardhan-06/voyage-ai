from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "Voyage AI Backend"
    MONGO_URI: str = os.getenv("MONGO_URI")
    DB_NAME: str = "voyage_ai"
    REDIS_URL: str = os.getenv("REDIS_URL")
    
    SECRET_KEY: str = "supersecretkey" # Change in production
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    # LLM_MODEL: str = "gemini-2.5-flash"
    LLM_MODEL: str = "gemini-2.5-flash-lite"

    AMADEUS_API_KEY: str = os.getenv("AMADEUS_API_KEY", "")
    AMADEUS_API_SECRET: str = os.getenv("AMADEUS_API_SECRET", "")

    # LangSmith tracing (set LANGSMITH_TRACING=true to enable)
    LANGSMITH_TRACING: str = os.getenv("LANGSMITH_TRACING", "false")
    LANGSMITH_ENDPOINT: str = os.getenv("LANGSMITH_ENDPOINT", "https://api.smith.langchain.com")
    LANGSMITH_API_KEY: str = os.getenv("LANGSMITH_API_KEY", "")
    LANGSMITH_PROJECT: str = os.getenv("LANGSMITH_PROJECT", "Voyage AI")

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()