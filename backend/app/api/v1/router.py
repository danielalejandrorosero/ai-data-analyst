from fastapi import APIRouter

from app.api.v1.analyses import router as analyses_router
from app.api.v1.audit_events import router as audit_events_router
from app.api.v1.auth import router as auth_router
from app.api.v1.datasets import router as datasets_router
from app.api.v1.organizations import router as organizations_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(organizations_router)
router.include_router(datasets_router)
router.include_router(analyses_router)
router.include_router(audit_events_router)

# SSE de eventos (/analyses/{id}/events) y artifacts quedan para cuando el
# import/analysis dejen de correr sincronicos en el request - ver
# docs/architecture.md seccion 12.
