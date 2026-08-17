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
    # Limites de complejidad de la consulta generada por el agente (RF-032) -
    # ademas de timeout/max_rows. El validador ya restringe a una unica tabla
    # fisica (mas CTEs), asi que estos limites acotan self-joins y subqueries
    # anidadas, no joins entre tablas distintas (eso ya esta bloqueado).
    agent_sql_max_joins: int = 2
    agent_sql_max_subqueries: int = 3
    # RF-022: el agente puede ejecutar mas de una consulta por pregunta
    # compleja - sin un tope, un LLM en loop es un vector de costo/DoS
    # nuevo que las otras defensas (timeout/max_rows/complejidad) no cubren
    # por si solas, porque cada consulta individual puede ser perfectamente
    # valida.
    agent_max_queries_per_run: int = 5
    # RF-041: mismo motivo que agent_max_queries_per_run, pero para
    # artifacts de tipo grafico (create_chart) - acota cuantas filas
    # analysis_artifacts puede generar un unico analysis.
    agent_max_charts_per_run: int = 5
    # Memoria entre analisis del mismo dataset (docs/adr/0010-agent-history-context.md) -
    # cuantos analisis COMPLETED previos se le pasan como contexto de
    # solo lectura al agente. "Todo el historial" en espiritu, acotado en
    # cantidad para no inflar sin limite el prompt/costo de cada corrida.
    agent_history_max_analyses: int = 10

    # Limites de importacion de datasets (RNF-014, RF-011).
    import_max_file_size_mb: int = 20
    import_max_rows: int = 200_000

    # RAG documental (SRS 3.7, RF-060 a RF-065, ADR-0011). El modelo es
    # configurable pero la dimension del vector (384) esta fija en el
    # schema - cambiar a un modelo de otra dimension exige migracion +
    # re-indexar, no solo editar esto.
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    document_max_file_size_mb: int = 20
    document_chunk_chars: int = 1200
    document_chunk_overlap_chars: int = 200
    document_search_top_k: int = 8
    # Presupuesto propio de search_documents por analisis (RF-063) -
    # separado del de consultas SQL, mismo motivo anti-loop.
    agent_max_doc_searches_per_run: int = 3

    # RF-053: retencion configurable de logs y resultados. En dias; un valor
    # <= 0 significa "retencion deshabilitada" (nunca borrar), no "borrar
    # todo ahora" - interpretar 0 como borrado inmediato seria destructivo y
    # sorprendente para quien solo quiere apagar la feature. Purga corre a
    # nivel de toda la plataforma (job de mantenimiento, sin organization_id),
    # ver domain/retention/service.py y workers/tasks/retention.py.
    audit_event_retention_days: int = 90
    analysis_retention_days: int = 180

    otel_exporter_otlp_endpoint: str = ""

    cors_origins: str = "http://localhost:5173"

    # Rate limiting (docs/security/threat-model.md - gap de fuerza bruta en
    # /auth/login y de costo de computo en import/documents/search). slowapi
    # + Redis, reusando settings.redis_url (mismo Redis que ARQ, ver
    # app/core/redis_client.py) en vez de un store nuevo. rate_limit_enabled
    # existe sobre todo para la suite de tests de integracion: corren
    # cientos de requests de login/register/import en la misma sesion
    # (misma IP/usuario simulados), asi que se apaga por default en
    # tests/conftest.py y se prende puntualmente en los tests que verifican
    # el 429.
    rate_limit_enabled: bool = True
    # RF/RNF sin numero propio todavia (gap de seguridad, no de producto) -
    # 5/minuto alcanza para uso legitimo (typos de password) y frena fuerza
    # bruta/enumeracion de emails.
    rate_limit_auth: str = "5/minute"
    # import/documents/search: mas permisivo que login porque son acciones
    # de trabajo normal de un usuario ya autenticado, pero cada una dispara
    # trabajo costoso (parseo de archivo, embeddings, o una query vectorial
    # por request).
    rate_limit_expensive: str = "10/minute"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
