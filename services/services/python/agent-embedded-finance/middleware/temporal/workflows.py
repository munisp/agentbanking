"""
Agent Embedded Finance — Temporal Workflows
Implements durable, fault-tolerant workflows for:
  1. LoanApplicationWorkflow   — full loan application → approval → disbursement
  2. LoanRepaymentWorkflow     — repayment processing with ledger updates
  3. OverdueLoanWorkflow       — daily overdue detection and penalty accrual
  4. BNPLOrderWorkflow         — BNPL order creation and installment scheduling
"""
import logging
from datetime import timedelta
from typing import Dict, Any, List, Optional

from temporalio import workflow, activity
from temporalio.common import RetryPolicy

logger = logging.getLogger(__name__)


# ── Activities ─────────────────────────────────────────────────────────────────

@activity.defn
async def evaluate_credit_eligibility_activity(
    agent_id: str, tenant_id: str, requested_amount: float, product_type: str
) -> Dict[str, Any]:
    """Calls the finance service credit eligibility engine."""
    import httpx, os
    dapr_port = os.getenv("DAPR_HTTP_PORT", "3500")
    activity.logger.info("Evaluating credit for agent=%s amount=%.2f", agent_id, requested_amount)

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"http://localhost:{dapr_port}/v1.0/invoke/agent-embedded-finance/method/api/v1/finance/credit/evaluate",
            json={
                "agent_id": agent_id,
                "tenant_id": tenant_id,
                "requested_amount": requested_amount,
                "product_type": product_type,
            },
        )
        resp.raise_for_status()
        return resp.json()


@activity.defn
async def create_loan_application_activity(
    agent_id: str, tenant_id: str, product_type: str,
    requested_amount: float, tenure_days: int, purpose: str
) -> Dict[str, Any]:
    """Creates a loan application record in the database."""
    import httpx, os
    dapr_port = os.getenv("DAPR_HTTP_PORT", "3500")

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"http://localhost:{dapr_port}/v1.0/invoke/agent-embedded-finance/method/api/v1/finance/loans/apply",
            json={
                "agent_id": agent_id,
                "tenant_id": tenant_id,
                "product_type": product_type,
                "requested_amount": requested_amount,
                "tenure_days": tenure_days,
                "purpose": purpose,
            },
        )
        resp.raise_for_status()
        return resp.json()


@activity.defn
async def disburse_loan_activity(application_id: str, agent_id: str,
                                  tenant_id: str) -> Dict[str, Any]:
    """
    Disburses an approved loan:
    1. Creates TigerBeetle ledger transfer
    2. Updates loan status to ACTIVE
    3. Publishes LOAN_DISBURSED Kafka event
    """
    import httpx, os
    dapr_port = os.getenv("DAPR_HTTP_PORT", "3500")
    activity.logger.info("Disbursing loan for application=%s agent=%s", application_id, agent_id)

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"http://localhost:{dapr_port}/v1.0/invoke/agent-embedded-finance/method/api/v1/finance/loans/{application_id}/disburse",
            json={"agent_id": agent_id, "tenant_id": tenant_id},
        )
        resp.raise_for_status()
        return resp.json()


@activity.defn
async def notify_loan_decision_activity(
    agent_id: str, tenant_id: str, decision: str,
    amount: float, reason: Optional[str] = None
) -> bool:
    """Sends loan approval/rejection notification to agent."""
    import httpx, os
    dapr_port = os.getenv("DAPR_HTTP_PORT", "3500")

    title = "Loan Approved!" if decision == "approved" else "Loan Application Update"
    body = (
        f"Your loan application for ₦{amount:,.2f} has been approved. Funds will be disbursed shortly."
        if decision == "approved"
        else f"Your loan application could not be approved at this time. Reason: {reason or 'See app for details.'}"
    )

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                f"http://localhost:{dapr_port}/v1.0/invoke/notification-service/method/notifications/send",
                json={
                    "recipient_id": agent_id,
                    "tenant_id": tenant_id,
                    "notification_type": f"LOAN_{decision.upper()}",
                    "title": title,
                    "body": body,
                    "channels": ["push", "sms"],
                    "metadata": {"decision": decision, "amount": amount, "reason": reason},
                },
            )
            return resp.status_code in (200, 201)
        except Exception as e:
            activity.logger.error("Loan notification failed: %s", e)
            return False


@activity.defn
async def detect_overdue_loans_activity(tenant_id: str) -> List[Dict[str, Any]]:
    """Fetches all overdue loans for a tenant from the finance service."""
    import httpx, os
    dapr_port = os.getenv("DAPR_HTTP_PORT", "3500")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(
                f"http://localhost:{dapr_port}/v1.0/invoke/agent-embedded-finance/method/api/v1/finance/loans/overdue",
                params={"tenant_id": tenant_id},
            )
            if resp.status_code == 200:
                return resp.json().get("loans", [])
        except Exception as e:
            activity.logger.error("Failed to fetch overdue loans: %s", e)
    return []


@activity.defn
async def accrue_penalty_activity(loan_id: str, agent_id: str, tenant_id: str) -> Dict[str, Any]:
    """Accrues daily penalty on an overdue loan."""
    import httpx, os
    dapr_port = os.getenv("DAPR_HTTP_PORT", "3500")

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"http://localhost:{dapr_port}/v1.0/invoke/agent-embedded-finance/method/api/v1/finance/admin/accrue-penalties",
            json={"loan_id": loan_id, "agent_id": agent_id, "tenant_id": tenant_id},
        )
        resp.raise_for_status()
        return resp.json()


@activity.defn
async def create_bnpl_order_activity(
    agent_id: str, tenant_id: str, merchant_name: str,
    item_description: str, total_amount: float, installments: int
) -> Dict[str, Any]:
    """Creates a BNPL order with installment schedule."""
    import httpx, os
    dapr_port = os.getenv("DAPR_HTTP_PORT", "3500")

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            f"http://localhost:{dapr_port}/v1.0/invoke/agent-embedded-finance/method/api/v1/finance/bnpl/orders",
            json={
                "agent_id": agent_id,
                "tenant_id": tenant_id,
                "merchant_name": merchant_name,
                "item_description": item_description,
                "total_amount": total_amount,
                "installments": installments,
            },
        )
        resp.raise_for_status()
        return resp.json()


# ── Workflows ──────────────────────────────────────────────────────────────────

@workflow.defn
class LoanApplicationWorkflow:
    """
    Full loan application workflow:
    1. Evaluate credit eligibility
    2. Create application record
    3. Auto-approve or reject based on eligibility
    4. Disburse if approved
    5. Notify agent of decision
    """

    @workflow.run
    async def run(self, agent_id: str, tenant_id: str, product_type: str,
                  requested_amount: float, tenure_days: int, purpose: str) -> Dict[str, Any]:
        workflow.logger.info(
            "LoanApplicationWorkflow started | agent=%s amount=%.2f product=%s",
            agent_id, requested_amount, product_type
        )

        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=2),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(minutes=2),
            maximum_attempts=3,
        )

        # Step 1: Evaluate credit eligibility
        eligibility = await workflow.execute_activity(
            evaluate_credit_eligibility_activity,
            args=[agent_id, tenant_id, requested_amount, product_type],
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=retry_policy,
        )

        is_eligible = eligibility.get("is_eligible", False)
        approved_amount = eligibility.get("approved_amount", 0.0)
        rejection_reason = eligibility.get("rejection_reason")

        # Step 2: Create application record
        application = await workflow.execute_activity(
            create_loan_application_activity,
            args=[agent_id, tenant_id, product_type, requested_amount, tenure_days, purpose],
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=retry_policy,
        )
        application_id = application.get("application_id")

        if not is_eligible:
            # Notify rejection
            await workflow.execute_activity(
                notify_loan_decision_activity,
                args=[agent_id, tenant_id, "rejected", requested_amount, rejection_reason],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            return {
                "status": "rejected",
                "application_id": application_id,
                "reason": rejection_reason,
            }

        # Step 3: Disburse loan
        disbursement = await workflow.execute_activity(
            disburse_loan_activity,
            args=[application_id, agent_id, tenant_id],
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=5),
                maximum_attempts=3,
                non_retryable_error_types=["InsufficientFundsError"],
            ),
        )

        # Step 4: Notify approval
        await workflow.execute_activity(
            notify_loan_decision_activity,
            args=[agent_id, tenant_id, "approved", approved_amount],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        workflow.logger.info(
            "LoanApplicationWorkflow completed | agent=%s loan=%s amount=%.2f",
            agent_id, disbursement.get("loan_id"), approved_amount
        )
        return {
            "status": "disbursed",
            "application_id": application_id,
            "loan_id": disbursement.get("loan_id"),
            "disbursed_amount": approved_amount,
        }


@workflow.defn
class OverdueLoanWorkflow:
    """
    Daily workflow that detects overdue loans and accrues penalties.
    Scheduled to run at 1 AM UTC via Dapr cron binding.
    """

    @workflow.run
    async def run(self, tenant_id: str) -> Dict[str, Any]:
        workflow.logger.info("OverdueLoanWorkflow started for tenant=%s", tenant_id)

        # Detect all overdue loans
        overdue_loans = await workflow.execute_activity(
            detect_overdue_loans_activity,
            args=[tenant_id],
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        workflow.logger.info("Found %d overdue loans for tenant=%s", len(overdue_loans), tenant_id)

        processed = 0
        failed = 0

        for loan in overdue_loans:
            try:
                await workflow.execute_activity(
                    accrue_penalty_activity,
                    args=[loan["loan_id"], loan["agent_id"], tenant_id],
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RetryPolicy(maximum_attempts=2),
                )
                processed += 1
            except Exception as e:
                workflow.logger.error("Penalty accrual failed for loan=%s: %s",
                                       loan.get("loan_id"), e)
                failed += 1

        return {
            "tenant_id": tenant_id,
            "overdue_loans_found": len(overdue_loans),
            "penalties_accrued": processed,
            "failures": failed,
            "completed_at": workflow.now().isoformat(),
        }


@workflow.defn
class BNPLOrderWorkflow:
    """
    BNPL order creation workflow with credit check and installment scheduling.
    """

    @workflow.run
    async def run(self, agent_id: str, tenant_id: str, merchant_name: str,
                  item_description: str, total_amount: float, installments: int) -> Dict[str, Any]:
        workflow.logger.info(
            "BNPLOrderWorkflow started | agent=%s amount=%.2f installments=%d",
            agent_id, total_amount, installments
        )

        retry_policy = RetryPolicy(maximum_attempts=3)

        # Credit check for BNPL
        eligibility = await workflow.execute_activity(
            evaluate_credit_eligibility_activity,
            args=[agent_id, tenant_id, total_amount, "bnpl"],
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=retry_policy,
        )

        if not eligibility.get("is_eligible", False):
            return {
                "status": "rejected",
                "reason": eligibility.get("rejection_reason", "Credit check failed"),
            }

        # Create BNPL order
        order = await workflow.execute_activity(
            create_bnpl_order_activity,
            args=[agent_id, tenant_id, merchant_name, item_description, total_amount, installments],
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=retry_policy,
        )

        # Notify agent
        await workflow.execute_activity(
            notify_loan_decision_activity,
            args=[agent_id, tenant_id, "approved", total_amount],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        workflow.logger.info("BNPLOrderWorkflow completed | order=%s", order.get("order_id"))
        return {"status": "created", "order": order}


# ── Worker Registration ────────────────────────────────────────────────────────

async def start_temporal_worker():
    """Start the Temporal worker for Agent Embedded Finance workflows."""
    from temporalio.client import Client
    from temporalio.worker import Worker
    import os

    temporal_host = os.getenv("TEMPORAL_HOST", "temporal-frontend:7233")
    namespace = os.getenv("TEMPORAL_NAMESPACE", "54link-production")
    task_queue = os.getenv("TEMPORAL_FINANCE_TASK_QUEUE", "agent-finance-task-queue")

    client = await Client.connect(temporal_host, namespace=namespace)

    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[LoanApplicationWorkflow, OverdueLoanWorkflow, BNPLOrderWorkflow],
        activities=[
            evaluate_credit_eligibility_activity,
            create_loan_application_activity,
            disburse_loan_activity,
            notify_loan_decision_activity,
            detect_overdue_loans_activity,
            accrue_penalty_activity,
            create_bnpl_order_activity,
        ],
    )

    logger.info("Starting Temporal worker on task_queue=%s namespace=%s", task_queue, namespace)
    await worker.run()
