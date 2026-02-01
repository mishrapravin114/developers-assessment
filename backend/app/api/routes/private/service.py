from typing import Any

from pydantic import BaseModel
from sqlmodel import Session

from app.core.security import get_password_hash
from app.models import User, UserPublic


class PrivateUserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    is_verified: bool = False


class PrivateService:
    @staticmethod
    def create_user(user_in: PrivateUserCreate, session: Session) -> UserPublic:
        """
        Create a new user.
        """
        user = User(
            email=user_in.email,
            full_name=user_in.full_name,
            hashed_password=get_password_hash(user_in.password),
        )

        session.add(user)
        session.commit()

        return user
