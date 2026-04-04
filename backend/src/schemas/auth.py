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
    