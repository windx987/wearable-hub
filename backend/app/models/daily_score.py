from datetime import date
from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import FKUser, PrimaryKey, numeric_5_2


class DailyScore(BaseDbModel):
    __tablename__ = "daily_score"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_daily_score_user_date"),)

    id: Mapped[PrimaryKey[UUID]]
    user_id: Mapped[FKUser]
    date: Mapped[date]

    score: Mapped[numeric_5_2]

    hrv_score: Mapped[numeric_5_2 | None]
    sleep_score: Mapped[numeric_5_2 | None]
    audio_score: Mapped[numeric_5_2 | None]
    survey_score: Mapped[numeric_5_2 | None]

    hrv_weight: Mapped[numeric_5_2 | None]
    sleep_weight: Mapped[numeric_5_2 | None]
    audio_weight: Mapped[numeric_5_2 | None]
    survey_weight: Mapped[numeric_5_2 | None]
