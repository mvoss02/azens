import time

import httpx

from core.config import settings as settings_daily

DAILY_API_URL = 'https://api.daily.co/v1'
HEADERS = {'Authorization': f'Bearer {settings_daily.daily_api_key}'}


async def create_room(expires_in_seconds: int = 3600) -> dict:
    """
    Create a video room. Returns {'url': '...', 'name': '...'}
    """

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f'{DAILY_API_URL}/rooms',
            headers=HEADERS,
            json={
                'properties': {
                    'exp': int(time.time()) + expires_in_seconds,
                    'enable_chat': False,
                }
            },
        )
        response.raise_for_status()
        data = response.json()
        return {'url': data['url'], 'name': data['name']}


async def create_meeting_token(room_name: str, user_name: str) -> str:
    """
    Create a token for a user to join a specific room.
    """

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f'{DAILY_API_URL}/meeting-tokens',
            headers=HEADERS,
            json={
                'properties': {
                    'room_name': room_name,
                    'user_name': user_name,
                    'is_owner': False,
                }
            },
        )
        response.raise_for_status()
        return response.json()['token']


async def delete_room(room_name: str) -> None:
    """Delete a Daily room by name. Best-effort: swallows errors so a
    cleanup caller (e.g. /session/start's Pipecat-fail rollback) can
    call this without adding a second failure mode on top of the first.

    The room would auto-expire on its own at its `exp` timestamp anyway,
    but calling this earlier frees the Daily concurrent-room quota and
    stops the billing clock sooner.
    """
    async with httpx.AsyncClient() as client:
        try:
            response = await client.delete(
                f'{DAILY_API_URL}/rooms/{room_name}',
                headers=HEADERS,
            )
            response.raise_for_status()
        except Exception:
            # Intentional swallow — caller is in an error path already
            # and doesn't want a secondary failure to mask the first.
            pass
