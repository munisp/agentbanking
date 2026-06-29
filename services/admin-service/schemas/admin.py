from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class CreateAdminSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    first_name: str = Field(..., alias="firstName")
    last_name: str = Field(..., alias="lastName")
    email: EmailStr
    phone: str
    uin: str
    # Accepts either a platform role or a tenant role (v2.perm named role string)
    access_level: Optional[str] = Field(None, alias="accessLevel")
    platform_role: Optional[str] = Field(None, alias="platformRole")
    tenant_role: Optional[str] = Field(None, alias="tenantRole")
    keycloak_id: str = Field(..., alias="keycloakId")

    def resolved_role(self) -> str:
        """Return the effective role: platform_role or tenant_role or access_level fallback."""
        return (
            self.platform_role
            or self.tenant_role
            or self.access_level
            or "support_agent"
        )


class AdminResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    email: str
    phone: str
    tenant_id: str
    keycloak_id: str
    is_suspended: bool
    access_level: str  # v2.perm named role
