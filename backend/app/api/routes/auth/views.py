from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.api.routes.auth.service import AuthService
from app.models import Message, NewPassword, Token, UserPublic

router = APIRouter(tags=["login"])


@router.post("/login/access-token")
def login_access_token(
    session: SessionDep, form_data: Annotated[OAuth2PasswordRequestForm, Depends()]
) -> Token:
    """
    OAuth2 compatible token login, get an access token for future requests
    """
    return AuthService.login_access_token(session, form_data)


@router.post("/login/test-token", response_model=UserPublic)
def test_token(current_user: CurrentUser) -> Any:
    """
    Test access token
    """
    return AuthService.test_token(current_user)


@router.post("/password-recovery/{email}")
def recover_password(email: str, session: SessionDep) -> Message:
    """
    Password Recovery
    """
    return AuthService.recover_password(email, session)


@router.post("/reset-password/")
def reset_password(session: SessionDep, body: NewPassword) -> Message:
    """
    Reset password
    """
    return AuthService.reset_password(session, body)


@router.post(
    "/password-recovery-html-content/{email}",
    dependencies=[Depends(get_current_active_superuser)],
    response_class=HTMLResponse,
)
def recover_password_html_content(email: str, session: SessionDep) -> Any:
    """
    HTML Content for Password Recovery
    """
    return AuthService.recover_password_html_content(email, session)
