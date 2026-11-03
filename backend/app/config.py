from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "UEBA Platform"
    environment: str = "development"

    database_url: str = (
        "postgresql+psycopg://ueba_app:change_me_local_only"
        "@localhost:5432/ueba_db"
    )

    groq_api_key: str = Field(default="", validation_alias="GROQ_API_KEY")
    groq_model: str = Field(default="openai/gpt-oss-20b", validation_alias="GROQ_MODEL")
    groq_max_output_tokens: int = Field(default=900, ge=128, le=4096, validation_alias="GROQ_MAX_OUTPUT_TOKENS")
    groq_timeout_seconds: float = Field(default=30.0, gt=0, le=180, validation_alias="GROQ_TIMEOUT_SECONDS")

    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", PROJECT_ROOT / "backend" / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
