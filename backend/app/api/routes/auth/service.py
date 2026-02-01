from datetime import timedelta
from typing import Any

from fastapi import HTTPException
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session

from app import crud
from app.core import security
from app.core.config import settings
from app.core.security import get_password_hash
from app.models import Message, NewPassword, Token, UserPublic
from app.utils import (
    generate_password_reset_token,
    generate_reset_password_email,
    send_email,
    verify_password_reset_token,
)


class AuthService:
    @staticmethod
    def login_access_token(
        session: Session, form_data: OAuth2PasswordRequestForm
    ) -> Token:
        """
        OAuth2 compatible token login, get an access token for future requests
        """
        user = crud.authenticate(
            session=session, email=form_data.username, password=form_data.password
        )
        if not user:
            raise HTTPException(status_code=400, detail="Incorrect email or password")
        elif not user.is_active:
            raise HTTPException(status_code=400, detail="Inactive user")
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        return Token(
            access_token=security.create_access_token(
                user.id, expires_delta=access_token_expires
            )
        )

    @staticmethod
    def test_token(current_user: Any) -> UserPublic:
        """
        Test access token
        """
        return current_user

    @staticmethod
    def recover_password(email: str, session: Session) -> Message:
        """
        Password Recovery
        """
        user = crud.get_user_by_email(session=session, email=email)

        if not user:
            raise HTTPException(
                status_code=404,
                detail="The user with this email does not exist in the system.",
            )
        password_reset_token = generate_password_reset_token(email=email)
        email_data = generate_reset_password_email(
            email_to=user.email, email=email, token=password_reset_token
        )
        send_email(
            email_to=user.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
        return Message(message="Password recovery email sent")

    @staticmethod
    def reset_password(session: Session, body: NewPassword) -> Message:
        """
        Reset password
        """
        email = verify_password_reset_token(token=body.token)
        if not email:
            raise HTTPException(status_code=400, detail="Invalid token")
        user = crud.get_user_by_email(session=session, email=email)
        if not user:
            raise HTTPException(
                status_code=404,
                detail="The user with this email does not exist in the system.",
            )
        elif not user.is_active:
            raise HTTPException(status_code=400, detail="Inactive user")
        hashed_password = get_password_hash(password=body.new_password)
        user.hashed_password = hashed_password
        session.add(user)
        session.commit()
        return Message(message="Password updated successfully")

    @staticmethod
    def recover_password_html_content(email: str, session: Session) -> HTMLResponse:
        """
        HTML Content for Password Recovery
        """
        user = crud.get_user_by_email(session=session, email=email)

        if not user:
            raise HTTPException(
                status_code=404,
                detail="The user with this username does not exist in the system.",
            )
        password_reset_token = generate_password_reset_token(email=email)
        email_data = generate_reset_password_email(
            email_to=user.email, email=email, token=password_reset_token
        )

        return HTMLResponse(
            content=email_data.html_content, headers={"subject:": email_data.subject}
        )
