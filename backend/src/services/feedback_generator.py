import logging
from uuid import UUID

from openai import AsyncOpenAI
from sqlalchemy import select

from core.config import settings as settings_feedback
from core.database import SessionLocal
from models.enums import FeedbackStatus, SeniorityLevel, SessionType
from models.feedback import Feedback
from models.session import Session
from models.transcript import Transcript
from prompts.feedback import (
    build_cv_screen_feedback_prompt,
    build_knowledge_drill_feedback_prompt,
)
from schemas.feedback_llm import CVScreenFeedback, KnowledgeDrillFeedback

logger = logging.getLogger(__name__)

_client = AsyncOpenAI(api_key=settings_feedback.openai_api_key)


async def _generate_cv_screen_feedback(
    transcript: str,
    seniority_level: SeniorityLevel | None,
) -> CVScreenFeedback:
    """Call ChatGPT with the CV screen rubric — returns a validated Pydantic instance."""
    instructions = build_cv_screen_feedback_prompt(
        seniority_level=seniority_level.value if seniority_level else 'analyst',
    )

    response = await _client.responses.parse(
        model=settings_feedback.openai_model_feedback,
        instructions=instructions,
        input=f'TRANSCRIPT:\n{transcript}',
        text_format=CVScreenFeedback,
    )
    return response.output_parsed


async def _generate_knowledge_drill_feedback(
    transcript: str,
    questions_asked: list[dict],
) -> KnowledgeDrillFeedback:
    """Call GPT-4o with the knowledge drill rubric — returns a validated Pydantic instance."""
    instructions = build_knowledge_drill_feedback_prompt(
        questions_asked=questions_asked,
    )

    response = await _client.responses.parse(
        model=settings_feedback.openai_model_feedback,
        instructions=instructions,
        input=f'TRANSCRIPT:\n{transcript}',
        text_format=KnowledgeDrillFeedback,
    )
    return response.output_parsed


async def _generate_feedback(
    interview_type: SessionType,
    transcript: str,
    seniority_level: SeniorityLevel | None = None,
    questions_asked: list[dict] | None = None,
) -> CVScreenFeedback | KnowledgeDrillFeedback:
    """Dispatcher — picks the right feedback generator based on interview type."""
    if interview_type == SessionType.CV_SCREEN:
        return await _generate_cv_screen_feedback(transcript, seniority_level)
    elif interview_type == SessionType.KNOWLEDGE_DRILL:
        if questions_asked is None:
            raise ValueError('questions_asked is required for knowledge drill feedback')
        return await _generate_knowledge_drill_feedback(transcript, questions_asked)
    elif interview_type == SessionType.CASE_STUDY:
        raise NotImplementedError('Case study feedback not implemented yet')
    else:
        raise ValueError(f'Unknown interview type: {interview_type}')


async def generate_and_save_feedback(session_id: UUID):
    # Runs as a FastAPI BackgroundTask. Every outcome flips
    # `Session.feedback_status` so the frontend can distinguish
    # "still generating" from "we tried and it failed" without refreshing.
    async with SessionLocal() as db:
        # 1. Load session
        result = await db.execute(select(Session).where(Session.id == session_id))
        curr_sess = result.scalar_one_or_none()

        if not curr_sess:
            # Shouldn't happen — session row was just created before /end fired.
            # No session means there's nothing to flip a status on, so just log.
            logger.error('Session %s not found, skipping feedback', session_id)
            return

        # 2. Load transcript (concat all transcript rows for this session)
        result = await db.execute(
            select(Transcript)
            .where(Transcript.session_id == session_id)
            .order_by(Transcript.timestamp)
        )
        transcripts = result.scalars().all()

        if not transcripts:
            # User likely disconnected before saying anything — mark SKIPPED
            # so the frontend can show "no transcript recorded" rather than
            # spinning on "Generating…" forever.
            curr_sess.feedback_status = FeedbackStatus.SKIPPED
            await db.commit()
            logger.warning(
                'No transcript for session %s — feedback_status=SKIPPED', session_id
            )
            return

        formatted_transcript = '\n'.join(f'{t.role}: {t.content}' for t in transcripts)

        try:
            # 3. Call generate_feedback() — OpenAI can fail for many reasons:
            # rate limit, quota, network, schema-parse, model unavailable.
            llm_result = await _generate_feedback(
                interview_type=curr_sess.session_type,
                transcript=formatted_transcript,
                seniority_level=curr_sess.seniority_level,
                questions_asked=None,
            )  # TODO: Implement question tracking

            # 4. Create Feedback record, flip status, commit atomically
            new_feedback = Feedback(
                session_id=session_id,
                feedback_type=curr_sess.session_type,
                data=llm_result.model_dump(),  # entire Pydantic -> JSONB
            )
            db.add(new_feedback)
            curr_sess.feedback_status = FeedbackStatus.GENERATED
            await db.commit()
        except Exception:
            # Roll back any pending writes from the happy path (e.g. half-
            # attached Feedback row), then flip status to FAILED in a fresh
            # transaction so the frontend stops polling and can show retry.
            # Re-query the session because after rollback the ORM object is
            # expired and attribute access would re-hit the DB anyway.
            await db.rollback()
            logger.exception('Feedback generation failed for session %s', session_id)
            result = await db.execute(select(Session).where(Session.id == session_id))
            sess = result.scalar_one_or_none()
            if sess is not None:
                sess.feedback_status = FeedbackStatus.FAILED
                await db.commit()
