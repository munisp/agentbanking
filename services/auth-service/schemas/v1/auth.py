from pydantic import BaseModel
from typing import Optional
from utils import UserRole


class CreateAuth(BaseModel):
    name: Optional[str] = None
    email: str
    user_role: Optional[UserRole] = None
    # v2.perm Permify roles — use one or both depending on the user scope:
    # platform_role → assigned on the `platform` entity (54agent-level admins)
    # tenant_role   → assigned on the `tenants` entity (bank/tenant-level staff)
    platform_role: Optional[str] = (
        None  # e.g. "super_admin", "it_admin", "compliance_officer"
    )
    tenant_role: Optional[str] = (
        None  # e.g. "branch_manager", "loan_officer", "vault_manager"
    )


class Login(BaseModel):
    email: str
    password: str
    type: Optional[UserRole] = None


class SetupPassword(BaseModel):
    keycloak_id: str
    password: str
    confirm_password: str


class ForgotPassword(BaseModel):
    email: str


class ResetPassword(BaseModel):
    keycloak_id: str
    otp_code: str
    new_password: str
    confirm_password: str


class ChangePassword(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str


class VerifyOTP(BaseModel):
    keycloak_id: str
    otp_code: str
