from motor.motor_asyncio import AsyncIOMotorClient
import redis.asyncio as redis
from src.config import settings

class Database:
    client: AsyncIOMotorClient = None
    redis_client: redis.Redis = None

db = Database()

async def connect_to_mongo():
    db.client = AsyncIOMotorClient(settings.MONGO_URI)
    print(f"Connected to MongoDB at {settings.MONGO_URI}")

async def close_mongo_connection():
    if db.client:
        db.client.close()
        print("Closed MongoDB connection")

async def connect_to_redis():
    db.redis_client = redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
    print(f"Connected to Redis at {settings.REDIS_URL}")

async def close_redis_connection():
    if db.redis_client:
        await db.redis_client.close()
        print("Closed Redis connection")

def get_database():
    return db.client[settings.DB_NAME]

def get_redis_client():
    return db.redis_client
