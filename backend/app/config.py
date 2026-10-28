from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    app_name: str = "UEBA Platform"
    environment: str = "development"

    database_url: str = (
        "postgresql+psycopg://ueba_app:change_me_local_only"
        "@localhost:5432/ueba_db"
    )

    llm_api_key: str = ""
    llm_model: str = ""
    llm_base_url: str = ""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()