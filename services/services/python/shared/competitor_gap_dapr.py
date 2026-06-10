"""
Shared Dapr integration for all 8 competitor-gap services.
Provides pub/sub publishing, state management, and service invocation.
"""
import json
import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

DAPR_HTTP_PORT     = os.getenv("DAPR_HTTP_PORT", "3500")
DAPR_BASE          = f"http://localhost:{DAPR_HTTP_PORT}/v1.0"
PUBSUB_NAME        = "competitor-gap-pubsub"
STATE_STORE_NAME   = "competitor-gap-statestore"
_HTTP_TIMEOUT      = 5.0


async def dapr_publish(topic: str, data: Dict[str, Any],
                        pubsub: str = PUBSUB_NAME) -> bool:
    """Publish an event to a Dapr pub/sub topic."""
    url = f"{DAPR_BASE}/publish/{pubsub}/{topic}"
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            resp = await client.post(url, json=data)
            if resp.status_code not in (200, 204):
                logger.warning("[dapr] publish failed topic=%s status=%d", topic, resp.status_code)
                return False
            return True
    except Exception as exc:
        logger.error("[dapr] publish error topic=%s: %s", topic, exc)
        return False


async def dapr_get_state(key: str, store: str = STATE_STORE_NAME) -> Optional[Any]:
    """Get a value from the Dapr state store."""
    url = f"{DAPR_BASE}/state/{store}/{key}"
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 204:
                return None
            logger.warning("[dapr] get_state failed key=%s status=%d", key, resp.status_code)
            return None
    except Exception as exc:
        logger.error("[dapr] get_state error key=%s: %s", key, exc)
        return None


async def dapr_save_state(key: str, value: Any,
                           store: str = STATE_STORE_NAME,
                           ttl_seconds: Optional[int] = None) -> bool:
    """Save a value to the Dapr state store."""
    url = f"{DAPR_BASE}/state/{store}"
    item: Dict[str, Any] = {"key": key, "value": value}
    if ttl_seconds:
        item["metadata"] = {"ttlInSeconds": str(ttl_seconds)}
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            resp = await client.post(url, json=[item])
            if resp.status_code not in (200, 204):
                logger.warning("[dapr] save_state failed key=%s status=%d", key, resp.status_code)
                return False
            return True
    except Exception as exc:
        logger.error("[dapr] save_state error key=%s: %s", key, exc)
        return False


async def dapr_delete_state(key: str, store: str = STATE_STORE_NAME) -> bool:
    """Delete a value from the Dapr state store."""
    url = f"{DAPR_BASE}/state/{store}/{key}"
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            resp = await client.delete(url)
            return resp.status_code in (200, 204)
    except Exception as exc:
        logger.error("[dapr] delete_state error key=%s: %s", key, exc)
        return False


async def dapr_invoke(app_id: str, method: str,
                       data: Optional[Dict[str, Any]] = None,
                       http_verb: str = "POST") -> Optional[Dict[str, Any]]:
    """Invoke a method on another Dapr-enabled service."""
    url = f"{DAPR_BASE}/invoke/{app_id}/method/{method}"
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            if http_verb.upper() == "GET":
                resp = await client.get(url)
            else:
                resp = await client.post(url, json=data or {})
            if resp.status_code == 200:
                return resp.json()
            logger.warning("[dapr] invoke failed app=%s method=%s status=%d",
                           app_id, method, resp.status_code)
            return None
    except Exception as exc:
        logger.error("[dapr] invoke error app=%s method=%s: %s", app_id, method, exc)
        return None


# ─── Service-specific Dapr helpers ───────────────────────────────────────────

class MultiSimDaprClient:
    """Dapr client for multi-sim-failover service."""
    SERVICE = "multi-sim-failover"

    async def cache_terminal_connectivity(self, terminal_id: str,
                                           profile: Dict[str, Any]) -> bool:
        return await dapr_save_state(
            f"terminal:connectivity:{terminal_id}", profile, ttl_seconds=300)

    async def get_terminal_connectivity(self, terminal_id: str) -> Optional[Dict]:
        return await dapr_get_state(f"terminal:connectivity:{terminal_id}")

    async def publish_failover(self, terminal_id: str, from_slot: int,
                                to_slot: int, reason: str) -> bool:
        return await dapr_publish("terminal.sim.failover_triggered", {
            "terminal_id": terminal_id, "from_slot": from_slot,
            "to_slot": to_slot, "reason": reason,
        })


class ReversalDaprClient:
    """Dapr client for instant-reversal-engine service."""
    SERVICE = "instant-reversal-engine"

    async def cache_reversal_status(self, reversal_id: str,
                                     status: Dict[str, Any]) -> bool:
        return await dapr_save_state(
            f"reversal:status:{reversal_id}", status, ttl_seconds=3600)

    async def get_reversal_status(self, reversal_id: str) -> Optional[Dict]:
        return await dapr_get_state(f"reversal:status:{reversal_id}")

    async def notify_reversal_complete(self, reversal_id: str, transaction_id: str,
                                        amount: float, agent_id: str) -> bool:
        return await dapr_publish("transaction.reversal.completed", {
            "reversal_id": reversal_id, "transaction_id": transaction_id,
            "amount": amount, "agent_id": agent_id,
        })

    async def invoke_notification_service(self, agent_id: str, customer_phone: str,
                                           amount: float, reversal_id: str) -> bool:
        result = await dapr_invoke("notification-service", "send-reversal-sms", {
            "agent_id": agent_id, "customer_phone": customer_phone,
            "amount": amount, "reversal_id": reversal_id,
        })
        return result is not None


class WalletDaprClient:
    """Dapr client for agent-wallet-transparency service."""

    async def cache_wallet_balance(self, agent_id: str, balance: float,
                                    tenant_id: str) -> bool:
        return await dapr_save_state(
            f"wallet:balance:{tenant_id}:{agent_id}",
            {"balance": balance, "agent_id": agent_id},
            ttl_seconds=60)

    async def get_cached_balance(self, agent_id: str, tenant_id: str) -> Optional[float]:
        data = await dapr_get_state(f"wallet:balance:{tenant_id}:{agent_id}")
        return data.get("balance") if data else None

    async def publish_balance_update(self, agent_id: str, new_balance: float,
                                      entry_type: str) -> bool:
        return await dapr_publish("agent.wallet.balance_updated", {
            "agent_id": agent_id, "new_balance": new_balance, "entry_type": entry_type,
        })


class CBNReportingDaprClient:
    """Dapr client for cbn-reporting-engine service."""

    async def cache_report(self, report_id: str, report_data: Dict[str, Any]) -> bool:
        return await dapr_save_state(
            f"cbn:report:{report_id}", report_data, ttl_seconds=86400)

    async def get_cached_report(self, report_id: str) -> Optional[Dict]:
        return await dapr_get_state(f"cbn:report:{report_id}")

    async def publish_report_generated(self, report_id: str, report_type: str,
                                        period: str, tenant_id: str) -> bool:
        return await dapr_publish("compliance.cbn.report_generated", {
            "report_id": report_id, "report_type": report_type,
            "period": period, "tenant_id": tenant_id,
        })


class NFCQRDaprClient:
    """Dapr client for nfc-qr-payments service."""

    async def cache_qr_code(self, qr_id: str, qr_data: Dict[str, Any],
                             ttl: int = 300) -> bool:
        return await dapr_save_state(f"qr:code:{qr_id}", qr_data, ttl_seconds=ttl)

    async def get_qr_code(self, qr_id: str) -> Optional[Dict]:
        return await dapr_get_state(f"qr:code:{qr_id}")

    async def invalidate_qr(self, qr_id: str) -> bool:
        return await dapr_delete_state(f"qr:code:{qr_id}")

    async def publish_qr_scanned(self, qr_id: str, agent_id: str,
                                  customer_id: str) -> bool:
        return await dapr_publish("payment.qr.scanned", {
            "qr_id": qr_id, "agent_id": agent_id, "customer_id": customer_id,
        })


class ReceiptDaprClient:
    """Dapr client for realtime-receipt-engine service."""

    async def cache_receipt(self, receipt_id: str, receipt_data: Dict[str, Any]) -> bool:
        return await dapr_save_state(
            f"receipt:{receipt_id}", receipt_data, ttl_seconds=86400)

    async def get_receipt(self, receipt_id: str) -> Optional[Dict]:
        return await dapr_get_state(f"receipt:{receipt_id}")

    async def invoke_sms_service(self, phone: str, message: str) -> bool:
        result = await dapr_invoke("notification-service", "send-sms", {
            "phone": phone, "message": message,
        })
        return result is not None

    async def invoke_whatsapp_service(self, phone: str, message: str,
                                       template_id: str) -> bool:
        result = await dapr_invoke("notification-service", "send-whatsapp", {
            "phone": phone, "message": message, "template_id": template_id,
        })
        return result is not None


class TrainingDaprClient:
    """Dapr client for agent-training-academy service."""

    async def cache_enrollment(self, agent_id: str, course_id: str,
                                progress: Dict[str, Any]) -> bool:
        return await dapr_save_state(
            f"training:progress:{agent_id}:{course_id}", progress, ttl_seconds=3600)

    async def get_enrollment_progress(self, agent_id: str,
                                       course_id: str) -> Optional[Dict]:
        return await dapr_get_state(f"training:progress:{agent_id}:{course_id}")

    async def publish_certificate_issued(self, agent_id: str, course_id: str,
                                          certificate_id: str,
                                          is_cbn_required: bool) -> bool:
        return await dapr_publish("training.certificate.issued", {
            "agent_id": agent_id, "course_id": course_id,
            "certificate_id": certificate_id, "is_cbn_required": is_cbn_required,
        })

    async def invoke_scorecard_recompute(self, agent_id: str, tenant_id: str) -> bool:
        result = await dapr_invoke("agent-scorecard", "recompute", {
            "agent_id": agent_id, "tenant_id": tenant_id,
        })
        return result is not None


class LiquidityDaprClient:
    """Dapr client for agent-liquidity-network service."""

    async def cache_liquidity_profile(self, agent_id: str,
                                       profile: Dict[str, Any]) -> bool:
        return await dapr_save_state(
            f"liquidity:profile:{agent_id}", profile, ttl_seconds=300)

    async def get_liquidity_profile(self, agent_id: str) -> Optional[Dict]:
        return await dapr_get_state(f"liquidity:profile:{agent_id}")

    async def publish_match_made(self, match_id: str, requester_id: str,
                                  provider_id: str, amount: float) -> bool:
        return await dapr_publish("liquidity.match.made", {
            "match_id": match_id, "requester_id": requester_id,
            "provider_id": provider_id, "amount": amount,
        })

    async def invoke_wallet_transfer(self, from_agent: str, to_agent: str,
                                      amount: float, match_id: str) -> bool:
        result = await dapr_invoke("agent-wallet-transparency", "internal-transfer", {
            "from_agent_id": from_agent, "to_agent_id": to_agent,
            "amount": amount, "reference": match_id,
        })
        return result is not None
