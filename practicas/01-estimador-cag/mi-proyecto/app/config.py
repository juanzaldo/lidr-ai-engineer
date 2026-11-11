from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        hide_input_in_errors=True,
    )

    OPENAI_API_KEY: SecretStr | None = None
    ANTHROPIC_API_KEY: SecretStr | None = None
    ANTHROPIC_WORKSPACE_ID: str | None = None

    LLM_PROVIDER: Literal["openai", "anthropic"] = "openai"
    LLM_MODEL: str = "gpt-4o-mini"
    APP_ENV: str = "development"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "DEBUG"
    MAX_CONVERSATION_TURNS: int = Field(default=6, ge=1)
    MAX_ATTACHMENTS: int = Field(default=5, ge=1)
    MAX_ATTACHMENT_BYTES: int = Field(default=5_000_000, ge=1)
    MAX_TOTAL_ATTACHMENT_BYTES: int = Field(default=10_000_000, ge=1)
    MAX_ATTACHMENT_CHARS: int = Field(default=60_000, ge=1)
    MAX_CONTEXT_CHARS: int = Field(default=80_000, ge=1)

    @model_validator(mode="after")
    def validate_provider_key(self) -> Self:
        key = (
            self.OPENAI_API_KEY
            if self.LLM_PROVIDER == "openai"
            else self.ANTHROPIC_API_KEY
        )

        if key is None or not key.get_secret_value().strip():
            variable = f"{self.LLM_PROVIDER.upper()}_API_KEY"
            raise ValueError(
                f"Debes configurar {variable} para usar {self.LLM_PROVIDER}."
            )

        return self


settings = Settings()
