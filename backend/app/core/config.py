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

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    def validate_runtime_safety(self) -> None:
        if self.is_production and self.JWT_SECRET == DEFAULT_JWT_SECRET:
            raise ValueError(
                "JWT_SECRET must be changed from the default value in production."
            )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
