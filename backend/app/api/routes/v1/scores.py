from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.database import DbSession
from app.schemas.roojai.score import DailyScoreRead, ScoreComputeRequest
from app.services.daily_score_service import daily_score_service
from app.utils.auth import SDKAuthDep

router = APIRouter()


@router.post(
    "/scores/users/{user_id}/compute",
    status_code=status.HTTP_200_OK,
    tags=["External: Scores"],
    summary="Compute daily stress & recovery score",
    description="Aggregates HRV, sleep, audio, and survey signals into a single 0–100 score. Upserts for the day.",
)
def compute_daily_score(
    user_id: UUID,
    body: ScoreComputeRequest,
    auth: SDKAuthDep,
    db: DbSession,
) -> DailyScoreRead:
    if auth.auth_type == "sdk_token" and (not auth.user_id or auth.user_id != user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token does not match user_id")

    try:
        record = daily_score_service.compute(db, user_id, body.target_date)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return DailyScoreRead.model_validate(record)


@router.get(
    "/scores/users/{user_id}/daily",
    status_code=status.HTTP_200_OK,
    tags=["External: Scores"],
    summary="List daily scores",
)
def list_daily_scores(
    user_id: UUID,
    auth: SDKAuthDep,
    db: DbSession,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 30,
) -> list[DailyScoreRead]:
    if auth.auth_type == "sdk_token" and (not auth.user_id or auth.user_id != user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token does not match user_id")

    records = daily_score_service.list_for_user(db, user_id, date_from, date_to, limit)
    return [DailyScoreRead.model_validate(r) for r in records]
