import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings as settings_logs
from core.database import get_db
from models.session import Session
from models.transcript import Transcript
from schemas.transcript import TranscriptRequest

router = APIRouter()


# Auth dependency for service-to-service calls
async def verify_service_key(x_service_key: str = Header(...)) -> None:
    """Check the X-Service-Key header matches our configured key."""
    # hmac.compare_digest is constant-time — a plain `!=` leaks key bytes
    # to an attacker who can measure response latency.
    if not hmac.compare_digest(x_service_key, settings_logs.service_api_key):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail='Invalid service key')


@router.post('/', status_code=status.HTTP_201_CREATED)
async def create_log(
    body: TranscriptRequest,
    _: None = Depends(
        verify_service_key
    ),  # auth check — underscore because we don't use the return
    db: AsyncSession = Depends(get_db),
) -> dict:
    # Confirm the session exists before inserting. Without this, a leaked
    # service key could fire transcripts at arbitrary UUIDs and pollute
    # other users' sessions (or fill the table with orphan rows).
    result = await db.execute(select(Session.id).where(Session.id == body.session_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail='Session not found'
        )

    entry = Transcript(
        session_id=body.session_id,
        role=body.role,
        content=body.content,
    )
    db.add(entry)
    await db.flush()
    return {'status': 'saved'}
