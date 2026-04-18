from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.admin import router as router_admin
from api.auth import router as router_auth
from api.billing import router as router_billing
from api.cvs import router as router_cv
from api.feedback import router as router_feedback
from api.sessions import router as router_session
from api.transcripts import router as router_transcripts
from core.logging import setup_logging

# Configure stdlib logging before anything else so import-time log lines
# (e.g. from services module globals) use our format, not the default.
setup_logging()

app = FastAPI(
    title='Azens FastAPI Swagger',
    version='0.1.0',
    description='API for Azens. An investment interview helper. Provides Voice Agents that walks you through realistic IB/PE interviews.',
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        '*'
    ],  # lock down in production to: ["https://www.azens.net"], so only frontend can call this API
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.include_router(router_auth, prefix='/api/v1/auth', tags=['auth'])
app.include_router(router_admin, prefix='/api/v1/admin', tags=['admin'])
app.include_router(router_cv, prefix='/api/v1/cv', tags=['cv'])
app.include_router(router_billing, prefix='/api/v1/billing', tags=['billing'])
app.include_router(router_session, prefix='/api/v1/session', tags=['session'])
app.include_router(router_feedback, prefix='/api/v1/feedback', tags=['feedback'])
app.include_router(
    router_transcripts, prefix='/api/v1/transcripts', tags=['transcripts']
)


@app.get('/health')
def get_health():
    return {'status': 'ok'}
