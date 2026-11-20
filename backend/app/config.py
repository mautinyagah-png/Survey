"""Application settings loaded from environment variables.

Required values are declared without defaults so the application refuses to
start if they are missing. This prevents accidental use of weak defaults.
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Survey Platform API"
    environment: str = "development"
    debug: bool = False

    database_url: str

    jwt_secret_key: str = Field(..., min_length=32)
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    refresh_token_days: int = 14

    allowed_origins: str = "http://localhost:5500,http://127.0.0.1:5500"

    # Daraja credentials are optional until payment checkout is configured.
    mpesa_environment: str = "sandbox"
    mpesa_consumer_key: str | None = None
    mpesa_consumer_secret: str | None = None
    mpesa_shortcode: str | None = None
    mpesa_passkey: str | None = None
    mpesa_callback_url: str | None = None
    mpesa_transaction_type: str = "CustomerPayBillOnline"
    mpesa_encryption_key: str | None = None

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @field_validator("jwt_secret_key")
    @classmethod
    def _reject_placeholder_secret(cls, value: str) -> str:
        placeholders = {"change-me", "changeme", "secret", "please-change"}
        if value.strip().lower() in placeholders:
            raise ValueError("JWT_SECRET_KEY must not be a placeholder value.")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
