from pydantic import BaseModel


class AuditEventSchema(BaseModel):
    actor_id: str
    tenant_id: str
    event_type: str
    event_data: dict
    timestamp: str
