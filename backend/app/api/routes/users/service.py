import uuid
from typing import Any

from fastapi import HTTPException
from sqlmodel import Session, col, delete, func, select

from app import crud
from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.models import (
    Item,
    Message,
    UpdatePassword,
    User,
    UserCreate,
    UserPublic,
    UserRegister,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
)
from app.utils import generate_new_account_email, send_email


class UserService:
    @staticmethod
    def get_users(session: Session, skip: int = 0, limit: int = 100) -> UsersPublic:
        """
        Retrieve users.
        """
        count_statement = select(func.count()).select_from(User)
        count = session.exec(count_statement).one()

        statement = select(User).offset(skip).limit(limit)
        users = session.exec(statement).all()

        return UsersPublic(data=users, count=count)

    @staticmethod
    def create_user(session: Session, user_in: UserCreate) -> UserPublic:
        """
        Create new user.
        """
        user = crud.get_user_by_email(session=session, email=user_in.email)
        if user:
            raise HTTPException(
                status_code=400,
                detail="The user with this email already exists in the system.",
            )

        user = crud.create_user(session=session, user_create=user_in)
        if settings.emails_enabled and user_in.email:
            email_data = generate_new_account_email(
                email_to=user_in.email, username=user_in.email, password=user_in.password
            )
            send_email(
                email_to=user_in.email,
                subject=email_data.subject,
                html_content=email_data.html_content,
            )
        return user

    @staticmethod
    def update_user_me(
        session: Session, user_in: UserUpdateMe, current_user: User
    ) -> UserPublic:
        """
        Update own user.
        """
        if user_in.email:
            existing_user = crud.get_user_by_email(session=session, email=user_in.email)
            if existing_user and existing_user.id != current_user.id:
                raise HTTPException(
                    status_code=409, detail="User with this email already exists"
                )
        user_data = user_in.model_dump(exclude_unset=True)
        current_user.sqlmodel_update(user_data)
        session.add(current_user)
        session.commit()
        session.refresh(current_user)
        return current_user

    @staticmethod
    def update_password_me(
        session: Session, body: UpdatePassword, current_user: User
    ) -> Message:
        """
        Update own password.
        """
        if not verify_password(body.current_password, current_user.hashed_password):
            raise HTTPException(status_code=400, detail="Incorrect password")
        if body.current_password == body.new_password:
            raise HTTPException(
                status_code=400, detail="New password cannot be the same as the current one"
            )
        hashed_password = get_password_hash(body.new_password)
        current_user.hashed_password = hashed_password
        session.add(current_user)
        session.commit()
        return Message(message="Password updated successfully")

    @staticmethod
    def get_user_me(current_user: User) -> UserPublic:
        """
        Get current user.
        """
        return current_user

    @staticmethod
    def delete_user_me(session: Session, current_user: User) -> Message:
        """
        Delete own user.
        """
        if current_user.is_superuser:
            raise HTTPException(
                status_code=403, detail="Super users are not allowed to delete themselves"
            )
        session.delete(current_user)
        session.commit()
        return Message(message="User deleted successfully")

    @staticmethod
    def register_user(session: Session, user_in: UserRegister) -> UserPublic:
        """
        Create new user without the need to be logged in.
        """
        user = crud.get_user_by_email(session=session, email=user_in.email)
        if user:
            raise HTTPException(
                status_code=400,
                detail="The user with this email already exists in the system",
            )
        user_create = UserCreate.model_validate(user_in)
        user = crud.create_user(session=session, user_create=user_create)
        return user

    @staticmethod
    def get_user_by_id(
        user_id: uuid.UUID, session: Session, current_user: User
    ) -> UserPublic:
        """
        Get a specific user by id.
        """
        user = session.get(User, user_id)
        if user == current_user:
            return user
        if not current_user.is_superuser:
            raise HTTPException(
                status_code=403,
                detail="The user doesn't have enough privileges",
            )
        return user

    @staticmethod
    def update_user(
        session: Session, user_id: uuid.UUID, user_in: UserUpdate
    ) -> UserPublic:
        """
        Update a user.
        """
        db_user = session.get(User, user_id)
        if not db_user:
            raise HTTPException(
                status_code=404,
                detail="The user with this id does not exist in the system",
            )
        if user_in.email:
            existing_user = crud.get_user_by_email(session=session, email=user_in.email)
            if existing_user and existing_user.id != user_id:
                raise HTTPException(
                    status_code=409, detail="User with this email already exists"
                )

        db_user = crud.update_user(session=session, db_user=db_user, user_in=user_in)
        return db_user

    @staticmethod
    def delete_user(
        session: Session, current_user: User, user_id: uuid.UUID
    ) -> Message:
        """
        Delete a user.
        """
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        if user == current_user:
            raise HTTPException(
                status_code=403, detail="Super users are not allowed to delete themselves"
            )
        statement = delete(Item).where(col(Item.owner_id) == user_id)
        session.exec(statement)  # type: ignore
        session.delete(user)
        session.commit()
        return Message(message="User deleted successfully")
