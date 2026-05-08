from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.database import DbSession
from app.schemas.roojai.audio import AudioDailySummaryRead, AudioSampleCreate, AudioSampleRead
from app.services.audio_sample_service import audio_sample_service
from app.utils.auth import SDKAuthDep

router = APIRouter()


@router.post(
    "/audio/users/{user_id}/features",
    status_code=status.HTTP_201_CREATED,
    tags=["External: Audio"],
    summary="Submit audio feature vector",
    description="Receives on-device extracted audio features. Raw audio is never sent or stored.",
)
def submit_audio_features(
    user_id: UUID,
    body: AudioSampleCreate,
    auth: SDKAuthDep,
    db: DbSession,
) -> AudioSampleRead:
    if auth.auth_type == "sdk_token" and (not auth.user_id or auth.user_id != user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token does not match user_id")

    sample = audio_sample_service.create(db, user_id, body)
    return AudioSampleRead.model_validate(sample)


@router.get(
    "/audio/users/{user_id}/features",
    status_code=status.HTTP_200_OK,
    tags=["External: Audio"],
    summary="List audio feature samples",
)
def list_audio_features(
    user_id: UUID,
    auth: SDKAuthDep,
    db: DbSession,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 100,
) -> list[AudioSampleRead]:
    if auth.auth_type == "sdk_token" and (not auth.user_id or auth.user_id != user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token does not match user_id")

    samples = audio_sample_service.list_for_user(db, user_id, date_from, date_to, limit)
    return [AudioSampleRead.model_validate(s) for s in samples]


@router.get(
    "/audio/users/{user_id}/daily-summary",
    status_code=status.HTTP_200_OK,
    tags=["External: Audio"],
    summary="Get daily audio summary",
)
def get_daily_audio_summary(
    user_id: UUID,
    auth: SDKAuthDep,
    db: DbSession,
    target_date: date = None,
) -> AudioDailySummaryRead:
    if auth.auth_type == "sdk_token" and (not auth.user_id or auth.user_id != user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token does not match user_id")

    from datetime import date as date_type
    d = target_date or date_type.today()
    summary = audio_sample_service.aggregate_daily(db, user_id, d)
    if not summary:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No audio data for this date")
    return AudioDailySummaryRead.model_validate(summary)
