from fastapi import APIRouter, Depends, status
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
