from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.database import DbSession
from app.schemas.roojai.questionnaire import (
    QuestionnaireResponseRead,
    QuestionnaireSubmit,
    QuestionnaireTodayRead,
)
from app.services.questionnaire_service import questionnaire_service
from app.utils.auth import SDKAuthDep

router = APIRouter()


@router.get(
    "/questionnaire/users/{user_id}/today",
    status_code=status.HTTP_200_OK,
    tags=["External: Questionnaire"],
    summary="Get today's adaptive check-in",
    description="Returns scenario + questions for today. Called by iOS before showing check-in UI.",
)
def get_questionnaire_today(
    user_id: UUID,
    auth: SDKAuthDep,
    db: DbSession,
    target_date: date | None = None,
) -> QuestionnaireTodayRead:
    if auth.auth_type == "sdk_token" and (not auth.user_id or auth.user_id != user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token does not match user_id")

    return questionnaire_service.get_today(db, user_id, target_date)


@router.post(
    "/questionnaire/users/{user_id}/submit",
    status_code=status.HTTP_201_CREATED,
    tags=["External: Questionnaire"],
    summary="Submit adaptive check-in answers",
    description="Accepts scenario + JSONB answers. Idempotent — returns existing record if already submitted today.",
)
def submit_questionnaire(
    user_id: UUID,
    body: QuestionnaireSubmit,
    auth: SDKAuthDep,
    db: DbSession,
    target_date: date | None = None,
) -> QuestionnaireResponseRead:
    if auth.auth_type == "sdk_token" and (not auth.user_id or auth.user_id != user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token does not match user_id")

    response = questionnaire_service.submit(db, user_id, body, target_date)
    return QuestionnaireResponseRead.model_validate(response)
