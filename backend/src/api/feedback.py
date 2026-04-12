from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user_id
from core.database import get_db
from models.feedback import Feedback
from models.session import Session
from schemas.feedback import FeedbackResponse

router = APIRouter()


@router.get(
    '/{session_id}', response_model=FeedbackResponse, status_code=status.HTTP_200_OK
)
async def get_feedback(
    session_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    result = await db.execute(
        select(Feedback)
        .join(Session, Feedback.session_id == Session.id)
        .where(Session.user_id == user_id, Feedback.session_id == session_id)
    )

    feedback = result.scalar_one_or_none()

    if not feedback:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail='Feedback not found')

    return feedback


@router.get('/', response_model=list[FeedbackResponse], status_code=status.HTTP_200_OK)
async def get_all_feedback(
    user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> list[FeedbackResponse]:
    result = await db.execute(
        select(Feedback)
        .join(Session, Feedback.session_id == Session.id)
        .where(Session.user_id == user_id)
        .order_by(Feedback.generated_at.desc())
    )

    return result.scalars().all()
