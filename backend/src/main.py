from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from api.admin import router as router_admin
from api.auth import router as router_auth
from api.billing import router as router_billing
from api.cvs import router as router_cv
from api.feedback import router as router_feedback
from api.sessions import router as router_session
from api.transcripts import router as router_transcripts
from api.waitlist import router as router_waitlist
from core.config import settings as settings_api
from core.logging import setup_logging
from core.rate_limit import limiter

# Configure stdlib logging before anything else so import-time log lines
# (e.g. from services module globals) use our format, not the default.
setup_logging()

app = FastAPI(
    title='Azens FastAPI Swagger',
    version='0.1.0',
    description='API for Azens. An investment interview helper. Provides Voice Agents that walks you through realistic IB/PE interviews.',
)

# Rate limiter wiring. `app.state.limiter` is the convention SlowAPI's
# middleware + decorator look up. The exception handler converts a
# RateLimitExceeded into a proper 429 response with Retry-After.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings_api.frontend_url,
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
app.include_router(router_waitlist, prefix='/api/v1/waitlist', tags=['waitlist'])


@app.get('/health')
def get_health():
    return {'status': 'ok'}
