import decimal
import logging

from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine, init_db
from app.models import (
    Task,
    TimeSegment,
    TimeSegmentStatus,
    User,
    WorkLog,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init() -> None:
    with Session(engine) as session:
        init_db(session)

        # Seed WorkLog settlement data if empty
        existing_tasks = session.exec(select(Task)).first()
        if existing_tasks is None:
            logger.info("Seeding WorkLog settlement data")
            user = session.exec(select(User).where(User.email == settings.FIRST_SUPERUSER)).first()
            if user:
                task1 = Task(title="Task Alpha", hourly_rate=decimal.Decimal("50.00"))
                task2 = Task(title="Task Beta", hourly_rate=decimal.Decimal("75.00"))
                session.add(task1)
                session.add(task2)
                session.flush()

                worklog1 = WorkLog(user_id=user.id, task_id=task1.id)
                worklog2 = WorkLog(user_id=user.id, task_id=task2.id)
                session.add(worklog1)
                session.add(worklog2)
                session.flush()

                # 120 minutes = 2 hours = $100 for task1
                session.add(
                    TimeSegment(worklog_id=worklog1.id, minutes=120, status=TimeSegmentStatus.ACTIVE)
                )
                session.add(
                    TimeSegment(worklog_id=worklog1.id, minutes=60, status=TimeSegmentStatus.ACTIVE)
                )
                # 90 minutes = 1.5 hours = $112.50 for task2
                session.add(
                    TimeSegment(worklog_id=worklog2.id, minutes=90, status=TimeSegmentStatus.ACTIVE)
                )
                session.commit()
                logger.info("WorkLog settlement seed data created")


def main() -> None:
    logger.info("Creating initial data")
    init()
    logger.info("Initial data created")


if __name__ == "__main__":
    main()
