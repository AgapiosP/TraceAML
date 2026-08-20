"""Field encryption and deployment-safety primitives."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Protocol


class FieldCipher(Protocol):
    is_secure: bool
    key_id: str

    def encrypt_json(self, value: dict[str, Any], context: str) -> bytes: ...

    def decrypt_json(self, value: bytes, context: str) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class AESGCMFieldCipher:
    """AES-256-GCM envelope for sensitive JSON fields.

    The caller owns key retrieval and rotation. The key is never persisted by
    TraceAML. Context is authenticated as additional data to prevent ciphertext
    from being moved between records.
    """

    key: bytes
    key_id: str
    is_secure: bool = True

    def __post_init__(self) -> None:
        if len(self.key) != 32:
            raise ValueError("AESGCMFieldCipher requires a 32-byte key")
        if not self.key_id.strip():
            raise ValueError("key_id is required")

    @classmethod
    def from_base64_environment(cls, variable: str, key_id: str) -> AESGCMFieldCipher:
        import base64

        raw = os.environ.get(variable)
        if raw is None:
            raise ValueError(f"missing encryption key environment variable: {variable}")
        try:
            key = base64.b64decode(raw, validate=True)
        except ValueError as exc:
            raise ValueError(f"{variable} must contain valid base64") from exc
        return cls(key=key, key_id=key_id)

    def encrypt_json(self, value: dict[str, Any], context: str) -> bytes:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        nonce = os.urandom(12)
        plaintext = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ciphertext = AESGCM(self.key).encrypt(nonce, plaintext, context.encode())
        return b"TA1" + nonce + ciphertext

    def decrypt_json(self, value: bytes, context: str) -> dict[str, Any]:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        if not value.startswith(b"TA1") or len(value) < 32:
            raise ValueError("unsupported or corrupt ciphertext")
        plaintext = AESGCM(self.key).decrypt(value[3:15], value[15:], context.encode())
        result = json.loads(plaintext)
        if not isinstance(result, dict):
            raise ValueError("encrypted value is not a JSON object")
        return result


@dataclass(frozen=True, slots=True)
class DevelopmentPlaintextCipher:
    """Explicitly unsafe codec for tests and local synthetic demonstrations."""

    key_id: str = "development-plaintext"
    is_secure: bool = False

    def encrypt_json(self, value: dict[str, Any], context: str) -> bytes:
        del context
        return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()

    def decrypt_json(self, value: bytes, context: str) -> dict[str, Any]:
        del context
        result = json.loads(value)
        if not isinstance(result, dict):
            raise ValueError("stored value is not a JSON object")
        return result


def require_secure_cipher(cipher: FieldCipher, production: bool) -> None:
    if production and not cipher.is_secure:
        raise ValueError("production mode requires an authenticated field cipher")
