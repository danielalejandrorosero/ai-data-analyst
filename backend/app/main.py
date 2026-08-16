import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.v1.router import router as v1_router
from app.core.config import settings

# Logging basico (stdout, formato legible) - instrumentacion completa
# (OpenTelemetry/Prometheus/Grafana) es Fase 7, ver docs/SRS.md seccion 9.
# Esto es lo minimo para que los ciclos de vida del agente (orchestrator.py)
# sean visibles via `docker compose logs api`.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(title="AI Data Analyst API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(v1_router, prefix="/api/v1")
