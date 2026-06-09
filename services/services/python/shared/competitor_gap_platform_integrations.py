"""
Shared platform services integration module for all 8 competitor-gap services.
Connects to: notification, commission, KYA analytics, float management,
agent management, credit scoring, and transaction processing services.
"""
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# ─── Internal service URLs ────────────────────────────────────────────────────
NOTIFICATION_SVC_URL   = os.getenv("NOTIFICATION_SERVICE_URL",   "http://notification-service:8001")
COMMISSION_SVC_URL     = os.getenv("COMMISSION_SERVICE_URL",     "http://commission-settlement:8002")
KYA_SVC_URL            = os.getenv("KYA_ANALYTICS_URL",          "http://kya-analytics:8003")
FLOAT_SVC_URL          = os.getenv("FLOAT_MANAGEMENT_URL",       "http://float-management:8004")
AGENT_MGMT_SVC_URL     = os.getenv("AGENT_MANAGEMENT_URL",       "http://agent-management:8005")
CREDIT_SCORING_SVC_URL = os.getenv("CREDIT_SCORING_URL",         "http://credit-scoring:8006")
TXN_SVC_URL            = os.getenv("TRANSACTION_SERVICE_URL",    "http://transaction-service:8007")
FRAUD_SVC_URL          = os.getenv("FRAUD_DETECTION_URL",        "http://fraud-detection:8008")
SCORECARD_SVC_URL      = os.getenv("AGENT_SCORECARD_URL",        "http://agent-scorecard:8081")

_HTTP_TIMEOUT = 10.0


async def _post(url: str, payload: Dict) -> Optional[Dict]:
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        logger.error("[platform-integration] POST %s failed: %s", url, exc)
        return None


async def _get(url: str, params: Optional[Dict] = None) -> Optional[Dict]:
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        logger.error("[platform-integration] GET %s failed: %s", url, exc)
        return None


# ─── Notification Service ─────────────────────────────────────────────────────

async def send_sms(phone_number: str, message: str, tenant_id: str) -> bool:
    result = await _post(f"{NOTIFICATION_SVC_URL}/api/v1/notifications/sms", {
        "phone_number": phone_number,
        "message": message,
        "tenant_id": tenant_id,
        "channel": "sms",
    })
    return result is not None


async def send_whatsapp(phone_number: str, message: str,
                         template_name: Optional[str], tenant_id: str) -> bool:
    result = await _post(f"{NOTIFICATION_SVC_URL}/api/v1/notifications/whatsapp", {
        "phone_number": phone_number,
        "message": message,
        "template_name": template_name,
        "tenant_id": tenant_id,
        "channel": "whatsapp",
    })
    return result is not None


async def send_push_notification(agent_id: str, title: str,
                                   body: str, data: Dict,
                                   tenant_id: str) -> bool:
    result = await _post(f"{NOTIFICATION_SVC_URL}/api/v1/notifications/push", {
        "agent_id": agent_id,
        "title": title,
        "body": body,
        "data": data,
        "tenant_id": tenant_id,
        "channel": "push",
    })
    return result is not None


async def send_email(email: str, subject: str, html_body: str,
                      tenant_id: str) -> bool:
    result = await _post(f"{NOTIFICATION_SVC_URL}/api/v1/notifications/email", {
        "email": email,
        "subject": subject,
        "html_body": html_body,
        "tenant_id": tenant_id,
        "channel": "email",
    })
    return result is not None


# ─── Agent Management Service ─────────────────────────────────────────────────

async def get_agent(agent_id: str, tenant_id: str) -> Optional[Dict]:
    return await _get(f"{AGENT_MGMT_SVC_URL}/api/v1/agents/{agent_id}",
                      {"tenant_id": tenant_id})


async def get_agent_phone(agent_id: str, tenant_id: str) -> Optional[str]:
    agent = await get_agent(agent_id, tenant_id)
    return agent.get("phone_number") if agent else None


async def get_agent_email(agent_id: str, tenant_id: str) -> Optional[str]:
    agent = await get_agent(agent_id, tenant_id)
    return agent.get("email") if agent else None


async def get_agent_location(agent_id: str, tenant_id: str) -> Optional[Dict]:
    """Returns {latitude, longitude, lga, state}"""
    agent = await get_agent(agent_id, tenant_id)
    if not agent:
        return None
    return {
        "latitude": agent.get("latitude"),
        "longitude": agent.get("longitude"),
        "lga": agent.get("lga"),
        "state": agent.get("state"),
    }


async def get_agents_by_tenant(tenant_id: str, active_only: bool = True) -> List[Dict]:
    result = await _get(f"{AGENT_MGMT_SVC_URL}/api/v1/agents",
                        {"tenant_id": tenant_id, "active": active_only})
    return result.get("agents", []) if result else []


async def update_agent_status(agent_id: str, status: str, tenant_id: str) -> bool:
    result = await _post(f"{AGENT_MGMT_SVC_URL}/api/v1/agents/{agent_id}/status", {
        "status": status,
        "tenant_id": tenant_id,
    })
    return result is not None


# ─── Float Management Service ─────────────────────────────────────────────────

async def get_agent_float_balance(agent_id: str, tenant_id: str) -> Optional[float]:
    result = await _get(f"{FLOAT_SVC_URL}/api/v1/float/{agent_id}/balance",
                        {"tenant_id": tenant_id})
    return result.get("balance") if result else None


async def debit_agent_float(agent_id: str, amount: float,
                              reference: str, tenant_id: str) -> bool:
    result = await _post(f"{FLOAT_SVC_URL}/api/v1/float/{agent_id}/debit", {
        "amount": amount,
        "reference": reference,
        "tenant_id": tenant_id,
    })
    return result is not None


async def credit_agent_float(agent_id: str, amount: float,
                               reference: str, tenant_id: str) -> bool:
    result = await _post(f"{FLOAT_SVC_URL}/api/v1/float/{agent_id}/credit", {
        "amount": amount,
        "reference": reference,
        "tenant_id": tenant_id,
    })
    return result is not None


async def get_float_transactions(agent_id: str, tenant_id: str,
                                   limit: int = 50) -> List[Dict]:
    result = await _get(f"{FLOAT_SVC_URL}/api/v1/float/{agent_id}/transactions",
                        {"tenant_id": tenant_id, "limit": limit})
    return result.get("transactions", []) if result else []


# ─── Commission Settlement Service ───────────────────────────────────────────

async def get_agent_commissions(agent_id: str, tenant_id: str,
                                  period: Optional[str] = None) -> Optional[Dict]:
    params = {"tenant_id": tenant_id}
    if period:
        params["period"] = period
    return await _get(f"{COMMISSION_SVC_URL}/api/v1/commissions/agent/{agent_id}",
                      params)


async def get_commission_summary(agent_id: str, tenant_id: str) -> Dict:
    result = await get_agent_commissions(agent_id, tenant_id)
    if not result:
        return {"total_earned": 0.0, "pending": 0.0, "paid": 0.0}
    return {
        "total_earned": result.get("total_earned", 0.0),
        "pending": result.get("pending", 0.0),
        "paid": result.get("paid", 0.0),
    }


# ─── KYA Analytics Service ────────────────────────────────────────────────────

async def get_kya_risk_score(agent_id: str, tenant_id: str) -> Optional[float]:
    result = await _get(f"{KYA_SVC_URL}/api/v1/kya/{agent_id}/risk-score",
                        {"tenant_id": tenant_id})
    return result.get("risk_score") if result else None


async def get_kya_behavioral_profile(agent_id: str, tenant_id: str) -> Optional[Dict]:
    return await _get(f"{KYA_SVC_URL}/api/v1/kya/{agent_id}/behavioral-profile",
                      {"tenant_id": tenant_id})


async def get_agent_transaction_metrics(agent_id: str, tenant_id: str,
                                          days: int = 30) -> Optional[Dict]:
    return await _get(f"{KYA_SVC_URL}/api/v1/kya/{agent_id}/transaction-metrics",
                      {"tenant_id": tenant_id, "days": days})


# ─── Credit Scoring Service ───────────────────────────────────────────────────

async def get_credit_score(agent_id: str, tenant_id: str) -> Optional[float]:
    result = await _get(f"{CREDIT_SCORING_SVC_URL}/api/v1/credit/{agent_id}/score",
                        {"tenant_id": tenant_id})
    return result.get("score") if result else None


async def get_credit_limit(agent_id: str, tenant_id: str) -> Optional[float]:
    result = await _get(f"{CREDIT_SCORING_SVC_URL}/api/v1/credit/{agent_id}/limit",
                        {"tenant_id": tenant_id})
    return result.get("credit_limit") if result else None


# ─── Transaction Service ──────────────────────────────────────────────────────

async def get_transaction(transaction_id: str, tenant_id: str) -> Optional[Dict]:
    return await _get(f"{TXN_SVC_URL}/api/v1/transactions/{transaction_id}",
                      {"tenant_id": tenant_id})


async def get_agent_transactions(agent_id: str, tenant_id: str,
                                   limit: int = 100,
                                   status: Optional[str] = None) -> List[Dict]:
    params = {"tenant_id": tenant_id, "limit": limit}
    if status:
        params["status"] = status
    result = await _get(f"{TXN_SVC_URL}/api/v1/transactions/agent/{agent_id}", params)
    return result.get("transactions", []) if result else []


async def get_failed_transactions(agent_id: str, tenant_id: str,
                                    hours: int = 24) -> List[Dict]:
    result = await _get(f"{TXN_SVC_URL}/api/v1/transactions/agent/{agent_id}/failed",
                        {"tenant_id": tenant_id, "hours": hours})
    return result.get("transactions", []) if result else []


async def get_transaction_volume(agent_id: str, tenant_id: str,
                                   period: str = "30d") -> Optional[Dict]:
    return await _get(f"{TXN_SVC_URL}/api/v1/transactions/agent/{agent_id}/volume",
                      {"tenant_id": tenant_id, "period": period})


# ─── Fraud Detection Service ──────────────────────────────────────────────────

async def check_fraud_risk(agent_id: str, transaction_data: Dict,
                             tenant_id: str) -> Optional[Dict]:
    result = await _post(f"{FRAUD_SVC_URL}/api/v1/fraud/check", {
        "agent_id": agent_id,
        "transaction": transaction_data,
        "tenant_id": tenant_id,
    })
    return result


async def get_fraud_incidents(agent_id: str, tenant_id: str,
                                days: int = 90) -> List[Dict]:
    result = await _get(f"{FRAUD_SVC_URL}/api/v1/fraud/incidents/agent/{agent_id}",
                        {"tenant_id": tenant_id, "days": days})
    return result.get("incidents", []) if result else []


# ─── Agent Scorecard Service (cross-service) ─────────────────────────────────

async def get_agent_scorecard(agent_id: str, tenant_id: str) -> Optional[Dict]:
    return await _get(f"{SCORECARD_SVC_URL}/api/v1/scorecard/agent/{agent_id}/latest",
                      {"tenant_id": tenant_id})


async def trigger_scorecard_recompute(agent_id: str, tenant_id: str,
                                        reason: str) -> bool:
    result = await _post(f"{SCORECARD_SVC_URL}/api/v1/scorecard/compute", {
        "agent_id": agent_id,
        "tenant_id": tenant_id,
        "trigger_reason": reason,
    })
    return result is not None


# ─── Composite helpers used by multiple services ──────────────────────────────

async def get_agent_full_profile(agent_id: str, tenant_id: str) -> Dict[str, Any]:
    """Aggregate agent data from multiple services for enriched context."""
    agent, float_bal, kya, commissions = await _gather_safely([
        get_agent(agent_id, tenant_id),
        get_agent_float_balance(agent_id, tenant_id),
        get_kya_risk_score(agent_id, tenant_id),
        get_commission_summary(agent_id, tenant_id),
    ])
    return {
        "agent": agent or {},
        "float_balance": float_bal or 0.0,
        "kya_risk_score": kya or 0.0,
        "commissions": commissions or {},
    }


async def _gather_safely(coros) -> List[Any]:
    """Run coroutines concurrently, returning None for any that fail."""
    import asyncio
    results = await asyncio.gather(*coros, return_exceptions=True)
    return [None if isinstance(r, Exception) else r for r in results]


async def notify_agent_multi_channel(agent_id: str, tenant_id: str,
                                       title: str, message: str,
                                       data: Optional[Dict] = None) -> None:
    """Send notification via push + SMS to an agent."""
    import asyncio
    phone = await get_agent_phone(agent_id, tenant_id)
    tasks = [
        send_push_notification(agent_id, title, message, data or {}, tenant_id),
    ]
    if phone:
        tasks.append(send_sms(phone, message, tenant_id))
    await asyncio.gather(*tasks, return_exceptions=True)
