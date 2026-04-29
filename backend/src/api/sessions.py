import asyncio
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import SessionCaller, get_current_user_id, get_subscribed_user_id, get_session_caller
from core.config import settings as settings_sessions
from core.database import get_db
from models.cv import CV
from models.enums import (
    CVParsingStatus,
    FeedbackStatus,
    Language,
    SeniorityLevel,
    SessionDuration,
    SessionStatus,
    SessionType,
    SubscriptionPlan,
)
from models.session import Session
from models.subscription import Subscription
from models.user import User
from prompts.cv_screener import build_cv_screen_interview_prompt
from schemas.session import SessionRequest, SessionResponse, StartSessionResponse
from services.cv_parser import parse_cv_from_s3
from services.daily_service import create_meeting_token, create_room, delete_room
from services.feedback_generator import generate_and_save_feedback
from services.pipecat_service import start_bot_session

logger = logging.getLogger(__name__)

router = APIRouter()


def _monthly_session_limit(plan: SubscriptionPlan) -> int | None:
    """Look up the per-month session cap for a subscription tier.

    Returns None for unlimited (currently MD only). Source values live in
    config.py — change them there, not here, so prod tunes don't need a
    redeploy. This wrapper exists because pydantic-settings can't natively
    hold an enum-keyed dict, so we keep the structural mapping (plan →
    setting name) in code and the values in config.
    """
    return {
        SubscriptionPlan.ANALYST: settings_sessions.session_limit_analyst,
        SubscriptionPlan.ASSOCIATE: settings_sessions.session_limit_associate,
        SubscriptionPlan.MANAGING_DIRECTOR: (
            settings_sessions.session_limit_managing_director
        ),
    }[plan]


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

    # Per-tier monthly cap, enforced via an atomic compare-and-increment on
    # the subscription's billing-period counter. The counter is the source
    # of truth — never decremented on session delete (option C in the
    # design discussion), reset to 0 on the Stripe invoice.paid webhook
    # for billing_reason='subscription_cycle'. get_subscribed_user_id
    # already verified an active subscription, so .scalar_one() is safe
    # for the plan lookup.
    plan_result = await db.execute(
        select(Subscription.plan).where(Subscription.user_id == user_id)
    )
    plan = plan_result.scalar_one()
    monthly_limit = _monthly_session_limit(plan)

    if monthly_limit is None:
        # Unlimited plan (currently MD): increment for accounting/visibility
        # but no cap to enforce. No CAS needed.
        await db.execute(
            update(Subscription)
            .where(Subscription.user_id == user_id)
            .values(
                sessions_used_this_period=Subscription.sessions_used_this_period + 1
            )
        )
    else:
        # Compare-and-increment in a single SQL UPDATE: bump the counter
        # only if it's still under the cap. If two parallel /session/start
        # calls race, exactly one wins and the other gets a 0-row result.
        # Same pattern as the /end endpoint's status CAS.
        cas_result = await db.execute(
            update(Subscription)
            .where(
                Subscription.user_id == user_id,
                Subscription.sessions_used_this_period < monthly_limit,
            )
            .values(
                sessions_used_this_period=Subscription.sessions_used_this_period + 1
            )
            .returning(Subscription.sessions_used_this_period)
        )
        if cas_result.scalar_one_or_none() is None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail=(
                    f'Monthly session limit reached ({monthly_limit} for '
                    'your plan). Upgrade or wait until next billing period.'
                ),
            )

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
            expires_in_seconds=body.duration_minutes.value * 60 + settings_sessions.daily_room_grace_seconds
        )
        user_token, bot_token = await asyncio.gather(
            create_meeting_token(
                room_name=meeting_room_dict['name'], user_name=str(user_id)
            ),
            create_meeting_token(
                room_name=meeting_room_dict['name'], user_name='Alex (Interviewer)'
            ),
        )
    except Exception as e:
        new_sess.status = SessionStatus.ERROR
        await db.flush()
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, detail=f'Failed to create video room: {e}'
        )

    new_sess.daily_room_name = meeting_room_dict['name']
    new_sess.daily_room_url = meeting_room_dict['url']
    new_sess.daily_token = user_token
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
            'daily_room_url': meeting_room_dict['url'],
            'daily_token': bot_token,
        }

        try:
            pipecat_result = await start_bot_session(
                body=new_sess_body,
                agent_name=settings_sessions.pipecat_agent_name_cv,
            )
            new_sess.pipecat_session_id = pipecat_result.get('session_id')
            new_sess.started_at = datetime.now(UTC)
        except Exception as e:
            # Pipecat refused / timed out — the Daily room we created a few
            # lines ago is orphaned. Delete it now so we don't leak quota
            # (the room would otherwise hang around until its natural `exp`
            # timestamp, tens of minutes later). Best-effort: delete_room
            # swallows errors so a second failure doesn't mask the first.
            await delete_room(meeting_room_dict['name'])
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


@router.post('/{session_id}/end', response_model=SessionResponse, status_code=status.HTTP_200_OK)
async def end_session(
    session_id: UUID,
    background_tasks: BackgroundTasks,
    caller: SessionCaller = Depends(get_session_caller),
    error: bool = False,
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    result = await db.execute(select(Session).where(Session.id == session_id))
    curr_sess = result.scalar_one_or_none()

    if not curr_sess:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail='Session not found')
    
    # Only check ownership for user callers; Server is trusted globally
    if caller.kind == "user" and curr_sess.user_id != caller.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN)
    
    # Did the user actually interview long enough for feedback to be worth
    # generating? We gate on a fraction of the scheduled duration rather than
    # a fixed minute count so a 90-min superday and a 15-min warm-up both get
    # sensible thresholds. `started_at` can be None if the bot never connected
    # — in that case nothing happened to give feedback on.
    now = datetime.now(UTC)
    scheduled_seconds = curr_sess.duration_minutes.value * 60
    actual_seconds = (
        (now - curr_sess.started_at).total_seconds() if curr_sess.started_at else 0
    )
    min_seconds = scheduled_seconds * settings_sessions.feedback_min_session_fraction
    too_short = actual_seconds < min_seconds

    if error:
        target_status = SessionStatus.ERROR
        target_feedback_status = FeedbackStatus.SKIPPED
    elif too_short:
        logger.info(
            'end_session skipping feedback session_id=%s actual_s=%.1f min_s=%.1f',
            session_id,
            actual_seconds,
            min_seconds,
        )
        target_status = SessionStatus.COMPLETED
        target_feedback_status = FeedbackStatus.SKIPPED
    else:
        target_status = SessionStatus.COMPLETED
        target_feedback_status = FeedbackStatus.PENDING
        
    cas_stmt = (
        update(Session)
        .where(
            Session.id == session_id,
            Session.status.in_([SessionStatus.PENDING, SessionStatus.ACTIVE]),
        )
        .values(
            status=target_status,
            feedback_status=target_feedback_status,
            ended_at=now,
        )
        .returning(Session)
        .execution_options(synchronize_session=False)
    )
    cas_result = await db.execute(cas_stmt)
    updated_sess = cas_result.scalar_one_or_none()

    if updated_sess is not None:
        # CAS won: we are the only writer that flipped the row. Now (and only
        # now) is it safe to schedule feedback.
        if target_feedback_status == FeedbackStatus.PENDING:
            background_tasks.add_task(generate_and_save_feedback, session_id)
        response_sess = updated_sess
    else:
        # CAS lost: another caller already terminated this session. Don't
        # 4xx, the session IS ended, just not by us. Re-read so the response
        # reflects the row's actual current state (not our stale snapshot).
        response_sess = curr_sess

    await db.commit()
    await db.refresh(response_sess)

    logger.info(
        'end_session session=%s caller=%s won_cas=%s target=(%s,%s)',
        session_id, caller.kind, updated_sess is not None,
        target_status.value, target_feedback_status.value,
    )

    return response_sess


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
    sessions = result.scalars().all()

    # Opportunistic zombie cleanup. If a session looks "live" (PENDING or
    # ACTIVE with started_at set) but has blown past its scheduled duration
    # plus the zombie grace window, force-complete it here so it doesn't
    # surface in the live-session banner a week later as a stale row.
    #
    # Mark feedback SKIPPED rather than scheduling GPT-4o: if the user has
    # been absent long enough for the zombie check to trip, the transcript
    # is stale and feedback from it isn't worth the API cost. The
    # single-session sweep in get_session() still schedules feedback for
    # users who come back and click Rejoin, so that path is preserved.
    now = datetime.now(UTC)
    zombies = [
        s for s in sessions
        if s.started_at is not None
        and s.status in (SessionStatus.PENDING, SessionStatus.ACTIVE)
        and now > s.started_at + timedelta(
            seconds=s.duration_minutes.value * 60
            + settings_sessions.zombie_grace_seconds
        )
    ]
    for s in zombies:
        s.status = SessionStatus.COMPLETED
        s.feedback_status = FeedbackStatus.SKIPPED
        s.ended_at = now
        logger.info('get_sessions auto-completing zombie session=%s', s.id)
    if zombies:
        await db.commit()

    return sessions


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
        select(Session).where(Session.id == session_id, Session.user_id == user_id)
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
            background_tasks.add_task(generate_and_save_feedback, curr_sess.id)
            logger.info('Session %s past zombie grace — force-ended', curr_sess.id)

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

@router.delete('/{session_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: UUID,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    # Scope by user_id to prevent cross-user delete via UUID guessing.
    # SQLAlchemy filters use comma-separated conditions (implicit AND) —
    # Python's `and` short-circuits and discards the first clause, which
    # silently lets the WHERE match any session owned by the user.
    result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.user_id == user_id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail='Session not found')

    # Children (transcripts, feedback) are removed automatically by DB-level
    # ON DELETE CASCADE on their session_id FKs (migration
    # f1a2b3c4d5e6_session_cascade_delete). Trust the DB instead of issuing
    # explicit bulk-deletes here — single source of truth, also covers
    # delete paths outside this endpoint.
    await db.delete(session)
    await db.commit()
