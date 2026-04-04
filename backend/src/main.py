from fastapi import FastAPI

app = FastAPI(
    title='Azens FastAPI Swagger',
    version='0.1.0',
    description='API for Azens. An investment interview helper. Provides Voice Agents that walks you through realistic IB/PE interviews.',
)


@app.get('/health')
def get_health():
    return {'status': 'ok'}
