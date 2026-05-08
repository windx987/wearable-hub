from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class QuestionnaireSubmit(BaseModel):
    answers: list[dict[str, Any]]
    scenario: str | None = None


class QuestionRead(BaseModel):
    id: str
    text: str


class QuestionnaireTodayRead(BaseModel):
    scenario: str
    questions: list[QuestionRead]
    already_submitted: bool
    context_snapshot: dict[str, Any] | None = None


class QuestionnaireResponseRead(BaseModel):
    id: UUID
    user_id: UUID
    date: date
    scenario: str
    answers: list[dict[str, Any]]
    context_snapshot: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}
