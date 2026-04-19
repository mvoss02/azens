import asyncio
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user_id, get_subscribed_user_id
from core.config import settings as settings_sessions
from core.database import get_db
from models.cv import CV
from models.enums import (
    CVParsingStatus,
    Language,
    SeniorityLevel,
    SessionDuration,
    SessionStatus,
    SessionType,
)
from models.session import Session
from models.user import User
from prompts.cv_screener import build_cv_screen_interview_prompt
from schemas.session import SessionRequest, SessionResponse, StartSessionResponse
from services.cv_parser import parse_cv_from_s3
from services.daily_service import create_meeting_token, create_room
from services.feedback_generator import generate_and_save_feedback
from services.pipecat_service import start_bot_session

logger = logging.getLogger(__name__)

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
    parsed_cv_text = None
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

            # Parsing pipeline gating:
            # - parsed_text present → happy path, use the cached text.
            # - parsing_status == PENDING → the upload-time background task is
            #   still running. Blocking the request on it would give the user
            #   a 40-second silent wait; cleaner to 409 and let them retry
            #   once the CV page shows "Ready."
            # - parsing_status == FAILED → tell the user to retry from the
            #   CV page, where they have the affordance.
            # - anything else (e.g. legacy PARSED row with parsed_text nulled
            #   by a manual DB mutation) → inline parse as a safety net, and
            #   sync the status columns so the UX catches up.
            if target_cv.parsed_text:
                parsed_cv_text = target_cv.parsed_text
            elif target_cv.parsing_status == CVParsingStatus.PENDING:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail=(
                        'Your CV is still being analysed. Please wait a moment '
                        'and try again — the CV list will show "Ready" when it\'s done.'
                    ),
                )
            elif target_cv.parsing_status == CVParsingStatus.FAILED:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        'Your CV failed to parse. Open the CV page and click '
                        '"Retry", or re-upload the file.'
                    ),
                )
            else:
                # Safety-net inline parse for status drift (status=PARSED but
                # parsed_text somehow cleared). Mirrors the background task's
                # status-update semantics so the columns stay consistent.
                try:
                    parsed_cv_text = await asyncio.to_thread(
                        parse_cv_from_s3, s3_key=target_cv.s3_key
                    )
                    target_cv.parsed_text = parsed_cv_text
                    target_cv.parsing_status = CVParsingStatus.PARSED
                    target_cv.parsing_error = None
                except Exception as exc:
                    logger.exception(
                        'session_start inline parse failed cv_id=%s', target_cv.id
                    )
                    target_cv.parsing_status = CVParsingStatus.FAILED
                    target_cv.parsing_error = repr(exc)[:500]
                    await db.commit()
                    raise HTTPException(
                        status.HTTP_502_BAD_GATEWAY,
                        detail='Failed to parse CV. Please retry from the CV page.',
                    ) from exc

    # Check count of sessions taken (this month)
    first_of_month = datetime.now(UTC).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )

    count = await db.execute(
        select(func.count())
        .select_from(Session)
        .where(
            Session.user_id == user_id,
            Session.created_at >= first_of_month,
            Session.status.in_([SessionStatus.COMPLETED, SessionStatus.ACTIVE]),
        )
    )
    session_count = count.scalar()

    if session_count >= 15:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail='Too many sessions')

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

    # Get room and token
    try:
        meeting_room_dict = await create_room(
            expires_in_seconds=body.duration_minutes.value * 60 + 600
        )
        token = await create_meeting_token(
            room_name=meeting_room_dict['name'], user_name=str(user_id)
        )
    except Exception as e:
        new_sess.status = SessionStatus.ERROR
        await db.flush()
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail=f'Failed to create video room: {e}'
        )

    new_sess.daily_room_name = meeting_room_dict['name']
    new_sess.daily_room_url = meeting_room_dict['url']
    new_sess.daily_token = token
    await db.flush()

    # Call bot
    result = await db.execute(select(User.full_name).where(User.id == user_id))
    user_name = result.scalar_one_or_none() or 'Candidate'

    if new_sess.session_type == SessionType.CV_SCREEN:
        seniority = (
            new_sess.seniority_level.value if new_sess.seniority_level else 'analyst'
        )
        new_sess_body = {
            'system_prompt': build_cv_screen_interview_prompt(
                parsed_cv_text,
                seniority,
                user_name,
                body.duration_minutes.value,
                body.personality,
            ),
            'language': body.language.value,
            'user_name': user_name,
            'duration_minutes': body.duration_minutes.value,
            'session_id': str(new_sess.id),
            'backend_url': settings_sessions.backend_url,
            'service_api_key': settings_sessions.service_api_key,
        }

        try:
            pipecat_result = await start_bot_session(
                body=new_sess_body,
                agent_name=settings_sessions.pipecat_agent_name_cv,
            )
            new_sess.pipecat_session_id = pipecat_result.get('session_id')
            new_sess.started_at = datetime.now(UTC)
        except Exception as e:
            new_sess.status = SessionStatus.ERROR
            await db.flush()
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                detail=f'Failed to start interview bot: {e}',
            )
    else:
        raise NotImplementedError(
            'Knowledge and case study interviews still need to be implemented'
        )

    await db.flush()

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


@router.get(
    '/{session_id}', response_model=SessionResponse, status_code=status.HTTP_200_OK
)
async def get_session(
    session_id: UUID,
    background_tasks: BackgroundTasks,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    # Owner-only read. Returns the Daily room URL + a freshly-minted
    # meeting token for ACTIVE sessions so the frontend can (re)join —
    # handles both page-refresh resilience and short network drops.
    #
    # Also runs the zombie check: if an ACTIVE session has blown past its
    # duration + grace window, we force-end it and schedule feedback here.
    # That way the first read after the bot has walked away is the one
    # that cleans up — no separate cron needed.
    result = await db.execute(
        select(Session).where(
            Session.id == session_id, Session.user_id == user_id
        )
    )
    curr_sess = result.scalar_one_or_none()

    if not curr_sess:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail='Session not found')

    if (
        curr_sess.status == SessionStatus.ACTIVE
        and curr_sess.started_at is not None
        and curr_sess.duration_minutes is not None
    ):
        deadline = curr_sess.started_at + timedelta(
            seconds=curr_sess.duration_minutes.value * 60
            + settings_sessions.zombie_grace_seconds
        )
        if datetime.now(UTC) > deadline:
            # Zombie — the bot is long gone, the user is probably gone too.
            # Flip to COMPLETED and kick off feedback so the frontend sees
            # feedback_status move from PENDING → GENERATED/FAILED/SKIPPED
            # on subsequent polls without needing a manual /end call.
            curr_sess.status = SessionStatus.COMPLETED
            curr_sess.ended_at = datetime.now(UTC)
            background_tasks.add_task(
                generate_and_save_feedback, curr_sess.id
            )
            logger.info(
                'Session %s past zombie grace — force-ended', curr_sess.id
            )

    # Mint a fresh Daily token if the session is (still) ACTIVE. Daily
    # tokens expire; the one stored at /start is only valid until the room
    # expires. For rejoin we want a clean short-lived token. If Daily is
    # unreachable we log and leave the old token — frontend will surface
    # the connection failure if that token has also expired.
    if curr_sess.status == SessionStatus.ACTIVE and curr_sess.daily_room_name:
        try:
            curr_sess.daily_token = await create_meeting_token(
                room_name=curr_sess.daily_room_name,
                user_name=str(user_id),
            )
        except Exception as e:
            logger.warning(
                'Could not mint fresh Daily token for session %s: %s',
                curr_sess.id,
                e,
            )

    await db.flush()
    await db.refresh(curr_sess)
    return curr_sess
