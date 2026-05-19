"""
Agent Embedded Finance — Platform Services Integration
Connects the Agent Embedded Finance service to existing 54link platform services:
  - Credit Scoring Engine: enriches credit eligibility with ML credit scores
  - Notification Service: sends loan status, disbursement, repayment, and BNPL notifications
  - Commission Service: pauses/resumes commission payouts for agents with overdue loans
  - Agent Scorecard: triggers scorecard recomputation after loan events
  - TigerBeetle Ledger: executes all financial transfers via the Go ledger service
"""
import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

# ── Service URLs ───────────────────────────────────────────────────────────────
CREDIT_SCORING_URL      = os.getenv("CREDIT_SCORING_URL",       "http://credit-scoring:8080")
NOTIFICATION_SERVICE_URL= os.getenv("NOTIFICATION_SERVICE_URL", "http://notification-service:8050")
COMMISSION_SERVICE_URL  = os.getenv("COMMISSION_SERVICE_URL",   "http://commission-service:8001")
AGENT_SCORECARD_URL     = os.getenv("AGENT_SCORECARD_URL",      "http://agent-scorecard:8010")
LEDGER_SERVICE_URL      = os.getenv("LEDGER_SERVICE_URL",       "http://agent-finance-ledger:8020")

SERVICE_TOKEN = os.getenv("INTERNAL_SERVICE_TOKEN", "")

_HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {SERVICE_TOKEN}",
    "X-Service-Name": "agent-embedded-finance",
}

_TIMEOUT = httpx.Timeout(15.0, connect=5.0)


# ── Credit Scoring Integration ────────────────────────────────────────────────

async def get_ml_credit_score(agent_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch the ML-based credit score from the Credit Scoring Engine.
    Returns score, risk_band, and feature explanations.
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
                return {
                    "score":       float(data.get("score", data.get("credit_score", 500))),
                    "risk_band":   data.get("risk_band", "medium"),
                    "max_credit":  float(data.get("recommended_limit", 50000)),
                    "features":    data.get("feature_importance", {}),
                }
            return None
    except Exception as e:
        logger.warning("Could not fetch ML credit score for agent=%s: %s", agent_id, e)
        return None


# ── TigerBeetle Ledger Integration ────────────────────────────────────────────

async def create_agent_ledger_account(
    agent_id: str,
    tenant_id: str,
    account_type: str = "agent_float",
    currency: str = "NGN",
) -> Optional[str]:
    """Create a TigerBeetle account for the agent via the Go ledger service."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{LEDGER_SERVICE_URL}/accounts",
                json={
                    "agent_id":     agent_id,
                    "tenant_id":    tenant_id,
                    "currency":     currency,
                    "account_type": account_type,
                },
                headers=_HEADERS,
            )
            if resp.status_code in (200, 201):
                return resp.json().get("account_id")
            logger.warning("Ledger account creation returned %d: %s",
                           resp.status_code, resp.text[:200])
            return None
    except Exception as e:
        logger.error("Failed to create ledger account for agent=%s: %s", agent_id, e)
        return None


async def execute_ledger_transfer(
    transfer_id: str,
    debit_account_id: str,
    credit_account_id: str,
    amount: int,  # In lowest denomination (kobo for NGN)
    currency: str,
    code: str,
    two_phase: bool = False,
) -> Dict[str, Any]:
    """
    Execute a financial transfer via the TigerBeetle Go ledger service.
    Returns {"transfer_id": ..., "status": "posted"|"pending"|"failed", "error": ...}
    """
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{LEDGER_SERVICE_URL}/transfers",
                json={
                    "transfer_id":       transfer_id,
                    "debit_account_id":  debit_account_id,
                    "credit_account_id": credit_account_id,
                    "amount":            amount,
                    "currency":          currency,
                    "code":              code,
                    "two_phase":         two_phase,
                },
                headers=_HEADERS,
            )
            if resp.status_code in (200, 201):
                return resp.json()
            return {
                "transfer_id": transfer_id,
                "status": "failed",
                "error": f"Ledger service returned {resp.status_code}: {resp.text[:200]}",
            }
    except Exception as e:
        logger.error("Ledger transfer failed: %s", e)
        return {"transfer_id": transfer_id, "status": "failed", "error": str(e)}


async def get_ledger_balance(account_id: str) -> Optional[int]:
    """Get the current balance of a TigerBeetle account (in lowest denomination)."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(
                f"{LEDGER_SERVICE_URL}/accounts/{account_id}",
                headers=_HEADERS,
            )
            if resp.status_code == 200:
                return int(resp.json().get("balance", 0))
            return None
    except Exception as e:
        logger.warning("Could not fetch ledger balance for account=%s: %s", account_id, e)
        return None


# ── Notification Service Integration ─────────────────────────────────────────

async def send_finance_notification(
    agent_id: str,
    tenant_id: str,
    notification_type: str,
    data: Dict[str, Any],
) -> bool:
    """
    Send a finance-related notification via the platform Notification Service.

    notification_type options:
      - "loan_application_received": Application submitted
      - "loan_approved": Loan approved with terms
      - "loan_rejected": Loan rejected with reason
      - "loan_disbursed": Funds disbursed to agent float
      - "repayment_received": Repayment acknowledged
      - "loan_overdue": Loan is past due date
      - "bnpl_order_created": BNPL order created
      - "bnpl_installment_due": Installment payment due reminder
      - "bnpl_installment_paid": Installment payment confirmed
    """
    templates = {
        "loan_application_received": {
            "title": "Loan Application Received",
            "body": (f"Your {data.get('product_type', 'loan')} application of "
                     f"₦{data.get('amount', 0):,.0f} is under review. "
                     f"Ref: {data.get('application_id', '')}"),
            "channels": ["push", "in_app"],
        },
        "loan_approved": {
            "title": "Loan Approved!",
            "body": (f"Your loan of ₦{data.get('principal', 0):,.0f} has been approved. "
                     f"Interest rate: {data.get('rate', 0):.1f}%. "
                     f"Repayment due: {data.get('due_date', '')}"),
            "channels": ["push", "sms", "in_app"],
        },
        "loan_rejected": {
            "title": "Loan Application Update",
            "body": (f"Your loan application could not be approved at this time. "
                     f"Reason: {data.get('reason', 'Does not meet eligibility criteria')}. "
                     f"Improve your scorecard to qualify."),
            "channels": ["push", "in_app"],
        },
        "loan_disbursed": {
            "title": "Funds Disbursed",
            "body": (f"₦{data.get('amount', 0):,.0f} has been credited to your float account. "
                     f"Repayment of ₦{data.get('total_repayable', 0):,.0f} due by "
                     f"{data.get('due_date', '')}."),
            "channels": ["push", "sms", "in_app"],
        },
        "repayment_received": {
            "title": "Repayment Confirmed",
            "body": (f"₦{data.get('amount', 0):,.0f} repayment received. "
                     f"Outstanding balance: ₦{data.get('outstanding', 0):,.0f}."),
            "channels": ["push", "in_app"],
        },
        "loan_overdue": {
            "title": "Loan Overdue — Action Required",
            "body": (f"Your loan of ₦{data.get('outstanding', 0):,.0f} is "
                     f"{data.get('days_overdue', 0)} days overdue. "
                     f"Daily penalty: ₦{data.get('daily_penalty', 0):,.0f}. "
                     f"Please repay immediately."),
            "channels": ["push", "sms", "in_app"],
        },
        "bnpl_order_created": {
            "title": "BNPL Order Confirmed",
            "body": (f"BNPL order of ₦{data.get('total_amount', 0):,.0f} created. "
                     f"{data.get('installments', 0)} installments of "
                     f"₦{data.get('installment_amount', 0):,.0f} each."),
            "channels": ["push", "in_app"],
        },
        "bnpl_installment_due": {
            "title": "BNPL Installment Due",
            "body": (f"₦{data.get('amount', 0):,.0f} BNPL installment due on "
                     f"{data.get('due_date', '')}. Pay now to avoid penalties."),
            "channels": ["push", "sms", "in_app"],
        },
        "bnpl_installment_paid": {
            "title": "BNPL Installment Paid",
            "body": (f"₦{data.get('amount', 0):,.0f} installment confirmed. "
                     f"Remaining: {data.get('remaining_installments', 0)} installments."),
            "channels": ["push", "in_app"],
        },
    }

    template = templates.get(notification_type, {
        "title": "Finance Update",
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
        "source":            "agent-embedded-finance",
    }

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{NOTIFICATION_SERVICE_URL}/send-notification",
                json=payload,
                headers=_HEADERS,
            )
            if resp.status_code in (200, 201, 204):
                logger.info("Finance notification sent: type=%s agent=%s",
                            notification_type, agent_id)
                return True
            logger.warning("Notification service returned %d: %s",
                           resp.status_code, resp.text[:200])
            return False
    except Exception as e:
        logger.error("Failed to send finance notification: %s", e)
        return False


# ── Commission Service Integration ────────────────────────────────────────────

async def pause_commission_payout(agent_id: str, tenant_id: str, loan_id: str) -> bool:
    """
    Notify the Commission Service to hold commission payouts for an overdue agent.
    Commissions are held in escrow until the loan is repaid.
    """
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{COMMISSION_SERVICE_URL}/api/v1/commissions/hold",
                json={
                    "agent_id":  agent_id,
                    "tenant_id": tenant_id,
                    "reason":    "overdue_loan",
                    "reference": loan_id,
                    "source":    "agent-embedded-finance",
                },
                headers=_HEADERS,
            )
            if resp.status_code in (200, 201, 204):
                logger.info("Commission payout held for agent=%s loan=%s", agent_id, loan_id)
                return True
            return False
    except Exception as e:
        logger.error("Failed to hold commission payout: %s", e)
        return False


async def resume_commission_payout(agent_id: str, tenant_id: str, loan_id: str) -> bool:
    """Resume commission payouts after loan is fully repaid."""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{COMMISSION_SERVICE_URL}/api/v1/commissions/release-hold",
                json={
                    "agent_id":  agent_id,
                    "tenant_id": tenant_id,
                    "reference": loan_id,
                    "source":    "agent-embedded-finance",
                },
                headers=_HEADERS,
            )
            return resp.status_code in (200, 201, 204)
    except Exception as e:
        logger.error("Failed to release commission hold: %s", e)
        return False


# ── Agent Scorecard Integration ───────────────────────────────────────────────

async def trigger_scorecard_recompute(agent_id: str, tenant_id: str,
                                       reason: str = "finance_event") -> bool:
    """
    Trigger an asynchronous scorecard recomputation after a significant finance event
    (loan disbursed, loan repaid, loan defaulted).
    """
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(
                f"{AGENT_SCORECARD_URL}/api/v1/scorecard/trigger-recompute",
                json={
                    "agent_id":  agent_id,
                    "tenant_id": tenant_id,
                    "reason":    reason,
                    "source":    "agent-embedded-finance",
                },
                headers=_HEADERS,
            )
            return resp.status_code in (200, 201, 202, 204)
    except Exception as e:
        logger.warning("Could not trigger scorecard recompute for agent=%s: %s", agent_id, e)
        return False


# ── Composite Post-Disbursement Handler ───────────────────────────────────────

async def post_loan_disbursed_integrations(
    agent_id: str,
    tenant_id: str,
    loan: Dict[str, Any],
) -> Dict[str, bool]:
    """Run all integrations after a loan is disbursed."""
    results: Dict[str, bool] = {}

    # 1. Notify agent
    results["notification"] = await send_finance_notification(
        agent_id=agent_id,
        tenant_id=tenant_id,
        notification_type="loan_disbursed",
        data={
            "amount":         loan.get("principal_amount", 0),
            "total_repayable": loan.get("total_repayable", 0),
            "due_date":       str(loan.get("due_date", "")),
            "loan_id":        str(loan.get("loan_id", "")),
        },
    )

    # 2. Write to Lakehouse
    try:
        from ..middleware.lakehouse.pipeline import get_finance_lakehouse_client
        lh = get_finance_lakehouse_client()
        results["lakehouse"] = lh.write_bronze_event(
            event_id=str(loan.get("loan_id", "")),
            event_type="loan_disbursed",
            agent_id=agent_id,
            tenant_id=tenant_id,
            payload=loan,
        )
    except Exception as e:
        logger.error("Lakehouse write failed post-disbursement: %s", e)
        results["lakehouse"] = False

    # 3. Trigger scorecard recompute (async, non-blocking)
    results["scorecard_recompute"] = await trigger_scorecard_recompute(
        agent_id, tenant_id, reason="loan_disbursed"
    )

    logger.info("Post-disbursement integrations for agent=%s: %s", agent_id, results)
    return results


async def post_loan_repaid_integrations(
    agent_id: str,
    tenant_id: str,
    loan: Dict[str, Any],
) -> Dict[str, bool]:
    """Run all integrations after a loan is fully repaid."""
    results: Dict[str, bool] = {}

    # 1. Notify agent
    results["notification"] = await send_finance_notification(
        agent_id=agent_id,
        tenant_id=tenant_id,
        notification_type="repayment_received",
        data={
            "amount":      loan.get("amount_repaid", 0),
            "outstanding": loan.get("outstanding_balance", 0),
            "loan_id":     str(loan.get("loan_id", "")),
        },
    )

    # 2. Release commission hold if loan is fully repaid
    if float(loan.get("outstanding_balance", 1)) <= 0:
        results["commission_hold_released"] = await resume_commission_payout(
            agent_id, tenant_id, str(loan.get("loan_id", ""))
        )

    # 3. Trigger scorecard recompute
    results["scorecard_recompute"] = await trigger_scorecard_recompute(
        agent_id, tenant_id, reason="loan_repaid"
    )

    logger.info("Post-repayment integrations for agent=%s: %s", agent_id, results)
    return results
