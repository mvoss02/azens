from typing import Literal

from pydantic import BaseModel, EmailStr

from models.enums import Language


class WaitlistRequest(BaseModel):
    email: EmailStr
    source: str
    language: Language | None = None


class WaitlistResponse(BaseModel):
    status: Literal['joined']
