from pydantic import BaseModel, ConfigDict


class GenerateRemittancesResponse(BaseModel):
    """Response for generate-remittances-for-all-users."""

    model_config = ConfigDict(from_attributes=True)

    message: str


class WorklogListItem(BaseModel):
    """Single worklog in list response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    task_id: str
    task_title: str | None
    created_at: str
    amount: float
    remittance_status: str


class WorklogListResponse(BaseModel):
    """Response for list-all-worklogs."""

    model_config = ConfigDict(from_attributes=True)

    data: list[WorklogListItem]
    count: int
