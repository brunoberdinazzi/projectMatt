from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from base64 import b64decode
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import HTTPException, Request, Response

from ..models import AuthSessionInfo, AuthSessionResponse, AuthUserResponse
from .auth_store import AuthStore


@dataclass
class AuthenticatedSession:
    user: AuthUserResponse
    session_id: str
    created_at: Optional[str] = None
    expires_at: Optional[str] = None

    def to_session_info(self) -> AuthSessionInfo:
        return AuthSessionInfo(
            session_id=self.session_id,
            created_at=self.created_at,
            expires_at=self.expires_at,
        )


class AuthService:
    def __init__(
        self,
        auth_store: AuthStore,
        cookie_name: Optional[str] = None,
        session_ttl_hours: Optional[int] = None,
        cookie_secure: Optional[bool] = None,
    ) -> None:
        self.auth_store = auth_store
        self.cookie_name = cookie_name or os.getenv("AUTH_COOKIE_NAME", "draux_session")
        self.session_ttl_hours = session_ttl_hours or int(os.getenv("AUTH_SESSION_TTL_HOURS", "168"))
        env_secure = os.getenv("AUTH_COOKIE_SECURE", "").strip().lower()
        self.cookie_secure = cookie_secure if cookie_secure is not None else env_secure in {"1", "true", "yes"}
        self.password_hasher = PasswordHasher(
            time_cost=3,
            memory_cost=65536,
            parallelism=4,
            hash_len=32,
            salt_len=16,
        )

    def register(self, full_name: str, email: str, password: str) -> AuthUserResponse:
        normalized_email = self._normalize_email(email)
        cleaned_name = " ".join((full_name or "").split())
        self._validate_credentials(cleaned_name, normalized_email, password)

        if self.auth_store.get_user_by_email(normalized_email):
            raise HTTPException(status_code=409, detail="Ja existe uma conta com este email.")

        user_id = self.auth_store.create_user(
            full_name=cleaned_name,
            email=normalized_email,
            password_hash=self._hash_password(password),
        )
        user_row = self.auth_store.get_user_by_id(user_id)
        return self._row_to_user(user_row)

    def login(self, email: str, password: str) -> AuthUserResponse:
        normalized_email = self._normalize_email(email)
        user_row = self.auth_store.get_user_by_email(normalized_email)
        if user_row is None:
            raise HTTPException(status_code=401, detail="Email ou senha invalidos.")
        is_valid, needs_rehash = self._verify_password(user_row["password_hash"], password)
        if not is_valid:
            raise HTTPException(status_code=401, detail="Email ou senha invalidos.")
        if needs_rehash:
            self.auth_store.update_user_password(
                user_id=int(user_row["id"]),
                password_hash=self._hash_password(password),
            )
        return self._row_to_user(user_row)

    def update_profile(self, user_id: int, full_name: str, email: str) -> AuthUserResponse:
        user_row = self.auth_store.get_user_auth_by_id(user_id)
        if user_row is None:
            raise HTTPException(status_code=404, detail="Conta nao encontrada.")

        cleaned_name = " ".join((full_name or "").split())
        normalized_email = self._normalize_email(email)
        self._validate_profile(cleaned_name, normalized_email)

        existing_user = self.auth_store.get_user_by_email(normalized_email)
        if existing_user is not None and int(existing_user["id"]) != int(user_id):
            raise HTTPException(status_code=409, detail="Ja existe uma conta com este email.")

        self.auth_store.update_user_profile(user_id=user_id, full_name=cleaned_name, email=normalized_email)
        return self._row_to_user(self.auth_store.get_user_by_id(user_id))

    def change_password(self, user_id: int, current_password: str, new_password: str) -> None:
        user_row = self.auth_store.get_user_auth_by_id(user_id)
        if user_row is None:
            raise HTTPException(status_code=404, detail="Conta nao encontrada.")
        is_valid, _needs_rehash = self._verify_password(user_row["password_hash"], current_password)
        if not is_valid:
            raise HTTPException(status_code=401, detail="A senha atual esta incorreta.")

        self._validate_password(new_password)
        if current_password == new_password:
            raise HTTPException(status_code=400, detail="A nova senha precisa ser diferente da atual.")

        self.auth_store.update_user_password(user_id=user_id, password_hash=self._hash_password(new_password))

    def create_session(self, response: Response, user: AuthUserResponse) -> AuthSessionInfo:
        session_token = secrets.token_urlsafe(32)
        session_public_id = f"sess_{secrets.token_urlsafe(9)}"
        issued_at = datetime.now(timezone.utc)
        expires_at = issued_at + timedelta(hours=self.session_ttl_hours)
        self.auth_store.create_session(
            user_id=user.id,
            session_public_id=session_public_id,
            token_hash=self._hash_token(session_token),
            expires_at=expires_at.isoformat(),
        )
        response.set_cookie(
            key=self.cookie_name,
            value=session_token,
            httponly=True,
            secure=self.cookie_secure,
            samesite="lax",
            max_age=self.session_ttl_hours * 3600,
            expires=self.session_ttl_hours * 3600,
            path="/",
        )
        return AuthSessionInfo(
            session_id=session_public_id,
            created_at=issued_at.isoformat(),
            expires_at=expires_at.isoformat(),
        )

    def clear_session(self, response: Response, request: Request) -> None:
        session_token = request.cookies.get(self.cookie_name)
        if session_token:
            self.auth_store.revoke_session_by_token_hash(
                self._hash_token(session_token),
                datetime.now(timezone.utc).isoformat(),
            )
        response.delete_cookie(key=self.cookie_name, path="/")

    def get_authenticated_user(self, request: Request) -> AuthUserResponse:
        return self.get_authenticated_session(request).user

    def get_authenticated_session(self, request: Request) -> AuthenticatedSession:
        session_token = request.cookies.get(self.cookie_name)
        if not session_token:
            raise HTTPException(status_code=401, detail="Autenticacao necessaria.")

        now_iso = datetime.now(timezone.utc).isoformat()
        token_hash = self._hash_token(session_token)
        self.auth_store.revoke_expired_sessions(now_iso)
        session_row = self.auth_store.get_session_by_token_hash(token_hash)
        if session_row is None:
            raise HTTPException(status_code=401, detail="Sessao invalida ou expirada.")
        if session_row["revoked_at"]:
            raise HTTPException(status_code=401, detail="Sessao invalida ou expirada.")
        if (session_row["expires_at"] or "") <= now_iso:
            self.auth_store.revoke_session_by_token_hash(token_hash, now_iso)
            raise HTTPException(status_code=401, detail="Sessao invalida ou expirada.")

        user = AuthUserResponse(
            id=int(session_row["user_id"]),
            full_name=session_row["full_name"],
            email=session_row["email"],
            created_at=session_row["user_created_at"],
        )
        return AuthenticatedSession(
            user=user,
            session_id=session_row["session_public_id"],
            created_at=session_row["session_created_at"],
            expires_at=session_row["expires_at"],
        )

    def get_session_response(self, request: Request) -> AuthSessionResponse:
        session = self.get_authenticated_session(request)
        return AuthSessionResponse(user=session.user, session=session.to_session_info())

    def _validate_credentials(self, full_name: str, email: str, password: str) -> None:
        self._validate_profile(full_name, email)
        self._validate_password(password)

    def _validate_profile(self, full_name: str, email: str) -> None:
        if len(full_name) < 3:
            raise HTTPException(status_code=400, detail="Informe um nome completo valido.")
        if "@" not in email or "." not in email.split("@")[-1]:
            raise HTTPException(status_code=400, detail="Informe um email valido.")

    def _validate_password(self, password: str) -> None:
        if len(password) < 8:
            raise HTTPException(status_code=400, detail="A senha precisa ter pelo menos 8 caracteres.")

    def _normalize_email(self, email: str) -> str:
        return (email or "").strip().lower()

    def _hash_password(self, password: str) -> str:
        return self.password_hasher.hash(password)

    def _verify_password(self, stored_hash: str, password: str) -> tuple[bool, bool]:
        if stored_hash.startswith("$argon2id$"):
            try:
                self.password_hasher.verify(stored_hash, password)
            except (VerifyMismatchError, InvalidHashError):
                return False, False
            return True, self.password_hasher.check_needs_rehash(stored_hash)

        try:
            algorithm, iterations_text, salt_text, digest_text = stored_hash.split("$", 3)
        except ValueError:
            return False, False
        if algorithm != "pbkdf2_sha256":
            return False, False
        try:
            iterations = int(iterations_text)
            salt = b64decode(salt_text.encode("ascii"))
            expected_digest = b64decode(digest_text.encode("ascii"))
        except Exception:
            return False, False
        actual_digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual_digest, expected_digest), True

    def _hash_token(self, token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _row_to_user(self, row) -> AuthUserResponse:
        return AuthUserResponse(
            id=int(row["id"]),
            full_name=row["full_name"],
            email=row["email"],
            created_at=row["created_at"],
        )
