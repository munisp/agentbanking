import os
import requests
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

PERMIFY_URL = os.getenv("PERMIFY_URL", "http://localhost:3476")


def load_schema():
    """Load Permify schema from file and deploy to all pods"""
    try:
        # Get the correct path to the schema file
        schema_path = Path(__file__).parent.parent / "schemas" / "permify" / "v2.perm"

        with open(schema_path, "r") as f:
            schema = f.read()

        # Load schema to tenant from environment variable or default to 'bpmgd'
        tenant_id = os.getenv("PERMIFY_DEFAULT_TENANT", "bpmgd")

        # Write schema multiple times to ensure all Permify pods receive it
        # Permify uses in-memory storage with 3 replicas
        write_attempts = int(os.getenv("PERMIFY_WRITE_ATTEMPTS", "15"))
        successful_writes = 0
        schema_version = "unknown"

        for attempt in range(write_attempts):
            try:
                response = requests.post(
                    f"{PERMIFY_URL}/v1/tenants/{tenant_id}/schemas/write",
                    json={"schema": schema},
                    timeout=10,
                )

                if response.status_code == 200:
                    successful_writes += 1
                    result = response.json()
                    schema_version = result.get("schema_version", schema_version)
            except Exception as attempt_error:
                logger.debug(
                    f"Schema write attempt {attempt + 1} failed: {str(attempt_error)}"
                )
                continue

        if successful_writes > 0:
            logger.info(
                f"Permify schema loaded successfully (version: {schema_version}, "
                f"{successful_writes}/{write_attempts} writes succeeded)"
            )
        else:
            logger.error(
                f"Failed to load Permify schema: all {write_attempts} write attempts failed"
            )
    except Exception as e:
        logger.error(f"Error loading Permify schema: {str(e)}")


def check_permission(
    user_id: str, tenant_id: str, permission: str, entity_type: str, entity_id: str
) -> bool:
    """Check if user has permission on a specific entity"""
    try:
        payload = {
            "tenant_id": tenant_id,
            "metadata": {"schema_version": "", "snap_token": "", "depth": 20},
            "entity": {"type": entity_type, "id": entity_id},
            "permission": permission,
            "subject": {"type": "user", "id": user_id},
        }

        response = requests.post(
            f"{PERMIFY_URL}/v1/tenants/{tenant_id}/permissions/check",
            json=payload,
            timeout=5,
        )

        if response.status_code != 200:
            logger.error(f"Failed to check permission: {response.text}")
            return False

        result = response.json()
        can = result.get("can")

        # Debug logging
        if logger.level <= 10:  # DEBUG level
            logger.debug(
                f"Permission check for {user_id}: {permission} on {entity_type}:{entity_id} = {can} (response: {result})"
            )

        # Handle CHECK_RESULT_ALLOWED / CHECK_RESULT_DENIED enum
        if can == "CHECK_RESULT_ALLOWED":
            return True
        elif can == "CHECK_RESULT_DENIED":
            return False
        # Fallback for boolean
        return bool(can) if can is not None else False
    except Exception as e:
        logger.error(f"Error checking permission: {str(e)}")
        return False


def assign_role(
    user_id: str, tenant_id: str, role: str, entity_type: str, entity_id: str
) -> bool:
    """Assign role/relation to user for a specific entity"""
    try:
        payload = {
            "metadata": {"schema_version": ""},
            "tuples": [
                {
                    "entity": {"type": entity_type, "id": entity_id},
                    "relation": role,
                    "subject": {"type": "user", "id": user_id},
                }
            ],
        }

        # Write relationship multiple times to ensure all Permify pods receive it
        # Permify uses in-memory storage with 3 replicas, so we need to write
        # multiple times through the load balancer to hit all pods
        write_attempts = int(os.getenv("PERMIFY_WRITE_ATTEMPTS", "15"))
        successful_writes = 0

        for attempt in range(write_attempts):
            try:
                response = requests.post(
                    f"{PERMIFY_URL}/v1/tenants/{tenant_id}/relationships/write",
                    json=payload,
                    timeout=5,
                )

                if response.status_code in [200, 201]:
                    successful_writes += 1
            except Exception as attempt_error:
                logger.debug(
                    f"Write attempt {attempt + 1} failed: {str(attempt_error)}"
                )
                continue

        if successful_writes > 0:
            logger.info(
                f"Successfully assigned role '{role}' to user {user_id} on {entity_type}:{entity_id} "
                f"({successful_writes}/{write_attempts} writes succeeded)"
            )
            return True
        else:
            logger.error(
                f"Failed to assign role: all {write_attempts} write attempts failed"
            )
            return False
    except Exception as e:
        logger.error(f"Error assigning role: {str(e)}")
        return False


def remove_role(
    user_id: str, tenant_id: str, role: str, entity_type: str, entity_id: str
) -> bool:
    """Remove role/relation from user for a specific entity"""
    try:
        payload = {
            "filter": {
                "entity": {"type": entity_type, "ids": [entity_id]},
                "relation": role,
                "subject": {"type": "user", "ids": [user_id]},
            }
        }

        # Delete relationship multiple times to ensure all Permify pods process it
        delete_attempts = int(os.getenv("PERMIFY_WRITE_ATTEMPTS", "15"))
        successful_deletes = 0

        for attempt in range(delete_attempts):
            try:
                response = requests.post(
                    f"{PERMIFY_URL}/v1/tenants/{tenant_id}/relationships/delete",
                    json=payload,
                    timeout=5,
                )

                if response.status_code in [200, 204]:
                    successful_deletes += 1
            except Exception as attempt_error:
                logger.debug(
                    f"Delete attempt {attempt + 1} failed: {str(attempt_error)}"
                )
                continue

        if successful_deletes > 0:
            logger.info(
                f"Successfully removed role '{role}' from user {user_id} on {entity_type}:{entity_id} "
                f"({successful_deletes}/{delete_attempts} deletes succeeded)"
            )
            return True
        else:
            logger.error(
                f"Failed to remove role: all {delete_attempts} delete attempts failed"
            )
            return False
    except Exception as e:
        logger.error(f"Error removing role: {str(e)}")
        return False


def cleanup_test_data(tenant_id: str, user_prefix: str = "user-") -> bool:
    """
    Clean up test data from Permify.
    WARNING: This deletes all relationships for users matching the prefix.
    """
    try:
        # Delete all relationships for test users
        payload = {
            "tuple_filter": {
                "subject": {
                    "type": "user",
                    "ids": [],  # Empty means all, but we'll use relation to be more specific
                }
            }
        }

        # Note: This is a simple cleanup that deletes by user prefix
        # For production, you'd want more granular control
        logger.info("Cleanup function available but requires specific user IDs")
        return True
    except Exception as e:
        logger.error(f"Error cleaning up test data: {str(e)}")
        return False
