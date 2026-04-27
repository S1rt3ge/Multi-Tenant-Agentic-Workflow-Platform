from pydantic_settings import BaseSettings
from functools import lru_cache


DEFAULT_JWT_SECRET = "change-me-in-production-use-256-bit-random-key"


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

    # LLM Providers
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # App
    APP_ENV: str = "development"
    CORS_ORIGINS: str = "http://localhost:3000"
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    @property
    def is_local_development(self) -> bool:
        return self.APP_ENV.lower() in {"development", "dev", "local", "test"}

    def validate_runtime_safety(self) -> None:
        if not self.is_local_development and self.JWT_SECRET == DEFAULT_JWT_SECRET:
            raise ValueError(
                "JWT_SECRET must be changed from the default value outside local development."
            )
        if not self.is_local_development and len(self.JWT_SECRET) < 32:
            raise ValueError("JWT_SECRET must be at least 32 characters outside local development.")


@lru_cache()
def get_settings() -> Settings:
    return Settings()
