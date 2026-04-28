from api.deps import get_session_caller
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.session import Session
from models.transcript import Transcript
from schemas.transcript import TranscriptRequest

router = APIRouter()


@router.post('/', status_code=status.HTTP_201_CREATED)
async def create_log(
    body: TranscriptRequest,
    _: None = Depends(
        get_session_caller
    ),  # auth check — underscore because we don't use the return
    db: AsyncSession = Depends(get_db),
) -> dict:
    # Confirm the session exists before inserting. Without this, a leaked
    # service key could fire transcripts at arbitrary UUIDs and pollute
    # other users' sessions (or fill the table with orphan rows).
    result = await db.execute(select(Session.id).where(Session.id == body.session_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail='Session not found')

    entry = Transcript(
        session_id=body.session_id,
        role=body.role,
        content=body.content,
    )
    db.add(entry)
    await db.flush()
    # Explicit commit: the feedback generator runs in a background task off
    # the /end endpoint and reads transcripts via a FRESH session. Without
    # an explicit commit here, the last few transcript rows (posted during
    # the final seconds of the interview) may not yet be visible when
    # feedback generation starts — producing a feedback report that
    # ignores the user's closing statements.
    await db.commit()
    return {'status': 'saved'}
