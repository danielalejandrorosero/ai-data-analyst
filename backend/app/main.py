import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.health import router as health_router
from app.api.router import router as api_router
from app.core.config import settings
from app.core.rate_limit import limiter

# Logging basico (stdout, formato legible) - instrumentacion completa
# (OpenTelemetry/Prometheus/Grafana) es Fase 7, ver docs/SRS.md seccion 9.
# Esto es lo minimo para que los ciclos de vida del agente (orchestrator.py)
# sean visibles via `docker compose logs api`.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(title="AI Data Analyst API", version="0.1.0")

# Rate limiting (slowapi + Redis, ver app/core/rate_limit.py). Patron
# estandar de slowapi: state.limiter + exception handler de RateLimitExceeded
# -> 429 automatico en los endpoints decorados con @limiter.limit(...).
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(api_router, prefix="/api")
