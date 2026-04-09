from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from ..models import (
    AuthPasswordForgotRequest,
    AuthPasswordForgotResponse,
    AuthPasswordResetRequest,
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
    limits = {
        "login": (20, 600, 10, 600),
        "register": (8, 3600, 4, 3600),
        "forgot": (8, 3600, 4, 3600),
        "reset": (12, 3600, 6, 3600),
    }
    ip_limit, ip_window, email_limit, email_window = limits.get(action, (8, 3600, 4, 3600))
    client_ip = rate_limit_service.client_ip(request)
    normalized_email = (email or "").strip().lower()
    rate_limit_service.enforce(
        rate_limit_service.auth_bucket(action, "ip", client_ip),
        limit=ip_limit,
        window_seconds=ip_window,
        detail="Muitas tentativas seguidas. Aguarde um pouco antes de tentar novamente.",
    )
    if normalized_email:
        rate_limit_service.enforce(
            rate_limit_service.auth_bucket(action, "email", normalized_email),
            limit=email_limit,
            window_seconds=email_window,
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


@router.post("/auth/password/forgot", response_model=AuthPasswordForgotResponse, dependencies=[Depends(require_trusted_origin)])
def auth_forgot_password(payload: AuthPasswordForgotRequest, request: Request) -> AuthPasswordForgotResponse:
    _throttle_auth_request(request, "forgot", payload.email)
    return auth_service.forgot_password(payload.email)


@router.post("/auth/password/reset", dependencies=[Depends(require_trusted_origin)])
def auth_reset_password(payload: AuthPasswordResetRequest, request: Request) -> dict[str, bool]:
    _throttle_auth_request(request, "reset", payload.token)
    auth_service.reset_password(token=payload.token, new_password=payload.new_password)
    return {"ok": True}
