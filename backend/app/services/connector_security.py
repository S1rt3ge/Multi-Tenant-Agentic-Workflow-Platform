import base64
import hashlib
import json
import re
from typing import Any

from cryptography.fernet import Fernet

from app.core.config import DEFAULT_DEV_CREDENTIAL_KEY, get_settings


SECRET_KEY_PARTS = {
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_key",
    "private_key",
    "x-api-key",
}

_BEARER_RE = re.compile(r"bearer\s+[A-Za-z0-9._~+/=-]+", flags=re.IGNORECASE)
_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(authorization|cookie|password|secret|token|api_key|apikey|"
    r"access_key|private_key|x-api-key)([\"']?\s*[:=]\s*[\"']?)([^\"'\s,;}{]+)"
)


def _fernet() -> Fernet:
    settings = get_settings()
    material = settings.CREDENTIAL_ENCRYPTION_KEY
    if not material:
        # Never silently fall back to JWT_SECRET: that conflates auth and
        # encryption key domains and makes a routine JWT rotation destroy the
        # ability to decrypt every stored credential. Outside local development
        # the missing key is a hard error (also enforced at startup).
        if not settings.is_local_development:
            raise RuntimeError("CREDENTIAL_ENCRYPTION_KEY is not configured.")
        material = DEFAULT_DEV_CREDENTIAL_KEY
    digest = hashlib.sha256(material.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_config(config: dict[str, Any]) -> dict[str, str]:
    payload = json.dumps(config, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {"ciphertext": _fernet().encrypt(payload).decode("utf-8")}


def decrypt_config(encrypted_config: dict[str, Any]) -> dict[str, Any]:
    ciphertext = encrypted_config.get("ciphertext")
    if not isinstance(ciphertext, str):
        return {}
    payload = _fernet().decrypt(ciphertext.encode("utf-8"))
    return json.loads(payload.decode("utf-8"))


def is_secret_key(key: Any) -> bool:
    lowered = str(key).lower()
    return any(part in lowered for part in SECRET_KEY_PARTS)


def mask_secret(value: Any) -> str:
    text = str(value)
    if len(text) <= 4:
        return "****"
    return f"********{text[-4:]}"


def redact_secret_values(value: Any) -> Any:
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if is_secret_key(key):
                redacted[key] = "****"
            else:
                redacted[key] = redact_secret_values(item)
        return redacted
    if isinstance(value, list):
        return [redact_secret_values(item) for item in value]
    return value


def sanitize_error(message: Any) -> str:
    text = str(message)
    text = _BEARER_RE.sub("Bearer ****", text)
    text = _SECRET_ASSIGNMENT_RE.sub(r"\1\2****", text)
    return text


def build_config_preview(auth_type: str, config: dict[str, Any]) -> dict[str, Any]:
    if auth_type == "api_key_header":
        return {
            "header_name": str(config.get("header_name", "")),
            "header_value": mask_secret(config.get("header_value", "")),
        }
    return redact_secret_values(config)
