from datetime import UTC, datetime, timedelta
from uuid import UUID
import httpx
from api.deps import get_current_user_id
from fastapi import APIRouter, status, Depends, HTTPException
from services.email import send_password_reset_email, send_verification_email
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from schemas.auth import ForgotPasswordRequest, ResetPasswordRequest, TokenResponse, SignUp, LogIn, UserResponse
from core.security import hash_password, create_access_token, verify_password
from core.database import get_db
from models.user import User
from urllib.parse import urlencode
import secrets
from core.config import settings as settings_auth

router = APIRouter()

@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(new_user: SignUp, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    # 1. Check if email already taken
    result = await db.execute(select(User).where(User.email == new_user.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    # 2. Create the user
    user = User(
        email=new_user.email,
        hashed_password=hash_password(new_user.password),
        full_name=new_user.full_name,
        verification_token=secrets.token_urlsafe(32)
    )
    db.add(user)
    await db.flush()  # flush sends the INSERT to DB and populates user.id, but doesn't commit yet
    
    # 3. Send a verification email
    send_verification_email(user.email, user.verification_token)
    
    # 4. Create token and return
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)

@router.post("/login", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def login(user: LogIn, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    # 1. Check if user exists
    result = await db.execute(select(User).where(User.email == user.email))
    
    existing_user = result.scalar_one_or_none()
    if not existing_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email or Password incorrect")

    # 2. Verify password
    password_is_valid = verify_password(user.password, existing_user.hashed_password)
    if not password_is_valid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email or Password incorrect")
    
    # 3. Create token and return
    token = create_access_token(str(existing_user.id))
    return TokenResponse(access_token=token)

@router.get("/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def me(user_id: UUID = Depends(get_current_user_id), db:AsyncSession = Depends(get_db)) -> UserResponse:
    # 1. Get user profile from DB
    result = await db.execute(select(User).where(User.id == user_id))

    existing_user = result.scalar_one_or_none()
    if not existing_user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authorized")
    
    # 2. Return user
    return existing_user

@router.get("/google", status_code=status.HTTP_200_OK)
async def google():
    params = urlencode({
        "client_id": settings_auth.google_client_id,
        "redirect_uri": "http://localhost:8080/api/v1/auth/google/callback",
        "scope": "openid email profile",
        "response_type": "code",
    })
    
    return {"redirect_url": f"https://accounts.google.com/o/oauth2/v2/auth?{params}"}

@router.get("/google/callback", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def google_callback(code: str, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    # 1. Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": settings_auth.google_client_id,
                "client_secret": settings_auth.google_client_secret,
                "code": code,
                "redirect_uri": "http://localhost:8080/api/v1/auth/google/callback",
                "grant_type": "authorization_code"
            },
            headers={"Accept": "application/json"},
        )
        access_token = token_resp.json()["access_token"]

        # Step 2: Use access token to get user profile
        profile_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        google_profile = profile_resp.json()

    # 2. Check if user already exists in DB
    result = await db.execute(select(User).where(User.google_id == google_profile["id"]))
    
    user = result.scalar_one_or_none()
    if not user:
        # Check if email already exists
        result = await db.execute(select(User).where(User.email == google_profile["email"]))
        user = result.scalar_one_or_none()

    if not user:
        # Create the user
        user = User(
            email=google_profile["email"],
            google_id=google_profile["id"],
            full_name=google_profile["name"],
        )
        db.add(user)
        await db.flush()
    elif not user.google_id:
        # Existing user, link Google ID
        user.google_id = google_profile["id"]

    # 3. Create token and return
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)
    
@router.get("/linkedin", status_code=status.HTTP_200_OK)
async def linkedin():
    params = urlencode({
        "client_id": settings_auth.linkedin_client_id,
        "redirect_uri": "http://localhost:8080/api/v1/auth/linkedin/callback",
        "scope": "openid profile email",
        "response_type": "code",
    })
    
    return {"redirect_url": f"https://www.linkedin.com/oauth/v2/authorization?{params}"}

@router.get("/linkedin/callback", response_model=TokenResponse, status_code=status.HTTP_200_OK)
async def linkedin_callback(code: str, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    # 1. Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://www.linkedin.com/oauth/v2/accessToken",
            data={
                "client_id": settings_auth.linkedin_client_id,
                "client_secret": settings_auth.linkedin_client_secret,
                "code": code,
                "redirect_uri": "http://localhost:8080/api/v1/auth/linkedin/callback",
                "grant_type": "authorization_code"
            },
            headers={
                "Accept": "application/json", 
                "Content-Type": "application/x-www-form-urlencoded"
            },
        )
        access_token = token_resp.json()["access_token"]

        # Step 2: Use access token to get user profile
        profile_resp = await client.get(
            "https://api.linkedin.com/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        linkedin_profile = profile_resp.json()

    # 2. Check if user already exists in DB
    result = await db.execute(select(User).where(User.linkedin_id == linkedin_profile["sub"]))
    
    user = result.scalar_one_or_none()
    if not user:
        # Check if email already exists
        result = await db.execute(select(User).where(User.email == linkedin_profile["email"]))
        user = result.scalar_one_or_none()

    if not user:
        # Create the user
        user = User(
            email=linkedin_profile["email"],
            linkedin_id=linkedin_profile["sub"],
            full_name=linkedin_profile["name"],
        )
        db.add(user)
        await db.flush()
    elif not user.linkedin_id:
        # Existing user, link Linkedin ID
        user.linkedin_id = linkedin_profile["sub"]

    # 3. Create token and return
    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)

@router.get("/verify", status_code=status.HTTP_200_OK)
async def verify_email(token: str, db: AsyncSession = Depends(get_db)) -> dict:
    # Find user by token
    result = await db.execute(select(User).where(User.verification_token == token))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid verification token")

    # Mark as verified, clear the token
    user.is_verified = True
    user.verification_token = None

    return {"message": "Email verified successfully"}

@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)) -> dict:
    # Find user by email
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    
    if not user:
        return {"message": "Password reset link sent"}
    
    # Generate reset token and expiry
    reset_token = secrets.token_urlsafe(32)
    reset_expires = datetime.now(UTC) + timedelta(hours=1)
    
    # Mark token and expiry
    user.password_reset_token = reset_token
    user.password_reset_expires = reset_expires
    
    # Send email
    send_password_reset_email(to_email=user.email, token=reset_token)
    
    return {"message": "Password reset link sent"}

@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)) -> dict:
    # Find user by token
    result = await db.execute(select(User).where(User.password_reset_token == body.token))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Invalid reset token")
    elif user.password_reset_expires < datetime.now(UTC):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Reset token expired")
    
    # Save new password, clear the token and expiry
    user.hashed_password = hash_password(body.new_password)
    user.password_reset_token = None
    user.password_reset_expires = None

    return {"message": "Password reset successfully"}
