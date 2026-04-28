from dataclasses import dataclass
from datetime import UTC, datetime
import hmac
from typing import Literal
from uuid import UUID

from fastapi import Depends, HTTPException, Header, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import decode_token
from models.subscription import Subscription
from models.user import User
from core.config import settings as settings_deps

# HTTPBearer automatically reads the "Authorization: Bearer <token>" header
# If the header is missing, it returns None (because auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> UUID:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Not authenticated',
        )

    # credentials.credentials is the actual token string (without "Bearer " prefix)
    user_id = decode_token(credentials.credentials)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid or expired token',
        )

    return UUID(user_id)


async def get_admin_user_id(
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> UUID:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail='Admin access required'
        )

    return user_id


async def get_verified_user_id(
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> UUID:
    """
    Allow only users who have confirmed their email.

    Apply this to state-changing routes that cost real money (sessions) or
    touch personal data (CV upload). Unverified users can still sign up,
    log in, update their profile, and pay — but they cannot spend API
    budget or push PII into our stores until they prove the email is theirs.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail='Not authenticated'
        )

    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Please verify your email before continuing',
        )

    return user_id


async def get_subscribed_user_id(
    user_id: UUID = Depends(get_verified_user_id),
    db: AsyncSession = Depends(get_db),
) -> UUID:
    # Chains through get_verified_user_id, so any route using this dep
    # also requires email verification. That's intentional: the moment a
    # user can spend API budget (sessions), we want the email confirmed.
    result = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    sub = result.scalar_one_or_none()

    if (
        not sub
        or not sub.is_active
        or (sub.current_period_end and sub.current_period_end < datetime.now(UTC))
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail='Active subscription required'
        )

    return user_id

# Who is pinging our endpoint? A user or a server?
@dataclass(frozen=True)
class SessionCaller:
    kind: Literal["user", "server"]
    user_id: UUID | None  # populated for "user", None for "server"

# Auth dependency for service-to-service calls
async def get_session_caller(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    x_service_key: str | None = Header(default=None),
) -> SessionCaller:
    # Service-key first: cheaper (no DB lookup), more specific.
    # If the header is present we commit to that path — a wrong key
    # is a hard 403, not a fallback to JWT.
    if x_service_key is not None:
        if not hmac.compare_digest(x_service_key, settings_deps.service_api_key):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid service key")
        return SessionCaller(kind="server", user_id=None)

    # No service key → expect a real user.
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    user_id = decode_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    return SessionCaller(kind="user", user_id=UUID(user_id))
