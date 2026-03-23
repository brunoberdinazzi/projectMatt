from __future__ import annotations

import base64
import hashlib
import hmac
import os
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class DataProtectionService:
    VERSION_PREFIX = "enc:v1:"

    def __init__(
        self,
        master_key: Optional[str] = None,
        key_path: Optional[Path] = None,
    ) -> None:
        base_dir = Path(__file__).resolve().parents[3]
        data_dir = base_dir / "backend" / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        self.key_path = key_path or (data_dir / ".draux_master_key")
        configured_key = master_key or os.getenv("DRAUX_DATA_KEY", "")
        self.master_key = self._load_master_key(configured_key)

    def encrypt_for_user(self, user_id: int, plaintext: str, field_name: str) -> str:
        if plaintext == "":
            return plaintext

        key = self._derive_user_key(user_id)
        nonce = os.urandom(12)
        aad = self._build_aad(user_id, field_name)
        ciphertext = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), aad)
        payload = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii").rstrip("=")
        return f"{self.VERSION_PREFIX}{payload}"

    def decrypt_for_user(self, user_id: int, token: str, field_name: str) -> str:
        if not token or not token.startswith(self.VERSION_PREFIX):
            return token

        payload = token[len(self.VERSION_PREFIX):]
        padded_payload = payload + "=" * (-len(payload) % 4)
        raw = base64.urlsafe_b64decode(padded_payload.encode("ascii"))
        nonce = raw[:12]
        ciphertext = raw[12:]
        key = self._derive_user_key(user_id)
        aad = self._build_aad(user_id, field_name)
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, aad)
        return plaintext.decode("utf-8")

    def _load_master_key(self, configured_key: str) -> bytes:
        normalized_key = (configured_key or "").strip()
        if normalized_key:
            return self._decode_master_key(normalized_key)

        if self.key_path.exists():
            return self._decode_master_key(self.key_path.read_text(encoding="utf-8").strip())

        generated = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
        self.key_path.write_text(generated, encoding="utf-8")
        try:
            os.chmod(self.key_path, 0o600)
        except OSError:
            pass
        return self._decode_master_key(generated)

    def _decode_master_key(self, raw_value: str) -> bytes:
        try:
            decoded = base64.urlsafe_b64decode(raw_value + "=" * (-len(raw_value) % 4))
        except Exception as exc:
            raise ValueError("DRAUX_DATA_KEY precisa estar em base64 urlsafe.") from exc
        if len(decoded) != 32:
            raise ValueError("DRAUX_DATA_KEY precisa representar 32 bytes.")
        return decoded

    def _derive_user_key(self, user_id: int) -> bytes:
        return hmac.new(
            self.master_key,
            f"draux:user:{user_id}".encode("utf-8"),
            hashlib.sha256,
        ).digest()

    def _build_aad(self, user_id: int, field_name: str) -> bytes:
        return f"draux|user:{user_id}|field:{field_name}".encode("utf-8")
