from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import SessionDep, get_current_active_superuser
from app.api.routes.worklogs.schemas import (
    GenerateRemittancesResponse,
    WorklogListResponse,
)
from app.api.routes.worklogs.service import WorklogService

router = APIRouter(tags=["worklogs"])


@router.post(
    "/generate-remittances-for-all-users",
    response_model=GenerateRemittancesResponse,
)
def generate_remittances_for_all_users(
    session: SessionDep,
    current_user: Annotated[Any, Depends(get_current_active_superuser)],
) -> Any:
    """
    Generate remittances for all users based on eligible (unremitted) work.
    Creates one remittance per user with eligible work. Admin only.
    """
    return WorklogService.generate_remittances_for_all_users(session)


@router.get(
    "/list-all-worklogs",
    response_model=WorklogListResponse,
)
def list_all_worklogs(
    session: SessionDep,
    current_user: Annotated[Any, Depends(get_current_active_superuser)],
    remittanceStatus: str | None = Query(
        default=None,
        alias="remittanceStatus",
        description="Filter by REMITTED or UNREMITTED",
    ),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    List all worklogs with amount information.
    Filter by remittanceStatus: REMITTED or UNREMITTED.
    """
    return WorklogService.list_all_worklogs(
        session,
        remittance_status=remittanceStatus,
        skip=skip,
        limit=limit,
    )
