from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class InsightRequest(BaseModel):
    target_date: date | None = None


class InsightRead(BaseModel):
    insight: str
    recommendations: list[str]
    mood_label: str
    score_interpretation: str
    generated_at: datetime


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


class ChatResponse(BaseModel):
    reply: str
    tools_used: list[str] = []
