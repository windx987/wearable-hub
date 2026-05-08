from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audio_daily_summary import AudioDailySummary
from app.models.data_point_series import DataPointSeries
from app.models.data_source import DataSource
from app.models.event_record import EventRecord
from app.models.questionnaire_response import QuestionnaireResponse
from app.models.series_type_definition import SeriesTypeDefinition
from app.models.sleep_details import SleepDetails

_RMSSD_DROP_THRESHOLD = Decimal("0.85")  # 15% below 30-day baseline
_RMSSD_BASELINE_DAYS = 30
_SLEEP_EFFICIENCY_THRESHOLD = Decimal("75.0")
_AROUSAL_HIGH_THRESHOLD = Decimal("0.65")
_STREAK_RISK_DAYS = 2  # no response in last N days = streak risk


def _get_today_rmssd(db: Session, user_id: UUID, target_date: date) -> Decimal | None:
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


def _had_workout_today(db: Session, user_id: UUID, target_date: date) -> bool:
    day_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)
    result = db.execute(
        select(EventRecord.id)
        .join(DataSource, EventRecord.data_source_id == DataSource.id)
        .where(
            DataSource.user_id == user_id,
            EventRecord.category == "activity",
            EventRecord.start_datetime >= day_start,
            EventRecord.start_datetime < day_end,
        )
        .limit(1)
    ).scalar()
    return result is not None


def _get_last_sleep_efficiency(db: Session, user_id: UUID, target_date: date) -> Decimal | None:
    day_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=timezone.utc)
    window_start = day_start - timedelta(days=2)
    result = db.execute(
        select(SleepDetails.sleep_efficiency_score)
        .join(EventRecord, SleepDetails.record_id == EventRecord.id)
        .join(DataSource, EventRecord.data_source_id == DataSource.id)
        .where(
            DataSource.user_id == user_id,
            EventRecord.category == "sleep",
            EventRecord.end_datetime >= window_start,
            EventRecord.end_datetime < day_start,
            SleepDetails.sleep_efficiency_score.is_not(None),
        )
        .order_by(EventRecord.end_datetime.desc())
        .limit(1)
    ).scalar()
    return Decimal(str(result)) if result is not None else None


def _get_today_audio_arousal(db: Session, user_id: UUID, target_date: date) -> Decimal | None:
    summary = db.execute(
        select(AudioDailySummary.avg_arousal).where(
            AudioDailySummary.user_id == user_id,
            AudioDailySummary.date == target_date,
        )
    ).scalar()
    return Decimal(str(summary)) if summary is not None else None


def _days_since_last_response(db: Session, user_id: UUID, target_date: date) -> int:
    last_date = db.execute(
        select(QuestionnaireResponse.date)
        .where(QuestionnaireResponse.user_id == user_id)
        .order_by(QuestionnaireResponse.date.desc())
        .limit(1)
    ).scalar()
    if last_date is None:
        return 999
    return (target_date - last_date).days


_ROPS_INTERVAL_DAYS = 30  # show ROPS screener once per month


def _days_since_last_rops(db: Session, user_id: UUID, target_date: date) -> int:
    last_date = db.execute(
        select(QuestionnaireResponse.date)
        .where(
            QuestionnaireResponse.user_id == user_id,
            QuestionnaireResponse.scenario == "rops",
        )
        .order_by(QuestionnaireResponse.date.desc())
        .limit(1)
    ).scalar()
    if last_date is None:
        return 999
    return (target_date - last_date).days


def detect_scenario(db: Session, user_id: UUID, target_date: date | None = None) -> tuple[str, dict]:
    """Returns (scenario_name, context_snapshot) based on today's signals."""
    today = target_date or date.today()
    context: dict = {}

    today_rmssd = _get_today_rmssd(db, user_id, today)
    baseline_rmssd = _get_rmssd_baseline(db, user_id, today)
    context["today_rmssd"] = float(today_rmssd) if today_rmssd is not None else None
    context["baseline_rmssd"] = float(baseline_rmssd) if baseline_rmssd is not None else None

    if (
        today_rmssd is not None
        and baseline_rmssd is not None
        and baseline_rmssd > 0
        and today_rmssd < baseline_rmssd * _RMSSD_DROP_THRESHOLD
    ):
        return "hrv_drop", context

    arousal = _get_today_audio_arousal(db, user_id, today)
    context["avg_arousal"] = float(arousal) if arousal is not None else None
    if arousal is not None and arousal > _AROUSAL_HIGH_THRESHOLD:
        return "elevated_arousal", context

    sleep_efficiency = _get_last_sleep_efficiency(db, user_id, today)
    context["sleep_efficiency"] = float(sleep_efficiency) if sleep_efficiency is not None else None
    if sleep_efficiency is not None and sleep_efficiency < _SLEEP_EFFICIENCY_THRESHOLD:
        return "poor_sleep", context

    had_workout = _had_workout_today(db, user_id, today)
    context["had_workout"] = had_workout
    if had_workout:
        return "post_workout", context

    days_gap = _days_since_last_response(db, user_id, today)
    context["days_since_last_response"] = days_gap
    if days_gap >= _STREAK_RISK_DAYS:
        return "streak_risk", context

    days_since_rops = _days_since_last_rops(db, user_id, today)
    context["days_since_last_rops"] = days_since_rops
    if days_since_rops >= _ROPS_INTERVAL_DAYS:
        return "rops", context

    return "baseline", context
