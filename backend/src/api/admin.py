from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_admin_user_id
from core.database import get_db
from models.enums import Difficulty, Language, SeniorityLevel, Topic
from models.question import Question
from schemas.admin import QuestionRequest, QuestionResponse, QuestionUpdate

router = APIRouter()

@router.get("/questions", response_model=list[QuestionResponse], status_code=status.HTTP_200_OK)
async def get_questions(seniority_level: SeniorityLevel | None = None, language: Language | None = None, topic: Topic | None = None, difficulty: Difficulty | None = None, admin_id: UUID = Depends(get_admin_user_id), db: AsyncSession = Depends(get_db)) -> QuestionResponse:
    query = select(Question).order_by(Question.created_at.desc())
    if seniority_level:
        query = query.where(Question.seniority_level == seniority_level)
    if language:
        query = query.where(Question.language == language)
    if topic:
        query = query.where(Question.topic == topic)
    if difficulty:
        query = query.where(Question.difficulty == difficulty)

    result = await db.execute(query)
    return result.scalars().all()

@router.post("/questions", response_model=QuestionResponse, status_code=status.HTTP_201_CREATED)
async def post_questions(body: QuestionRequest, admin_id: UUID = Depends(get_admin_user_id), db: AsyncSession = Depends(get_db)) -> QuestionResponse:
    question = Question(**body.model_dump())
    db.add(question)
    await db.flush()
    await db.refresh(question)  # re-reads the object from DB, including updated_at
    return question

@router.put("/questions/{question_id}", response_model=QuestionResponse, status_code=status.HTTP_200_OK)
async def update_questions(question_id: UUID, body: QuestionUpdate, admin_id: UUID = Depends(get_admin_user_id), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Question).where(Question.id == question_id))
    question = result.scalar_one_or_none()

    if not question:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Question not found")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(question, field, value)

    await db.flush()
    await db.refresh(question)  # re-reads the object from DB, including updated_at
    return question

@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_questions(question_id: UUID, admin_id: UUID = Depends(get_admin_user_id), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Question).where(Question.id == question_id))
    question = result.scalar_one_or_none()

    if not question:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Question not found")

    await db.delete(question)
