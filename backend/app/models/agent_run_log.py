from datetime import datetime
from uuid import UUID

from sqlalchemy import Index
from sqlalchemy.orm import Mapped, mapped_column

from app.database import BaseDbModel
from app.mappings import FKUser, PrimaryKey, json_binary, str_16, str_32


class AgentRunLog(BaseDbModel):
    __tablename__ = "agent_run_log"
    __table_args__ = (Index("ix_agent_run_log_user_created", "user_id", "created_at"),)

    id: Mapped[PrimaryKey[UUID]]
    user_id: Mapped[FKUser]
    triggered_by: Mapped[str_32]        # daily_cron | manual | on_submit | on_score | hrv_drop
    risk_level: Mapped[str_16]          # low | moderate | elevated | critical
    observations: Mapped[json_binary]
    reasoning: Mapped[str | None] = mapped_column(nullable=True)
    actions_planned: Mapped[json_binary]
    actions_executed: Mapped[json_binary]
    context_snapshot: Mapped[json_binary | None] = mapped_column(nullable=True)
