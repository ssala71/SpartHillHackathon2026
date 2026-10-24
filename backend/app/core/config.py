from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "SMS Disaster Resource Coordinator API"
    app_env: str = "development"
    log_level: str = "info"
    database_url: str | None = None
    aws_region: str = "us-east-1"
    bedrock_enabled: bool = False
    # Claude Sonnet 5.5 via the US cross-region inference profile (required for this model).
    bedrock_model_id: str = "us.anthropic.claude-sonnet-5-5"
    # "gazetteer" (offline demo landmarks) or "aws_location" (Amazon Location Service)
    geocoding_provider: str = "gazetteer"
    # Bias geocoding toward downtown San Jose.
    geocoding_bias_latitude: float = 37.3382
    geocoding_bias_longitude: float = -121.8863

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
