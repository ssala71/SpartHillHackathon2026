from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SMS Disaster Resource Coordinator API"
    app_env: str = "development"
    log_level: str = "info"
    database_url: str | None = None
    aws_region: str = "us-east-1"
    bedrock_enabled: bool = False
    bedrock_model_id: str = "amazon.nova-lite-v1:0"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
