import httpx

from core.config import settings as settings_agent


async def start_bot_session(body: dict, agent_name: str):
    headers = {
        'Authorization': f'Bearer {settings_agent.pipecat_api_key}',
        'Content-Type': 'application/json',
    }
    # Pipecat Cloud's /start contract (see pipecatcloud/api.py:502 in the SDK):
    #   { "createDailyRoom": bool, "body": <your custom payload> }
    # Our backend already creates the Daily room + bot token, so
    # createDailyRoom=False — otherwise PCC would spin up a second, unrelated
    # room and hand the bot DailySessionArguments pointing there, away from
    # the room the user is actually sitting in.
    payload = {
        'createDailyRoom': False,
        'body': body,
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url=f'https://api.pipecat.daily.co/v1/public/{agent_name}/start',
            headers=headers,
            json=payload,
        )

    response.raise_for_status()

    return response.json()
