import time

import httpx
from core.config import settings as settings_daily

DAILY_API_URL = "https://api.daily.co/v1"
HEADERS = {"Authorization": f"Bearer {settings_daily.daily_api_key}"}


async def create_room(expires_in_seconds: int = 3600) -> dict:
    """
    Create a video room. Returns {'url': '...', 'name': '...'}
    """
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{DAILY_API_URL}/rooms",
            headers=HEADERS,
            json={
                "properties": {
                    "exp": int(time.time()) + expires_in_seconds,
                    "enable_chat": False,
                }
            },
        )
        response.raise_for_status()
        data = response.json()
        return {"url": data["url"], "name": data["name"]}


async def create_meeting_token(room_name: str, user_name: str) -> str:
    """
    Create a token for a user to join a specific room.
    """
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{DAILY_API_URL}/meeting-tokens",
            headers=HEADERS,
            json={
                "properties": {
                    "room_name": room_name,
                    "user_name": user_name,
                    "is_owner": False,
                }
            },
        )
        response.raise_for_status()
        return response.json()["token"]
