from sqlalchemy.orm import Session
from models import Admin
from schemas import CreateAdminSchema, Context


class AdminRepository:
    """Admin repository."""

    def __init__(self, db: Session):
        self.__db = db

    def create_admin(self, payload: CreateAdminSchema, context: Context) -> Admin:
        admin = Admin(
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email,
            phone=payload.phone,
            uin=payload.uin,
            tenant_id=context.tenant_id,
            keycloak_id=payload.keycloak_id,
            access_level=payload.resolved_role(),
        )

        self.__db.add(admin)
        return admin

    def get_admin_by_id(self, admin_id: str, context: Context):
        return (
            self.__db.query(Admin)
            .filter(Admin.id == admin_id, Admin.tenant_id == context.tenant_id)
            .first()
        )

    def get_admin_by_keycloak_id(self, keycloak_id: str, context: Context):
        return (
            self.__db.query(Admin)
            .filter(
                Admin.keycloak_id == keycloak_id, Admin.tenant_id == context.tenant_id
            )
            .first()
        )

    def get_admins(self, context: Context):
        return (
            self.__db.query(Admin)
            .filter(Admin.tenant_id == context.tenant_id)
            .order_by(Admin.created_at)
            .all()
        )

    def set_suspended(self, admin_id: str, context: Context, suspended: bool):
        admin = (
            self.__db.query(Admin)
            .filter(Admin.id == admin_id, Admin.tenant_id == context.tenant_id)
            .first()
        )

        if not admin:
            return None

        admin.is_suspended = suspended
        return admin

    def save_kyc_state(self, keycloak_id: str, payload: dict, context: Context):
        updated = (
            self.__db.query(Admin)
            .filter(
                Admin.keycloak_id == keycloak_id, Admin.tenant_id == context.tenant_id
            )
            .update({Admin.kyc_url: payload.get("kyc_url")}, synchronize_session=False)
        )

        return updated

    def complete_kyc(self, keycloak_id: str, context: Context):
        updated = (
            self.__db.query(Admin)
            .filter(
                Admin.keycloak_id == keycloak_id, Admin.tenant_id == context.tenant_id
            )
            .update({Admin.is_verified: True}, synchronize_session=False)
        )

        return updated
