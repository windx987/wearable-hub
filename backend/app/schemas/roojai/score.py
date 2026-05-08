from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class ScoreComputeRequest(BaseModel):
    target_date: date | None = None


class DailyScoreRead(BaseModel):
    id: UUID
    user_id: UUID
    date: date
    score: Decimal
    hrv_score: Decimal | None
    sleep_score: Decimal | None
    audio_score: Decimal | None
    survey_score: Decimal | None
    hrv_weight: Decimal | None
    sleep_weight: Decimal | None
    audio_weight: Decimal | None
    survey_weight: Decimal | None
    created_at: datetime

    model_config = {"from_attributes": True}
