from fastapi import FastAPI
from api.auth import router as router_auth
from api.admin import router as router_admin

app = FastAPI(
    title='Azens FastAPI Swagger',
    version='0.1.0',
    description='API for Azens. An investment interview helper. Provides Voice Agents that walks you through realistic IB/PE interviews.',
)

app.include_router(router_auth, prefix="/api/v1/auth", tags=["auth"])
app.include_router(router_admin, prefix="/api/v1/admin", tags=["admin"])


@app.get('/health')
def get_health():
    return {'status': 'ok'}
