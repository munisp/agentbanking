import threading
from typing import Dict

import httpx

from utils import create_logger, get_config
from schemas import Context, AuditEventSchema

logger = create_logger(__name__)
config = get_config()


class AuditServiceAdapter:
    """Audit service adapter with non-blocking best-effort delivery."""

    def __init__(self):
        self.base_url = config.AUDIT_SVC_URL.rstrip("/")

    def _emit_audit(self, payload: AuditEventSchema, context: Context):
        headers: Dict[str, str] = {
            "Content-Type": "application/json",
            "x-tenant-id": context.tenant_id,
            "x-keycloak-id": context.keycloak_id or "system",
        }

        try:
            with httpx.Client(timeout=10.0) as client:
                client.post(
                    f"{self.base_url}/audits",
                    json=payload.model_dump(),
                    headers=headers,
                )
        except Exception:
            logger.warning("Failed to emit audit event")

    def create_audit(self, payload: AuditEventSchema, context: Context):
        """Fire-and-forget audit emission."""
        thread = threading.Thread(
            target=self._emit_audit,
            args=(payload, context),
            daemon=True,
        )
        thread.start()
