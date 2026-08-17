from fastapi import APIRouter

from app.api.analyses import router as analyses_router
from app.api.audit_events import router as audit_events_router
from app.api.auth import router as auth_router
from app.api.datasets import router as datasets_router
from app.api.documents import router as documents_router
from app.api.organizations import router as organizations_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(organizations_router)
router.include_router(datasets_router)
router.include_router(documents_router)
router.include_router(analyses_router)
router.include_router(audit_events_router)
