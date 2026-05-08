from datetime import date
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.database import DbSession
from app.models.agent_run_log import AgentRunLog
from app.schemas.roojai.agent import AgentRunLogRead, AgentRunRequest
from app.services import ApiKeyDep
from app.services.agent_core import agent_core

router = APIRouter()


@router.post(
    "/agent/users/{user_id}/run",
    status_code=status.HTTP_200_OK,
    tags=["External: AI Agent"],
    summary="Trigger autonomous agent run",
    description="Runs the full perceive→reason→act loop for the user. Normally called by Celery daily at 07:00 ICT.",
)
def run_agent(
    user_id: UUID,
    body: AgentRunRequest,
    _auth: ApiKeyDep,
    db: DbSession,
) -> AgentRunLogRead:
    try:
        log = agent_core.run(db, user_id, trigger=body.trigger, target_date=body.target_date)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    return AgentRunLogRead.model_validate(log)


@router.get(
    "/agent/users/{user_id}/log",
    status_code=status.HTTP_200_OK,
    tags=["External: AI Agent"],
    summary="List agent run history",
    description="Returns the agent's run log — what it observed, decided, and acted on.",
)
def get_agent_log(
    user_id: UUID,
    _auth: ApiKeyDep,
    db: DbSession,
    limit: int = 10,
) -> list[AgentRunLogRead]:
    logs = db.execute(
        select(AgentRunLog)
        .where(AgentRunLog.user_id == user_id)
        .order_by(AgentRunLog.created_at.desc())
        .limit(limit)
    ).scalars().all()

    return [AgentRunLogRead.model_validate(log) for log in logs]
