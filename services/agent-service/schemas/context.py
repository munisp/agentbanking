from pydantic import BaseModel


class Context(BaseModel):
    tenant_id: str
    keycloak_id: str
