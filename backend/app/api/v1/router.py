from fastapi import APIRouter

from app.api.v1.audit_events import router as audit_events_router
from app.api.v1.auth import router as auth_router
from app.api.v1.datasets import router as datasets_router
from app.api.v1.organizations import router as organizations_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(organizations_router)
router.include_router(datasets_router)
router.include_router(audit_events_router)

# Los routers de analyses, agent, etc. se agregan aca a medida que se
# implementan (Fase 3 en adelante). Ver docs/SRS.md seccion 7.
