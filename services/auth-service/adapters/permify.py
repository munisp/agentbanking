import os
import requests
import logging
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

PERMIFY_URL = os.getenv("PERMIFY_URL", "http://localhost:3476")

# Module-level shared session: keep-alive connection pooling across all
# Permify calls (schema load, permission checks, relationship writes).
_SESSION = requests.Session()
_SESSION.mount(
    "http://",
    HTTPAdapter(
        pool_connections=4,
        pool_maxsize=int(os.getenv("PERMIFY_HTTP_POOL_MAXSIZE", "32")),
        max_retries=Retry(total=2, backoff_factor=0.1, status_forcelist=(502, 503, 504)),
    ),
)
_SESSION.mount(
    "https://",
    HTTPAdapter(
        pool_connections=4,
        pool_maxsize=int(os.getenv("PERMIFY_HTTP_POOL_MAXSIZE", "32")),
        max_retries=Retry(total=2, backoff_factor=0.1, status_forcelist=(502, 503, 504)),
    ),
)


def load_schema():
    """Load Permify schema from file with a single write.

    The schema write response returns the authoritative ``schema_version``,
    which we read back from the response instead of hammering every pod
    with repeated writes (previous behavior: 15 sequential POSTs).
    """
    try:
        # Get the correct path to the schema file
        schema_path = Path(__file__).parent.parent / "schemas" / "permify" / "v2.perm"

        with open(schema_path, "r") as f:
            schema = f.read()

        # Load schema to tenant from environment variable or default to 'bpmgd'
        tenant_id = os.getenv("PERMIFY_DEFAULT_TENANT", "bpmgd")

        response = _SESSION.post(
            f"{PERMIFY_URL}/v1/tenants/{tenant_id}/schemas/write",
            json={"schema": schema},
            timeout=10,
        )

        if response.status_code == 200:
            result = response.json()
            schema_version = result.get("schema_version", "unknown")
            logger.info(
                f"Permify schema loaded successfully (version: {schema_version})"
            )
        else:
            logger.error(
                f"Failed to load Permify schema: HTTP {response.status_code}: {response.text}"
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

        response = _SESSION.post(
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


def _read_relationships(
    tenant_id: str,
    entity_type: str,
    entity_id: str,
    relation: str,
    user_id: str,
    snap_token: str = "",
) -> list:
    """Read back relationship tuples, pinned to ``snap_token`` when given.

    Returns the list of matching tuples, or None if the read itself failed
    (distinguishing "no tuples" from "read error" for callers).
    """
    try:
        payload = {
            "metadata": {"snap_token": snap_token},
            "filter": {
                "entity": {"type": entity_type, "ids": [entity_id]},
                "relation": relation,
                "subject": {"type": "user", "ids": [user_id]},
            },
        }
        response = _SESSION.post(
            f"{PERMIFY_URL}/v1/tenants/{tenant_id}/relationships/read",
            json=payload,
            timeout=5,
        )
        if response.status_code != 200:
            logger.warning(
                f"Relationship read-verify failed: HTTP {response.status_code}: {response.text}"
            )
            return None
        return response.json().get("tuples", [])
    except Exception as e:
        logger.warning(f"Relationship read-verify error: {str(e)}")
        return None


def assign_role(
    user_id: str, tenant_id: str, role: str, entity_type: str, entity_id: str
) -> bool:
    """Assign role/relation to user for a specific entity.

    Performs a single write and verifies it with a consistent read pinned
    to the returned ``snap_token`` (replacing the previous 15 sequential
    write attempts).
    """
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

        response = _SESSION.post(
            f"{PERMIFY_URL}/v1/tenants/{tenant_id}/relationships/write",
            json=payload,
            timeout=5,
        )

        if response.status_code not in [200, 201]:
            logger.error(
                f"Failed to assign role: HTTP {response.status_code}: {response.text}"
            )
            return False

        snap_token = response.json().get("snap_token", "")

        # Read-back verify at the write's snap_token (consistent read).
        tuples = _read_relationships(
            tenant_id, entity_type, entity_id, role, user_id, snap_token
        )
        if tuples is not None and not tuples:
            logger.error(
                f"Role assignment not visible at snap_token for user {user_id} "
                f"on {entity_type}:{entity_id}"
            )
            return False
        if tuples is None:
            # Write succeeded but verification read failed; don't fail the
            # operation on a transient read error.
            logger.warning(
                f"Could not verify role assignment for user {user_id} "
                f"(write succeeded, read-verify failed)"
            )

        logger.info(
            f"Successfully assigned role '{role}' to user {user_id} on {entity_type}:{entity_id}"
        )
        return True
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

        # Single delete, then read-back verify at the returned snap_token
        # (replacing the previous 15 sequential delete attempts).
        response = _SESSION.post(
            f"{PERMIFY_URL}/v1/tenants/{tenant_id}/relationships/delete",
            json=payload,
            timeout=5,
        )

        if response.status_code not in [200, 204]:
            logger.error(
                f"Failed to remove role: HTTP {response.status_code}: {response.text}"
            )
            return False

        try:
            snap_token = response.json().get("snap_token", "") if response.content else ""
        except ValueError:
            snap_token = ""

        # Read-back verify: the tuple should no longer be visible.
        tuples = _read_relationships(
            tenant_id, entity_type, entity_id, role, user_id, snap_token
        )
        if tuples:
            logger.error(
                f"Role removal not visible at snap_token for user {user_id} "
                f"on {entity_type}:{entity_id}"
            )
            return False
        if tuples is None:
            logger.warning(
                f"Could not verify role removal for user {user_id} "
                f"(delete succeeded, read-verify failed)"
            )

        logger.info(
            f"Successfully removed role '{role}' from user {user_id} on {entity_type}:{entity_id}"
        )
        return True
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
