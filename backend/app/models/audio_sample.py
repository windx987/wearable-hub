from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import BaseDbModel
from app.mappings import FKUser, PrimaryKey, numeric_6_3, str_10, str_16, str_32


class AudioSample(BaseDbModel):
    __tablename__ = "audio_sample"
    __table_args__ = (Index("ix_audio_sample_user_recorded_at", "user_id", "recorded_at"),)

    id: Mapped[PrimaryKey[UUID]]
    user_id: Mapped[FKUser]
    recorded_at: Mapped[datetime]
    zone_offset: Mapped[str_10 | None]
    sample_duration_sec: Mapped[numeric_6_3]

    trigger: Mapped[str_32 | None]
    ambient_db: Mapped[numeric_6_3 | None]
    was_skipped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    environment_quality: Mapped[str_16 | None]

    pitch_mean: Mapped[numeric_6_3 | None]
    energy_rms: Mapped[numeric_6_3 | None]
    silence_ratio: Mapped[numeric_6_3 | None]
    breathing_rate: Mapped[numeric_6_3 | None]
    valence_score: Mapped[numeric_6_3 | None]
    arousal_score: Mapped[numeric_6_3 | None]
    model_version: Mapped[str | None] = mapped_column(nullable=True)
