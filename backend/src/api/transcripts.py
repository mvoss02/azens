from fastapi import APIRouter, Depends, HTTPException, Header, status
from schemas.transcript import TranscriptRequest
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings as settings_logs
from core.database import get_db
from models.transcript import Transcript

router = APIRouter()


# Auth dependency for service-to-service calls
async def verify_service_key(x_service_key: str = Header(...)) -> None:
    """Check the X-Service-Key header matches our configured key."""
    if x_service_key != settings_logs.service_api_key:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Invalid service key")
    
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_log(body: TranscriptRequest, _: None = Depends(verify_service_key),  # auth check — underscore because we don't use the return
                    db: AsyncSession = Depends(get_db),) -> dict:
    entry = Transcript(
        session_id=body.session_id,
        role=body.role,
        content=body.content,
    )
    db.add(entry)
    await db.flush()
    return {"status": "saved"}
    