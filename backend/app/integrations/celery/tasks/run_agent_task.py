from logging import getLogger
from uuid import UUID

from celery import shared_task

from app.database import SessionLocal

logger = getLogger(__name__)


@shared_task(name="app.integrations.celery.tasks.run_agent_task.run_agent_for_user")
def run_agent_for_user(user_id: str, trigger: str = "daily_cron") -> dict:
    """Run the autonomous agent loop for a single user."""
    from app.services.agent_core import agent_core
    with SessionLocal() as db:
        log = agent_core.run(db, UUID(user_id), trigger=trigger)
        return {"log_id": str(log.id), "risk_level": log.risk_level, "actions": len(log.actions_executed)}


@shared_task(name="app.integrations.celery.tasks.run_agent_task.run_agent_for_all_users")
def run_agent_for_all_users(trigger: str = "daily_cron") -> dict:
    """Run the autonomous agent loop for every user. Scheduled daily at 00:00 UTC (07:00 ICT)."""
    from sqlalchemy import select
    from app.models.user import User
    from app.services.agent_core import agent_core

    with SessionLocal() as db:
        user_ids = db.execute(select(User.id)).scalars().all()

    results = {"total": len(user_ids), "completed": 0, "failed": 0}
    for uid in user_ids:
        run_agent_for_user.delay(str(uid), trigger)
        results["completed"] += 1

    return results
