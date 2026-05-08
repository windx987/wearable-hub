#!/usr/bin/env python3
"""Inject signal data so a specific questionnaire scenario triggers for a user today.

Usage:
    uv run python scripts/seed_scenario.py --user EMAIL --scenario SCENARIO

Scenarios:
    hrv_drop         — today's HRV is 30% below 30-day baseline
    elevated_arousal — today's audio arousal > 0.65
    poor_sleep       — last night's sleep efficiency < 70%
    post_workout     — workout recorded today
    streak_risk      — no questionnaire response in last 3 days
    rops             — no ROPS response in last 30 days + all other signals normal
    baseline         — clear all signals; falls through to baseline
"""
import argparse
import random
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, select

from app.database import SessionLocal
from app.models.audio_daily_summary import AudioDailySummary
from app.models.data_point_series import DataPointSeries
from app.models.data_source import DataSource
from app.models.event_record import EventRecord
from app.models.questionnaire_response import QuestionnaireResponse
from app.models.series_type_definition import SeriesTypeDefinition
from app.models.sleep_details import SleepDetails
from app.models.user import User
from app.models.workout_details import WorkoutDetails
from app.schemas.enums import ProviderName

SCENARIOS = ["hrv_drop", "elevated_arousal", "poor_sleep", "post_workout", "streak_risk", "rops", "baseline"]


def _get_or_create_datasource(db, user_id):
    ds = db.execute(
        select(DataSource).where(
            DataSource.user_id == user_id,
            DataSource.source == "scenario_seed",
        )
    ).scalar_one_or_none()
    if ds:
        return ds
    ds = DataSource(
        id=uuid4(), user_id=user_id, provider=ProviderName.GARMIN,
        user_connection_id=None, device_model="Garmin Fenix 7",
        software_version="14.20", source="scenario_seed", device_type="watch",
    )
    db.add(ds)
    db.flush()
    return ds


def _hrv_series_id(db) -> int:
    return db.execute(
        select(SeriesTypeDefinition.id).where(SeriesTypeDefinition.code == "heart_rate_variability_rmssd")
    ).scalar_one()


def _insert_hrv(db, ds_id, recorded_at: datetime, value: float):
    stdef_id = _hrv_series_id(db)
    db.add(DataPointSeries(
        id=uuid4(), data_source_id=ds_id,
        series_type_definition_id=stdef_id,
        recorded_at=recorded_at, value=Decimal(str(round(value, 3))),
    ))


def seed_hrv_drop(db, user_id, ds_id, today: date):
    """30-day baseline ~55ms, today ~28ms (49% below → triggers 15% threshold)."""
    stdef_id = _hrv_series_id(db)
    # Clear existing HRV on this datasource to avoid duplicates
    db.execute(delete(DataPointSeries).where(
        DataPointSeries.data_source_id == ds_id,
        DataPointSeries.series_type_definition_id == stdef_id,
    ))
    db.flush()

    print("  Inserting 30-day HRV baseline (~55ms)…")
    for day_offset in range(30, 0, -1):
        d = today - timedelta(days=day_offset)
        for hour in [7, 12, 18]:
            ts = datetime(d.year, d.month, d.day, hour, tzinfo=timezone.utc)
            _insert_hrv(db, ds_id, ts, random.gauss(55, 3))

    print("  Inserting today's HRV (~28ms — 49% below baseline)…")
    for hour in [7, 10, 13]:
        ts = datetime(today.year, today.month, today.day, hour, tzinfo=timezone.utc)
        _insert_hrv(db, ds_id, ts, random.gauss(28, 2))


def seed_elevated_arousal(db, user_id, today: date):
    """Audio arousal = 0.78 (above 0.65 threshold)."""
    print("  Upserting audio summary with arousal=0.78…")
    existing = db.execute(
        select(AudioDailySummary).where(
            AudioDailySummary.user_id == user_id,
            AudioDailySummary.date == today,
        )
    ).scalar_one_or_none()
    if existing:
        existing.avg_arousal = Decimal("0.78")
        existing.avg_valence = Decimal("0.35")
    else:
        db.add(AudioDailySummary(
            id=uuid4(), user_id=user_id, date=today,
            sample_count=10, usable_count=8, skipped_count=2,
            avg_valence=Decimal("0.35"), avg_arousal=Decimal("0.78"),
            avg_breathing_rate=Decimal("16.5"),
        ))


def seed_poor_sleep(db, ds_id, today: date):
    """Last night's sleep with efficiency=65% (below 75% threshold)."""
    print("  Inserting poor sleep session (efficiency=65%)…")
    prev_day = today - timedelta(days=1)
    sleep_start = datetime(prev_day.year, prev_day.month, prev_day.day, 23, 30, tzinfo=timezone.utc)
    sleep_end = datetime(today.year, today.month, today.day, 7, 0, tzinfo=timezone.utc)

    # Remove any existing sleep for this night
    existing = db.execute(
        select(EventRecord.id).where(
            EventRecord.data_source_id == ds_id,
            EventRecord.category == "sleep",
        )
    ).scalars().all()
    for eid in existing:
        db.execute(delete(SleepDetails).where(SleepDetails.record_id == eid))
        db.execute(delete(EventRecord).where(EventRecord.id == eid))

    total_min = 420
    sleep_id = uuid4()
    db.add(EventRecord(
        id=sleep_id, data_source_id=ds_id, category="sleep", type="sleep",
        source_name="Garmin Fenix 7", start_datetime=sleep_start,
        end_datetime=sleep_end, duration_seconds=int((sleep_end - sleep_start).total_seconds()),
    ))
    db.flush()
    db.add(SleepDetails(
        record_id=sleep_id, detail_type="sleep",
        sleep_total_duration_minutes=round(total_min * 0.65),
        sleep_time_in_bed_minutes=total_min,
        sleep_efficiency_score=Decimal("65.0"),
        sleep_deep_minutes=40, sleep_rem_minutes=60,
        sleep_light_minutes=127, sleep_awake_minutes=46,
        is_nap=False, sleep_stages=[],
    ))


def seed_post_workout(db, ds_id, today: date):
    """Workout session this morning."""
    print("  Inserting today's workout session…")
    existing = db.execute(
        select(EventRecord.id).where(
            EventRecord.data_source_id == ds_id,
            EventRecord.category == "workout",
        )
    ).scalars().all()
    for eid in existing:
        db.execute(delete(WorkoutDetails).where(WorkoutDetails.record_id == eid))
        db.execute(delete(EventRecord).where(EventRecord.id == eid))

    start = datetime(today.year, today.month, today.day, 7, 0, tzinfo=timezone.utc)
    end = start + timedelta(minutes=45)
    workout_id = uuid4()
    db.add(EventRecord(
        id=workout_id, data_source_id=ds_id, category="workout", type="running",
        source_name="Garmin Fenix 7", start_datetime=start,
        end_datetime=end, duration_seconds=45 * 60,
    ))
    db.flush()
    db.add(WorkoutDetails(
        record_id=workout_id, detail_type="workout",
        heart_rate_min=130, heart_rate_max=172,
        heart_rate_avg=Decimal("151"), energy_burned=Decimal("420"),
        distance=Decimal("7.2"), steps_count=6800, moving_time_seconds=45 * 60,
    ))


def seed_streak_risk(db, user_id, today: date):
    """Remove questionnaire responses from the last 3 days."""
    print("  Removing recent questionnaire responses to create streak gap…")
    cutoff = today - timedelta(days=3)
    db.execute(
        delete(QuestionnaireResponse).where(
            QuestionnaireResponse.user_id == user_id,
            QuestionnaireResponse.date >= cutoff,
        )
    )


def seed_rops(db, user_id, today: date):
    """Remove ROPS responses so days_since_last_rops >= 30."""
    print("  Removing all ROPS questionnaire responses…")
    db.execute(
        delete(QuestionnaireResponse).where(
            QuestionnaireResponse.user_id == user_id,
            QuestionnaireResponse.scenario == "rops",
        )
    )
    # Also clear streak so streak_risk doesn't trigger first
    recent = today - timedelta(days=1)
    existing = db.execute(
        select(QuestionnaireResponse).where(
            QuestionnaireResponse.user_id == user_id,
            QuestionnaireResponse.date == recent,
        )
    ).scalar_one_or_none()
    if not existing:
        db.add(QuestionnaireResponse(
            id=uuid4(), user_id=user_id, date=recent,
            scenario="baseline", answers=[], context_snapshot={},
        ))


def seed_baseline(db, user_id, ds_id, today: date):
    """Clear all signals — scenario falls through to baseline."""
    print("  Clearing today's signals so baseline is triggered…")
    # Remove today's audio
    db.execute(delete(AudioDailySummary).where(
        AudioDailySummary.user_id == user_id, AudioDailySummary.date == today,
    ))
    # Remove today's workout
    day_start = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
    day_end = day_start + timedelta(days=1)
    workout_ids = db.execute(
        select(EventRecord.id).where(
            EventRecord.data_source_id == ds_id,
            EventRecord.category == "workout",
            EventRecord.start_datetime >= day_start,
            EventRecord.start_datetime < day_end,
        )
    ).scalars().all()
    for eid in workout_ids:
        db.execute(delete(WorkoutDetails).where(WorkoutDetails.record_id == eid))
        db.execute(delete(EventRecord).where(EventRecord.id == eid))
    # Ensure a recent questionnaire response exists (avoid streak_risk)
    recent = today - timedelta(days=1)
    existing = db.execute(
        select(QuestionnaireResponse).where(
            QuestionnaireResponse.user_id == user_id,
            QuestionnaireResponse.date == recent,
        )
    ).scalar_one_or_none()
    if not existing:
        db.add(QuestionnaireResponse(
            id=uuid4(), user_id=user_id, date=recent,
            scenario="baseline", answers=[], context_snapshot={},
        ))
    # Ensure recent ROPS response (avoid rops trigger)
    rops_recent = today - timedelta(days=10)
    rops_existing = db.execute(
        select(QuestionnaireResponse).where(
            QuestionnaireResponse.user_id == user_id,
            QuestionnaireResponse.scenario == "rops",
            QuestionnaireResponse.date >= rops_recent,
        )
    ).scalar_one_or_none()
    if not rops_existing:
        db.add(QuestionnaireResponse(
            id=uuid4(), user_id=user_id, date=rops_recent,
            scenario="rops", answers=[], context_snapshot={},
        ))


def _reset_scenario_data(db, user_id, ds_id, today: date):
    """Wipe all previously seeded scenario data so each run starts clean."""
    # All DataPointSeries from scenario_seed datasource
    db.execute(delete(DataPointSeries).where(DataPointSeries.data_source_id == ds_id))

    # Audio summary for today
    db.execute(delete(AudioDailySummary).where(
        AudioDailySummary.user_id == user_id,
        AudioDailySummary.date == today,
    ))

    # Sleep + workout event records from scenario_seed datasource
    event_ids = db.execute(
        select(EventRecord.id).where(EventRecord.data_source_id == ds_id)
    ).scalars().all()
    for eid in event_ids:
        db.execute(delete(SleepDetails).where(SleepDetails.record_id == eid))
        db.execute(delete(WorkoutDetails).where(WorkoutDetails.record_id == eid))
        db.execute(delete(EventRecord).where(EventRecord.id == eid))

    # Questionnaire stubs seeded by previous scenario runs (empty answers)
    db.execute(delete(QuestionnaireResponse).where(
        QuestionnaireResponse.user_id == user_id,
        QuestionnaireResponse.answers == [],
    ))

    db.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--user", metavar="EMAIL", required=True)
    parser.add_argument("--scenario", choices=SCENARIOS, required=True)
    args = parser.parse_args()

    today = date.today()

    with SessionLocal() as db:
        user = db.execute(select(User).where(User.email == args.user)).scalar_one_or_none()
        if not user:
            sys.exit(f"User not found: {args.user}")

        ds = _get_or_create_datasource(db, user.id)

        print(f"Resetting previous scenario data for {args.user}…")
        _reset_scenario_data(db, user.id, ds.id, today)

        print(f"Seeding scenario '{args.scenario}'…")

        if args.scenario == "hrv_drop":
            seed_hrv_drop(db, user.id, ds.id, today)
        elif args.scenario == "elevated_arousal":
            seed_elevated_arousal(db, user.id, today)
        elif args.scenario == "poor_sleep":
            seed_poor_sleep(db, ds.id, today)
        elif args.scenario == "post_workout":
            seed_post_workout(db, ds.id, today)
        elif args.scenario == "streak_risk":
            seed_streak_risk(db, user.id, today)
        elif args.scenario == "rops":
            seed_rops(db, user.id, today)
        elif args.scenario == "baseline":
            seed_baseline(db, user.id, ds.id, today)

        db.commit()
        print(f"Done. Scenario '{args.scenario}' seeded.")

        print("Running agent…")
        try:
            from app.services.agent_core import agent_core
            log = agent_core.run(db, user.id, trigger="scenario_seed", target_date=today)
            print(f"Agent complete — risk={log.risk_level}, actions={[a['type'] for a in log.actions_planned]}")
        except Exception as exc:
            print(f"Agent run skipped: {exc}")


if __name__ == "__main__":
    main()
