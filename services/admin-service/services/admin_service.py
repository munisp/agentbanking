from sqlalchemy.orm import Session
from repositories import AdminRepository
from utils import create_logger
from schemas import CreateAdminSchema, Context
from fastapi import HTTPException

logger = create_logger(__name__)


class AdminService:
    def __init__(self, db: Session):
        self.__db = db
        self.__repository = AdminRepository(db)

    def create_admin(self, payload: CreateAdminSchema, context: Context):
        admin = self.__repository.create_admin(payload, context)
        self.__db.commit()

        logger.info(f"Admin created: {admin.email}")
        return admin

    def get_admin_by_id(self, admin_id: str, context: Context):
        admin = self.__repository.get_admin_by_id(admin_id, context)

        if not admin:
            raise HTTPException(status_code=404, detail="Admin not found")

        return admin

    def get_admin_by_keycloak_id(self, keycloak_id: str, context: Context):
        admin = self.__repository.get_admin_by_keycloak_id(keycloak_id, context)

        if not admin:
            raise HTTPException(status_code=404, detail="Admin not found")

        return admin

    def get_admins(self, context: Context):
        return self.__repository.get_admins(context)

    def suspend_admin(self, admin_id: str, context: Context):
        admin = self.__repository.set_suspended(admin_id, context, True)
        self.__db.commit()
        return admin

    def unsuspend_admin(self, admin_id: str, context: Context):
        admin = self.__repository.set_suspended(admin_id, context, False)
        self.__db.commit()
        return admin

    def save_kyc_state(self, keycloak_id: str, payload: dict, context: Context):
        admin = self.__repository.get_admin_by_keycloak_id(keycloak_id, context)

        if not admin:
            raise HTTPException(status_code=404, detail="Admin not found")

        self.__repository.save_kyc_state(keycloak_id, payload, context)
        self.__db.commit()
        self.__db.refresh(admin)

        logger.info(f"KYC state saved for admin {admin.id}")
        return admin

    def complete_kyc(self, keycloak_id: str, context: Context):
        admin = self.__repository.get_admin_by_keycloak_id(keycloak_id, context)

        if not admin:
            raise HTTPException(status_code=404, detail="Admin not found")

        self.__repository.complete_kyc(keycloak_id, context)
        self.__db.commit()
        self.__db.refresh(admin)

        logger.info(f"KYC completed for admin {admin.id}")
        return admin
