from datetime import date
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.questionnaire_response import QuestionnaireResponse
from app.schemas.roojai.questionnaire import QuestionnaireSubmit, QuestionnaireTodayRead
from app.services.questionnaire_questions import SCENARIO_QUESTIONS
from app.services.questionnaire_scenario_service import detect_scenario


_ROPS_QUESTION_IDS = {"rops_sleep", "rops_fedup", "rops_tired", "rops_mental_help", "rops_life_stress", "rops_bmi"}


def _compute_rops_score(answers: list[dict]) -> dict:
    score = sum(
        1 for a in answers
        if a.get("id") in _ROPS_QUESTION_IDS and str(a.get("answer", "")).lower() in ("yes", "ใช่", "1", "true")
    )
    if score <= 2:
        risk = "low"
    elif score <= 4:
        risk = "moderate"
    else:
        risk = "high"
    return {"rops_score": score, "rops_risk": risk}


class QuestionnaireService:
    def get_today(self, db: Session, user_id: UUID, target_date: date | None = None) -> QuestionnaireTodayRead:
        today = target_date or date.today()

        existing = self._get_existing(db, user_id, today)
        if existing:
            return QuestionnaireTodayRead(
                scenario=existing.scenario,
                questions=SCENARIO_QUESTIONS.get(existing.scenario, []),
                already_submitted=True,
                context_snapshot=existing.context_snapshot,
            )

        scenario, context = detect_scenario(db, user_id, today)
        questions = SCENARIO_QUESTIONS.get(scenario, [])
        return QuestionnaireTodayRead(
            scenario=scenario,
            questions=questions,
            already_submitted=False,
            context_snapshot=context,
        )

    def submit(
        self,
        db: Session,
        user_id: UUID,
        payload: QuestionnaireSubmit,
        target_date: date | None = None,
    ) -> QuestionnaireResponse:
        today = target_date or date.today()

        existing = self._get_existing(db, user_id, today)
        if existing:
            return existing

        scenario = payload.scenario
        context: dict | None = None
        if not scenario:
            scenario, context = detect_scenario(db, user_id, today)

        if scenario == "rops":
            rops_meta = _compute_rops_score(payload.answers)
            context = {**(context or {}), **rops_meta}

        response = QuestionnaireResponse(
            id=uuid4(),
            user_id=user_id,
            date=today,
            scenario=scenario,
            answers=payload.answers,
            context_snapshot=context,
        )
        db.add(response)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            existing = self._get_existing(db, user_id, today)
            return existing  # type: ignore[return-value]
        db.refresh(response)
        return response

    def _get_existing(self, db: Session, user_id: UUID, target_date: date) -> QuestionnaireResponse | None:
        return db.execute(
            select(QuestionnaireResponse).where(
                QuestionnaireResponse.user_id == user_id,
                QuestionnaireResponse.date == target_date,
            )
        ).scalar_one_or_none()


questionnaire_service = QuestionnaireService()
