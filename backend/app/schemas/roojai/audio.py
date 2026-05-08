from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class AudioSampleCreate(BaseModel):
    recorded_at: datetime
    zone_offset: str | None = None
    sample_duration_sec: Decimal = Field(gt=0)
    trigger: str | None = None
    ambient_db: Decimal | None = None
    was_skipped: bool = False
    environment_quality: str | None = None
    pitch_mean: Decimal | None = None
    energy_rms: Decimal | None = None
    silence_ratio: Decimal | None = None
    breathing_rate: Decimal | None = None
    valence_score: Decimal | None = Field(None, ge=0, le=1)
    arousal_score: Decimal | None = Field(None, ge=0, le=1)
    model_version: str | None = None


class AudioSampleRead(BaseModel):
    id: UUID
    user_id: UUID
    recorded_at: datetime
    zone_offset: str | None
    sample_duration_sec: Decimal
    trigger: str | None
    ambient_db: Decimal | None
    was_skipped: bool
    environment_quality: str | None
    pitch_mean: Decimal | None
    energy_rms: Decimal | None
    silence_ratio: Decimal | None
    breathing_rate: Decimal | None
    valence_score: Decimal | None
    arousal_score: Decimal | None
    model_version: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class AudioDailySummaryRead(BaseModel):
    id: UUID
    user_id: UUID
    date: date
    sample_count: int | None
    usable_count: int | None
    skipped_count: int | None
    avg_valence: Decimal | None
    avg_arousal: Decimal | None
    avg_pitch_mean: Decimal | None
    avg_energy_rms: Decimal | None
    avg_silence_ratio: Decimal | None
    avg_breathing_rate: Decimal | None

    model_config = {"from_attributes": True}
