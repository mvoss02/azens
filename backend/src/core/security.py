from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from core.config import settings as settings_auth

ALGORITHM = 'HS256'


def hash_password(password: str) -> str:
    """
    Signup route calls this. It is taking plain text and returns hash for DB storage.
    """
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str | None) -> bool:
    """
    Login calls this — checks if the password matches.
    """
    # OAuth-only users have no password hash. Return False (= "no match")
    # instead of crashing on None.encode().
    if not isinstance(hashed, str):
        return False
          
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_access_token(subject: str) -> str:
    """
    Login route calls this — creates a JWT with the user's ID baked in.
    """
    payload = {
        'sub': subject,  # subject — who this token is for
        'exp': datetime.now(UTC) + timedelta(minutes=30),  # expiration
        'type': 'access',  # so we can distinguish access vs refresh tokens
    }
    token = jwt.encode(payload, settings_auth.secret_key, algorithm=ALGORITHM)
    return token


def decode_token(token: str) -> str | None:
    """
    Protected routes call this — returns user ID or None if invalid.
    """
    try:
        data = jwt.decode(token, settings_auth.secret_key, algorithms=[ALGORITHM])
        user_id = data['sub']  # "user-uuid-here"
        return user_id
    except JWTError:
        return None
