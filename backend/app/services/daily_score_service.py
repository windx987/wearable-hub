from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from logging import getLogger
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.audio_daily_summary import AudioDailySummary
from app.models.daily_score import DailyScore
from app.models.data_point_series import DataPointSeries
from app.models.data_source import DataSource
from app.models.questionnaire_response import QuestionnaireResponse
from app.models.series_type_definition import SeriesTypeDefinition
from app.services.scores.sleep_service import sleep_score_service
from app.utils.exceptions import ResourceNotFoundError

logger = getLogger(__name__)

_BASE_WEIGHTS: dict[str, float] = {
    "hrv": 0.40,
    "sleep": 0.25,
    "audio": 0.20,
    "survey": 0.15,
}
_RMSSD_BASELINE_DAYS = 30


def _get_rmssd_today(db: Session, user_id: UUID, target_date: date) -> Decimal | None:
    day_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)
    result = db.execute(
        select(func.avg(DataPointSeries.value))
        .join(DataSource, DataPointSeries.data_source_id == DataSource.id)
        .join(SeriesTypeDefinition, DataPointSeries.series_type_definition_id == SeriesTypeDefinition.id)
        .where(
            DataSource.user_id == user_id,
            SeriesTypeDefinition.code == "heart_rate_variability_rmssd",
            DataPointSeries.recorded_at >= day_start,
            DataPointSeries.recorded_at < day_end,
        )
    ).scalar()
    return Decimal(str(result)) if result is not None else None


def _get_rmssd_baseline(db: Session, user_id: UUID, target_date: date) -> Decimal | None:
    window_end = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    window_start = window_end - timedelta(days=_RMSSD_BASELINE_DAYS)
    result = db.execute(
        select(func.avg(DataPointSeries.value))
        .join(DataSource, DataPointSeries.data_source_id == DataSource.id)
        .join(SeriesTypeDefinition, DataPointSeries.series_type_definition_id == SeriesTypeDefinition.id)
        .where(
            DataSource.user_id == user_id,
            SeriesTypeDefinition.code == "heart_rate_variability_rmssd",
            DataPointSeries.recorded_at >= window_start,
            DataPointSeries.recorded_at < window_end,
        )
    ).scalar()
    return Decimal(str(result)) if result is not None else None


def _compute_hrv_score(today_rmssd: Decimal | None, baseline_rmssd: Decimal | None) -> float | None:
    if today_rmssd is None or baseline_rmssd is None or baseline_rmssd == 0:
        return None
    ratio = float(today_rmssd) / float(baseline_rmssd)
    # At baseline ratio=1.0 → score=70. Scales linearly; capped 0–100.
    return max(0.0, min(100.0, ratio * 70.0))


def _compute_audio_score(summary: AudioDailySummary | None) -> float | None:
    if summary is None:
        return None
    if summary.avg_valence is None and summary.avg_arousal is None:
        return None
    valence = float(summary.avg_valence) if summary.avg_valence is not None else 0.5
    arousal = float(summary.avg_arousal) if summary.avg_arousal is not None else 0.5
    # valence: higher = better (0-1 → contributes 0-60 pts)
    # arousal: calm alertness ≈ 0.4 optimal; extreme high/low = worse (contributes 0-40 pts)
    arousal_score = max(0.0, 1.0 - abs(arousal - 0.40) * 2.5) * 40.0
    return max(0.0, min(100.0, valence * 60.0 + arousal_score))


def _compute_survey_score(response: QuestionnaireResponse | None) -> float | None:
    if response is None:
        return None
    numeric_vals: list[float] = []
    for answer in (response.answers or []):
        val = answer.get("value")
        if val is not None:
            try:
                n = float(val)
                if 1.0 <= n <= 5.0:
                    numeric_vals.append(n)
            except (TypeError, ValueError):
                pass
    if not numeric_vals:
        return 60.0  # submitted but no numeric answers → neutral-positive baseline
    avg = sum(numeric_vals) / len(numeric_vals)
    # Map 1-5 scale → 0-100: (avg - 1) / 4 * 100
    return max(0.0, min(100.0, (avg - 1.0) / 4.0 * 100.0))


def _apply_fallback_weights(scores: dict[str, float | None]) -> tuple[float, dict[str, float]]:
    """Redistribute weights from missing signals to present ones. Returns (final_score, weights_used)."""
    available = {k: _BASE_WEIGHTS[k] for k in scores if scores[k] is not None}
    if not available:
        raise ValueError("No signals available to compute score")
    total = sum(available.values())
    weights_used = {k: v / total for k, v in available.items()}
    final_score = sum(scores[k] * weights_used[k] for k in available)  # type: ignore[operator]
    return final_score, weights_used


class DailyScoreService:
    def compute(self, db: Session, user_id: UUID, target_date: date | None = None) -> DailyScore:
        today = target_date or date.today()

        today_rmssd = _get_rmssd_today(db, user_id, today)
        baseline_rmssd = _get_rmssd_baseline(db, user_id, today)
        hrv_score = _compute_hrv_score(today_rmssd, baseline_rmssd)

        sleep_score: float | None = None
        try:
            result = sleep_score_service.get_sleep_score_for_user(db, user_id, today)
            sleep_score = float(result.overall_score)
        except (ResourceNotFoundError, Exception):
            pass

        audio_summary = db.execute(
            select(AudioDailySummary).where(
                AudioDailySummary.user_id == user_id,
                AudioDailySummary.date == today,
            )
        ).scalar_one_or_none()
        audio_score = _compute_audio_score(audio_summary)

        survey_response = db.execute(
            select(QuestionnaireResponse).where(
                QuestionnaireResponse.user_id == user_id,
                QuestionnaireResponse.date == today,
            )
        ).scalar_one_or_none()
        survey_score = _compute_survey_score(survey_response)

        raw_scores: dict[str, float | None] = {
            "hrv": hrv_score,
            "sleep": sleep_score,
            "audio": audio_score,
            "survey": survey_score,
        }

        final_score, weights_used = _apply_fallback_weights(raw_scores)

        score_data = dict(
            user_id=user_id,
            date=today,
            score=Decimal(str(round(final_score, 2))),
            hrv_score=Decimal(str(round(hrv_score, 2))) if hrv_score is not None else None,
            sleep_score=Decimal(str(round(sleep_score, 2))) if sleep_score is not None else None,
            audio_score=Decimal(str(round(audio_score, 2))) if audio_score is not None else None,
            survey_score=Decimal(str(round(survey_score, 2))) if survey_score is not None else None,
            hrv_weight=Decimal(str(round(weights_used.get("hrv", 0), 4))) if "hrv" in weights_used else None,
            sleep_weight=Decimal(str(round(weights_used.get("sleep", 0), 4))) if "sleep" in weights_used else None,
            audio_weight=Decimal(str(round(weights_used.get("audio", 0), 4))) if "audio" in weights_used else None,
            survey_weight=Decimal(str(round(weights_used.get("survey", 0), 4))) if "survey" in weights_used else None,
        )

        existing = db.execute(
            select(DailyScore).where(
                DailyScore.user_id == user_id,
                DailyScore.date == today,
            )
        ).scalar_one_or_none()

        if existing:
            for k, v in score_data.items():
                setattr(existing, k, v)
            db.commit()
            db.refresh(existing)
            return existing

        record = DailyScore(id=uuid4(), **score_data)
        db.add(record)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = db.execute(
                select(DailyScore).where(DailyScore.user_id == user_id, DailyScore.date == today)
            ).scalar_one()
            return existing
        db.refresh(record)
        return record

    def list_for_user(
        self,
        db: Session,
        user_id: UUID,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 30,
    ) -> list[DailyScore]:
        query = select(DailyScore).where(DailyScore.user_id == user_id)
        if date_from:
            query = query.where(DailyScore.date >= date_from)
        if date_to:
            query = query.where(DailyScore.date <= date_to)
        query = query.order_by(DailyScore.date.desc()).limit(limit)
        return list(db.execute(query).scalars().all())


daily_score_service = DailyScoreService()
