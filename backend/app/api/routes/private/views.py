from typing import Any

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.api.routes.private.service import PrivateService, PrivateUserCreate
from app.models import UserPublic

router = APIRouter(tags=["private"], prefix="/private")


@router.post("/users/", response_model=UserPublic)
def create_user(user_in: PrivateUserCreate, session: SessionDep) -> Any:
    """
    Create a new user.
    """
    return PrivateService.create_user(user_in, session)
