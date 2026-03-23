from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from ..models import (
    AuthLoginRequest,
    AuthPasswordUpdateRequest,
    AuthProfileUpdateRequest,
    AuthRegisterRequest,
    AuthSessionResponse,
)
from ..runtime import auth_service, require_authenticated_session
from ..services.auth_service import AuthenticatedSession


router = APIRouter()


@router.post("/auth/register", response_model=AuthSessionResponse)
def auth_register(payload: AuthRegisterRequest, response: Response) -> AuthSessionResponse:
    user = auth_service.register(
        full_name=payload.full_name,
        email=payload.email,
        password=payload.password,
    )
    session = auth_service.create_session(response, user)
    return AuthSessionResponse(user=user, session=session)


@router.post("/auth/login", response_model=AuthSessionResponse)
def auth_login(payload: AuthLoginRequest, response: Response) -> AuthSessionResponse:
    user = auth_service.login(email=payload.email, password=payload.password)
    session = auth_service.create_session(response, user)
    return AuthSessionResponse(user=user, session=session)


@router.post("/auth/logout")
def auth_logout(request: Request, response: Response) -> dict[str, bool]:
    auth_service.clear_session(response, request)
    return {"ok": True}


@router.get("/auth/me", response_model=AuthSessionResponse)
def auth_me(request: Request) -> AuthSessionResponse:
    return auth_service.get_session_response(request)


@router.put("/auth/profile", response_model=AuthSessionResponse)
def auth_update_profile(
    payload: AuthProfileUpdateRequest,
    current_session: AuthenticatedSession = Depends(require_authenticated_session),
) -> AuthSessionResponse:
    user = auth_service.update_profile(
        user_id=current_session.user.id,
        full_name=payload.full_name,
        email=payload.email,
    )
    return AuthSessionResponse(user=user, session=current_session.to_session_info())


@router.post("/auth/password")
def auth_change_password(
    payload: AuthPasswordUpdateRequest,
    current_session: AuthenticatedSession = Depends(require_authenticated_session),
) -> dict[str, bool]:
    auth_service.change_password(
        user_id=current_session.user.id,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    return {"ok": True}
