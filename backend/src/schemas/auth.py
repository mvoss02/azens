from uuid import UUID

from models.enums import Language, SeniorityLevel
from pydantic import BaseModel, EmailStr


class SignUp(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None
    
class LogIn(BaseModel):
    email: EmailStr
    password: str
    
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    
class UserResponse(BaseModel):
    model_config = {'from_attributes': True}
    
    id: UUID
    email: EmailStr
    full_name: str | None
    seniority_level: SeniorityLevel | None
    preferred_language: Language | None
    is_verified: bool
    
class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    
class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
