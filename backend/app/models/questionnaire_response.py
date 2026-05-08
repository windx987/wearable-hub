from datetime import date
from uuid import UUID

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import BaseDbModel
from app.mappings import FKUser, PrimaryKey, json_binary, str_32


class QuestionnaireResponse(BaseDbModel):
    __tablename__ = "questionnaire_response"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_questionnaire_response_user_date"),)

    id: Mapped[PrimaryKey[UUID]]
    user_id: Mapped[FKUser]
    date: Mapped[date]
    scenario: Mapped[str_32]
    answers: Mapped[json_binary]
    context_snapshot: Mapped[json_binary | None] = mapped_column(nullable=True)
