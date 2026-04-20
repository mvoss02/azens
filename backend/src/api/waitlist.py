from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from models.waitlist import Waitlist
from schemas.waitlist import WaitlistRequest, WaitlistResponse

router = APIRouter()


@router.post('/join', status_code=status.HTTP_200_OK)
async def join_waitlist(
    body: WaitlistRequest,
    db: AsyncSession = Depends(get_db),
) -> WaitlistResponse:
    waitlist_mail = Waitlist(
        email=body.email.lower(), source=body.source, language=body.language
    )
    try:
        db.add(waitlist_mail)
        await db.flush()
        await db.commit()
        await db.refresh(waitlist_mail)
    except IntegrityError:
        await db.rollback()

    return WaitlistResponse(status='joined')


@router.delete('/unsubscribe/{token}',
status_code=status.HTTP_204_NO_CONTENT)
async def unsubscribe(
    token: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    stmt = delete(Waitlist).where(Waitlist.unsubscribe_token == token)
    await db.execute(stmt)
    await db.commit()
    # Return 204 regardless of whether a row was deleted. Prevents token
    # enumeration: an attacker probing random UUIDs can't distinguish
    # "valid token just used" from "never existed."
