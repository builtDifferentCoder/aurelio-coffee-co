import os
from typing import List
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ANTHROPIC_API_KEY: str = ""
    PORT: int = 8000
    CHROMA_PERSIST_DIR: str = "./data/chroma_db"
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    RATE_LIMIT_PER_IP_DAILY: int = 30
    MAX_MESSAGES_PER_SESSION: int = 20
    ENVIRONMENT: str = "development"
    MODEL_NAME: str = "claude-3-5-haiku-20241022"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("ANTHROPIC_API_KEY")
    @classmethod
    def validate_anthropic_api_key(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError(
                "ANTHROPIC_API_KEY is missing or empty. "
                "Please configure a valid Anthropic API key in your .env file or environment variables."
            )
        return v.strip()

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]


def get_settings() -> Settings:
    try:
        return Settings()
    except Exception as exc:
        raise RuntimeError(
            f"Failed to initialize application settings: {exc}. "
            "Please ensure all required environment variables (e.g. ANTHROPIC_API_KEY) are set in backend/.env"
        ) from exc


settings = get_settings()
