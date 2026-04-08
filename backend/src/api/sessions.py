from uuid import UUID

from core.database import get_db
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user_id
from schemas.session import StartSessionResponse, SessionRequest, SessionResponse

router = APIRouter()


@router.post("/start", response_model=StartSessionResponse, status_code=status.HTTP_200_OK)
async def start_session(body: SessionRequest, user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)) -> StartSessionResponse:
    pass

@router.post("/{session_id}/end", response_model=SessionResponse, status_code=status.HTTP_200_OK)
async def end_session(session_id: UUID, user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)) -> SessionResponse:
    pass

@router.get("/", response_model=list[SessionResponse], status_code=status.HTTP_200_OK)
async def get_sessions(user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)) -> list[SessionResponse]:
    pass

@router.get("/{session_id}/feedback", response_model=SessionResponse, status_code=status.HTTP_200_OK)
async def get_feedback(session_id: UUID, user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)) -> SessionResponse:
    pass
