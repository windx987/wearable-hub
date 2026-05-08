from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class AgentRunRequest(BaseModel):
    target_date: date | None = None
    trigger: str = "manual"


class AgentRunLogRead(BaseModel):
    id: UUID
    user_id: UUID
    triggered_by: str
    risk_level: str
    observations: list[str]
    reasoning: str | None
    actions_planned: list[dict[str, Any]]
    actions_executed: list[dict[str, Any]]
    context_snapshot: dict[str, Any] | None
    created_at: datetime

    model_config = {"from_attributes": True}
