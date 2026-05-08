from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.database import DbSession
from app.schemas.roojai.ai import ChatRequest, ChatResponse, InsightRead, InsightRequest
from app.services.ai_agent_service import ai_agent_service
from app.utils.auth import SDKAuthDep

router = APIRouter()


@router.post(
    "/ai/users/{user_id}/insights",
    status_code=status.HTTP_200_OK,
    tags=["External: AI Agent"],
    summary="Generate daily Thai-language health insight",
    description="Calls GPT with today's score, audio, and check-in data to generate a personalised insight + recommendations.",
)
def generate_insights(
    user_id: UUID,
    body: InsightRequest,
    auth: SDKAuthDep,
    db: DbSession,
) -> InsightRead:
    if auth.auth_type == "sdk_token" and (not auth.user_id or auth.user_id != user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token does not match user_id")

    try:
        result = ai_agent_service.generate_insights(db, user_id, body.target_date)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    return InsightRead(
        insight=result.get("insight", ""),
        recommendations=result.get("recommendations", []),
        mood_label=result.get("mood_label", ""),
        score_interpretation=result.get("score_interpretation", ""),
        generated_at=datetime.now(timezone.utc),
    )


@router.post(
    "/ai/users/{user_id}/chat",
    status_code=status.HTTP_200_OK,
    tags=["External: AI Agent"],
    summary="Chat with Roojai AI agent",
    description="Conversational agent with function-calling tools: get_daily_scores, get_audio_summary, get_questionnaire_history, get_hrv_trend.",
)
def chat(
    user_id: UUID,
    body: ChatRequest,
    auth: SDKAuthDep,
    db: DbSession,
) -> ChatResponse:
    if auth.auth_type == "sdk_token" and (not auth.user_id or auth.user_id != user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token does not match user_id")

    try:
        reply, tools_used = ai_agent_service.chat(
            db,
            user_id,
            body.message,
            [m.model_dump() for m in body.history],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    return ChatResponse(reply=reply, tools_used=tools_used)
