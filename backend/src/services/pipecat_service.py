import httpx

from core.config import settings as settings_agent


async def start_bot_session(body: dict, agent_name: str):
    headers = {
        'Authorization': f'Bearer {settings_agent.pipecat_api_key}',
        'Content-Type': 'application/json',
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url=f'https://api.pipecat.daily.co/v1/public/{agent_name}/start',
            headers=headers,
            json=body,
        )

    response.raise_for_status()

    return response.json()
