"""
Agent Scorecard — Platform Services Integration
Connects the Agent Scorecard service to existing 54agent platform services:
  - Commission Service: adjusts tier multipliers based on scorecard tier
  - KYA Analytics: feeds scorecard data into KYA behavioral models
  - Notification Service: sends scorecard computed / tier change notifications
  - Credit Scoring Engine: provides credit score input to scorecard compliance dimension
"""
import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

# ── Service URLs ───────────────────────────────────────────────────────────────
COMMISSION_SERVICE_URL  = os.getenv("COMMISSION_SERVICE_URL",  "http://commission-service:8001")
KYA_ANALYTICS_URL       = os.getenv("KYA_ANALYTICS_URL",       "http://kya-analytics:8132")
NOTIFICATION_SERVICE_URL= os.getenv("NOTIFICATION_SERVICE_URL","http://notification-service:8050")
CREDIT_SCORING_URL      = os.getenv("CREDIT_SCORING_URL",      "http://credit-scoring:8080")

# Internal service-to-service auth token (Keycloak client credentials)
SERVICE_TOKEN           = os.getenv("INTERNAL_SERVICE_TOKEN", "")

_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {SERVICE_TOKEN}",
    "X-Service-Name": "agent-scorecard",
}

_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


# ── Commission Service Integration ────────────────────────────────────────────

async def notify_commission_service_tier_change(
    agent_id: str,
    tenant_id: str,
    old_tier: str,
    new_tier: str,
    composite_score: float,
) -> bool:
    """
    Notify the Commission Service when an agent's scorecard tier changes.
    The Commission Service uses tier to apply the correct multiplier to commissions.
    """
    payload = {
        "agent_id":       agent_id,
        "tenant_id":      tenant_id,
        "old_tier":       old_tier,
        "new_tier":       new_tier,
        "composite_score": composite_score,
        "source":         "agent-scorecard",
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{COMMISSION_SERVICE_URL}/api/v1/commissions/agent-tier-update",
                json=payload,
                headers=_HEADERS,
            )
            if resp.status_code in (200, 201, 204):
                logger.info(
                    "Commission service notified of tier change: agent=%s %s→%s",
                    agent_id, old_tier, new_tier,
                )
                return True
            logger.warning(
                "Commission service returned %d for tier update: %s",
                resp.status_code, resp.text[:200],
            )
            return False
    except Exception as e:
        logger.error("Failed to notify commission service: %s", e)
        return False


# ── KYA Analytics Integration ─────────────────────────────────────────────────

async def push_scorecard_to_kya(
    agent_id: str,
    tenant_id: str,
    scorecard: Dict[str, Any],
) -> bool:
    """
    Push the latest scorecard metrics to the KYA Analytics service.
    KYA uses these as features for its behavioral risk models.
    """
    payload = {
        "agent_id":                  agent_id,
        "tenant_id":                 tenant_id,
        "composite_score":           scorecard.get("composite_score", 0.0),
        "tier":                      scorecard.get("tier", "Unrated"),
        "transaction_score":         scorecard.get("transaction_score", 0.0),
        "compliance_score":          scorecard.get("compliance_score", 0.0),
        "customer_experience_score": scorecard.get("customer_experience_score", 0.0),
        "training_score":            scorecard.get("training_score", 0.0),
        "network_score":             scorecard.get("network_score", 0.0),
        "fraud_incidents_90d":       scorecard.get("fraud_incidents_90d", 0),
        "transaction_count_30d":     scorecard.get("transaction_count_30d", 0),
        "transaction_success_rate":  scorecard.get("transaction_success_rate", 0.0),
        "source":                    "agent-scorecard",
        "computed_at":               scorecard.get("computed_at", ""),
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{KYA_ANALYTICS_URL}/api/v1/kya/ingest-scorecard",
                json=payload,
                headers=_HEADERS,
            )
            if resp.status_code in (200, 201, 204):
                logger.debug("KYA Analytics updated for agent=%s", agent_id)
                return True
            logger.warning("KYA Analytics returned %d: %s", resp.status_code, resp.text[:200])
            return False
    except Exception as e:
        logger.error("Failed to push scorecard to KYA Analytics: %s", e)
        return False


# ── Notification Service Integration ─────────────────────────────────────────

async def send_scorecard_notification(
    agent_id: str,
    tenant_id: str,
    notification_type: str,
    data: Dict[str, Any],
) -> bool:
    """
    Send a notification via the platform Notification Service.

    notification_type options:
      - "scorecard_computed": Monthly scorecard ready
      - "tier_upgrade": Agent moved to a higher tier
      - "tier_downgrade": Agent moved to a lower tier
      - "critical_recommendation": High-priority action required
    """
    templates = {
        "scorecard_computed": {
            "title": "Your Monthly Scorecard is Ready",
            "body": (
                f"Your scorecard for this period: {data.get('composite_score', 0):.0f}/1000 "
                f"({data.get('tier', 'Unrated')} tier). "
                f"View your detailed breakdown in the app."
            ),
            "channels": ["push", "in_app"],
        },
        "tier_upgrade": {
            "title": f"Congratulations! You've reached {data.get('new_tier', '')} tier!",
            "body": (
                f"Your performance has earned you a tier upgrade from "
                f"{data.get('old_tier', '')} to {data.get('new_tier', '')}. "
                f"You now qualify for higher commission rates!"
            ),
            "channels": ["push", "sms", "in_app"],
        },
        "tier_downgrade": {
            "title": "Your Tier Has Changed",
            "body": (
                f"Your tier has changed from {data.get('old_tier', '')} to "
                f"{data.get('new_tier', '')}. Check your scorecard for improvement tips."
            ),
            "channels": ["push", "in_app"],
        },
        "critical_recommendation": {
            "title": "Action Required: Scorecard Alert",
            "body": data.get("message", "Please review your scorecard for important actions."),
            "channels": ["push", "sms", "in_app"],
        },
    }

    template = templates.get(notification_type, {
        "title": "Scorecard Update",
        "body": str(data),
        "channels": ["in_app"],
    })

    payload = {
        "user_id":           agent_id,
        "tenant_id":         tenant_id,
        "notification_type": notification_type,
        "title":             template["title"],
        "body":              template["body"],
        "channels":          template["channels"],
        "data":              data,
        "source":            "agent-scorecard",
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{NOTIFICATION_SERVICE_URL}/send-notification",
                json=payload,
                headers=_HEADERS,
            )
            if resp.status_code in (200, 201, 204):
                logger.info(
                    "Notification sent: type=%s agent=%s", notification_type, agent_id
                )
                return True
            logger.warning(
                "Notification service returned %d: %s", resp.status_code, resp.text[:200]
            )
            return False
    except Exception as e:
        logger.error("Failed to send notification: %s", e)
        return False


# ── Credit Scoring Integration ────────────────────────────────────────────────

async def get_credit_score_for_compliance(
    agent_id: str,
    tenant_id: str,
) -> Optional[float]:
    """
    Fetch the agent's credit score from the Credit Scoring Engine.
    Used as an input to the compliance dimension of the scorecard.
    Returns a normalized score between 0 and 100, or None if unavailable.
    """
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{CREDIT_SCORING_URL}/api/v1/credit-scores/{agent_id}",
                params={"tenant_id": tenant_id},
                headers=_HEADERS,
            )
            if resp.status_code == 200:
                data = resp.json()
                raw_score = data.get("score", data.get("credit_score", None))
                if raw_score is not None:
                    # Normalize to 0-100 range (credit scores typically 300-850)
                    normalized = min(100.0, max(0.0, (float(raw_score) - 300) / 5.5))
                    return normalized
            return None
    except Exception as e:
        logger.warning("Could not fetch credit score for agent=%s: %s", agent_id, e)
        return None


# ── Composite Integration Handler ─────────────────────────────────────────────

async def post_scorecard_computed_integrations(
    agent_id: str,
    tenant_id: str,
    scorecard: Dict[str, Any],
    previous_tier: Optional[str] = None,
) -> Dict[str, bool]:
    """
    Run all post-scorecard-computation integrations in sequence.
    Returns a dict of integration results for observability.
    """
    results: Dict[str, bool] = {}

    # 1. Push to KYA Analytics
    results["kya_analytics"] = await push_scorecard_to_kya(agent_id, tenant_id, scorecard)

    # 2. Push to Lakehouse (imported here to avoid circular)
    try:
        from ..middleware.lakehouse.pipeline import get_lakehouse_client
        lh = get_lakehouse_client()
        results["lakehouse_silver"] = lh.write_silver_scorecard({
            **scorecard,
            "agent_id": agent_id,
            "tenant_id": tenant_id,
        })
        results["lakehouse_bronze"] = lh.write_bronze_event(
            event_id=str(scorecard.get("scorecard_id", "")),
            event_type="scorecard_computed",
            agent_id=agent_id,
            tenant_id=tenant_id,
            payload=scorecard,
        )
    except Exception as e:
        logger.error("Lakehouse integration failed: %s", e)
        results["lakehouse_silver"] = False
        results["lakehouse_bronze"] = False

    # 3. Check for tier change and notify commission service + agent
    current_tier = scorecard.get("tier", "Unrated")
    if previous_tier and previous_tier != current_tier:
        results["commission_tier_update"] = await notify_commission_service_tier_change(
            agent_id=agent_id,
            tenant_id=tenant_id,
            old_tier=previous_tier,
            new_tier=current_tier,
            composite_score=scorecard.get("composite_score", 0.0),
        )

        # Determine if upgrade or downgrade
        tier_order = {"Unrated": 0, "Bronze": 1, "Silver": 2, "Gold": 3, "Platinum": 4}
        old_rank = tier_order.get(previous_tier, 0)
        new_rank = tier_order.get(current_tier, 0)
        notif_type = "tier_upgrade" if new_rank > old_rank else "tier_downgrade"

        results["tier_change_notification"] = await send_scorecard_notification(
            agent_id=agent_id,
            tenant_id=tenant_id,
            notification_type=notif_type,
            data={
                "old_tier": previous_tier,
                "new_tier": current_tier,
                "composite_score": scorecard.get("composite_score", 0.0),
            },
        )
    else:
        # Always send scorecard_computed notification
        results["scorecard_notification"] = await send_scorecard_notification(
            agent_id=agent_id,
            tenant_id=tenant_id,
            notification_type="scorecard_computed",
            data={
                "composite_score": scorecard.get("composite_score", 0.0),
                "tier": current_tier,
                "scorecard_id": str(scorecard.get("scorecard_id", "")),
            },
        )

    logger.info(
        "Post-scorecard integrations for agent=%s: %s",
        agent_id, results,
    )
    return results
