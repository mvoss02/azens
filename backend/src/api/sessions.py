from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from services.cv_parser import parse_cv_from_s3
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user_id, get_subscribed_user_id
from core.database import get_db
from models.cv import CV
from models.enums import (
    Language,
    SeniorityLevel,
    SessionDuration,
    SessionStatus,
    SessionType,
)
from models.session import Session
from schemas.session import SessionRequest, SessionResponse, StartSessionResponse
from services.feedback_generator import generate_and_save_feedback

router = APIRouter()


@router.post(
    '/start', response_model=StartSessionResponse, status_code=status.HTTP_200_OK
)
async def start_session(
    body: SessionRequest,
    user_id: UUID = Depends(get_subscribed_user_id),
    db: AsyncSession = Depends(get_db),
) -> StartSessionResponse:
    # Check if CV screening
    if body.session_type == SessionType.CV_SCREEN:
        if not body.cv_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail='CV not found')
        else:
            result = await db.execute(
                select(CV).where(
                    CV.id == body.cv_id, CV.user_id == user_id, CV.is_active == True
                )
            )
            target_cv = result.scalar_one_or_none()

            if not target_cv:
                raise HTTPException(status.HTTP_404_NOT_FOUND, detail='CV not found')

            # Get CV from S3 and parse
            if target_cv.parsed_text:
                parsed_cv_text = target_cv.parsed_text
            else:
                parsed_cv_text = parse_cv_from_s3(s3_key=target_cv.s3_key)
                target_cv.parsed_text = parsed_cv_text

    # Create new session
    new_sess = Session(
        user_id=user_id,
        cv_id=body.cv_id,
        session_type=body.session_type,
        seniority_level=body.seniority_level,
        language=body.language,
        duration_minutes=body.duration_minutes,
    )

    db.add(new_sess)
    await db.flush()

    # TODO: Create session

    await db.refresh(new_sess)

    return new_sess


@router.post(
    '/{session_id}/end', response_model=SessionResponse, status_code=status.HTTP_200_OK
)
async def end_session(
    session_id: UUID,
    background_tasks: BackgroundTasks,
    error: bool = False,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    result = await db.execute(
        select(Session).where(Session.id == session_id, Session.user_id == user_id)
    )
    curr_sess = result.scalar_one_or_none()

    if not curr_sess:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail='Session not found')

    if error:
        curr_sess.status = SessionStatus.ERROR
    else:
        curr_sess.status = SessionStatus.COMPLETED
        background_tasks.add_task(generate_and_save_feedback, session_id)

    curr_sess.ended_at = datetime.now(UTC)

    await db.flush()
    await db.refresh(curr_sess)

    return curr_sess


@router.get('/', response_model=list[SessionResponse], status_code=status.HTTP_200_OK)
async def get_sessions(
    session_type: SessionType | None = None,
    seniority_level: SeniorityLevel | None = None,
    language: Language | None = None,
    duration_minutes: SessionDuration | None = None,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> list[SessionResponse]:
    query = (
        select(Session)
        .where(Session.user_id == user_id)
        .order_by(Session.created_at.desc())
    )
    if session_type:
        query = query.where(Session.session_type == session_type)
    if seniority_level:
        query = query.where(Session.seniority_level == seniority_level)
    if language:
        query = query.where(Session.language == language)
    if duration_minutes:
        query = query.where(Session.duration_minutes == duration_minutes)

    result = await db.execute(query)
    return result.scalars().all()
