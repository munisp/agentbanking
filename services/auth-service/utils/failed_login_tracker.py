"""
Failed Login Attempt Tracking and Account Suspension Service
"""

import json
from datetime import datetime, timedelta
from typing import Optional, Dict
from sqlalchemy.orm import Session
from utils.helpers import create_logger
from utils.external_api_client import ExternalAPIClient
from utils.config import get_config

logger = create_logger(__name__)
config = get_config()


class FailedLoginTracker:
    """Tracks failed login attempts and triggers account suspension after threshold"""

    MAX_ATTEMPTS = 6
    LOCKOUT_DURATION_MINUTES = 30  # How long to track failed attempts

    def __init__(self, db: Session):
        self.db = db
        self._cache = {}  # In-memory cache for failed attempts
        # Note: For production, use Redis for distributed tracking

    def record_failed_attempt(
        self, email: str, tenant_id: str, keycloak_id: Optional[str] = None
    ) -> Dict:
        """
        Record a failed login attempt.

        Args:
            email: User's email
            tenant_id: Tenant ID
            keycloak_id: Keycloak ID (if available)

        Returns:
            Dict with attempt info: {
                'attempts': int,
                'remaining': int,
                'suspended': bool,
                'lockout_until': datetime (if suspended)
            }
        """
        cache_key = f"{tenant_id}:{email}"

        # Get or initialize attempt data
        if cache_key not in self._cache:
            self._cache[cache_key] = {
                "attempts": 0,
                "first_attempt": datetime.utcnow(),
                "keycloak_id": keycloak_id,
            }

        attempt_data = self._cache[cache_key]

        # Check if lockout period has expired
        if datetime.utcnow() - attempt_data["first_attempt"] > timedelta(
            minutes=self.LOCKOUT_DURATION_MINUTES
        ):
            # Reset counter if lockout period has passed
            logger.info(
                f"Lockout period expired for {email}. Resetting failed attempt counter."
            )
            attempt_data["attempts"] = 0
            attempt_data["first_attempt"] = datetime.utcnow()

        # Increment attempts
        attempt_data["attempts"] += 1
        remaining = max(0, self.MAX_ATTEMPTS - attempt_data["attempts"])

        logger.warning(
            f"Failed login attempt {attempt_data['attempts']}/{self.MAX_ATTEMPTS} for {email} (tenant: {tenant_id})"
        )

        result = {
            "attempts": attempt_data["attempts"],
            "remaining": remaining,
            "suspended": False,
            "lockout_until": None,
        }

        # Trigger suspension if max attempts reached
        if attempt_data["attempts"] >= self.MAX_ATTEMPTS:
            logger.critical(
                f"Max failed login attempts reached for {email}. Triggering account suspension."
            )

            # Suspend the account
            if keycloak_id:
                suspension_result = self._suspend_account(
                    keycloak_id=keycloak_id, tenant_id=tenant_id, email=email
                )
                result["suspended"] = suspension_result
            else:
                logger.error(
                    f"Cannot suspend account for {email} - keycloak_id not available"
                )

            lockout_until = datetime.utcnow() + timedelta(
                minutes=self.LOCKOUT_DURATION_MINUTES
            )
            result["lockout_until"] = lockout_until

        return result

    def reset_attempts(self, email: str, tenant_id: str):
        """Reset failed attempts counter (e.g., after successful login)"""
        cache_key = f"{tenant_id}:{email}"
        if cache_key in self._cache:
            logger.info(f"Resetting failed login attempts for {email}")
            del self._cache[cache_key]

    def get_remaining_attempts(self, email: str, tenant_id: str) -> int:
        """Get remaining login attempts before suspension"""
        cache_key = f"{tenant_id}:{email}"
        if cache_key not in self._cache:
            return self.MAX_ATTEMPTS

        attempt_data = self._cache[cache_key]

        # Check if lockout period has expired
        if datetime.utcnow() - attempt_data["first_attempt"] > timedelta(
            minutes=self.LOCKOUT_DURATION_MINUTES
        ):
            return self.MAX_ATTEMPTS

        return max(0, self.MAX_ATTEMPTS - attempt_data["attempts"])

    def _suspend_account(
        self, keycloak_id: str, tenant_id: str, email: str
    ) -> bool:
        """
        Suspend user or admin account via external API.

        Args:
            keycloak_id: Keycloak ID
            tenant_id: Tenant ID
            email: User email

        Returns:
            bool: True if suspension successful, False otherwise
        """
        try:
            # First, get user/admin details to get their ID
            user_details = self._get_user_or_admin_details(
                keycloak_id=keycloak_id, tenant_id=tenant_id
            )

            if not user_details:
                logger.error(
                    f"Failed to get user/admin details for keycloak_id: {keycloak_id}"
                )
                return False

            account_type = user_details["type"]  # 'user' or 'admin'
            account_id = user_details["id"]

            # Suspend the account
            suspension_success = self._call_suspension_api(
                account_type=account_type, account_id=account_id, tenant_id=tenant_id
            )

            if suspension_success:
                logger.info(
                    f"Successfully suspended {account_type} account: {email} (ID: {account_id})"
                )
            else:
                logger.error(
                    f"Failed to suspend {account_type} account: {email} (ID: {account_id})"
                )

            return suspension_success

        except Exception as e:
            logger.error(f"Error suspending account for {email}: {e}")
            return False

    def _get_user_or_admin_details(
        self, keycloak_id: str, tenant_id: str
    ) -> Optional[Dict]:
        """
        Get user or admin details from external APIs.
        
        IMPORTANT: 
        - GET endpoints use keycloak_id to fetch the account
        - Returns the account's 'id' field (UUID for users, int for admins)
        - This 'id' is then used for the suspension endpoint

        Returns:
            Dict with 'type' ('user' or 'admin') and 'id', or None if not found
        """
        base_url = "https://54agent-dev.upi.dev"

        # Try to get as user first
        # GET /user/user?keycloak_id={keycloak_id}
        try:
            user_client = ExternalAPIClient(
                base_url=base_url,
                headers={
                    "x-tenant-id": tenant_id,
                    "Content-Type": "application/json",
                },
            )

            user_response = user_client._get(
                endpoint=f"/user/user", params={"keycloak_id": keycloak_id}
            )

            if user_response and user_response.get("user"):
                user_data = user_response["user"]
                logger.info(f"Found user account with keycloak_id: {keycloak_id}")
                # Extract the user's UUID id (not keycloak_id) for suspension endpoint
                return {"type": "user", "id": user_data["id"], "data": user_data}

        except Exception as e:
            logger.info(
                f"Not a user account (keycloak_id: {keycloak_id}): {e}. Trying admin..."
            )

        # Try to get as admin
        # GET /admin/admin/keycloak/{keycloak_id}
        try:
            admin_client = ExternalAPIClient(
                base_url=base_url,
                headers={
                    "x-tenant-id": tenant_id,
                    "Content-Type": "application/json",
                },
            )

            admin_response = admin_client._get(
                endpoint=f"/admin/admin/keycloak/{keycloak_id}"
            )

            if admin_response and admin_response.get("admin"):
                admin_data = admin_response["admin"]
                logger.info(f"Found admin account with keycloak_id: {keycloak_id}")
                # Extract the admin's integer id (not keycloak_id) for suspension endpoint
                return {"type": "admin", "id": admin_data["id"], "data": admin_data}

        except Exception as e:
            logger.error(
                f"Not an admin account (keycloak_id: {keycloak_id}): {e}"
            )

        logger.error(
            f"Could not find user or admin account with keycloak_id: {keycloak_id}"
        )
        return None

    def _call_suspension_api(
        self, account_type: str, account_id: str, tenant_id: str
    ) -> bool:
        """
        Call the appropriate suspension API endpoint.
        
        IMPORTANT:
        - Suspension endpoints use the account's 'id' (NOT keycloak_id)
        - User: PUT /user/user/{user_uuid}/suspend
        - Admin: PATCH /admin/admin/{admin_int_id}/suspend

        Args:
            account_type: 'user' or 'admin'
            account_id: User UUID or Admin integer ID (NOT keycloak_id)
            tenant_id: Tenant ID

        Returns:
            bool: True if successful, False otherwise
        """
        base_url = "https://54agent-dev.upi.dev"

        try:
            client = ExternalAPIClient(
                base_url=base_url,
                headers={
                    "x-tenant-id": tenant_id,
                    "Content-Type": "application/json",
                },
            )

            if account_type == "user":
                # PUT /user/user/{id}/suspend (id is user UUID from user.id)
                endpoint = f"/user/user/{account_id}/suspend"
                response = client._put(endpoint=endpoint, get_response=False)
            else:  # admin
                # PATCH /admin/admin/{id}/suspend (id is admin integer from admin.id)
                endpoint = f"/admin/admin/{account_id}/suspend"
                response = client._patch(endpoint=endpoint, get_response=False)

            status_code = response.get("status_code", 0)

            if status_code == 200:
                logger.info(
                    f"Successfully suspended {account_type} ID: {account_id}"
                )
                return True
            else:
                logger.error(
                    f"Failed to suspend {account_type} ID: {account_id}. Status: {status_code}"
                )
                return False

        except Exception as e:
            logger.error(
                f"Error calling suspension API for {account_type} ID {account_id}: {e}"
            )
            return False


# Singleton instance
_failed_login_tracker_instance = None


def get_failed_login_tracker(db: Session) -> FailedLoginTracker:
    """Get or create FailedLoginTracker instance"""
    global _failed_login_tracker_instance
    if _failed_login_tracker_instance is None:
        _failed_login_tracker_instance = FailedLoginTracker(db)
    return _failed_login_tracker_instance
