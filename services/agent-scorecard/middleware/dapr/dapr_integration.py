"""
Agent Scorecard — Dapr Integration
Implements Dapr pub/sub subscriptions, state store operations,
and service invocation for the Agent Scorecard service.
"""
import json
import logging
import os
from typing import Optional, Dict, Any, List
from datetime import datetime

from dapr.clients import DaprClient
from dapr.ext.fastapi import DaprApp
from fastapi import FastAPI, Request, HTTPException
from cloudevents.http import from_http

logger = logging.getLogger(__name__)

DAPR_APP_ID       = os.getenv("DAPR_APP_ID", "agent-scorecard")
DAPR_HTTP_PORT    = int(os.getenv("DAPR_HTTP_PORT", "3500"))
PUBSUB_NAME       = "agent-scorecard-pubsub"
STATE_STORE_NAME  = "agent-scorecard-statestore"

# ── Dapr State Store (Redis) Operations ───────────────────────────────────────

class ScorecardStateStore:
    """
    Wraps Dapr state store operations for scorecard caching.
    Uses Redis Cluster via Dapr sidecar.
    """

    def __init__(self):
        self._client: Optional[DaprClient] = None

    def _get_client(self) -> DaprClient:
        if self._client is None:
            self._client = DaprClient()
        return self._client

    def cache_scorecard(self, agent_id: str, tenant_id: str,
                        scorecard_data: Dict[str, Any], ttl_seconds: int = 3600) -> bool:
        """Cache a computed scorecard in Redis via Dapr state store."""
        key = f"{tenant_id}:agent:{agent_id}:latest_scorecard"
        try:
            client = self._get_client()
            client.save_state(
                store_name=STATE_STORE_NAME,
                key=key,
                value=json.dumps(scorecard_data),
                state_metadata={"ttlInSeconds": str(ttl_seconds)},
            )
            logger.debug("Cached scorecard for agent=%s tenant=%s", agent_id, tenant_id)
            return True
        except Exception as e:
            logger.error("Failed to cache scorecard for agent=%s: %s", agent_id, e)
            return False

    def get_cached_scorecard(self, agent_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a cached scorecard from Redis via Dapr state store."""
        key = f"{tenant_id}:agent:{agent_id}:latest_scorecard"
        try:
            client = self._get_client()
            result = client.get_state(store_name=STATE_STORE_NAME, key=key)
            if result.data:
                return json.loads(result.data.decode("utf-8"))
            return None
        except Exception as e:
            logger.error("Failed to get cached scorecard for agent=%s: %s", agent_id, e)
            return None

    def cache_leaderboard(self, tenant_id: str, leaderboard: List[Dict[str, Any]],
                          ttl_seconds: int = 300) -> bool:
        """Cache the leaderboard snapshot (5-minute TTL)."""
        key = f"{tenant_id}:leaderboard:latest"
        try:
            client = self._get_client()
            client.save_state(
                store_name=STATE_STORE_NAME,
                key=key,
                value=json.dumps({"data": leaderboard, "cached_at": datetime.utcnow().isoformat()}),
                state_metadata={"ttlInSeconds": str(ttl_seconds)},
            )
            return True
        except Exception as e:
            logger.error("Failed to cache leaderboard for tenant=%s: %s", tenant_id, e)
            return False

    def get_cached_leaderboard(self, tenant_id: str) -> Optional[List[Dict[str, Any]]]:
        """Retrieve cached leaderboard."""
        key = f"{tenant_id}:leaderboard:latest"
        try:
            client = self._get_client()
            result = client.get_state(store_name=STATE_STORE_NAME, key=key)
            if result.data:
                cached = json.loads(result.data.decode("utf-8"))
                return cached.get("data")
            return None
        except Exception as e:
            logger.error("Failed to get cached leaderboard for tenant=%s: %s", tenant_id, e)
            return None

    def invalidate_scorecard(self, agent_id: str, tenant_id: str) -> bool:
        """Invalidate a cached scorecard when a recompute is triggered."""
        key = f"{tenant_id}:agent:{agent_id}:latest_scorecard"
        try:
            client = self._get_client()
            client.delete_state(store_name=STATE_STORE_NAME, key=key)
            return True
        except Exception as e:
            logger.error("Failed to invalidate scorecard cache for agent=%s: %s", agent_id, e)
            return False

    def cache_benchmark(self, tenant_id: str, benchmark_data: Dict[str, Any],
                        ttl_seconds: int = 3600) -> bool:
        """Cache tier benchmark statistics."""
        key = f"{tenant_id}:benchmarks:latest"
        try:
            client = self._get_client()
            client.save_state(
                store_name=STATE_STORE_NAME,
                key=key,
                value=json.dumps(benchmark_data),
                state_metadata={"ttlInSeconds": str(ttl_seconds)},
            )
            return True
        except Exception as e:
            logger.error("Failed to cache benchmarks for tenant=%s: %s", tenant_id, e)
            return False

    def get_cached_benchmark(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve cached benchmark data."""
        key = f"{tenant_id}:benchmarks:latest"
        try:
            client = self._get_client()
            result = client.get_state(store_name=STATE_STORE_NAME, key=key)
            if result.data:
                return json.loads(result.data.decode("utf-8"))
            return None
        except Exception as e:
            logger.error("Failed to get cached benchmarks for tenant=%s: %s", tenant_id, e)
            return None


# ── Dapr Service Invocation ────────────────────────────────────────────────────

class ScorecardServiceInvoker:
    """
    Invokes other platform services via Dapr service invocation.
    Provides type-safe wrappers for cross-service calls.
    """

    def __init__(self):
        self._client: Optional[DaprClient] = None

    def _get_client(self) -> DaprClient:
        if self._client is None:
            self._client = DaprClient()
        return self._client

    def get_agent_transactions(self, agent_id: str, tenant_id: str,
                                days: int = 30) -> Optional[Dict[str, Any]]:
        """Invoke commission-settlement service to get agent transaction metrics."""
        try:
            client = self._get_client()
            resp = client.invoke_method(
                app_id="commission-settlement",
                method_name=f"agents/{agent_id}/metrics",
                data=json.dumps({"tenant_id": tenant_id, "days": days}).encode(),
                content_type="application/json",
                http_verb="GET",
            )
            return json.loads(resp.data)
        except Exception as e:
            logger.error("Failed to get agent transactions via Dapr: %s", e)
            return None

    def get_agent_kyc_status(self, agent_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Invoke compliance-kyc service to get agent KYC status."""
        try:
            client = self._get_client()
            resp = client.invoke_method(
                app_id="compliance-kyc",
                method_name=f"agents/{agent_id}/kyc-status",
                data=json.dumps({"tenant_id": tenant_id}).encode(),
                content_type="application/json",
                http_verb="GET",
            )
            return json.loads(resp.data)
        except Exception as e:
            logger.error("Failed to get KYC status via Dapr: %s", e)
            return None

    def get_agent_training_progress(self, agent_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Invoke agent-training service to get training completion metrics."""
        try:
            client = self._get_client()
            resp = client.invoke_method(
                app_id="agent-training",
                method_name=f"agents/{agent_id}/progress",
                data=json.dumps({"tenant_id": tenant_id}).encode(),
                content_type="application/json",
                http_verb="GET",
            )
            return json.loads(resp.data)
        except Exception as e:
            logger.error("Failed to get training progress via Dapr: %s", e)
            return None

    def get_agent_fraud_incidents(self, agent_id: str, tenant_id: str,
                                   days: int = 90) -> Optional[Dict[str, Any]]:
        """Invoke fraud-detection service to get agent fraud incidents."""
        try:
            client = self._get_client()
            resp = client.invoke_method(
                app_id="fraud-detection",
                method_name=f"agents/{agent_id}/incidents",
                data=json.dumps({"tenant_id": tenant_id, "days": days}).encode(),
                content_type="application/json",
                http_verb="GET",
            )
            return json.loads(resp.data)
        except Exception as e:
            logger.error("Failed to get fraud incidents via Dapr: %s", e)
            return None

    def notify_tier_change(self, agent_id: str, tenant_id: str,
                            old_tier: str, new_tier: str) -> bool:
        """Invoke notification service when agent tier changes."""
        try:
            client = self._get_client()
            client.invoke_method(
                app_id="notification-service",
                method_name="notifications/send",
                data=json.dumps({
                    "recipient_id": agent_id,
                    "tenant_id": tenant_id,
                    "notification_type": "TIER_CHANGE",
                    "title": f"Your agent tier has changed to {new_tier}",
                    "body": f"Congratulations! You have moved from {old_tier} to {new_tier} tier.",
                    "channels": ["push", "sms", "email"],
                    "metadata": {"old_tier": old_tier, "new_tier": new_tier},
                }).encode(),
                content_type="application/json",
                http_verb="POST",
            )
            return True
        except Exception as e:
            logger.error("Failed to send tier change notification via Dapr: %s", e)
            return False

    def update_credit_limit_from_scorecard(self, agent_id: str, tenant_id: str,
                                            composite_score: float, tier: str) -> bool:
        """Invoke agent-embedded-finance to update credit limit based on new scorecard."""
        try:
            client = self._get_client()
            client.invoke_method(
                app_id="agent-embedded-finance",
                method_name="credit-profiles/update-from-scorecard",
                data=json.dumps({
                    "agent_id": agent_id,
                    "tenant_id": tenant_id,
                    "composite_score": composite_score,
                    "tier": tier,
                }).encode(),
                content_type="application/json",
                http_verb="POST",
            )
            return True
        except Exception as e:
            logger.error("Failed to update credit limit from scorecard via Dapr: %s", e)
            return False


# ── Dapr Pub/Sub Subscription Handlers ────────────────────────────────────────

def register_dapr_subscriptions(app: FastAPI, db_session_factory):
    """
    Register all Dapr pub/sub subscription endpoints on the FastAPI app.
    These endpoints are called by the Dapr sidecar when messages arrive.
    """
    dapr_app = DaprApp(app)

    @dapr_app.subscribe(pubsub=PUBSUB_NAME, topic="transaction.completed")
    async def on_transaction_completed(request: Request):
        """Handle transaction.completed events — queue scorecard recompute."""
        try:
            body = await request.body()
            event = from_http(dict(request.headers), body)
            data = json.loads(event.data) if isinstance(event.data, (str, bytes)) else event.data

            agent_id = data.get("agent_id")
            tenant_id = data.get("tenant_id", "default")
            if agent_id:
                with db_session_factory() as db:
                    from sqlalchemy import text
                    db.execute(
                        text("""
                            INSERT INTO scorecard_recompute_queue
                                (agent_id, tenant_id, trigger_reason, priority, queued_at)
                            VALUES (:agent_id, :tenant_id, 'transaction_completed', 'normal', NOW())
                            ON CONFLICT (agent_id, tenant_id)
                            DO UPDATE SET trigger_reason='transaction_completed', queued_at=NOW()
                        """),
                        {"agent_id": agent_id, "tenant_id": tenant_id}
                    )
                    db.commit()
            return {"status": "SUCCESS"}
        except Exception as e:
            logger.error("Error handling transaction.completed: %s", e)
            return {"status": "RETRY"}

    @dapr_app.subscribe(pubsub=PUBSUB_NAME, topic="agent.kyc.updated")
    async def on_kyc_updated(request: Request):
        """Handle agent.kyc.updated events — queue compliance dimension recompute."""
        try:
            body = await request.body()
            event = from_http(dict(request.headers), body)
            data = json.loads(event.data) if isinstance(event.data, (str, bytes)) else event.data

            agent_id = data.get("agent_id")
            tenant_id = data.get("tenant_id", "default")
            if agent_id:
                with db_session_factory() as db:
                    from sqlalchemy import text
                    db.execute(
                        text("""
                            INSERT INTO scorecard_recompute_queue
                                (agent_id, tenant_id, trigger_reason, priority, queued_at)
                            VALUES (:agent_id, :tenant_id, 'kyc_updated', 'high', NOW())
                            ON CONFLICT (agent_id, tenant_id)
                            DO UPDATE SET trigger_reason='kyc_updated', priority='high', queued_at=NOW()
                        """),
                        {"agent_id": agent_id, "tenant_id": tenant_id}
                    )
                    db.commit()
            return {"status": "SUCCESS"}
        except Exception as e:
            logger.error("Error handling agent.kyc.updated: %s", e)
            return {"status": "RETRY"}

    @dapr_app.subscribe(pubsub=PUBSUB_NAME, topic="fraud.alert.raised")
    async def on_fraud_alert(request: Request):
        """Handle fraud.alert.raised — immediate high-priority recompute."""
        try:
            body = await request.body()
            event = from_http(dict(request.headers), body)
            data = json.loads(event.data) if isinstance(event.data, (str, bytes)) else event.data

            agent_id = data.get("agent_id")
            tenant_id = data.get("tenant_id", "default")
            if agent_id:
                with db_session_factory() as db:
                    from sqlalchemy import text
                    db.execute(
                        text("""
                            INSERT INTO scorecard_recompute_queue
                                (agent_id, tenant_id, trigger_reason, priority, queued_at)
                            VALUES (:agent_id, :tenant_id, 'fraud_alert', 'critical', NOW())
                            ON CONFLICT (agent_id, tenant_id)
                            DO UPDATE SET trigger_reason='fraud_alert', priority='critical', queued_at=NOW()
                        """),
                        {"agent_id": agent_id, "tenant_id": tenant_id}
                    )
                    db.commit()
            return {"status": "SUCCESS"}
        except Exception as e:
            logger.error("Error handling fraud.alert.raised: %s", e)
            return {"status": "RETRY"}

    @dapr_app.subscribe(pubsub=PUBSUB_NAME, topic="agent.finance.loan_disbursed")
    async def on_loan_disbursed(request: Request):
        """Handle loan disbursement — update scorecard finance health dimension."""
        try:
            body = await request.body()
            event = from_http(dict(request.headers), body)
            data = json.loads(event.data) if isinstance(event.data, (str, bytes)) else event.data

            agent_id = data.get("agent_id")
            tenant_id = data.get("tenant_id", "default")
            if agent_id:
                with db_session_factory() as db:
                    from sqlalchemy import text
                    db.execute(
                        text("""
                            INSERT INTO scorecard_recompute_queue
                                (agent_id, tenant_id, trigger_reason, priority, queued_at)
                            VALUES (:agent_id, :tenant_id, 'loan_disbursed', 'normal', NOW())
                            ON CONFLICT (agent_id, tenant_id)
                            DO UPDATE SET trigger_reason='loan_disbursed', queued_at=NOW()
                        """),
                        {"agent_id": agent_id, "tenant_id": tenant_id}
                    )
                    db.commit()
            return {"status": "SUCCESS"}
        except Exception as e:
            logger.error("Error handling loan_disbursed: %s", e)
            return {"status": "RETRY"}

    logger.info("Dapr pub/sub subscriptions registered for Agent Scorecard service")


# ── Singletons ─────────────────────────────────────────────────────────────────

_state_store: Optional[ScorecardStateStore] = None
_invoker: Optional[ScorecardServiceInvoker] = None


def get_scorecard_state_store() -> ScorecardStateStore:
    global _state_store
    if _state_store is None:
        _state_store = ScorecardStateStore()
    return _state_store


def get_scorecard_service_invoker() -> ScorecardServiceInvoker:
    global _invoker
    if _invoker is None:
        _invoker = ScorecardServiceInvoker()
    return _invoker
