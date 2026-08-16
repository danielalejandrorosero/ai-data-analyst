from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "local"

    database_url: str
    redis_url: str

    # Conexion de solo lectura para SQL generado por el agente (RF-030) -
    # rol Postgres separado, sin permisos sobre las tablas de la
    # plataforma. Ver infrastructure/postgres/init/002-agent-readonly-role.sh
    # y docs/adr/0004-secrets-management.md.
    agent_database_url: str = ""

    auth_secret_key: str
    auth_token_expire_minutes: int = 60

    secret_encryption_key: str

    llm_provider: str = ""
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""

    agent_sql_timeout_seconds: int = 30
    agent_sql_max_rows: int = 5000

    # Limites de importacion de datasets (RNF-014, RF-011).
    import_max_file_size_mb: int = 20
    import_max_rows: int = 200_000

    otel_exporter_otlp_endpoint: str = ""

    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
