import threading
from utils import ExternalAPIClient, get_config, create_logger
from schemas.v1 import Context, AuditEventSchema

logger = create_logger(__name__)
config = get_config()


class AuditServiceAdapter(ExternalAPIClient):
    """Audit service adapter."""

    def __init__(self):
        ExternalAPIClient.__init__(
            self,
            base_url=config.AUDIT_SVC_URL,
            headers={
                "Content-Type": "application/json",
            },
        )

    def _emit_audit(self, payload: AuditEventSchema, context: Context):
        headers = {
            "x-tenant-id": context.tenant_id,
            "x-keycloak-id": "system",
        }

        try:
            self._post(
                endpoint="/audits",
                data=payload.model_dump(),
                headers=headers,
            )
        except Exception as exc:
            # Explicitly swallow — audit failures must never affect core flow
            logger.warning(
                "Failed to emit audit event"
            )

    def create_audit(self, payload: AuditEventSchema, context: Context):
        """Fire-and-forget audit emission."""

        thread = threading.Thread(
            target=self._emit_audit,
            args=(payload, context),
            daemon=True,  # Dies with the process
        )
        thread.start()
