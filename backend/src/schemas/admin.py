from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from models.enums import Topic, Difficulty, SeniorityLevel, Language

class QuestionRequest(BaseModel):
    question: str
    answer: str
    topic: Topic
    difficulty: Difficulty
    seniority_level: SeniorityLevel
    language: Language

class QuestionResponse(BaseModel):
    model_config = {'from_attributes': True}
    
    id: UUID
    question: str
    answer: str
    topic: Topic
    difficulty: Difficulty
    seniority_level: SeniorityLevel
    language: Language
    created_at: datetime
    updated_at: datetime | None
    is_active: bool

class QuestionUpdate(BaseModel):
    question: str | None = None
    answer: str | None = None
    topic: Topic | None = None
    difficulty: Difficulty | None = None
    seniority_level: SeniorityLevel | None = None
    language: Language | None = None
    
