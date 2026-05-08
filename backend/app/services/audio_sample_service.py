from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audio_daily_summary import AudioDailySummary
from app.models.audio_sample import AudioSample
from app.models.data_point_series import DataPointSeries
from app.models.series_type_definition import SeriesTypeDefinition
from app.schemas.roojai.audio import AudioSampleCreate

_NOISE_THRESHOLD_DB = Decimal("70.0")
_NOISE_THRESHOLD_ANC_DB = Decimal("85.0")
_WATCH_WINDOW_MINUTES = 5


def _resolve_environment_quality(
    db: Session,
    user_id: UUID,
    recorded_at,
    ambient_db: Decimal | None,
    was_skipped: bool,
) -> str:
    if was_skipped:
        return "skipped"

    watch_db = _get_watch_db(db, user_id, recorded_at)
    effective_db = watch_db if watch_db is not None else ambient_db

    if effective_db is None:
        return "clean"

    anc_active = _is_anc_active(db, user_id, recorded_at)
    threshold = _NOISE_THRESHOLD_ANC_DB if anc_active else _NOISE_THRESHOLD_DB

    return "noisy" if effective_db > threshold else "clean"


def _get_watch_db(db: Session, user_id: UUID, recorded_at) -> Decimal | None:
    window_start = recorded_at - timedelta(minutes=_WATCH_WINDOW_MINUTES)
    window_end = recorded_at + timedelta(minutes=_WATCH_WINDOW_MINUTES)

    result = (
        db.execute(
            select(func.avg(DataPointSeries.value))
            .join(SeriesTypeDefinition, DataPointSeries.series_type_definition_id == SeriesTypeDefinition.id)
            .where(
                SeriesTypeDefinition.code == "environmental_audio_exposure",
                DataPointSeries.recorded_at.between(window_start, window_end),
            )
        )
        .scalar()
    )
    return Decimal(str(result)) if result is not None else None


def _is_anc_active(db: Session, user_id: UUID, recorded_at) -> bool:
    window_start = recorded_at - timedelta(minutes=_WATCH_WINDOW_MINUTES)
    window_end = recorded_at + timedelta(minutes=_WATCH_WINDOW_MINUTES)

    result = (
        db.execute(
            select(func.avg(DataPointSeries.value))
            .join(SeriesTypeDefinition, DataPointSeries.series_type_definition_id == SeriesTypeDefinition.id)
            .where(
                SeriesTypeDefinition.code == "environmental_sound_reduction",
                DataPointSeries.recorded_at.between(window_start, window_end),
            )
        )
        .scalar()
    )
    return result is not None and Decimal(str(result)) > Decimal("10.0")


class AudioSampleService:
    def create(self, db: Session, user_id: UUID, payload: AudioSampleCreate) -> AudioSample:
        environment_quality = payload.environment_quality or _resolve_environment_quality(
            db,
            user_id,
            payload.recorded_at,
            payload.ambient_db,
            payload.was_skipped,
        )

        sample = AudioSample(
            id=uuid4(),
            user_id=user_id,
            recorded_at=payload.recorded_at,
            zone_offset=payload.zone_offset,
            sample_duration_sec=payload.sample_duration_sec,
            trigger=payload.trigger,
            ambient_db=payload.ambient_db,
            was_skipped=payload.was_skipped,
            environment_quality=environment_quality,
            pitch_mean=payload.pitch_mean,
            energy_rms=payload.energy_rms,
            silence_ratio=payload.silence_ratio,
            breathing_rate=payload.breathing_rate,
            valence_score=payload.valence_score,
            arousal_score=payload.arousal_score,
            model_version=payload.model_version,
        )
        db.add(sample)
        db.commit()
        db.refresh(sample)
        return sample

    def list_for_user(
        self,
        db: Session,
        user_id: UUID,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 100,
    ) -> list[AudioSample]:
        query = select(AudioSample).where(AudioSample.user_id == user_id)
        if date_from:
            query = query.where(AudioSample.recorded_at >= datetime(date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc))
        if date_to:
            query = query.where(AudioSample.recorded_at < datetime(date_to.year, date_to.month, date_to.day + 1, tzinfo=timezone.utc))
        query = query.order_by(AudioSample.recorded_at.desc()).limit(limit)
        return list(db.execute(query).scalars().all())

    def aggregate_daily(self, db: Session, user_id: UUID, target_date: date) -> AudioDailySummary | None:
        day_start = target_date
        day_end = target_date + timedelta(days=1)

        rows = db.execute(
            select(AudioSample).where(
                AudioSample.user_id == user_id,
                AudioSample.recorded_at >= day_start,
                AudioSample.recorded_at < day_end,
            )
        ).scalars().all()

        if not rows:
            return None

        usable = [r for r in rows if not r.was_skipped and r.environment_quality != "noisy"]

        def _avg(vals: list) -> Decimal | None:
            clean = [v for v in vals if v is not None]
            if not clean:
                return None
            return Decimal(str(sum(clean) / len(clean)))

        summary_data = {
            "user_id": user_id,
            "date": target_date,
            "sample_count": len(rows),
            "usable_count": len(usable),
            "skipped_count": sum(1 for r in rows if r.was_skipped),
            "avg_valence": _avg([r.valence_score for r in usable]),
            "avg_arousal": _avg([r.arousal_score for r in usable]),
            "avg_pitch_mean": _avg([r.pitch_mean for r in usable]),
            "avg_energy_rms": _avg([r.energy_rms for r in usable]),
            "avg_silence_ratio": _avg([r.silence_ratio for r in usable]),
            "avg_breathing_rate": _avg([r.breathing_rate for r in usable]),
        }

        existing = db.execute(
            select(AudioDailySummary).where(
                AudioDailySummary.user_id == user_id,
                AudioDailySummary.date == target_date,
            )
        ).scalar_one_or_none()

        if existing:
            for k, v in summary_data.items():
                setattr(existing, k, v)
            db.commit()
            db.refresh(existing)
            return existing

        summary = AudioDailySummary(id=uuid4(), **summary_data)
        db.add(summary)
        db.commit()
        db.refresh(summary)
        return summary


audio_sample_service = AudioSampleService()
