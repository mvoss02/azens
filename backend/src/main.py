from fastapi import FastAPI
from api.auth import router as router_auth
from api.admin import router as router_admin
from api.cv import router as router_cv
from api.billing import router as router_billing

app = FastAPI(
    title='Azens FastAPI Swagger',
    version='0.1.0',
    description='API for Azens. An investment interview helper. Provides Voice Agents that walks you through realistic IB/PE interviews.',
)

app.include_router(router_auth, prefix="/api/v1/auth", tags=["auth"])
app.include_router(router_admin, prefix="/api/v1/admin", tags=["admin"])
app.include_router(router_cv, prefix="/api/v1/cv", tags=["cv"])
app.include_router(router_billing, prefix="/api/v1/billing", tags=["billing"])


@app.get('/health')
def get_health():
    return {'status': 'ok'}
