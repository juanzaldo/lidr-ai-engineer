from pathlib import Path
from typing import Literal, Self

from pydantic import SecretStr, model_validator
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

    LLM_PROVIDER: Literal["openai", "anthropic"] = "openai"
    LLM_MODEL: str = "gpt-4o-mini"
    APP_ENV: str = "development"
    LOG_LEVEL: str = "DEBUG"

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