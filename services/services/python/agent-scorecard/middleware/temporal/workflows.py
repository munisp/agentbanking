"""
Agent Scorecard — Temporal Workflows
Implements durable, fault-tolerant workflows for:
  1. ScorecardRecomputeWorkflow    — event-driven single-agent recompute
  2. BatchScorecardWorkflow        — daily batch recompute for all agents
  3. TierChangeNotificationWorkflow — handles tier change side effects
"""
import logging
from datetime import timedelta
from typing import Optional, Dict, Any, List

from temporalio import workflow, activity
from temporalio.common import RetryPolicy

logger = logging.getLogger(__name__)

# ── Activity Definitions ───────────────────────────────────────────────────────

@activity.defn
async def fetch_raw_metrics_activity(agent_id: str, tenant_id: str) -> Dict[str, Any]:
    """
    Fetches all raw metrics needed for scorecard computation.
    Calls commission-settlement, compliance-kyc, fraud-detection,
    and agent-training services via Dapr service invocation.
    """
    activity.logger.info("Fetching raw metrics for agent=%s tenant=%s", agent_id, tenant_id)
    import httpx
    import os

    dapr_port = os.getenv("DAPR_HTTP_PORT", "3500")
    base = f"http://localhost:{dapr_port}/v1.0/invoke"

    metrics: Dict[str, Any] = {
        "agent_id": agent_id,
        "tenant_id": tenant_id,
        "transaction_count_30d": 0,
        "transaction_success_rate": 0.0,
        "transaction_volume_30d": 0.0,
        "transaction_growth_rate": 0.0,
        "avg_transaction_time_seconds": 0.0,
        "kyc_status": "pending",
        "aml_alerts_count": 0,
        "regulatory_violations": 0,
        "fraud_incidents_90d": 0,
        "customer_complaints_30d": 0,
        "complaint_resolution_rate": 0.0,
        "nps_score": 0.0,
        "training_modules_completed": 0,
        "training_modules_total": 10,
        "certification_score": 0.0,
        "sub_agents_count": 0,
        "active_sub_agents": 0,
        "float_utilization_rate": 0.0,
        "uptime_percentage": 0.0,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        # Commission/transaction metrics
        try:
            resp = await client.get(
                f"{base}/commission-settlement/method/agents/{agent_id}/metrics",
                params={"tenant_id": tenant_id, "days": 30},
            )
            if resp.status_code == 200:
                data = resp.json()
                metrics.update({
                    "transaction_count_30d": data.get("transaction_count", 0),
                    "transaction_success_rate": data.get("success_rate", 0.0),
                    "transaction_volume_30d": data.get("total_volume", 0.0),
                    "transaction_growth_rate": data.get("growth_rate", 0.0),
                    "avg_transaction_time_seconds": data.get("avg_processing_time", 0.0),
                })
        except Exception as e:
            activity.logger.warning("Could not fetch transaction metrics: %s", e)

        # KYC/compliance metrics
        try:
            resp = await client.get(
                f"{base}/compliance-kyc/method/agents/{agent_id}/kyc-status",
                params={"tenant_id": tenant_id},
            )
            if resp.status_code == 200:
                data = resp.json()
                metrics.update({
                    "kyc_status": data.get("status", "pending"),
                    "aml_alerts_count": data.get("aml_alerts", 0),
                    "regulatory_violations": data.get("violations", 0),
                })
        except Exception as e:
            activity.logger.warning("Could not fetch KYC metrics: %s", e)

        # Fraud metrics
        try:
            resp = await client.get(
                f"{base}/fraud-detection/method/agents/{agent_id}/incidents",
                params={"tenant_id": tenant_id, "days": 90},
            )
            if resp.status_code == 200:
                data = resp.json()
                metrics["fraud_incidents_90d"] = data.get("incident_count", 0)
        except Exception as e:
            activity.logger.warning("Could not fetch fraud metrics: %s", e)

        # Customer experience metrics
        try:
            resp = await client.get(
                f"{base}/customer-management/method/agents/{agent_id}/cx-metrics",
                params={"tenant_id": tenant_id, "days": 30},
            )
            if resp.status_code == 200:
                data = resp.json()
                metrics.update({
                    "customer_complaints_30d": data.get("complaints", 0),
                    "complaint_resolution_rate": data.get("resolution_rate", 0.0),
                    "nps_score": data.get("nps_score", 0.0),
                })
        except Exception as e:
            activity.logger.warning("Could not fetch CX metrics: %s", e)

        # Training metrics
        try:
            resp = await client.get(
                f"{base}/agent-training/method/agents/{agent_id}/progress",
                params={"tenant_id": tenant_id},
            )
            if resp.status_code == 200:
                data = resp.json()
                metrics.update({
                    "training_modules_completed": data.get("completed", 0),
                    "training_modules_total": data.get("total", 10),
                    "certification_score": data.get("certification_score", 0.0),
                })
        except Exception as e:
            activity.logger.warning("Could not fetch training metrics: %s", e)

        # Network/sub-agent metrics
        try:
            resp = await client.get(
                f"{base}/agent-management/method/agents/{agent_id}/network",
                params={"tenant_id": tenant_id},
            )
            if resp.status_code == 200:
                data = resp.json()
                metrics.update({
                    "sub_agents_count": data.get("total_sub_agents", 0),
                    "active_sub_agents": data.get("active_sub_agents", 0),
                    "float_utilization_rate": data.get("float_utilization", 0.0),
                    "uptime_percentage": data.get("uptime_pct", 0.0),
                })
        except Exception as e:
            activity.logger.warning("Could not fetch network metrics: %s", e)

    return metrics


@activity.defn
async def compute_and_persist_scorecard_activity(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calls the scorecard service to compute and persist the scorecard.
    Returns the computed scorecard data.
    """
    import httpx
    import os

    dapr_port = os.getenv("DAPR_HTTP_PORT", "3500")
    agent_id = metrics["agent_id"]
    tenant_id = metrics["tenant_id"]

    activity.logger.info("Computing scorecard for agent=%s", agent_id)

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"http://localhost:{dapr_port}/v1.0/invoke/agent-scorecard/method/api/v1/scorecard/compute",
            json={"agent_id": agent_id, "tenant_id": tenant_id, "raw_metrics": metrics},
        )
        resp.raise_for_status()
        return resp.json()


@activity.defn
async def send_tier_change_notification_activity(
    agent_id: str, tenant_id: str, old_tier: str, new_tier: str,
    composite_score: float
) -> bool:
    """Sends tier change notification via the notification service."""
    import httpx
    import os

    dapr_port = os.getenv("DAPR_HTTP_PORT", "3500")
    activity.logger.info("Sending tier change notification for agent=%s: %s → %s",
                          agent_id, old_tier, new_tier)

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"http://localhost:{dapr_port}/v1.0/invoke/notification-service/method/notifications/send",
                json={
                    "recipient_id": agent_id,
                    "tenant_id": tenant_id,
                    "notification_type": "TIER_CHANGE",
                    "title": f"Agent Tier Update: {new_tier}",
                    "body": (
                        f"Your agent tier has changed from {old_tier} to {new_tier}. "
                        f"Your current composite score is {composite_score:.0f}/1000."
                    ),
                    "channels": ["push", "sms", "email"],
                    "metadata": {
                        "old_tier": old_tier,
                        "new_tier": new_tier,
                        "composite_score": composite_score,
                    },
                },
            )
            return resp.status_code in (200, 201)
        except Exception as e:
            activity.logger.error("Notification failed: %s", e)
            return False


@activity.defn
async def update_finance_credit_limit_activity(
    agent_id: str, tenant_id: str, composite_score: float, tier: str
) -> bool:
    """Updates the agent's credit limit in the finance service based on new scorecard tier."""
    import httpx
    import os

    dapr_port = os.getenv("DAPR_HTTP_PORT", "3500")
    activity.logger.info("Updating credit limit for agent=%s based on tier=%s", agent_id, tier)

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"http://localhost:{dapr_port}/v1.0/invoke/agent-embedded-finance/method/api/v1/finance/credit-profiles/update-from-scorecard",
                json={
                    "agent_id": agent_id,
                    "tenant_id": tenant_id,
                    "composite_score": composite_score,
                    "tier": tier,
                },
            )
            return resp.status_code in (200, 201)
        except Exception as e:
            activity.logger.error("Credit limit update failed: %s", e)
            return False


@activity.defn
async def get_all_agents_activity(tenant_id: str) -> List[str]:
    """Fetches all active agent IDs for a tenant from agent-management service."""
    import httpx
    import os

    dapr_port = os.getenv("DAPR_HTTP_PORT", "3500")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(
                f"http://localhost:{dapr_port}/v1.0/invoke/agent-management/method/agents/active",
                params={"tenant_id": tenant_id},
            )
            if resp.status_code == 200:
                data = resp.json()
                return [a["agent_id"] for a in data.get("agents", [])]
        except Exception as e:
            activity.logger.error("Failed to fetch agents: %s", e)
    return []


# ── Workflow Definitions ───────────────────────────────────────────────────────

@workflow.defn
class ScorecardRecomputeWorkflow:
    """
    Event-driven workflow that recomputes a single agent's scorecard.
    Triggered by: transaction completion, KYC update, fraud alert, etc.
    """

    @workflow.run
    async def run(self, agent_id: str, tenant_id: str, trigger: str) -> Dict[str, Any]:
        workflow.logger.info(
            "ScorecardRecomputeWorkflow started | agent=%s tenant=%s trigger=%s",
            agent_id, tenant_id, trigger
        )

        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=2),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(minutes=5),
            maximum_attempts=5,
        )

        # Step 1: Fetch all raw metrics from platform services
        metrics = await workflow.execute_activity(
            fetch_raw_metrics_activity,
            args=[agent_id, tenant_id],
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=retry_policy,
        )

        # Step 2: Compute and persist the scorecard
        scorecard = await workflow.execute_activity(
            compute_and_persist_scorecard_activity,
            args=[metrics],
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=retry_policy,
        )

        # Step 3: If tier changed, trigger side effects
        old_tier = scorecard.get("previous_tier")
        new_tier = scorecard.get("tier")
        composite_score = scorecard.get("composite_score", 0.0)

        if old_tier and new_tier and old_tier != new_tier:
            # Send notification
            await workflow.execute_activity(
                send_tier_change_notification_activity,
                args=[agent_id, tenant_id, old_tier, new_tier, composite_score],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            # Update credit limit
            await workflow.execute_activity(
                update_finance_credit_limit_activity,
                args=[agent_id, tenant_id, composite_score, new_tier],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )

        workflow.logger.info(
            "ScorecardRecomputeWorkflow completed | agent=%s score=%.0f tier=%s",
            agent_id, composite_score, new_tier
        )
        return scorecard


@workflow.defn
class BatchScorecardWorkflow:
    """
    Daily batch workflow that recomputes scorecards for ALL agents in a tenant.
    Scheduled to run at 2 AM UTC via Dapr cron binding.
    Fans out to individual ScorecardRecomputeWorkflow instances.
    """

    @workflow.run
    async def run(self, tenant_id: str) -> Dict[str, Any]:
        workflow.logger.info("BatchScorecardWorkflow started for tenant=%s", tenant_id)

        # Get all active agents
        agent_ids = await workflow.execute_activity(
            get_all_agents_activity,
            args=[tenant_id],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        workflow.logger.info("Processing %d agents for tenant=%s", len(agent_ids), tenant_id)

        # Fan out: launch child workflows for each agent
        # Process in batches of 50 to avoid overwhelming downstream services
        batch_size = 50
        success_count = 0
        failure_count = 0

        for i in range(0, len(agent_ids), batch_size):
            batch = agent_ids[i:i + batch_size]
            handles = []

            for agent_id in batch:
                handle = await workflow.start_child_workflow(
                    ScorecardRecomputeWorkflow.run,
                    args=[agent_id, tenant_id, "batch_daily"],
                    id=f"scorecard-batch-{tenant_id}-{agent_id}",
                    execution_timeout=timedelta(minutes=10),
                )
                handles.append((agent_id, handle))

            # Wait for all in batch
            for agent_id, handle in handles:
                try:
                    await handle
                    success_count += 1
                except Exception as e:
                    workflow.logger.error("Batch recompute failed for agent=%s: %s", agent_id, e)
                    failure_count += 1

        result = {
            "tenant_id": tenant_id,
            "total_agents": len(agent_ids),
            "success_count": success_count,
            "failure_count": failure_count,
            "completed_at": workflow.now().isoformat(),
        }
        workflow.logger.info("BatchScorecardWorkflow completed: %s", result)
        return result


# ── Worker Registration ────────────────────────────────────────────────────────

async def start_temporal_worker():
    """Start the Temporal worker for Agent Scorecard workflows."""
    from temporalio.client import Client
    from temporalio.worker import Worker
    import os

    temporal_host = os.getenv("TEMPORAL_HOST", "temporal-frontend:7233")
    namespace = os.getenv("TEMPORAL_NAMESPACE", "54link-production")
    task_queue = os.getenv("TEMPORAL_SCORECARD_TASK_QUEUE", "agent-scorecard-task-queue")

    client = await Client.connect(temporal_host, namespace=namespace)

    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[ScorecardRecomputeWorkflow, BatchScorecardWorkflow],
        activities=[
            fetch_raw_metrics_activity,
            compute_and_persist_scorecard_activity,
            send_tier_change_notification_activity,
            update_finance_credit_limit_activity,
            get_all_agents_activity,
        ],
    )

    logger.info("Starting Temporal worker on task_queue=%s namespace=%s", task_queue, namespace)
    await worker.run()
