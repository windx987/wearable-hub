#!/usr/bin/env python3
"""Seed activity data: create users with comprehensive health data.

This script is a thin wrapper around the SeedDataService, kept for
backward compatibility with `make seed`. All generation logic lives
in app.services.seed_data.
"""

from app.database import SessionLocal
from app.schemas.enums import SeriesType
from app.schemas.utils.seed_data import SeedDataRequest, SeedProfileConfig, TimeSeriesConfig
from app.services.seed_data import seed_data_service

_DEFAULT_SERIES_TYPES = [
    SeriesType.heart_rate,
    SeriesType.resting_heart_rate,
    SeriesType.heart_rate_variability_sdnn,
    SeriesType.respiratory_rate,
    SeriesType.oxygen_saturation,
    SeriesType.steps,
    SeriesType.energy,
    SeriesType.basal_energy,
    SeriesType.distance_walking_running,
    SeriesType.flights_climbed,
    SeriesType.weight,
    SeriesType.body_fat_percentage,
    SeriesType.vo2_max,
    SeriesType.skin_temperature,
    SeriesType.running_power,
    SeriesType.running_speed,
    SeriesType.cadence,
]


def seed_activity_data() -> None:
    """Create 2 users with comprehensive health data."""
    request = SeedDataRequest(
        num_users=2,
        profile=SeedProfileConfig(
            time_series_config=TimeSeriesConfig(
                enabled_types=_DEFAULT_SERIES_TYPES,
                include_blood_pressure=True,
            ),
        ),
    )
    with SessionLocal() as db:
        summary = seed_data_service.generate(db, request)

    print("✓ Successfully created:")
    print(f"  - {summary['users']} users")
    print(f"  - {summary['connections']} provider connections")
    print(f"  - {summary['workouts']} workouts")
    print(f"  - {summary['sleeps']} sleep records")
    print(f"  - {summary['time_series_samples']} time series samples")
    print(f"  - {summary['health_scores']} health scores")


if __name__ == "__main__":
    seed_activity_data()
