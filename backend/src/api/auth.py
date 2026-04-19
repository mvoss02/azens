import asyncio
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user_id
from core.config import settings as settings_auth
from core.database import get_db
from core.security import create_access_token, hash_password, verify_password
from models.cv import CV
from models.feedback import Feedback
from models.session import Session
from models.subscription import Subscription
from models.transcript import Transcript
from models.user import User
from schemas.auth import (
    ForgotPasswordRequest,
    LogIn,
    ResetPasswordRequest,
    SignUp,
    TokenResponse,
    UpdateProfileRequest,
    UserResponse,
)
from services.email import send_password_reset_email, send_verification_email
from services.s3 import delete_object

router = APIRouter()


_last_resend_at: dict[UUID, datetime] = {}
_DUMMY_PASSWORD_HASH = hash_password('moritz-is-great') # any placeholder string


@router.post(
    '/signup', response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
async def signup(new_user: SignUp, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    # 1. Check if email already taken
    result = await db.execute(select(User).where(User.email == new_user.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail='Email already registered'
        )

    # 2. Create the user
    user = User(
        email=new_user.email,
        hashed_password=hash_password(new_user.password),
        full_name=new_user.full_name,
        verification_token=secrets.token_urlsafe(32),
        verification_token_expires=datetime.now(UTC)
        + timedelta(hours=settings_auth.verification_token_ttl_hours),
    )
    db.add(user)
    await (
        db.flush()
    )  # flush sends the INSERT to DB and populates user.id, but doesn't commit yet

    # 3. Send a verification email
    await asyncio.to_thread(send_verification_email, user.email, user.verification_token)

    # 4. Create token and return
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)


@router.post('/login', response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(user: LogIn, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    # 1. Check if user exists
    result = await db.execute(select(User).where(User.email == user.email))

    existing_user = result.scalar_one_or_none()
    
    # 2. Validate password
    if existing_user and existing_user.hashed_password:
        hash_to_check = existing_user.hashed_password
    else:
        hash_to_check = _DUMMY_PASSWORD_HASH
    
    password_is_valid = verify_password(user.password, hash_to_check)
    
    # Note: Also catches OAuth-only users (hashed_password is None) trying to
    # password-login; they fall through to the dummy hash and fail the
    # bcrypt check.
    if not existing_user or not password_is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Email or Password incorrect',
        )

    # 3. Create token and return
    token = create_access_token(str(existing_user.id))
    return TokenResponse(access_token=token)


@router.get('/me', response_model=UserResponse, status_code=status.HTTP_200_OK)
async def me(
    user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
) -> UserResponse:
    # 1. Get user profile from DB
    result = await db.execute(select(User).where(User.id == user_id))

    existing_user = result.unique().scalar_one_or_none()
    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail='Not authorized'
        )

    # 2. Return user
    return existing_user


@router.put('/me', response_model=UserResponse, status_code=status.HTTP_200_OK)
async def update_me(
    body: UpdateProfileRequest,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail='User not found')

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(user, field, value)

    await db.flush()
    await db.refresh(user)
    return user


@router.get('/google', status_code=status.HTTP_200_OK)
async def google():
    params = urlencode(
        {
            'client_id': settings_auth.google_client_id,
            'redirect_uri': f'{settings_auth.backend_url}/api/v1/auth/google/callback',
            'scope': 'openid email profile',
            'response_type': 'code',
        }
    )

    return {'redirect_url': f'https://accounts.google.com/o/oauth2/v2/auth?{params}'}


@router.get('/google/callback')
async def google_callback(
    code: str, db: AsyncSession = Depends(get_db)
):
    # 1. Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            'https://oauth2.googleapis.com/token',
            data={
                'client_id': settings_auth.google_client_id,
                'client_secret': settings_auth.google_client_secret,
                'code': code,
                'redirect_uri': f'{settings_auth.backend_url}/api/v1/auth/google/callback',
                'grant_type': 'authorization_code',
            },
            headers={'Accept': 'application/json'},
        )
        access_token = token_resp.json()['access_token']

        # Step 2: Use access token to get user profile
        profile_resp = await client.get(
            'https://www.googleapis.com/oauth2/v2/userinfo',
            headers={'Authorization': f'Bearer {access_token}'},
        )
        google_profile = profile_resp.json()

    # 2. Check if user already exists in DB
    result = await db.execute(
        select(User).where(User.google_id == google_profile['id'])
    )

    user = result.scalar_one_or_none()
    if not user:
        # Check if email already exists
        result = await db.execute(
            select(User).where(User.email == google_profile['email'])
        )
        user = result.scalar_one_or_none()

    if not user:
        # Create the user
        user = User(
            email=google_profile['email'],
            google_id=google_profile['id'],
            full_name=google_profile['name'],
        )
        db.add(user)
        await db.flush()
    elif not user.google_id:
        # Existing user, link Google ID
        user.google_id = google_profile['id']

    # 3. Create token and redirect to frontend
    token = create_access_token(str(user.id))
    return RedirectResponse(
        url=f'{settings_auth.frontend_url}/auth/oauth-callback#token={token}'
    )


@router.get('/linkedin', status_code=status.HTTP_200_OK)
async def linkedin():
    params = urlencode(
        {
            'client_id': settings_auth.linkedin_client_id,
            'redirect_uri': f'{settings_auth.backend_url}/api/v1/auth/linkedin/callback',
            'scope': 'openid profile email',
            'response_type': 'code',
        }
    )

    return {'redirect_url': f'https://www.linkedin.com/oauth/v2/authorization?{params}'}


@router.get('/linkedin/callback')
async def linkedin_callback(
    code: str, db: AsyncSession = Depends(get_db)
):
    # 1. Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            'https://www.linkedin.com/oauth/v2/accessToken',
            data={
                'client_id': settings_auth.linkedin_client_id,
                'client_secret': settings_auth.linkedin_client_secret,
                'code': code,
                'redirect_uri': f'{settings_auth.backend_url}/api/v1/auth/linkedin/callback',
                'grant_type': 'authorization_code',
            },
            headers={
                'Accept': 'application/json',
                'Content-Type': 'application/x-www-form-urlencoded',
            },
        )
        access_token = token_resp.json()['access_token']

        # Step 2: Use access token to get user profile
        profile_resp = await client.get(
            'https://api.linkedin.com/v2/userinfo',
            headers={'Authorization': f'Bearer {access_token}'},
        )
        linkedin_profile = profile_resp.json()

    # 2. Check if user already exists in DB
    result = await db.execute(
        select(User).where(User.linkedin_id == linkedin_profile['sub'])
    )

    user = result.scalar_one_or_none()
    if not user:
        # Check if email already exists
        result = await db.execute(
            select(User).where(User.email == linkedin_profile['email'])
        )
        user = result.scalar_one_or_none()

    if not user:
        # Create the user
        user = User(
            email=linkedin_profile['email'],
            linkedin_id=linkedin_profile['sub'],
            full_name=linkedin_profile['name'],
        )
        db.add(user)
        await db.flush()
    elif not user.linkedin_id:
        # Existing user, link Linkedin ID
        user.linkedin_id = linkedin_profile['sub']

    # 3. Create token and redirect to frontend
    token = create_access_token(str(user.id))
    return RedirectResponse(
        url=f'{settings_auth.frontend_url}/auth/oauth-callback#token={token}'
    )


@router.get('/verify', status_code=status.HTTP_200_OK)
async def verify_email(token: str, db: AsyncSession = Depends(get_db)) -> dict:
    # Find user by token
    result = await db.execute(select(User).where(User.verification_token == token))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail='Invalid verification token'
        )

    # Reject expired tokens. The column is nullable to accommodate users
    # created before this column existed (pre-migration) — treat a null
    # expiry the same as "expired" rather than "never expires."
    if (
        user.verification_token_expires is None
        or user.verification_token_expires < datetime.now(UTC)
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail='Verification token expired'
        )

    # Mark as verified, clear the token + expiry so it can't be replayed
    user.is_verified = True
    user.verification_token = None
    user.verification_token_expires = None

    return {'message': 'Email verified successfully'}


@router.post('/resend-verification', status_code=status.HTTP_200_OK)
async def resend_verification(
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Issue a fresh verification token + email for the current user.

    - Silently no-ops if the user is already verified (prevents info leak
      about account state via a 400/409).
    - Rate-limited per-user to avoid Brevo-quota abuse on rapid clicks.
    """
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail='Not authenticated'
        )

    # No-op for already-verified users. We return 200 rather than 400 so
    # double-clicks on the banner right after verifying don't throw a scary
    # error at the user.
    if user.is_verified:
        return {'message': 'Email is already verified'}

    now = datetime.now(UTC)
    last = _last_resend_at.get(user_id)
    if last is not None:
        elapsed = (now - last).total_seconds()
        if elapsed < settings_auth.resend_verification_cooldown_seconds:
            retry_after = int(settings_auth.resend_verification_cooldown_seconds - elapsed)
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f'Please wait {retry_after}s before requesting another email',
            )

    # Rotate the token — even if the previous one was still valid, we want
    # the user's fresh email to point at a working link, and we want any
    # leaked earlier token to stop working.
    user.verification_token = secrets.token_urlsafe(32)
    user.verification_token_expires = now + timedelta(
        hours=settings_auth.verification_token_ttl_hours
    )

    await asyncio.to_thread(
        send_verification_email, user.email, user.verification_token
    )

    _last_resend_at[user_id] = now
    return {'message': 'Verification email sent'}


@router.post('/forgot-password', status_code=status.HTTP_200_OK)
async def forgot_password(
    background_tasks: BackgroundTasks,
    body: ForgotPasswordRequest, 
    db: AsyncSession = Depends(get_db)
) -> dict:
    # Find user by email
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user:
        _ = secrets.token_urlsafe(32) # match the existing-user path's CPU
        return {'message': 'Password reset link sent'}

    # Generate reset token and expiry
    reset_token = secrets.token_urlsafe(32)
    reset_expires = datetime.now(UTC) + timedelta(hours=1)

    # Mark token and expiry
    user.password_reset_token = reset_token
    user.password_reset_expires = reset_expires

    # Send email
    background_tasks.add_task(send_password_reset_email, user.email, reset_token)
    
    return {'message': 'Password reset link sent'}


@router.post('/reset-password', status_code=status.HTTP_200_OK)
async def reset_password(
    body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)
) -> dict:
    # Find user by token
    result = await db.execute(
        select(User).where(User.password_reset_token == body.token)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail='Invalid reset token')
    elif user.password_reset_expires < datetime.now(UTC):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail='Reset token expired')

    # Save new password, clear the token and expiry
    user.hashed_password = hash_password(body.new_password)
    user.password_reset_token = None
    user.password_reset_expires = None

    return {'message': 'Password reset successfully'}


@router.delete('/delete-account', status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(user_id: UUID = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)) -> None:
    # Find user by token
    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail='User not found')
    
    # Find sessions to delete
    result_sessions = await db.execute(
        select(Session).where(Session.user_id == user_id)
    )
    
    sessions = result_sessions.scalars().all()
    
    if sessions:
        # Find and delete user-related feedback
        result_feedback = await db.execute(
            select(Feedback).where(Feedback.session_id.in_([s.id for s in sessions]))
        )
        
        feedbacks = result_feedback.scalars().all()
        
        for feedback in feedbacks:
            await db.delete(feedback)
        
        # Find and delete all transcripts
        result_transcripts = await db.execute(
            select(Transcript).where(Transcript.session_id.in_([s.id for s in sessions]))
        )
        
        transcripts = result_transcripts.scalars().all()
        
        for transcript in transcripts:
            await db.delete(transcript)
        
        # Delete sessions
        for session in sessions:
            await db.delete(session)
    
    # Find CV(s) and delete
    result_cvs = await db.execute(
        select(CV).where(CV.user_id == user_id)
    )
    
    cvs = result_cvs.scalars().all()
    
    for cv in cvs:
        # Delete in Blob
        await asyncio.to_thread(delete_object, cv.s3_key)
        
        # Delete in DB
        await db.delete(cv)
    
    # Find subscription and delete
    result_sub = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    
    sub = result_sub.scalar_one_or_none()
    
    if sub:
        await db.delete(sub)
        await db.flush()
    
    # Delete user
    await db.delete(user)
