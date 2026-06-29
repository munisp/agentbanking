import threading
from typing import Optional

import httpx

from utils import create_logger, get_config

logger = create_logger(__name__)
config = get_config()


class ComplianceServiceAdapter:
    """Fire-and-forget KYC status sync to the compliance service."""

    def __init__(self):
        self.base_url = config.COMPLIANCE_SVC_URL.rstrip("/")

    def _emit_kyc_update(self, agent_id: str, kyc_status: str, tenant_id: str, agent_name: Optional[str] = None):
        try:
            with httpx.Client(timeout=10.0) as client:
                client.post(
                    f"{self.base_url}/api/v1/kyc-ingest",
                    json={
                        "agent_id": agent_id,
                        "kyc_status": kyc_status,
                        "tenant_id": tenant_id,
                        "agent_name": agent_name,
                    },
                )
        except Exception:
            logger.warning("Failed to sync KYC update to compliance service for agent %s", agent_id)

    def push_kyc_update(self, agent_id: str, kyc_status: str, tenant_id: str, agent_name: Optional[str] = None):
        """Non-blocking KYC status push to compliance service."""
        threading.Thread(
            target=self._emit_kyc_update,
            args=(agent_id, kyc_status, tenant_id, agent_name),
            daemon=True,
        ).start()
