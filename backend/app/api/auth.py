from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from ..models import (
    AuthLoginRequest,
    AuthPasswordUpdateRequest,
    AuthProfileUpdateRequest,
    AuthRegisterRequest,
    AuthSessionResponse,
)
from ..runtime import auth_service, rate_limit_service, require_authenticated_session, require_trusted_origin
from ..services.auth_service import AuthenticatedSession


router = APIRouter()


def _throttle_auth_request(request: Request, action: str, email: str) -> None:
    client_ip = rate_limit_service.client_ip(request)
    normalized_email = (email or "").strip().lower()
    rate_limit_service.enforce(
        rate_limit_service.auth_bucket(action, "ip", client_ip),
        limit=20 if action == "login" else 8,
        window_seconds=600 if action == "login" else 3600,
        detail="Muitas tentativas seguidas. Aguarde um pouco antes de tentar novamente.",
    )
    if normalized_email:
        rate_limit_service.enforce(
            rate_limit_service.auth_bucket(action, "email", normalized_email),
            limit=10 if action == "login" else 4,
            window_seconds=600 if action == "login" else 3600,
            detail="Muitas tentativas seguidas para esta conta. Aguarde um pouco antes de tentar novamente.",
        )


@router.post("/auth/register", response_model=AuthSessionResponse, dependencies=[Depends(require_trusted_origin)])
def auth_register(payload: AuthRegisterRequest, request: Request, response: Response) -> AuthSessionResponse:
    _throttle_auth_request(request, "register", payload.email)
    user = auth_service.register(
        full_name=payload.full_name,
        email=payload.email,
        password=payload.password,
    )
    session = auth_service.create_session(response, user, request=request)
    return AuthSessionResponse(user=user, session=session)


@router.post("/auth/login", response_model=AuthSessionResponse, dependencies=[Depends(require_trusted_origin)])
def auth_login(payload: AuthLoginRequest, request: Request, response: Response) -> AuthSessionResponse:
    _throttle_auth_request(request, "login", payload.email)
    user = auth_service.login(email=payload.email, password=payload.password)
    session = auth_service.create_session(response, user, request=request)
    return AuthSessionResponse(user=user, session=session)


@router.post("/auth/logout", dependencies=[Depends(require_trusted_origin)])
def auth_logout(request: Request, response: Response) -> dict[str, bool]:
    auth_service.clear_session(response, request)
    return {"ok": True}


@router.get("/auth/me", response_model=AuthSessionResponse)
def auth_me(request: Request) -> AuthSessionResponse:
    return auth_service.get_session_response(request)


@router.put("/auth/profile", response_model=AuthSessionResponse, dependencies=[Depends(require_trusted_origin)])
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


@router.post("/auth/password", dependencies=[Depends(require_trusted_origin)])
def auth_change_password(
    payload: AuthPasswordUpdateRequest,
    request: Request,
    response: Response,
    current_session: AuthenticatedSession = Depends(require_authenticated_session),
) -> dict[str, bool]:
    auth_service.change_password(
        user_id=current_session.user.id,
        current_password=payload.current_password,
        new_password=payload.new_password,
        response=response,
        request=request,
    )
    return {"ok": True}
