from pydantic import BaseModel

class Context(BaseModel):
    tenant_id: str
    keycloak_realm: str
    keycloak_pub_key: str
