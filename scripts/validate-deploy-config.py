import os
import sys
from urllib.parse import urlparse


REQUIRED_SECRETS = [
    "DEPLOY_HOST",
    "DEPLOY_USER",
    "DEPLOY_PATH",
    "DEPLOY_SSH_KEY",
    "DB_PASSWORD",
    "JWT_SECRET",
]

OPTIONAL_SECRETS = [
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
]

REQUIRED_VARS = [
    "CORS_ORIGINS",
]

OPTIONAL_VARS = [
    "LOG_LEVEL",
    "LOG_FORMAT",
    "VITE_API_URL",
]


def main() -> int:
    missing = []
    errors = []

    for key in REQUIRED_SECRETS:
        value = os.getenv(key, "").strip()
        if not value:
            missing.append(f"secret:{key}")

    for key in REQUIRED_VARS:
        value = os.getenv(key, "").strip()
        if not value:
            missing.append(f"var:{key}")

    if missing:
        print("Missing deployment configuration:", file=sys.stderr)
        for item in missing:
            print(f"- {item}", file=sys.stderr)
        errors.append("missing required configuration")

    jwt_secret = os.getenv("JWT_SECRET", "")
    if jwt_secret and (len(jwt_secret) < 32 or jwt_secret in {"change-me-in-production-use-256-bit-random-key", "dev-secret-change-in-production"}):
        errors.append("JWT_SECRET must be a non-placeholder value with at least 32 characters")

    db_password = os.getenv("DB_PASSWORD", "")
    if db_password and (len(db_password) < 16 or db_password.lower() in {"password", "localpassword", "changeme"}):
        errors.append("DB_PASSWORD must be a non-placeholder value with at least 16 characters")

    cors_origins = [item.strip() for item in os.getenv("CORS_ORIGINS", "").split(",") if item.strip()]
    for origin in cors_origins:
        parsed = urlparse(origin)
        if origin == "*" or parsed.scheme != "https" or not parsed.netloc:
            errors.append("CORS_ORIGINS must contain explicit https origins only")
            break

    vite_api_url = os.getenv("VITE_API_URL", "").strip()
    if vite_api_url:
        parsed = urlparse(vite_api_url)
        if parsed.scheme != "https" or not parsed.netloc:
            errors.append("VITE_API_URL must be an https URL when set")

    log_format = os.getenv("LOG_FORMAT", "json") or "json"
    if log_format not in {"json", "text"}:
        errors.append("LOG_FORMAT must be json or text")

    log_level = os.getenv("LOG_LEVEL", "INFO") or "INFO"
    if log_level.upper() not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        errors.append("LOG_LEVEL is invalid")

    if errors:
        for error in errors:
            print(f"Configuration error: {error}", file=sys.stderr)
        return 1

    print("Required deployment configuration is present.")

    for key in OPTIONAL_SECRETS + OPTIONAL_VARS:
        if not os.getenv(key, "").strip():
            print(f"Optional deployment configuration not set: {key}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
