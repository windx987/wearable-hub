#!/usr/bin/env python3
"""Stream realistic wearable data into the database, simulating a live device feed.

Instead of bulk-inserting historical data like `make seed`, this script runs
continuously and inserts data points timestamped to simulated-now, mimicking
how a real wearable device would push data over time.

Usage (from backend/):
    uv run python scripts/stream_data.py
    uv run python scripts/stream_data.py --speed 3600   # 1 real sec = 1 sim hour
    uv run python scripts/stream_data.py --speed 1      # real-time
    uv run python scripts/stream_data.py --user jwoods@example.org
    uv run python scripts/stream_data.py --speed 300 --tick 0.5

Speed examples:
    --speed 1      real-time (5-min HR = 5 min wait)
    --speed 60     default — 1 real sec = 1 sim min (5-min HR every 5 real sec)
    --speed 3600   1 real sec = 1 sim hour (good for testing daily agent runs)
"""
import argparse
import random
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Ensure /root_project (project source) takes precedence over the installed package
# in site-packages, which may be missing models added after the image was built.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.database import SessionLocal
from app.models.audio_daily_summary import AudioDailySummary
from app.models.data_point_series import DataPointSeries
from app.models.data_source import DataSource
from app.models.event_record import EventRecord
from app.models.series_type_definition import SeriesTypeDefinition
from app.models.sleep_details import SleepDetails
from app.models.workout_details import WorkoutDetails
from app.models.user import User
from app.schemas.enums import ProviderName

# ── Metric specs ──────────────────────────────────────────────────────────────
# interval_s  : simulated seconds between readings
# lo / hi     : realistic value range
# noise       : Gaussian std-dev for random walk drift per tick

METRICS: list[dict] = [
    {"code": "heart_rate",                   "interval_s": 300,   "lo": 55,   "hi": 95,   "noise": 3.0},
    {"code": "heart_rate_variability_rmssd", "interval_s": 300,   "lo": 30,   "hi": 75,   "noise": 4.0},
    {"code": "respiratory_rate",             "interval_s": 300,   "lo": 12,   "hi": 20,   "noise": 0.5},
    {"code": "steps",                        "interval_s": 300,   "lo": 0,    "hi": 800,  "noise": 80.0},
    {"code": "energy",                       "interval_s": 300,   "lo": 0,    "hi": 8,    "noise": 1.5},
    {"code": "basal_energy",                 "interval_s": 300,   "lo": 4,    "hi": 8,    "noise": 0.5},
    {"code": "oxygen_saturation",            "interval_s": 1800,  "lo": 95,   "hi": 99,   "noise": 0.3},
    {"code": "blood_pressure_systolic",      "interval_s": 1800,  "lo": 100,  "hi": 130,  "noise": 3.0},
    {"code": "blood_pressure_diastolic",     "interval_s": 1800,  "lo": 60,   "hi": 85,   "noise": 2.0},
    {"code": "body_temperature",             "interval_s": 900,   "lo": 36.1, "hi": 37.2, "noise": 0.1},
    {"code": "resting_heart_rate",           "interval_s": 86400, "lo": 52,   "hi": 68,   "noise": 1.0},
    {"code": "weight",                       "interval_s": 604800, "lo": 65,  "hi": 85,   "noise": 0.2},
    {"code": "height",                       "interval_s": 604800, "lo": 170, "hi": 180,  "noise": 0.0},
    {"code": "body_fat_percentage",          "interval_s": 604800, "lo": 12,  "hi": 28,   "noise": 0.2},
    {"code": "skeletal_muscle_mass",         "interval_s": 604800, "lo": 28,  "hi": 44,   "noise": 0.2},
    {"code": "body_mass_index",              "interval_s": 604800, "lo": 20,  "hi": 27,   "noise": 0.1},
]


def _load_series_ids(db) -> dict[str, int]:
    codes = [m["code"] for m in METRICS]
    rows = db.execute(
        select(SeriesTypeDefinition.code, SeriesTypeDefinition.id)
        .where(SeriesTypeDefinition.code.in_(codes))
    ).all()
    return {r.code: r.id for r in rows}


def _get_or_create_datasource(db, user_id) -> DataSource:
    existing = db.execute(
        select(DataSource).where(
            DataSource.user_id == user_id,
            DataSource.provider == ProviderName.GARMIN,
            DataSource.source == "stream_sim",
        )
    ).scalar_one_or_none()
    if existing:
        return existing
    ds = DataSource(
        id=uuid4(),
        user_id=user_id,
        provider=ProviderName.GARMIN,
        user_connection_id=None,
        device_model="Garmin Fenix 7",
        software_version="14.20",
        source="stream_sim",
        device_type="watch",
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return ds


def _insert_point(db, ds_id, stdef_id, recorded_at: datetime, value: float) -> bool:
    db.add(DataPointSeries(
        id=uuid4(),
        data_source_id=ds_id,
        series_type_definition_id=stdef_id,
        recorded_at=recorded_at,
        value=Decimal(str(round(value, 3))),
    ))
    try:
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False


def _upsert_audio_summary(db, user_id, sim_date: date) -> None:
    exists = db.execute(
        select(AudioDailySummary.id).where(
            AudioDailySummary.user_id == user_id,
            AudioDailySummary.date == sim_date,
        )
    ).scalar_one_or_none()
    if exists:
        return
    db.add(AudioDailySummary(
        id=uuid4(),
        user_id=user_id,
        date=sim_date,
        sample_count=random.randint(8, 20),
        usable_count=random.randint(6, 15),
        skipped_count=random.randint(0, 3),
        avg_valence=Decimal(str(round(random.uniform(0.30, 0.75), 3))),
        avg_arousal=Decimal(str(round(random.uniform(0.20, 0.70), 3))),
        avg_breathing_rate=Decimal(str(round(random.uniform(12.0, 18.0), 3))),
    ))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()


def _generate_sleep_session(db, ds_id, sim_date: date) -> bool:
    """Insert a sleep session ending on sim_date morning (previous night's sleep)."""
    prev_day = sim_date - timedelta(days=1)

    # bedtime: previous day 21:00–23:00
    bedtime_hour = random.randint(21, 23)
    bedtime_minute = random.randint(0, 59)
    sleep_start = datetime(prev_day.year, prev_day.month, prev_day.day,
                           bedtime_hour, bedtime_minute, tzinfo=timezone.utc)

    # wake time: sim_date 05:00–08:00
    wake_hour = random.randint(5, 8)
    wake_minute = random.randint(0, 59)
    sleep_end = datetime(sim_date.year, sim_date.month, sim_date.day,
                         wake_hour, wake_minute, tzinfo=timezone.utc)

    time_in_bed = int((sleep_end - sleep_start).total_seconds() / 60)
    efficiency = random.uniform(0.72, 0.95)
    total_min = max(1, round(time_in_bed * efficiency))

    deep_min  = max(1, round(total_min * random.uniform(0.15, 0.22)))
    rem_min   = max(1, round(total_min * random.uniform(0.18, 0.25)))
    awake_min = max(1, round(total_min * random.uniform(0.04, 0.09)))
    light_min = max(1, total_min - deep_min - rem_min - awake_min)

    # deduplicate by date — one sleep session per night
    exists = db.execute(
        select(EventRecord.id).where(
            EventRecord.data_source_id == ds_id,
            EventRecord.category == "sleep",
            func.date(EventRecord.start_datetime) == prev_day,
        )
    ).scalar_one_or_none()
    if exists:
        return False

    sleep_id = uuid4()
    db.add(EventRecord(
        id=sleep_id,
        data_source_id=ds_id,
        category="sleep",
        type="sleep",
        source_name="Garmin Fenix 7",
        start_datetime=sleep_start,
        end_datetime=sleep_end,
        duration_seconds=int((sleep_end - sleep_start).total_seconds()),
    ))
    db.flush()
    db.add(SleepDetails(
        record_id=sleep_id,
        detail_type="sleep",
        sleep_total_duration_minutes=total_min,
        sleep_time_in_bed_minutes=time_in_bed,
        sleep_efficiency_score=Decimal(str(round(efficiency * 100, 2))),
        sleep_deep_minutes=deep_min,
        sleep_rem_minutes=rem_min,
        sleep_light_minutes=light_min,
        sleep_awake_minutes=awake_min,
        is_nap=False,
        sleep_stages=[],
    ))
    try:
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False


_WORKOUT_DAYS = {0, 1, 2, 3, 4, 5, 6}  # every day

_WORKOUT_TYPES = [
    ("running",          30, 60,  130, 175, 300, 600, 3.0,  10.0),
    ("cycling",          45, 90,  120, 165, 300, 700, 15.0, 40.0),
    ("strength_training",45, 75,  110, 155, 200, 500, None, None),
    ("yoga",             30, 60,   80, 120, 100, 250, None, None),
    ("walking",          30, 60,   90, 130, 150, 300, 2.0,  6.0),
]
# (type, dur_min, dur_max, hr_lo, hr_hi, cal_lo, cal_hi, dist_lo, dist_hi)


def _generate_workout_session(db, ds_id, sim_date: date) -> str | None:
    """Insert a workout on sim_date if it's a workout day (Mon/Wed/Fri). Returns type or None."""
    if sim_date.weekday() not in _WORKOUT_DAYS:
        return None

    wtype, dur_min, dur_max, hr_lo, hr_hi, cal_lo, cal_hi, dist_lo, dist_hi = random.choice(_WORKOUT_TYPES)

    # morning (6–8) or evening (17–19), random
    hour = random.choice([random.randint(6, 8), random.randint(17, 19)])
    start = datetime(sim_date.year, sim_date.month, sim_date.day,
                     hour, random.randint(0, 59), tzinfo=timezone.utc)
    duration_min = random.randint(dur_min, dur_max)
    end = start + timedelta(minutes=duration_min)

    # deduplicate by date — one workout per day
    exists = db.execute(
        select(EventRecord.id).where(
            EventRecord.data_source_id == ds_id,
            EventRecord.category == "workout",
            func.date(EventRecord.start_datetime) == sim_date,
        )
    ).scalar_one_or_none()
    if exists:
        return None

    hr_min = random.randint(hr_lo, hr_lo + 20)
    hr_max = random.randint(hr_hi - 20, hr_hi)
    cal = Decimal(str(random.randint(cal_lo, cal_hi)))
    dist = Decimal(str(round(random.uniform(dist_lo, dist_hi), 3))) if dist_lo else None

    workout_id = uuid4()
    db.add(EventRecord(
        id=workout_id,
        data_source_id=ds_id,
        category="workout",
        type=wtype,
        source_name="Garmin Fenix 7",
        start_datetime=start,
        end_datetime=end,
        duration_seconds=duration_min * 60,
    ))
    db.flush()
    db.add(WorkoutDetails(
        record_id=workout_id,
        detail_type="workout",
        heart_rate_min=hr_min,
        heart_rate_max=hr_max,
        heart_rate_avg=Decimal(str((hr_min + hr_max) // 2)),
        energy_burned=cal,
        distance=dist,
        steps_count=random.randint(2000, 8000) if wtype in ("running", "walking") else None,
        moving_time_seconds=duration_min * 60,
    ))
    try:
        db.commit()
        return wtype
    except IntegrityError:
        db.rollback()
        return None


def _resume_point(db, ds_id, fallback: datetime) -> datetime:
    """Return the latest recorded_at for this data source, or fallback if none."""
    latest = db.execute(
        select(func.max(DataPointSeries.recorded_at))
        .where(DataPointSeries.data_source_id == ds_id)
    ).scalar()
    if latest is None:
        return fallback
    return latest.replace(tzinfo=timezone.utc) if latest.tzinfo is None else latest


def _drift(current: float, lo: float, hi: float, noise: float) -> float:
    """Random walk with mean-reversion toward midpoint."""
    mid = (lo + hi) / 2
    new = current + random.gauss(0, noise) + (mid - current) * 0.05
    return max(lo, min(hi, new))


class _UserStream:
    __slots__ = ("user_id", "email", "ds_id", "series_ids", "sim_now", "last_at", "value", "last_audio_date")

    def __init__(self, user_id, email: str, ds_id, series_ids: dict[str, int], sim_now: datetime):
        self.user_id = user_id
        self.email = email
        self.ds_id = ds_id
        self.series_ids = series_ids
        self.sim_now = sim_now
        self.last_at: dict[str, datetime] = {}
        self.value: dict[str, float] = {
            m["code"]: random.uniform(m["lo"], m["hi"]) for m in METRICS
        }
        self.last_audio_date: date | None = None


def run(speed: float, user_email: str | None, tick_s: float, start: datetime | None) -> None:
    advance = timedelta(seconds=tick_s * speed)
    fallback = datetime(datetime.now(timezone.utc).year, 1, 1, tzinfo=timezone.utc)

    with SessionLocal() as db:
        series_ids = _load_series_ids(db)
        missing = [m["code"] for m in METRICS if m["code"] not in series_ids]
        if missing:
            print(f"[warn] Missing series_type_definition codes: {missing}")
            print("       Run `make migrate` to ensure all migrations are applied.\n")

        q = select(User.id, User.email)
        if user_email:
            q = q.where(User.email == user_email)
        users = db.execute(q).all()
        if not users:
            sys.exit("No users found. Run `make seed` first.")

        streams = []
        for u in users:
            ds = _get_or_create_datasource(db, u.id)
            # resume from last recorded point unless --start was explicitly given
            user_start = start if start is not None else _resume_point(db, ds.id, fallback)
            streams.append(_UserStream(u.id, u.email or str(u.id), ds.id, series_ids, user_start))

    sim_now = streams[0].sim_now if len(streams) == 1 else min(s.sim_now for s in streams)
    speed_label = f"{int(speed)}x" if speed >= 1 else f"1/{int(1/speed)}x"
    resumed = start is None and sim_now != fallback
    label = "Resuming from" if resumed else "Simulated start:"
    print(f"Streaming {len(streams)} user(s) | speed={speed_label} | tick={tick_s}s")
    print(f"{label} {sim_now.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print("Ctrl+C to stop.\n")

    ticks = 0
    inserted_total = 0
    try:
        while True:
            ticks += 1

            with SessionLocal() as db:
                for stream in streams:
                    prev_sim = stream.sim_now
                    stream.sim_now += advance
                    tick_inserts: list[str] = []

                    # Backfill every missed interval within the hop window
                    for m in METRICS:
                        code = m["code"]
                        stdef_id = stream.series_ids.get(code)
                        if stdef_id is None:
                            continue
                        interval = timedelta(seconds=m["interval_s"])
                        last = stream.last_at.get(code)
                        next_at = (last + interval) if last is not None else prev_sim
                        count = 0
                        while next_at <= stream.sim_now:
                            stream.value[code] = _drift(stream.value[code], m["lo"], m["hi"], m["noise"])
                            if _insert_point(db, stream.ds_id, stdef_id, next_at, stream.value[code]):
                                count += 1
                                inserted_total += 1
                            stream.last_at[code] = next_at
                            next_at += interval
                        if count:
                            tick_inserts.append(f"{code}={stream.value[code]:.1f}(×{count})")

                    # Daily records — iterate through every date that rolled over in this hop
                    start_date = (stream.last_audio_date or prev_sim.date())
                    d = start_date + timedelta(days=1)
                    while d <= stream.sim_now.date():
                        _upsert_audio_summary(db, stream.user_id, d)
                        if _generate_sleep_session(db, stream.ds_id, d):
                            tick_inserts.append(f"sleep_session({d})")
                        prev_day = d - timedelta(days=1)
                        wtype = _generate_workout_session(db, stream.ds_id, prev_day)
                        if wtype:
                            tick_inserts.append(f"workout({prev_day},{wtype})")
                        tick_inserts.append(f"audio_summary({d})")
                        stream.last_audio_date = d
                        d += timedelta(days=1)

                    if tick_inserts:
                        ts = stream.sim_now.strftime("%Y-%m-%d %H:%M")
                        print(f"[{ts}] {stream.email}: {', '.join(tick_inserts)}")

            time.sleep(tick_s)

    except KeyboardInterrupt:
        last_sim = streams[0].sim_now if streams else datetime.now(timezone.utc)
        print(f"\nStopped after {ticks} ticks | {inserted_total} data points inserted")
        print(f"Simulated time reached: {last_sim.strftime('%Y-%m-%d %H:%M:%S')} UTC")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--speed", type=float, default=60.0,
        help="Simulated seconds per real second (default: 60)",
    )
    parser.add_argument(
        "--user", metavar="EMAIL", default=None,
        help="Target a specific user by email (default: all users)",
    )
    parser.add_argument(
        "--tick", type=float, default=1.0,
        help="Real seconds per loop iteration (default: 1.0)",
    )
    parser.add_argument(
        "--start", metavar="YYYY-MM-DD", default=None,
        help="Simulated start date (default: Jan 1 of current year)",
    )
    args = parser.parse_args()

    start_dt = datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc) if args.start else None

    run(speed=args.speed, user_email=args.user, tick_s=args.tick, start=start_dt)


if __name__ == "__main__":
    main()
