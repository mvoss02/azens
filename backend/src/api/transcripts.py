from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from services.pipecat_service import start_bot_session
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user_id, get_subscribed_user_id
from core.database import get_db

from core.config import settings as settings_transcripts

router = APIRouter()