import uuid
from datetime import datetime

from pydantic import BaseModel


class AuditEventOut(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    actor_id: uuid.UUID | None
    action: str
    target: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
