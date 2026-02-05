import decimal
import uuid

from sqlmodel import Session, func, select

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
    amounts = _calculate_worklog_amounts_batch(session, [worklog.id])
    return amounts.get(worklog.id, decimal.Decimal("0"))


def _calculate_worklog_amounts_batch(
    session: Session, worklog_ids: list[uuid.UUID]
) -> dict[uuid.UUID, decimal.Decimal]:
    """Batch calculate amounts for multiple worklogs. Avoids N+1 queries."""
    if not worklog_ids:
        return {}

    ts_stmt = (
        select(TimeSegment.worklog_id, TimeSegment.minutes)
        .where(TimeSegment.worklog_id.in_(worklog_ids))
        .where(TimeSegment.status == TimeSegmentStatus.ACTIVE)
    )
    ts_rows = session.exec(ts_stmt).all()
    minutes_by_wl: dict[uuid.UUID, int] = {}
    for wl_id, mins in ts_rows:
        minutes_by_wl[wl_id] = minutes_by_wl.get(wl_id, 0) + mins

    adj_stmt = select(Adjustment.worklog_id, Adjustment.amount).where(
        Adjustment.worklog_id.in_(worklog_ids)
    )
    adj_rows = session.exec(adj_stmt).all()
    adj_by_wl: dict[uuid.UUID, decimal.Decimal] = {}
    for wl_id, amt in adj_rows:
        adj_by_wl[wl_id] = adj_by_wl.get(wl_id, decimal.Decimal("0")) + amt

    worklogs = session.exec(select(WorkLog).where(WorkLog.id.in_(worklog_ids))).all()
    task_ids = {wl.task_id for wl in worklogs}
    tasks = {t.id: t for t in session.exec(select(Task).where(Task.id.in_(task_ids))).all()}

    result: dict[uuid.UUID, decimal.Decimal] = {}
    for wl in worklogs:
        total_mins = minutes_by_wl.get(wl.id, 0)
        task = tasks.get(wl.task_id)
        rate = task.hourly_rate if task else decimal.Decimal("0")
        time_amt = (decimal.Decimal(total_mins) / 60) * rate
        adj_amt = adj_by_wl.get(wl.id, decimal.Decimal("0"))
        result[wl.id] = time_amt + adj_amt
    return result


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
        Uses SQL OFFSET/LIMIT for pagination; prefetches Task and RemittanceWorkLog.
        """
        rw_stmt = (
            select(RemittanceWorkLog.worklog_id, RemittanceWorkLog.amount)
            .join(Remittance, RemittanceWorkLog.remittance_id == Remittance.id)
            .where(Remittance.status == RemittanceStatus.SUCCEEDED)
        )
        remitted_rows = session.exec(rw_stmt).all()
        remitted_ids = {row[0] for row in remitted_rows}
        remitted_amounts: dict[uuid.UUID, decimal.Decimal] = {
            row[0]: row[1] for row in remitted_rows
        }

        if remittance_status:
            rs_upper = remittance_status.upper()
            if rs_upper not in ("REMITTED", "UNREMITTED"):
                return {"data": [], "count": 0}

        worklogs_stmt = select(WorkLog)
        if remittance_status:
            rs_upper = remittance_status.upper()
            if rs_upper == "REMITTED":
                if not remitted_ids:
                    return {"data": [], "count": 0}
                worklogs_stmt = worklogs_stmt.where(WorkLog.id.in_(remitted_ids))
            else:
                if remitted_ids:
                    worklogs_stmt = worklogs_stmt.where(~WorkLog.id.in_(remitted_ids))

        count_stmt = select(func.count()).select_from(worklogs_stmt.subquery())
        count = session.exec(count_stmt).one()

        worklogs_stmt = worklogs_stmt.offset(skip).limit(limit)
        worklogs = list(session.exec(worklogs_stmt).all())

        if not worklogs:
            return {"data": [], "count": count}

        task_ids = {wl.task_id for wl in worklogs}
        tasks_stmt = select(Task).where(Task.id.in_(task_ids))
        tasks_by_id = {t.id: t for t in session.exec(tasks_stmt).all()}

        amounts_by_wl: dict[uuid.UUID, decimal.Decimal] = {}
        unremitted_ids = [wl.id for wl in worklogs if wl.id not in remitted_ids]
        if unremitted_ids:
            amounts_by_wl.update(
                _calculate_worklog_amounts_batch(session, unremitted_ids)
            )
        for wl in worklogs:
            if wl.id in remitted_ids:
                amounts_by_wl[wl.id] = remitted_amounts.get(wl.id, decimal.Decimal("0"))

        result = []
        for worklog in worklogs:
            task = tasks_by_id.get(worklog.task_id)
            amount = amounts_by_wl.get(worklog.id, decimal.Decimal("0"))
            is_remitted = worklog.id in remitted_ids
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
