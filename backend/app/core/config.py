from pydantic_settings import BaseSettings
from functools import lru_cache


DEFAULT_JWT_SECRET = "change-me-in-production-use-256-bit-random-key"
# Used ONLY for local development / tests when CREDENTIAL_ENCRYPTION_KEY is unset.
# Decoupled from JWT_SECRET so rotating the auth secret never breaks decryption.
DEFAULT_DEV_CREDENTIAL_KEY = "dev-only-credential-encryption-key-do-not-use-in-prod"


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = (
        "postgresql+asyncpg://platform:password@localhost:5432/agentic_platform"
    )

    # Auth
    JWT_SECRET: str = DEFAULT_JWT_SECRET
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    CREDENTIAL_ENCRYPTION_KEY: str = ""

    # Refresh-token cookie (httpOnly). Secure defaults to on in production.
    REFRESH_COOKIE_NAME: str = "refresh_token"
    REFRESH_COOKIE_PATH: str = "/api/v1/auth"
    REFRESH_COOKIE_SAMESITE: str = "lax"  # lax | strict | none (none requires https)
    REFRESH_COOKIE_SECURE: bool | None = None  # None -> auto (secure in production)

    # LLM Providers
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # App
    APP_ENV: str = "development"
    CORS_ORIGINS: str = "http://localhost:3000"
    # Set True only when behind a trusted reverse proxy that sets X-Forwarded-For.
    RATE_LIMIT_TRUST_FORWARDED: bool = False
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    WEBHOOK_DISPATCHER_ENABLED: bool = False
    WEBHOOK_DISPATCHER_INTERVAL_SECONDS: float = 5.0
    WEBHOOK_DISPATCHER_BATCH_LIMIT: int = 10
    DISPATCH_ALERT_EVALUATOR_ENABLED: bool = False
    DISPATCH_ALERT_EVALUATOR_INTERVAL_SECONDS: float = 60.0
    DISPATCH_ALERT_EVALUATOR_TENANT_LIMIT: int = 25
    DISPATCH_ALERT_EVALUATOR_WINDOW_HOURS: int = 24
    DISPATCH_AUTOMATION_WORKER_ENABLED: bool = False
    DISPATCH_AUTOMATION_WORKER_INTERVAL_SECONDS: float = 60.0
    DISPATCH_AUTOMATION_WORKER_TENANT_LIMIT: int = 25

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    @property
    def is_local_development(self) -> bool:
        # NOTE: "test" is intentionally excluded so a production deployment that
        # accidentally sets APP_ENV=test does not bypass the runtime secret
        # checks. The pytest suite runs with the default APP_ENV ("development").
        return self.APP_ENV.lower() in {"development", "dev", "local"}

    def validate_runtime_safety(self) -> None:
        if self.is_local_development:
            return
        if self.JWT_SECRET == DEFAULT_JWT_SECRET:
            raise ValueError(
                "JWT_SECRET must be changed from the default value outside local development."
            )
        if len(self.JWT_SECRET) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters outside local development.")
        if not self.CREDENTIAL_ENCRYPTION_KEY:
            raise ValueError(
                "CREDENTIAL_ENCRYPTION_KEY must be set outside local development."
            )
        if len(self.CREDENTIAL_ENCRYPTION_KEY) < 32:
            raise ValueError(
                "CREDENTIAL_ENCRYPTION_KEY must be at least 32 characters outside local development."
            )
        if self.CREDENTIAL_ENCRYPTION_KEY == self.JWT_SECRET:
            raise ValueError(
                "CREDENTIAL_ENCRYPTION_KEY must be different from JWT_SECRET "
                "to keep auth and encryption key domains separate."
            )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
