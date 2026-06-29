from sqlalchemy.orm import Session
from models.trustedDevices import TrustedDevice
from typing import Optional
import hashlib


class DeviceRepository:
    """Device repository for trusted devices."""

    def __init__(self, db: Session):
        self.__db = db

    def get_trusted_device(
        self, device_id: str, user_email: str, tenant_id: str
    ) -> Optional[TrustedDevice]:
        """Get a trusted device by device_id, user_email and tenant_id."""
        return (
            self.__db.query(TrustedDevice)
            .filter(
                TrustedDevice.device_id == device_id,
                TrustedDevice.user_email == user_email,
                TrustedDevice.tenant_id == tenant_id,
            )
            .first()
        )

    def create_or_update_trusted_device(
        self,
        device_id: str,
        device_ip: str,
        user_agent: str,
        user_email: str,
        tenant_id: str,
        keycloak_id: str = None,
    ) -> TrustedDevice:
        """Create or update a trusted device."""
        existing_device = self.get_trusted_device(device_id, user_email, tenant_id)

        if existing_device:
            # Update existing device
            existing_device.device_ip = device_ip
            existing_device.user_agent = user_agent
            if keycloak_id:
                existing_device.keycloak_id = keycloak_id
            return existing_device
        else:
            # Create new trusted device
            device = TrustedDevice(
                device_id=device_id,
                device_ip=device_ip,
                user_agent=user_agent,
                user_email=user_email,
                tenant_id=tenant_id,
                keycloak_id=keycloak_id or "",
            )
            self.__db.add(device)
            return device

    def get_user_devices(self, user_email: str, tenant_id: str):
        """Get all trusted devices for a user."""
        return (
            self.__db.query(TrustedDevice)
            .filter(
                TrustedDevice.user_email == user_email,
                TrustedDevice.tenant_id == tenant_id,
            )
            .all()
        )

    def get_user_devices_by_keycloak_id(self, keycloak_id: str, tenant_id: str):
        """Get all trusted devices for a user by keycloak_id."""
        return (
            self.__db.query(TrustedDevice)
            .filter(
                TrustedDevice.keycloak_id == keycloak_id,
                TrustedDevice.tenant_id == tenant_id,
            )
            .all()
        )

    def get_trusted_device_by_keycloak(
        self, device_id: str, keycloak_id: str, tenant_id: str
    ):
        """Get a trusted device by device_id, keycloak_id and tenant_id."""
        return (
            self.__db.query(TrustedDevice)
            .filter(
                TrustedDevice.device_id == device_id,
                TrustedDevice.keycloak_id == keycloak_id,
                TrustedDevice.tenant_id == tenant_id,
            )
            .first()
        )

    @staticmethod
    def generate_device_id(user_agent: str, ip: str) -> str:
        """Generate a unique device ID based on user agent and IP."""
        device_string = f"{user_agent}_{ip}"
        return hashlib.sha256(device_string.encode()).hexdigest()
