import asyncio
import httpx
from src.config import settings
from src.database import connect_to_mongo, close_mongo_connection, get_database

# Helper function to clear test data
async def clear_test_data(email: str):
    await connect_to_mongo()
    db = get_database()
    await db.users.delete_many({"email": email})
    await close_mongo_connection()

async def test_api():
    base_url = "http://127.0.0.1:8000"
    test_email = "testuser@example.com"
    test_password = "testpassword"

    # Clear previous test data
    await clear_test_data(test_email)

    async with httpx.AsyncClient(base_url=base_url) as client:
        # 1. Health Check
        print("Testing Root Endpoint...")
        try:
            resp = await client.get("/")
            print(f"Root Status: {resp.status_code}")
            print(f"Root Response: {resp.json()}")
        except Exception as e:
            print(f"Failed to connect to root: {e}")
            return

        # 2. Register
        print("\nTesting Registration...")
        register_payload = {
            "email": test_email,
            "password": test_password,
            "name": "Test User"
        }
        resp = await client.post("/auth/register", json=register_payload)
        print(f"Register Status: {resp.status_code}")
        print(f"Register Response: {resp.json()}")
        
        if resp.status_code != 200:
            print("Registration failed, stopping test.")
            return

        # 3. Login
        print("\nTesting Login...")
        login_payload = {
            "email": test_email,
            "password": test_password
        }
        resp = await client.post("/auth/login", json=login_payload)
        print(f"Login Status: {resp.status_code}")
        print(f"Login Response: {resp.json()}")

        if resp.status_code == 200:
            token = resp.json().get("access_token")
            print(f"Received Token: {token[:10]}...")
        else:
            print("Login failed")

if __name__ == "__main__":
    # Note: The server must be running separately for this script to work fully via valid HTTP requests.
    # However, since we cannot easily run a background server and test it in one go without complex setup,
    # we will rely on manual verification or assume the user runs the server.
    # For now, I will just output instructions on how to run.
    print("To verify, run the server with: uvicorn application:app --reload")
    print("Then run this script.")
