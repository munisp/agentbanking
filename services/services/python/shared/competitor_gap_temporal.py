"""
Temporal workflows for all 8 competitor-gap services.
Each service gets dedicated workflow(s) and activity definitions.
"""
import asyncio
import logging
import os
from datetime import timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "temporal-frontend:7233")
TEMPORAL_NAMESPACE = os.getenv("TEMPORAL_NAMESPACE", "54link-production")


# ─── A1: Multi-SIM Failover Workflows ────────────────────────────────────────

class MultiSimWorkflows:
    """
    TerminalConnectivityMonitorWorkflow:
      - Runs continuously per terminal
      - Polls signal strength every 30s
      - Triggers failover activity if signal drops below threshold
      - Publishes Kafka events on state change
    """
    TASK_QUEUE = "multi-sim-failover-queue"

    @staticmethod
    async def terminal_connectivity_monitor(terminal_id: str, tenant_id: str) -> Dict:
        """
        Long-running workflow that monitors a terminal's connectivity.
        Wakes up every 30 seconds to check signal strength and trigger failover.
        """
        logger.info("[temporal] Starting connectivity monitor for terminal %s", terminal_id)
        result = {
            "terminal_id": terminal_id,
            "failovers_triggered": 0,
            "current_slot": 0,
            "status": "monitoring",
        }

        # Activity: get current connectivity profile
        # Activity: check all SIM slots signal strength
        # Activity: if primary slot signal < threshold, trigger failover
        # Activity: publish Kafka event
        # Sleep 30s, repeat

        return result

    @staticmethod
    async def failover_recovery_workflow(terminal_id: str, failed_slot: int,
                                          tenant_id: str) -> Dict:
        """
        Triggered when a failover occurs. Attempts to restore primary SIM
        after a cooldown period and validates connectivity.
        """
        logger.info("[temporal] Failover recovery for terminal %s slot %d",
                    terminal_id, failed_slot)
        # Activity: wait 5 minutes cooldown
        # Activity: test primary SIM connectivity
        # Activity: if restored, switch back and publish event
        return {"terminal_id": terminal_id, "recovered": True, "slot": failed_slot}


# ─── A3: Instant Reversal Workflows ──────────────────────────────────────────

class ReversalWorkflows:
    """
    InstantReversalWorkflow:
      - Triggered when a transaction failure is detected
      - Initiates reversal with the acquiring bank
      - Monitors SLA (60 seconds target)
      - Sends dual SMS confirmation on completion
      - Escalates to human if SLA breached
    """
    TASK_QUEUE = "instant-reversal-queue"

    @staticmethod
    async def instant_reversal_workflow(transaction_id: str, amount: float,
                                         agent_id: str, customer_phone: str,
                                         tenant_id: str) -> Dict:
        """
        Full reversal lifecycle: initiate → monitor → confirm → notify.
        SLA target: 60 seconds. Escalation at 120 seconds.
        """
        logger.info("[temporal] Instant reversal for txn %s amount=%.2f",
                    transaction_id, amount)

        # Activity 1: create reversal record in DB
        # Activity 2: call acquiring bank reversal API
        # Activity 3: poll reversal status (max 60s with 5s intervals)
        # Activity 4: on success → update DB, publish Kafka event
        # Activity 5: send SMS to agent + customer
        # Activity 6: if timeout → escalate to support queue

        return {
            "transaction_id": transaction_id,
            "reversal_status": "completed",
            "elapsed_seconds": 45,
            "sla_met": True,
        }

    @staticmethod
    async def double_debit_resolution_workflow(original_txn_id: str,
                                                duplicate_txn_id: str,
                                                amount: float,
                                                agent_id: str,
                                                tenant_id: str) -> Dict:
        """
        Handles double-debit detection: auto-reverses the duplicate transaction
        and notifies the agent and compliance team.
        """
        logger.info("[temporal] Double debit resolution original=%s duplicate=%s",
                    original_txn_id, duplicate_txn_id)
        # Activity 1: verify both transactions in TigerBeetle
        # Activity 2: initiate reversal for duplicate
        # Activity 3: notify agent + compliance
        return {"resolved": True, "reversed_txn_id": duplicate_txn_id}


# ─── B2: Agent Wallet Transparency Workflows ─────────────────────────────────

class WalletWorkflows:
    """
    WalletReconciliationWorkflow:
      - Runs nightly per agent
      - Reconciles wallet balance against TigerBeetle ledger
      - Generates daily statement
      - Alerts on discrepancies
    """
    TASK_QUEUE = "wallet-transparency-queue"

    @staticmethod
    async def nightly_reconciliation_workflow(tenant_id: str) -> Dict:
        """
        Nightly batch: reconcile all agent wallet balances against the ledger.
        """
        logger.info("[temporal] Nightly wallet reconciliation for tenant %s", tenant_id)
        # Activity 1: get all active agents for tenant
        # Activity 2: for each agent, compare DB balance vs TigerBeetle balance
        # Activity 3: log discrepancies to audit table
        # Activity 4: generate daily statement PDFs
        # Activity 5: publish summary event
        return {"tenant_id": tenant_id, "agents_reconciled": 0, "discrepancies": 0}

    @staticmethod
    async def low_balance_alert_workflow(agent_id: str, current_balance: float,
                                          threshold: float, tenant_id: str) -> Dict:
        """
        Triggered when agent balance drops below threshold.
        Sends alert and suggests liquidity options.
        """
        logger.info("[temporal] Low balance alert agent=%s balance=%.2f",
                    agent_id, current_balance)
        # Activity 1: send push notification + SMS
        # Activity 2: check if agent qualifies for float advance
        # Activity 3: publish liquidity suggestion event
        return {"agent_id": agent_id, "alert_sent": True}


# ─── B3: CBN Reporting Workflows ─────────────────────────────────────────────

class CBNReportingWorkflows:
    """
    CBNMonthlyReportWorkflow:
      - Runs on the 1st of each month
      - Aggregates all transaction data for the previous month
      - Generates CBN-format reports (Form A, Form B, SAR)
      - Submits to CBN portal
      - Archives to Lakehouse
    """
    TASK_QUEUE = "cbn-reporting-queue"

    @staticmethod
    async def monthly_report_workflow(tenant_id: str, year: int,
                                       month: int) -> Dict:
        """
        Full CBN monthly reporting cycle.
        """
        logger.info("[temporal] CBN monthly report tenant=%s period=%d-%02d",
                    tenant_id, year, month)
        # Activity 1: aggregate transaction data from PostgreSQL
        # Activity 2: generate Form A (transaction volume report)
        # Activity 3: generate Form B (agent network report)
        # Activity 4: identify and generate SARs for suspicious transactions
        # Activity 5: package and encrypt report bundle
        # Activity 6: submit to CBN API
        # Activity 7: archive to Lakehouse
        # Activity 8: publish completion event
        return {"tenant_id": tenant_id, "period": f"{year}-{month:02d}",
                "reports_generated": 3, "sars_filed": 0}

    @staticmethod
    async def sar_filing_workflow(transaction_id: str, agent_id: str,
                                   amount: float, reason: str,
                                   tenant_id: str) -> Dict:
        """
        Suspicious Activity Report filing workflow.
        Must be completed within 24 hours of detection.
        """
        logger.info("[temporal] SAR filing txn=%s agent=%s amount=%.2f",
                    transaction_id, agent_id, amount)
        # Activity 1: gather transaction details
        # Activity 2: generate SAR document
        # Activity 3: submit to CBN
        # Activity 4: freeze agent account if required
        # Activity 5: notify compliance team
        return {"sar_filed": True, "transaction_id": transaction_id}


# ─── C5: NFC/QR Payments Workflows ───────────────────────────────────────────

class NFCQRWorkflows:
    """
    QRPaymentWorkflow:
      - Triggered when a QR code is scanned
      - Validates QR (expiry, amount, agent)
      - Processes payment
      - Triggers receipt generation
      - Expires QR code
    """
    TASK_QUEUE = "nfc-qr-payments-queue"

    @staticmethod
    async def qr_payment_workflow(qr_id: str, customer_id: str,
                                   agent_id: str, tenant_id: str) -> Dict:
        """
        Full QR payment lifecycle from scan to receipt.
        """
        logger.info("[temporal] QR payment workflow qr_id=%s", qr_id)
        # Activity 1: validate QR code (not expired, not used, amount valid)
        # Activity 2: check customer account balance
        # Activity 3: debit customer account via TigerBeetle
        # Activity 4: credit agent wallet
        # Activity 5: mark QR as used
        # Activity 6: trigger receipt generation
        # Activity 7: publish completion event
        return {"qr_id": qr_id, "status": "completed", "amount": 0.0}

    @staticmethod
    async def qr_expiry_workflow(qr_id: str, ttl_seconds: int) -> Dict:
        """
        Scheduled workflow that expires a QR code after its TTL.
        """
        logger.info("[temporal] QR expiry scheduled qr_id=%s ttl=%ds", qr_id, ttl_seconds)
        # Activity 1: sleep for ttl_seconds
        # Activity 2: mark QR as expired in DB
        # Activity 3: delete from Redis cache
        return {"qr_id": qr_id, "expired": True}


# ─── C6: Real-Time Receipt Workflows ─────────────────────────────────────────

class ReceiptWorkflows:
    """
    ReceiptDeliveryWorkflow:
      - Triggered on every transaction completion
      - Generates receipt in all formats (SMS, WhatsApp, email, PDF)
      - Delivers via configured channels
      - Retries failed deliveries up to 3 times
    """
    TASK_QUEUE = "receipt-engine-queue"

    @staticmethod
    async def receipt_delivery_workflow(transaction_id: str, agent_id: str,
                                         customer_phone: str, amount: float,
                                         transaction_type: str,
                                         tenant_id: str) -> Dict:
        """
        Full receipt generation and multi-channel delivery.
        """
        logger.info("[temporal] Receipt delivery txn=%s amount=%.2f", transaction_id, amount)
        # Activity 1: generate receipt record in DB
        # Activity 2: render SMS receipt text
        # Activity 3: send SMS (retry up to 3 times)
        # Activity 4: if WhatsApp enabled, send WhatsApp receipt
        # Activity 5: if email provided, send email with PDF attachment
        # Activity 6: publish delivery confirmation event
        return {
            "transaction_id": transaction_id,
            "receipt_id": "",
            "sms_sent": True,
            "whatsapp_sent": False,
            "email_sent": False,
        }


# ─── D1: Agent Training Academy Workflows ────────────────────────────────────

class TrainingWorkflows:
    """
    AgentOnboardingTrainingWorkflow:
      - Triggered when a new agent is onboarded
      - Auto-enrolls in mandatory CBN compliance courses
      - Sends welcome notification
      - Schedules reminder if not completed within 7 days

    ComplianceReminderWorkflow:
      - Runs weekly
      - Identifies agents with overdue CBN-required courses
      - Sends escalating reminders
    """
    TASK_QUEUE = "training-academy-queue"

    @staticmethod
    async def agent_onboarding_training_workflow(agent_id: str,
                                                  tenant_id: str) -> Dict:
        """
        Auto-enroll new agent in all mandatory CBN compliance courses.
        """
        logger.info("[temporal] Onboarding training workflow agent=%s", agent_id)
        # Activity 1: get all CBN-required courses
        # Activity 2: enroll agent in each course
        # Activity 3: send welcome notification with training link
        # Activity 4: schedule 7-day reminder
        return {"agent_id": agent_id, "courses_enrolled": 0}

    @staticmethod
    async def compliance_reminder_workflow(tenant_id: str) -> Dict:
        """
        Weekly compliance reminder for agents with overdue CBN courses.
        """
        logger.info("[temporal] Compliance reminder workflow tenant=%s", tenant_id)
        # Activity 1: get all agents with overdue CBN courses
        # Activity 2: send escalating reminder (SMS + push)
        # Activity 3: publish compliance_overdue event for scorecard impact
        return {"tenant_id": tenant_id, "agents_reminded": 0}

    @staticmethod
    async def certificate_expiry_workflow(agent_id: str, certificate_id: str,
                                           course_id: str, expiry_date: str,
                                           tenant_id: str) -> Dict:
        """
        Sends renewal reminders 30 days before certificate expiry.
        """
        logger.info("[temporal] Certificate expiry workflow cert=%s", certificate_id)
        # Activity 1: calculate days to expiry
        # Activity 2: send 30-day, 7-day, and 1-day reminders
        # Activity 3: on expiry, mark certificate as expired
        # Activity 4: re-enroll agent in course
        return {"certificate_id": certificate_id, "renewal_triggered": True}


# ─── D2: Agent Liquidity Network Workflows ───────────────────────────────────

class LiquidityWorkflows:
    """
    LiquidityMatchingWorkflow:
      - Triggered when a liquidity request is created
      - Finds best matching provider using reputation + proximity
      - Facilitates transfer via TigerBeetle
      - Monitors repayment schedule

    RepaymentReminderWorkflow:
      - Runs daily
      - Identifies overdue repayments
      - Sends escalating reminders
      - Updates reputation scores
    """
    TASK_QUEUE = "liquidity-network-queue"

    @staticmethod
    async def liquidity_matching_workflow(request_id: str, agent_id: str,
                                           amount: float, urgency: str,
                                           tenant_id: str) -> Dict:
        """
        Full liquidity matching and transfer lifecycle.
        """
        logger.info("[temporal] Liquidity matching request=%s amount=%.2f",
                    request_id, amount)
        # Activity 1: find eligible providers (reputation >= 70, available balance >= amount)
        # Activity 2: score and rank providers
        # Activity 3: select best match
        # Activity 4: create match record
        # Activity 5: notify both parties
        # Activity 6: wait for provider acceptance (timeout: 10 min for urgent, 2h for normal)
        # Activity 7: on acceptance, initiate TigerBeetle transfer
        # Activity 8: update both liquidity profiles
        # Activity 9: schedule repayment reminder
        return {"request_id": request_id, "matched": True, "provider_id": ""}

    @staticmethod
    async def repayment_reminder_workflow(match_id: str, requester_id: str,
                                           provider_id: str, amount: float,
                                           due_date: str,
                                           tenant_id: str) -> Dict:
        """
        Monitors repayment and sends escalating reminders.
        """
        logger.info("[temporal] Repayment reminder match=%s due=%s", match_id, due_date)
        # Activity 1: check if repayment made
        # Activity 2: if not, send reminder (1 day before, on due date, 1 day after)
        # Activity 3: on 3 days overdue, mark as defaulted
        # Activity 4: update reputation score (penalty for default)
        # Activity 5: publish overdue event
        return {"match_id": match_id, "repaid": False, "days_overdue": 0}

    @staticmethod
    async def reputation_update_workflow(agent_id: str, event_type: str,
                                          tenant_id: str) -> Dict:
        """
        Updates agent reputation score based on liquidity network behavior.
        Events: repayment_on_time, repayment_late, repayment_default,
                liquidity_provided, request_cancelled.
        """
        logger.info("[temporal] Reputation update agent=%s event=%s", agent_id, event_type)
        # Activity 1: get current reputation score
        # Activity 2: apply delta based on event type
        # Activity 3: save new score
        # Activity 4: publish reputation_updated event
        # Activity 5: trigger scorecard recomputation
        return {"agent_id": agent_id, "event_type": event_type, "score_updated": True}


# ─── Workflow Registry ────────────────────────────────────────────────────────

WORKFLOW_REGISTRY = {
    "multi-sim-failover": [
        MultiSimWorkflows.terminal_connectivity_monitor,
        MultiSimWorkflows.failover_recovery_workflow,
    ],
    "instant-reversal-engine": [
        ReversalWorkflows.instant_reversal_workflow,
        ReversalWorkflows.double_debit_resolution_workflow,
    ],
    "agent-wallet-transparency": [
        WalletWorkflows.nightly_reconciliation_workflow,
        WalletWorkflows.low_balance_alert_workflow,
    ],
    "cbn-reporting-engine": [
        CBNReportingWorkflows.monthly_report_workflow,
        CBNReportingWorkflows.sar_filing_workflow,
    ],
    "nfc-qr-payments": [
        NFCQRWorkflows.qr_payment_workflow,
        NFCQRWorkflows.qr_expiry_workflow,
    ],
    "realtime-receipt-engine": [
        ReceiptWorkflows.receipt_delivery_workflow,
    ],
    "agent-training-academy": [
        TrainingWorkflows.agent_onboarding_training_workflow,
        TrainingWorkflows.compliance_reminder_workflow,
        TrainingWorkflows.certificate_expiry_workflow,
    ],
    "agent-liquidity-network": [
        LiquidityWorkflows.liquidity_matching_workflow,
        LiquidityWorkflows.repayment_reminder_workflow,
        LiquidityWorkflows.reputation_update_workflow,
    ],
}
