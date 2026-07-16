import time
from utils import ExternalAPIClient, get_config, create_logger
from schemas import Context, AuditEventSchema

logger = create_logger(__name__)
config = get_config()

_MAX_RETRIES = 3
_RETRY_DELAYS = [0.2, 0.5, 1.0]  # seconds between retries


class AuditServiceAdapter(ExternalAPIClient):
    """Audit service adapter — synchronous with retry and structured fallback logging."""

    def __init__(self):
        ExternalAPIClient.__init__(
            self,
            base_url=config.AUDIT_SVC_URL,
            headers={"Content-Type": "application/json"},
        )

    def create_audit(self, payload: AuditEventSchema, context: Context = None) -> None:
        """
        Emit an audit event synchronously with up to _MAX_RETRIES attempts.
        On total failure, logs the full event as CRITICAL so it can be reconstructed
        from log aggregation — audit failures must never propagate to the caller.
        """
        headers = {
            "x-tenant-id": context.tenant_id if context else "system",
            "x-keycloak-id": "system",
        }
        event_data = payload.model_dump()

        last_exc = None
        for attempt in range(_MAX_RETRIES):
            try:
                self._post(endpoint="/audits", data=event_data, headers=headers)
                return
            except Exception as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(_RETRY_DELAYS[attempt])

        # All retries exhausted — log the full event for ops reconstruction.
        logger.critical(
            "audit_emission_failed_all_retries event_type=%s actor_id=%s tenant_id=%s "
            "event_data=%s error=%s ACTION=reconstruct_from_logs",
            getattr(payload, "event_type", "UNKNOWN"),
            getattr(payload, "actor_id", "UNKNOWN"),
            context.tenant_id if context else "UNKNOWN",
            event_data,
            str(last_exc),
        )
