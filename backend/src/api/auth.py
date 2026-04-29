import asyncio
import logging
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from uuid import UUID

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_current_user_id
from core.config import settings as settings_auth
from core.database import get_db
from core.rate_limit import limiter
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
from services.oauth_state import consume_state, create_state
from services.s3 import delete_object_best_effort

logger = logging.getLogger(__name__)

router = APIRouter()


_last_resend_at: dict[UUID, datetime] = {}
_DUMMY_PASSWORD_HASH = hash_password('moritz-is-great')  # any placeholder string


@router.post(
    '/signup', response_model=TokenResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit('10/hour')
async def signup(
    request: Request,
    new_user: SignUp,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
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
    await asyncio.to_thread(
        send_verification_email, user.email, user.verification_token
    )

    # 4. Create token and return
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)


@router.post('/login', response_model=TokenResponse, status_code=status.HTTP_200_OK)
# 20/hour is an aggressive-but-not-annoying ceiling for a real user who
# fat-fingers their password a few times. Behind it, bcrypt still costs
# ~150ms per attempt — so even within the limit, an attacker is CPU-bound.
@limiter.limit('20/hour')
async def login(
    request: Request,
    user: LogIn,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
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
    # state: short-lived random token bound to this attempt. The callback
    # below refuses any request whose `state` isn't one we issued here —
    # blocks OAuth login-CSRF (attacker-generated `code` replayed through
    # the victim's browser). See services/oauth_state.py for the rationale.
    params = urlencode(
        {
            'client_id': settings_auth.google_client_id,
            'redirect_uri': f'{settings_auth.backend_url}/api/v1/auth/google/callback',
            'scope': 'openid email profile',
            'response_type': 'code',
            'state': create_state(),
        }
    )

    return {'redirect_url': f'https://accounts.google.com/o/oauth2/v2/auth?{params}'}


@router.get('/google/callback')
async def google_callback(
    code: str,
    state: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    # CSRF check: reject any callback whose state wasn't issued by our
    # /auth/google endpoint (or was already used / expired). consume_state
    # is atomic single-use — a second callback with the same state
    # immediately returns False.
    if not consume_state(state):
        logger.warning('Google OAuth callback with missing/invalid state')
        return RedirectResponse(
            url=f'{settings_auth.frontend_url}/auth/login?error=oauth_failed'
        )

    # All failure modes below bounce the user back to /auth/login with a
    # generic error. We don't surface Google's internal error codes to the
    # UI — they're unhelpful to humans and sometimes leak info about the
    # auth provider's state. The real cause is logged server-side.
    oauth_failed_redirect = RedirectResponse(
        url=f'{settings_auth.frontend_url}/auth/login?error=oauth_failed'
    )

    # 1. Exchange code for access token
    async with httpx.AsyncClient() as client:
        try:
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
            token_resp.raise_for_status()
            token_data = token_resp.json()
        except httpx.HTTPError as e:
            logger.warning('Google token exchange failed: %s', e)
            return oauth_failed_redirect

        access_token = token_data.get('access_token')
        if not access_token:
            logger.warning(
                'Google token exchange returned no access_token: %s', token_data
            )
            return oauth_failed_redirect

        # 2. Use access token to get user profile
        try:
            profile_resp = await client.get(
                'https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f'Bearer {access_token}'},
            )
            profile_resp.raise_for_status()
            google_profile = profile_resp.json()
        except httpx.HTTPError as e:
            logger.warning('Google profile fetch failed: %s', e)
            return oauth_failed_redirect

    # Validate the fields we need. Google should always return both, but
    # guard in case the API evolves or the response body is an error shape.
    if not google_profile.get('id') or not google_profile.get('email'):
        logger.warning('Google userinfo missing id or email: %s', google_profile)
        return oauth_failed_redirect

    # Only trust emails Google has verified. Without this, a user with an
    # unverified secondary email on their Google account could sign in as
    # if we'd verified it ourselves, defeating the is_verified=True shortcut
    # we apply to new OAuth users. Default to False on missing field.
    # Note: Google v2 userinfo uses `verified_email` (vs `email_verified` on OIDC).
    if not google_profile.get('verified_email', False):
        logger.warning('Google email not verified: %s', google_profile.get('email'))
        return oauth_failed_redirect

    # 3. Existing Google user → log them in
    result = await db.execute(
        select(User).where(User.google_id == google_profile['id'])
    )
    user = result.scalar_one_or_none()
    if user:
        token = create_access_token(str(user.id))
        return RedirectResponse(
            url=f'{settings_auth.frontend_url}/auth/oauth-callback#token={token}'
        )

    # 4. Email is already registered (password user or different OAuth provider).
    # Refuse to silently link — forces the user to sign in the original way.
    result = await db.execute(select(User).where(User.email == google_profile['email']))
    user = result.scalar_one_or_none()
    if user:
        return RedirectResponse(
            url=f'{settings_auth.frontend_url}/auth/login?error=email_taken'
        )

    # 5. Brand-new user → create with is_verified=True (Google already verified)
    user = User(
        email=google_profile['email'],
        google_id=google_profile['id'],
        full_name=google_profile.get('name'),
        is_verified=True,
    )
    db.add(user)
    await db.flush()
    # Explicit commit: we're about to hand the browser a JWT for this
    # user. If the get_db post-yield commit loses (disk full, constraint
    # violation we didn't catch), the user would have a valid token for a
    # non-existent DB row — every subsequent request 401s. Commit before
    # minting the token so at least the rows agree.
    await db.commit()

    token = create_access_token(str(user.id))
    return RedirectResponse(
        url=f'{settings_auth.frontend_url}/auth/oauth-callback#token={token}'
    )


@router.get('/linkedin', status_code=status.HTTP_200_OK)
async def linkedin():
    # state: same CSRF protection as /auth/google. See services/oauth_state.py.
    params = urlencode(
        {
            'client_id': settings_auth.linkedin_client_id,
            'redirect_uri': f'{settings_auth.backend_url}/api/v1/auth/linkedin/callback',
            'scope': 'openid profile email',
            'response_type': 'code',
            'state': create_state(),
        }
    )

    return {'redirect_url': f'https://www.linkedin.com/oauth/v2/authorization?{params}'}


@router.get('/linkedin/callback')
async def linkedin_callback(
    code: str,
    state: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    oauth_failed_redirect = RedirectResponse(
        url=f'{settings_auth.frontend_url}/auth/login?error=oauth_failed'
    )

    # CSRF check — reject callbacks whose state wasn't issued by /auth/linkedin.
    if not consume_state(state):
        logger.warning('LinkedIn OAuth callback with missing/invalid state')
        return oauth_failed_redirect

    # 1. Exchange code for access token
    async with httpx.AsyncClient() as client:
        try:
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
            token_resp.raise_for_status()
            token_data = token_resp.json()
        except httpx.HTTPError as e:
            logger.warning('LinkedIn token exchange failed: %s', e)
            return oauth_failed_redirect

        access_token = token_data.get('access_token')
        if not access_token:
            logger.warning(
                'LinkedIn token exchange returned no access_token: %s', token_data
            )
            return oauth_failed_redirect

        # 2. Use access token to get user profile
        try:
            profile_resp = await client.get(
                'https://api.linkedin.com/v2/userinfo',
                headers={'Authorization': f'Bearer {access_token}'},
            )
            profile_resp.raise_for_status()
            linkedin_profile = profile_resp.json()
        except httpx.HTTPError as e:
            logger.warning('LinkedIn profile fetch failed: %s', e)
            return oauth_failed_redirect

    # LinkedIn's OIDC userinfo returns 'sub' (unique id) and 'email'. Both
    # are required; bail if either is missing.
    if not linkedin_profile.get('sub') or not linkedin_profile.get('email'):
        logger.warning('LinkedIn userinfo missing sub or email: %s', linkedin_profile)
        return oauth_failed_redirect

    # Only trust verified emails — same argument as the Google branch.
    # LinkedIn OIDC uses `email_verified` (the OIDC standard field name).
    if not linkedin_profile.get('email_verified', False):
        logger.warning('LinkedIn email not verified: %s', linkedin_profile.get('email'))
        return oauth_failed_redirect

    # 3. Existing LinkedIn user → log them in
    result = await db.execute(
        select(User).where(User.linkedin_id == linkedin_profile['sub'])
    )
    user = result.scalar_one_or_none()
    if user:
        token = create_access_token(str(user.id))
        return RedirectResponse(
            url=f'{settings_auth.frontend_url}/auth/oauth-callback#token={token}'
        )

    # 4. Email is already registered (password user or different OAuth provider).
    # Refuse to silently link — forces the user to sign in the original way.
    result = await db.execute(
        select(User).where(User.email == linkedin_profile['email'])
    )
    user = result.scalar_one_or_none()
    if user:
        return RedirectResponse(
            url=f'{settings_auth.frontend_url}/auth/login?error=email_taken'
        )

    # 5. Brand-new user → create with is_verified=True (LinkedIn already verified)
    user = User(
        email=linkedin_profile['email'],
        linkedin_id=linkedin_profile['sub'],
        full_name=linkedin_profile.get('name'),
        is_verified=True,
    )
    db.add(user)
    await db.flush()
    # Commit before minting the JWT — same reasoning as google_callback.
    await db.commit()

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
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail='Not authenticated')

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
            retry_after = int(
                settings_auth.resend_verification_cooldown_seconds - elapsed
            )
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
# Tight per-IP cap: each triggers an SMTP send. An attacker could otherwise
# harass arbitrary users with reset emails OR burn our Brevo quota.
@limiter.limit('5/hour')
async def forgot_password(
    request: Request,
    background_tasks: BackgroundTasks,
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    # Find user by email
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user:
        _ = secrets.token_urlsafe(32)  # match the existing-user path's CPU
        return {'message': 'Password reset link sent'}

    # Generate reset token and expiry
    reset_token = secrets.token_urlsafe(32)
    reset_expires = datetime.now(UTC) + timedelta(hours=settings_auth.password_reset_token_ttl_hours)

    # Mark token and expiry
    user.password_reset_token = reset_token
    user.password_reset_expires = reset_expires

    # Send email
    background_tasks.add_task(send_password_reset_email, user.email, reset_token)

    return {'message': 'Password reset link sent'}


@router.post('/reset-password', status_code=status.HTTP_200_OK)
# Prevents brute-forcing the password_reset_token URL parameter. 32-byte
# URL-safe tokens are effectively unguessable, but the limit is cheap
# insurance and also bounds the CPU cost of bcrypt-hashing new passwords.
@limiter.limit('20/hour')
async def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
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
async def delete_account(
    background_tasks: BackgroundTasks,
    user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> None:
    # Design: all DB deletes happen inside a single transaction (via get_db
    # auto-commit at response end). S3 cleanup is deferred to a BackgroundTask
    # so that the DB write succeeds first and the user's GDPR right-to-erasure
    # is satisfied even if S3 is slow or flaky. If an S3 delete fails, it's
    # logged and the orphan is left for a future janitor sweep — better than
    # "we deleted half your files and told you it worked" or "we can't delete
    # your account because S3 is down."
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail='User not found')

    # Collect S3 keys BEFORE deleting the CV rows — after `db.delete(cv)` the
    # ORM objects are expired and reading `cv.s3_key` would re-query (or fail).
    result_cvs = await db.execute(select(CV).where(CV.user_id == user_id))
    cvs = result_cvs.scalars().all()
    s3_keys_to_delete = [cv.s3_key for cv in cvs]

    # Delete session-scoped children first (feedback + transcripts), then
    # sessions themselves. FK constraints would complain otherwise.
    result_sessions = await db.execute(
        select(Session).where(Session.user_id == user_id)
    )
    sessions = result_sessions.scalars().all()

    if sessions:
        session_ids = [s.id for s in sessions]

        result_feedback = await db.execute(
            select(Feedback).where(Feedback.session_id.in_(session_ids))
        )
        for feedback in result_feedback.scalars().all():
            await db.delete(feedback)

        result_transcripts = await db.execute(
            select(Transcript).where(Transcript.session_id.in_(session_ids))
        )
        for transcript in result_transcripts.scalars().all():
            await db.delete(transcript)

        for session in sessions:
            await db.delete(session)

    # Delete CV rows (S3 objects scheduled for cleanup below).
    for cv in cvs:
        await db.delete(cv)

    # Delete subscription, if any.
    result_sub = await db.execute(
        select(Subscription).where(Subscription.user_id == user_id)
    )
    sub = result_sub.scalar_one_or_none()
    if sub:
        await db.delete(sub)

    # Delete user — the commit happens automatically when the route returns
    # (via get_db's finally block).
    await db.delete(user)

    # Schedule best-effort S3 cleanup. BackgroundTasks fire after the response
    # is sent AND after get_db commits, so by the time these run the DB state
    # is durable. Each helper call logs + swallows on failure.
    for s3_key in s3_keys_to_delete:
        background_tasks.add_task(delete_object_best_effort, s3_key)
