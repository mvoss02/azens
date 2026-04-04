from fastapi import APIRouter, status, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from schemas.auth import TokenResponse, SignUp, LogIn
from core.security import hash_password, create_access_token, verify_password
from core.database import get_db
from models.user import User

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
    )
    db.add(user)
    await db.flush()  # flush sends the INSERT to DB and populates user.id, but doesn't commit yet

    # 3. Create token and return
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
