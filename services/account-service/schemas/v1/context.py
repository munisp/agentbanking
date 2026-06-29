from pydantic import BaseModel

class Context(BaseModel):
    tenant_id: str
    keycloak_id: str
    ledger_id: str
    mint_account_id: str | None = None
