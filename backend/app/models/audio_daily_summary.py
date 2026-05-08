from datetime import date
from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped

from app.database import BaseDbModel
from app.mappings import FKUser, PrimaryKey, numeric_6_3


class AudioDailySummary(BaseDbModel):
    __tablename__ = "audio_daily_summary"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_audio_daily_summary_user_date"),)

    id: Mapped[PrimaryKey[UUID]]
    user_id: Mapped[FKUser]
    date: Mapped[date]

    sample_count: Mapped[int | None]
    usable_count: Mapped[int | None]
    skipped_count: Mapped[int | None]

    avg_valence: Mapped[numeric_6_3 | None]
    avg_arousal: Mapped[numeric_6_3 | None]
    avg_pitch_mean: Mapped[numeric_6_3 | None]
    avg_energy_rms: Mapped[numeric_6_3 | None]
    avg_silence_ratio: Mapped[numeric_6_3 | None]
    avg_breathing_rate: Mapped[numeric_6_3 | None]
