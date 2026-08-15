from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"

    database_url: str
    redis_url: str

    auth_secret_key: str
    auth_token_expire_minutes: int = 60

    secret_encryption_key: str

    llm_provider: str = ""
    llm_api_key: str = ""
    llm_model: str = ""

    agent_sql_timeout_seconds: int = 30
    agent_sql_max_rows: int = 5000

    otel_exporter_otlp_endpoint: str = ""

    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
