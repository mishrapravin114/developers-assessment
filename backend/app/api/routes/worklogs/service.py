import decimal
import uuid

from sqlmodel import Session, select

from app.models import (
    Adjustment,
    Remittance,
    RemittanceStatus,
    RemittanceWorkLog,
    Task,
    TimeSegment,
    TimeSegmentStatus,
    User,
    WorkLog,
)


def calculate_worklog_amount(session: Session, worklog: WorkLog) -> decimal.Decimal:
    """Calculate the current amount for a worklog from time segments and adjustments."""
    # Sum active time segments (minutes)
    time_stmt = (
        select(TimeSegment.minutes)
        .where(TimeSegment.worklog_id == worklog.id)
        .where(TimeSegment.status == TimeSegmentStatus.ACTIVE)
    )
    total_minutes = sum(session.exec(time_stmt).all()) or 0

    # Get task hourly rate
    task = session.get(Task, worklog.task_id)
    hourly_rate = task.hourly_rate if task else decimal.Decimal("0")

    # Amount from time: (minutes / 60) * hourly_rate
    time_amount = (decimal.Decimal(total_minutes) / 60) * hourly_rate

    # Sum adjustments
    adj_stmt = select(Adjustment.amount).where(Adjustment.worklog_id == worklog.id)
    adjustments_sum = sum(session.exec(adj_stmt).all()) or decimal.Decimal("0")

    return time_amount + adjustments_sum


def get_unremitted_worklogs(session: Session, user_id: uuid.UUID) -> list[WorkLog]:
    """Get worklogs that are not part of any succeeded remittance."""
    # Worklogs that are in a succeeded remittance
    remitted_stmt = (
        select(RemittanceWorkLog.worklog_id)
        .join(Remittance, RemittanceWorkLog.remittance_id == Remittance.id)
        .where(Remittance.status == RemittanceStatus.SUCCEEDED)
    )
    remitted_ids = {row for row in session.exec(remitted_stmt).all()}

    # All worklogs for user
    all_worklogs_stmt = select(WorkLog).where(WorkLog.user_id == user_id)
    all_worklogs = session.exec(all_worklogs_stmt).all()

    return [wl for wl in all_worklogs if wl.id not in remitted_ids]


class WorklogService:
    @staticmethod
    def generate_remittances_for_all_users(session: Session) -> dict:
        """
        Generate remittances for all users based on eligible (unremitted) work.
        Creates one remittance per user with eligible work.
        """
        users_stmt = select(User).where(User.is_active == True)
        users = session.exec(users_stmt).all()

        created_count = 0
        for user in users:
            unremitted = get_unremitted_worklogs(session, user.id)
            if not unremitted:
                continue

            total_amount = decimal.Decimal("0")
            worklog_amounts: list[tuple[WorkLog, decimal.Decimal]] = []

            for worklog in unremitted:
                amount = calculate_worklog_amount(session, worklog)
                if amount > 0:
                    total_amount += amount
                    worklog_amounts.append((worklog, amount))

            if total_amount <= 0:
                continue

            remittance = Remittance(
                user_id=user.id,
                total_amount=total_amount,
                status=RemittanceStatus.SUCCEEDED,
            )
            session.add(remittance)
            session.flush()

            for worklog, amount in worklog_amounts:
                rwl = RemittanceWorkLog(
                    remittance_id=remittance.id,
                    worklog_id=worklog.id,
                    amount=amount,
                )
                session.add(rwl)

            created_count += 1

        session.commit()
        return {"message": f"Generated {created_count} remittance(s) for users with eligible work"}

    @staticmethod
    def list_all_worklogs(
        session: Session,
        remittance_status: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> dict:
        """
        List all worklogs with amount information.
        Filter by remittanceStatus: REMITTED or UNREMITTED.
        """
        remitted_ids: set[uuid.UUID] = set()
        rw_stmt = (
            select(RemittanceWorkLog.worklog_id)
            .join(Remittance, RemittanceWorkLog.remittance_id == Remittance.id)
            .where(Remittance.status == RemittanceStatus.SUCCEEDED)
        )
        remitted_ids = set(session.exec(rw_stmt).all())

        if remittance_status:
            remittance_status_upper = remittance_status.upper()
            if remittance_status_upper not in ("REMITTED", "UNREMITTED"):
                return {"data": [], "count": 0}

        worklogs_stmt = select(WorkLog)
        if remittance_status:
            remittance_status_upper = remittance_status.upper()
            if remittance_status_upper == "REMITTED":
                if not remitted_ids:
                    return {"data": [], "count": 0}
                worklogs_stmt = worklogs_stmt.where(WorkLog.id.in_(remitted_ids))
            else:
                # UNREMITTED: worklogs not in any succeeded remittance
                if remitted_ids:
                    worklogs_stmt = worklogs_stmt.where(~WorkLog.id.in_(remitted_ids))

        all_matching = list(session.exec(worklogs_stmt).all())
        count = len(all_matching)
        worklogs = all_matching[skip : skip + limit]

        result = []
        for worklog in worklogs:
            amount = decimal.Decimal("0")
            is_remitted = worklog.id in remitted_ids

            if is_remitted:
                rw_stmt = (
                    select(RemittanceWorkLog)
                    .join(Remittance, RemittanceWorkLog.remittance_id == Remittance.id)
                    .where(RemittanceWorkLog.worklog_id == worklog.id)
                    .where(Remittance.status == RemittanceStatus.SUCCEEDED)
                )
                rwl = session.exec(rw_stmt).first()
                amount = rwl.amount if rwl else decimal.Decimal("0")
            else:
                amount = calculate_worklog_amount(session, worklog)

            task = session.get(Task, worklog.task_id)
            result.append(
                {
                    "id": str(worklog.id),
                    "user_id": str(worklog.user_id),
                    "task_id": str(worklog.task_id),
                    "task_title": task.title if task else None,
                    "created_at": worklog.created_at.isoformat(),
                    "amount": float(amount),
                    "remittance_status": "REMITTED" if is_remitted else "UNREMITTED",
                }
            )

        return {"data": result, "count": count}
