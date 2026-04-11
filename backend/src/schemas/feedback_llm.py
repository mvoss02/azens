"""Pydantic schemas for LLM structured output (not API responses)."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

# ── CV screener feedback ──────────────────────────────────────────────────────

class CategoryScores(BaseModel):
    communication_clarity: int = Field(..., ge=1, le=10)
    technical_accuracy: int = Field(..., ge=1, le=10)
    structure: int = Field(..., ge=1, le=10)
    confidence: int = Field(..., ge=1, le=10)
    depth_of_experience: int = Field(..., ge=1, le=10)


class CVScreenFeedback(BaseModel):
    overall_score: int = Field(..., ge=1, le=10)
    category_scores: CategoryScores
    strengths: list[str] = Field(..., min_length=1, max_length=5)
    weaknesses: list[str] = Field(..., min_length=1, max_length=5)
    recommendations: list[str] = Field(..., min_length=1, max_length=5)
    summary: str


# ── Knowledge drill feedback ──────────────────────────────────────────────────

class QuestionEvaluation(BaseModel):
    question_id: UUID
    topic: str
    verdict: Literal['correct', 'partial', 'wrong']
    explanation: str


class KnowledgeDrillFeedback(BaseModel):
    evaluations: list[QuestionEvaluation]
    overall_summary: str
