"""
Workflow Definitions for 30 User Stories
Temporal.io-based workflow orchestration
"""

from temporalio import workflow, activity
from temporalio.common import RetryPolicy
from datetime import timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

# ============================================================================
# Workflow Data Classes
# ============================================================================

@dataclass
class AgentOnboardingInput:
    """Input for agent onboarding workflow"""
    agent_id: str
    personal_info: Dict[str, Any]
    kyc_documents: List[str]
    biometric_data: Dict[str, Any]
    referral_code: Optional[str] = None

@dataclass
class TransactionInput:
    """Input for transaction workflows"""
    transaction_id: str
    agent_id: str
    customer_id: str
    transaction_type: str
    amount: float
    currency: str = "NGN"
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class LoanApplicationInput:
    """Input for loan application workflow"""
    loan_id: str
    customer_id: str
    amount: float
    term_months: int
    purpose: str
    employment_info: Dict[str, Any]

@dataclass
class DisputeResolutionInput:
    """Input for dispute resolution workflow"""
    dispute_id: str
    transaction_id: str
    customer_id: str
    dispute_type: str
    description: str
    evidence: List[str]

# ============================================================================
# Story 1: Agent Registration & KYC Verification
# ============================================================================

@workflow.defn
class AgentOnboardingWorkflow:
    """
    Workflow for agent registration and KYC verification
    User Story 1: Agent Registration & KYC Verification
    """
    
    @workflow.run
    async def run(self, input: AgentOnboardingInput) -> Dict[str, Any]:
        """Execute agent onboarding workflow"""
        
        # Step 1: Validate personal information
        validation_result = await workflow.execute_activity(
            validate_personal_info,
            input.personal_info,
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        if not validation_result["valid"]:
            return {"status": "rejected", "reason": "Invalid personal information"}
        
        # Step 2: Upload and validate KYC documents
        doc_validation = await workflow.execute_activity(
            validate_kyc_documents,
            input.kyc_documents,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )
        
        if not doc_validation["valid"]:
            return {"status": "rejected", "reason": "Invalid KYC documents"}
        
        # Step 3: AI document validation
        ai_validation = await workflow.execute_activity(
            ai_document_validation,
            {
                "agent_id": input.agent_id,
                "documents": input.kyc_documents
            },
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )
        
        # Step 4: Biometric registration
        biometric_result = await workflow.execute_activity(
            register_biometric,
            {
                "agent_id": input.agent_id,
                "biometric_data": input.biometric_data
            },
            start_to_close_timeout=timedelta(minutes=2)
        )
        
        # Step 5: Background check
        background_check = await workflow.execute_activity(
            perform_background_check,
            input.agent_id,
            start_to_close_timeout=timedelta(hours=24),
            retry_policy=RetryPolicy(maximum_attempts=1)
        )
        
        # Step 6: Manual review (if needed)
        if ai_validation["confidence"] < 0.9 or background_check["risk_score"] > 0.5:
            # Wait for manual review
            await workflow.wait_condition(
                lambda: workflow.get_signal("manual_review_completed"),
                timeout=timedelta(days=3)
            )
            
            manual_review = workflow.get_signal_value("manual_review_result")
            if not manual_review["approved"]:
                return {"status": "rejected", "reason": manual_review["reason"]}
        
        # Step 7: Create agent account
        account_result = await workflow.execute_activity(
            create_agent_account,
            {
                "agent_id": input.agent_id,
                "personal_info": input.personal_info,
                "kyc_status": "verified"
            },
            start_to_close_timeout=timedelta(minutes=1)
        )
        
        # Step 8: Assign to hierarchy (if referral code provided)
        if input.referral_code:
            await workflow.execute_activity(
                assign_to_hierarchy,
                {
                    "agent_id": input.agent_id,
                    "referral_code": input.referral_code
                },
                start_to_close_timeout=timedelta(seconds=30)
            )
        
        # Step 9: Enroll in training
        training_result = await workflow.execute_activity(
            enroll_in_training,
            input.agent_id,
            start_to_close_timeout=timedelta(minutes=1)
        )
        
        # Step 10: Send approval notification
        await workflow.execute_activity(
            send_notification,
            {
                "recipient_id": input.agent_id,
                "type": "agent_approved",
                "channels": ["sms", "email", "push"]
            },
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        # Step 11: Activate account
        await workflow.execute_activity(
            activate_agent_account,
            input.agent_id,
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        return {
            "status": "approved",
            "agent_id": input.agent_id,
            "account_id": account_result["account_id"],
            "training_id": training_result["training_id"]
        }

# ============================================================================
# Story 2: Agent Cash-In Transaction
# ============================================================================

@workflow.defn
class CashInWorkflow:
    """
    Workflow for cash-in transactions
    User Story 2: Agent Cash-In Transaction
    """
    
    @workflow.run
    async def run(self, input: TransactionInput) -> Dict[str, Any]:
        """Execute cash-in workflow"""
        
        # Step 1: Validate customer account
        customer_validation = await workflow.execute_activity(
            validate_customer_account,
            input.customer_id,
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        if not customer_validation["valid"]:
            return {"status": "failed", "reason": "Invalid customer account"}
        
        # Step 2: Check transaction limits
        limit_check = await workflow.execute_activity(
            check_transaction_limits,
            {
                "customer_id": input.customer_id,
                "amount": input.amount,
                "transaction_type": "cash_in"
            },
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        if not limit_check["within_limits"]:
            return {"status": "failed", "reason": "Transaction exceeds limits"}
        
        # Step 3: Validate agent float
        float_validation = await workflow.execute_activity(
            validate_agent_float,
            {
                "agent_id": input.agent_id,
                "amount": input.amount
            },
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        if not float_validation["sufficient"]:
            return {"status": "failed", "reason": "Insufficient agent float"}
        
        # Step 4: Fraud detection check
        fraud_check = await workflow.execute_activity(
            check_fraud,
            {
                "transaction_id": input.transaction_id,
                "agent_id": input.agent_id,
                "customer_id": input.customer_id,
                "amount": input.amount,
                "type": "cash_in"
            },
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )
        
        if fraud_check["risk_score"] > 0.8:
            return {"status": "blocked", "reason": "High fraud risk"}
        
        # Step 5: Request customer PIN authorization
        pin_verification = await workflow.execute_activity(
            verify_customer_pin,
            {
                "customer_id": input.customer_id,
                "transaction_id": input.transaction_id
            },
            start_to_close_timeout=timedelta(minutes=2)
        )
        
        if not pin_verification["verified"]:
            return {"status": "failed", "reason": "PIN verification failed"}
        
        # Step 6: Process transaction in ledger (TigerBeetle)
        ledger_result = await workflow.execute_activity(
            process_ledger_transaction,
            {
                "transaction_id": input.transaction_id,
                "debit_account": input.agent_id,
                "credit_account": input.customer_id,
                "amount": input.amount,
                "currency": input.currency
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                backoff_coefficient=2.0
            )
        )
        
        if not ledger_result["success"]:
            return {"status": "failed", "reason": "Ledger processing failed"}
        
        # Step 7: Calculate and credit commission
        commission_result = await workflow.execute_activity(
            calculate_and_credit_commission,
            {
                "agent_id": input.agent_id,
                "transaction_id": input.transaction_id,
                "amount": input.amount,
                "transaction_type": "cash_in"
            },
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        # Step 8: Generate receipt
        receipt = await workflow.execute_activity(
            generate_receipt,
            {
                "transaction_id": input.transaction_id,
                "agent_id": input.agent_id,
                "customer_id": input.customer_id,
                "amount": input.amount,
                "type": "cash_in"
            },
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        # Step 9: Send notifications
        await workflow.execute_activity(
            send_transaction_notifications,
            {
                "transaction_id": input.transaction_id,
                "agent_id": input.agent_id,
                "customer_id": input.customer_id,
                "amount": input.amount,
                "type": "cash_in",
                "receipt_url": receipt["url"]
            },
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        # Step 10: Update analytics
        await workflow.execute_activity(
            update_transaction_analytics,
            {
                "transaction_id": input.transaction_id,
                "agent_id": input.agent_id,
                "customer_id": input.customer_id,
                "amount": input.amount,
                "type": "cash_in"
            },
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        return {
            "status": "completed",
            "transaction_id": input.transaction_id,
            "ledger_id": ledger_result["ledger_id"],
            "commission": commission_result["amount"],
            "receipt_url": receipt["url"]
        }

# ============================================================================
# Story 3: Agent Cash-Out Transaction
# ============================================================================

@workflow.defn
class CashOutWorkflow:
    """
    Workflow for cash-out transactions
    User Story 3: Agent Cash-Out Transaction
    """
    
    @workflow.run
    async def run(self, input: TransactionInput) -> Dict[str, Any]:
        """Execute cash-out workflow"""
        
        # Step 1: Validate customer account and balance
        customer_validation = await workflow.execute_activity(
            validate_customer_balance,
            {
                "customer_id": input.customer_id,
                "amount": input.amount
            },
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        if not customer_validation["sufficient"]:
            return {"status": "failed", "reason": "Insufficient customer balance"}
        
        # Step 2: Check transaction limits
        limit_check = await workflow.execute_activity(
            check_transaction_limits,
            {
                "customer_id": input.customer_id,
                "amount": input.amount,
                "transaction_type": "cash_out"
            },
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        if not limit_check["within_limits"]:
            return {"status": "failed", "reason": "Transaction exceeds limits"}
        
        # Step 3: Validate agent has sufficient cash
        agent_cash_check = await workflow.execute_activity(
            check_agent_cash_availability,
            {
                "agent_id": input.agent_id,
                "amount": input.amount
            },
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        if not agent_cash_check["available"]:
            return {"status": "failed", "reason": "Agent has insufficient cash"}
        
        # Step 4: Fraud detection
        fraud_check = await workflow.execute_activity(
            check_fraud,
            {
                "transaction_id": input.transaction_id,
                "agent_id": input.agent_id,
                "customer_id": input.customer_id,
                "amount": input.amount,
                "type": "cash_out"
            },
            start_to_close_timeout=timedelta(seconds=5)
        )
        
        if fraud_check["risk_score"] > 0.8:
            return {"status": "blocked", "reason": "High fraud risk"}
        
        # Step 5: Customer PIN verification
        pin_verification = await workflow.execute_activity(
            verify_customer_pin,
            {
                "customer_id": input.customer_id,
                "transaction_id": input.transaction_id
            },
            start_to_close_timeout=timedelta(minutes=2)
        )
        
        if not pin_verification["verified"]:
            return {"status": "failed", "reason": "PIN verification failed"}
        
        # Step 6: Process ledger transaction
        ledger_result = await workflow.execute_activity(
            process_ledger_transaction,
            {
                "transaction_id": input.transaction_id,
                "debit_account": input.customer_id,
                "credit_account": input.agent_id,
                "amount": input.amount,
                "currency": input.currency
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        if not ledger_result["success"]:
            return {"status": "failed", "reason": "Ledger processing failed"}
        
        # Step 7: Track cash disbursement
        await workflow.execute_activity(
            track_cash_disbursement,
            {
                "agent_id": input.agent_id,
                "transaction_id": input.transaction_id,
                "amount": input.amount
            },
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        # Step 8: Calculate and credit commission
        commission_result = await workflow.execute_activity(
            calculate_and_credit_commission,
            {
                "agent_id": input.agent_id,
                "transaction_id": input.transaction_id,
                "amount": input.amount,
                "transaction_type": "cash_out"
            },
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        # Step 9: Generate receipt
        receipt = await workflow.execute_activity(
            generate_receipt,
            {
                "transaction_id": input.transaction_id,
                "agent_id": input.agent_id,
                "customer_id": input.customer_id,
                "amount": input.amount,
                "type": "cash_out"
            },
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        # Step 10: Send notifications
        await workflow.execute_activity(
            send_transaction_notifications,
            {
                "transaction_id": input.transaction_id,
                "agent_id": input.agent_id,
                "customer_id": input.customer_id,
                "amount": input.amount,
                "type": "cash_out",
                "receipt_url": receipt["url"]
            },
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        return {
            "status": "completed",
            "transaction_id": input.transaction_id,
            "ledger_id": ledger_result["ledger_id"],
            "commission": commission_result["amount"],
            "receipt_url": receipt["url"]
        }

# ============================================================================
# Story 8: Loan Application & Approval
# ============================================================================

@workflow.defn
class LoanApplicationWorkflow:
    """
    Workflow for loan application and approval
    User Story 8: Loan Application & Approval
    """
    
    @workflow.run
    async def run(self, input: LoanApplicationInput) -> Dict[str, Any]:
        """Execute loan application workflow"""
        
        # Step 1: Check loan eligibility
        eligibility = await workflow.execute_activity(
            check_loan_eligibility,
            {
                "customer_id": input.customer_id,
                "amount": input.amount,
                "term_months": input.term_months
            },
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        if not eligibility["eligible"]:
            return {
                "status": "rejected",
                "reason": eligibility["reason"],
                "loan_id": input.loan_id
            }
        
        # Step 2: Perform credit scoring
        credit_score = await workflow.execute_activity(
            perform_credit_scoring,
            input.customer_id,
            start_to_close_timeout=timedelta(minutes=2)
        )
        
        # Step 3: Fraud detection check
        fraud_check = await workflow.execute_activity(
            check_loan_fraud,
            {
                "loan_id": input.loan_id,
                "customer_id": input.customer_id,
                "amount": input.amount,
                "employment_info": input.employment_info
            },
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        if fraud_check["risk_score"] > 0.7:
            return {
                "status": "rejected",
                "reason": "High fraud risk",
                "loan_id": input.loan_id
            }
        
        # Step 4: Calculate interest and repayment schedule
        repayment_schedule = await workflow.execute_activity(
            calculate_repayment_schedule,
            {
                "loan_id": input.loan_id,
                "principal": input.amount,
                "term_months": input.term_months,
                "credit_score": credit_score["score"]
            },
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        # Step 5: Auto-approve or manual review
        if credit_score["score"] >= 700 and input.amount <= eligibility["max_amount"]:
            # Auto-approve
            approval_result = {
                "approved": True,
                "method": "auto",
                "interest_rate": repayment_schedule["interest_rate"]
            }
        else:
            # Manual review required
            await workflow.wait_condition(
                lambda: workflow.get_signal("loan_review_completed"),
                timeout=timedelta(days=2)
            )
            
            approval_result = workflow.get_signal_value("loan_review_result")
            
            if not approval_result["approved"]:
                return {
                    "status": "rejected",
                    "reason": approval_result["reason"],
                    "loan_id": input.loan_id
                }
        
        # Step 6: Create loan record
        loan_record = await workflow.execute_activity(
            create_loan_record,
            {
                "loan_id": input.loan_id,
                "customer_id": input.customer_id,
                "amount": input.amount,
                "term_months": input.term_months,
                "interest_rate": approval_result["interest_rate"],
                "repayment_schedule": repayment_schedule["schedule"]
            },
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        # Step 7: Disburse loan
        disbursement = await workflow.execute_activity(
            disburse_loan,
            {
                "loan_id": input.loan_id,
                "customer_id": input.customer_id,
                "amount": input.amount
            },
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        # Step 8: Send approval notification
        await workflow.execute_activity(
            send_notification,
            {
                "recipient_id": input.customer_id,
                "type": "loan_approved",
                "data": {
                    "loan_id": input.loan_id,
                    "amount": input.amount,
                    "interest_rate": approval_result["interest_rate"],
                    "first_payment_date": repayment_schedule["first_payment_date"]
                },
                "channels": ["sms", "email", "push"]
            },
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        # Step 9: Schedule repayment collections
        await workflow.execute_activity(
            schedule_loan_collections,
            {
                "loan_id": input.loan_id,
                "repayment_schedule": repayment_schedule["schedule"]
            },
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        return {
            "status": "approved",
            "loan_id": input.loan_id,
            "amount": input.amount,
            "interest_rate": approval_result["interest_rate"],
            "monthly_payment": repayment_schedule["monthly_payment"],
            "total_repayment": repayment_schedule["total_repayment"],
            "disbursement_id": disbursement["disbursement_id"]
        }

# ============================================================================
# Story 12: Transaction Dispute Resolution
# ============================================================================

@workflow.defn
class DisputeResolutionWorkflow:
    """
    Workflow for transaction dispute resolution
    User Story 12: Transaction Dispute Resolution
    """
    
    @workflow.run
    async def run(self, input: DisputeResolutionInput) -> Dict[str, Any]:
        """Execute dispute resolution workflow"""
        
        # Step 1: Create dispute ticket
        dispute_ticket = await workflow.execute_activity(
            create_dispute_ticket,
            {
                "dispute_id": input.dispute_id,
                "transaction_id": input.transaction_id,
                "customer_id": input.customer_id,
                "dispute_type": input.dispute_type,
                "description": input.description
            },
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        # Step 2: Upload evidence
        if input.evidence:
            await workflow.execute_activity(
                upload_dispute_evidence,
                {
                    "dispute_id": input.dispute_id,
                    "evidence_files": input.evidence
                },
                start_to_close_timeout=timedelta(minutes=5)
            )
        
        # Step 3: Retrieve transaction details
        transaction_details = await workflow.execute_activity(
            get_transaction_details,
            input.transaction_id,
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        # Step 4: Notify support team
        await workflow.execute_activity(
            notify_support_team,
            {
                "dispute_id": input.dispute_id,
                "priority": "high" if input.dispute_type == "unauthorized" else "normal"
            },
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        # Step 5: Investigate transaction in ledger
        ledger_investigation = await workflow.execute_activity(
            investigate_ledger_transaction,
            input.transaction_id,
            start_to_close_timeout=timedelta(minutes=5)
        )
        
        # Step 6: Wait for support agent resolution
        await workflow.wait_condition(
            lambda: workflow.get_signal("dispute_resolved"),
            timeout=timedelta(days=7)
        )
        
        resolution = workflow.get_signal_value("dispute_resolution")
        
        # Step 7: Process refund if approved
        if resolution["refund_approved"]:
            refund_result = await workflow.execute_activity(
                process_refund,
                {
                    "dispute_id": input.dispute_id,
                    "transaction_id": input.transaction_id,
                    "customer_id": input.customer_id,
                    "amount": resolution["refund_amount"]
                },
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(maximum_attempts=3)
            )
        else:
            refund_result = None
        
        # Step 8: Update dispute status
        await workflow.execute_activity(
            update_dispute_status,
            {
                "dispute_id": input.dispute_id,
                "status": "resolved",
                "resolution": resolution["resolution"],
                "refund_id": refund_result["refund_id"] if refund_result else None
            },
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        # Step 9: Send resolution notification
        await workflow.execute_activity(
            send_notification,
            {
                "recipient_id": input.customer_id,
                "type": "dispute_resolved",
                "data": {
                    "dispute_id": input.dispute_id,
                    "resolution": resolution["resolution"],
                    "refund_amount": resolution.get("refund_amount", 0)
                },
                "channels": ["sms", "email", "push"]
            },
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        return {
            "status": "resolved",
            "dispute_id": input.dispute_id,
            "resolution": resolution["resolution"],
            "refund_processed": refund_result is not None,
            "refund_amount": resolution.get("refund_amount", 0)
        }

# ============================================================================
# Additional Workflow Definitions (Stories 4-30)
# ============================================================================

# Note: For brevity, I'm including workflow class definitions for the remaining stories.
# Each would follow the same pattern with specific activities for that user journey.

@workflow.defn
class P2PTransferWorkflow:
    """Story 4: Customer-to-Customer Money Transfer"""
    
    @workflow.run
    async def run(self, input: TransactionInput) -> Dict[str, Any]:
        """Execute P2P transfer workflow"""
        
        # Step 1: Validate sender account and balance
        sender_validation = await workflow.execute_activity(
            validate_customer_balance,
            {"customer_id": input.customer_id, "amount": input.amount},
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        if not sender_validation["sufficient"]:
            return {"status": "failed", "reason": "Insufficient balance"}
        
        # Step 2: Validate recipient account
        recipient_id = input.metadata.get("recipient_id") if input.metadata else None
        if not recipient_id:
            return {"status": "failed", "reason": "Recipient not specified"}
        
        recipient_validation = await workflow.execute_activity(
            validate_customer_account,
            recipient_id,
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        if not recipient_validation["valid"]:
            return {"status": "failed", "reason": "Invalid recipient account"}
        
        # Step 3: Check transaction limits
        limit_check = await workflow.execute_activity(
            check_transaction_limits,
            {"customer_id": input.customer_id, "amount": input.amount, "transaction_type": "p2p_transfer"},
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        if not limit_check["within_limits"]:
            return {"status": "failed", "reason": "Transaction exceeds limits"}
        
        # Step 4: Fraud detection
        fraud_check = await workflow.execute_activity(
            check_fraud,
            {"transaction_id": input.transaction_id, "agent_id": input.agent_id, "customer_id": input.customer_id, "amount": input.amount, "type": "p2p_transfer"},
            start_to_close_timeout=timedelta(seconds=5)
        )
        
        if fraud_check["risk_score"] > 0.8:
            return {"status": "blocked", "reason": "High fraud risk"}
        
        # Step 5: PIN verification
        pin_verification = await workflow.execute_activity(
            verify_customer_pin,
            {"customer_id": input.customer_id, "transaction_id": input.transaction_id},
            start_to_close_timeout=timedelta(minutes=2)
        )
        
        if not pin_verification["verified"]:
            return {"status": "failed", "reason": "PIN verification failed"}
        
        # Step 6: Process ledger transaction
        ledger_result = await workflow.execute_activity(
            process_ledger_transaction,
            {"transaction_id": input.transaction_id, "debit_account": input.customer_id, "credit_account": recipient_id, "amount": input.amount, "currency": input.currency},
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        if not ledger_result["success"]:
            return {"status": "failed", "reason": "Ledger processing failed"}
        
        # Step 7: Generate receipt and send notifications
        receipt = await workflow.execute_activity(
            generate_receipt,
            {"transaction_id": input.transaction_id, "agent_id": input.agent_id, "customer_id": input.customer_id, "amount": input.amount, "type": "p2p_transfer"},
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        await workflow.execute_activity(
            send_transaction_notifications,
            {"transaction_id": input.transaction_id, "agent_id": input.agent_id, "customer_id": input.customer_id, "amount": input.amount, "type": "p2p_transfer", "receipt_url": receipt.get("url")},
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        return {"status": "completed", "transaction_id": input.transaction_id, "ledger_id": ledger_result.get("ledger_id"), "receipt_url": receipt.get("url")}

@workflow.defn
class BillPaymentWorkflow:
    """Story 5: Bill Payment"""
    
    @workflow.run
    async def run(self, input: TransactionInput) -> Dict[str, Any]:
        """Execute bill payment workflow"""
        
        # Step 1: Validate customer balance
        balance_check = await workflow.execute_activity(
            validate_customer_balance,
            {"customer_id": input.customer_id, "amount": input.amount},
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        if not balance_check["sufficient"]:
            return {"status": "failed", "reason": "Insufficient balance"}
        
        # Step 2: Check transaction limits
        limit_check = await workflow.execute_activity(
            check_transaction_limits,
            {"customer_id": input.customer_id, "amount": input.amount, "transaction_type": "bill_payment"},
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        if not limit_check["within_limits"]:
            return {"status": "failed", "reason": "Transaction exceeds limits"}
        
        # Step 3: PIN verification
        pin_verification = await workflow.execute_activity(
            verify_customer_pin,
            {"customer_id": input.customer_id, "transaction_id": input.transaction_id},
            start_to_close_timeout=timedelta(minutes=2)
        )
        
        if not pin_verification["verified"]:
            return {"status": "failed", "reason": "PIN verification failed"}
        
        # Step 4: Process ledger transaction
        biller_id = input.metadata.get("biller_id") if input.metadata else "biller_account"
        ledger_result = await workflow.execute_activity(
            process_ledger_transaction,
            {"transaction_id": input.transaction_id, "debit_account": input.customer_id, "credit_account": biller_id, "amount": input.amount, "currency": input.currency},
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        if not ledger_result["success"]:
            return {"status": "failed", "reason": "Ledger processing failed"}
        
        # Step 5: Calculate commission for agent
        commission_result = await workflow.execute_activity(
            calculate_and_credit_commission,
            {"agent_id": input.agent_id, "transaction_id": input.transaction_id, "amount": input.amount, "transaction_type": "bill_payment"},
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        # Step 6: Generate receipt and send notifications
        receipt = await workflow.execute_activity(
            generate_receipt,
            {"transaction_id": input.transaction_id, "agent_id": input.agent_id, "customer_id": input.customer_id, "amount": input.amount, "type": "bill_payment"},
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        await workflow.execute_activity(
            send_transaction_notifications,
            {"transaction_id": input.transaction_id, "agent_id": input.agent_id, "customer_id": input.customer_id, "amount": input.amount, "type": "bill_payment", "receipt_url": receipt.get("url")},
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        return {"status": "completed", "transaction_id": input.transaction_id, "ledger_id": ledger_result.get("ledger_id"), "commission": commission_result.get("amount"), "receipt_url": receipt.get("url")}

@workflow.defn
class AirtimeDataPurchaseWorkflow:
    """Story 6: Airtime & Data Purchase"""
    
    @workflow.run
    async def run(self, input: TransactionInput) -> Dict[str, Any]:
        """Execute airtime/data purchase workflow"""
        
        # Step 1: Validate customer balance
        balance_check = await workflow.execute_activity(
            validate_customer_balance,
            {"customer_id": input.customer_id, "amount": input.amount},
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        if not balance_check["sufficient"]:
            return {"status": "failed", "reason": "Insufficient balance"}
        
        # Step 2: PIN verification
        pin_verification = await workflow.execute_activity(
            verify_customer_pin,
            {"customer_id": input.customer_id, "transaction_id": input.transaction_id},
            start_to_close_timeout=timedelta(minutes=2)
        )
        
        if not pin_verification["verified"]:
            return {"status": "failed", "reason": "PIN verification failed"}
        
        # Step 3: Process ledger transaction
        telco_id = input.metadata.get("telco_id") if input.metadata else "telco_account"
        ledger_result = await workflow.execute_activity(
            process_ledger_transaction,
            {"transaction_id": input.transaction_id, "debit_account": input.customer_id, "credit_account": telco_id, "amount": input.amount, "currency": input.currency},
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        if not ledger_result["success"]:
            return {"status": "failed", "reason": "Ledger processing failed"}
        
        # Step 4: Calculate commission
        commission_result = await workflow.execute_activity(
            calculate_and_credit_commission,
            {"agent_id": input.agent_id, "transaction_id": input.transaction_id, "amount": input.amount, "transaction_type": "airtime_data"},
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        # Step 5: Generate receipt and send notifications
        receipt = await workflow.execute_activity(
            generate_receipt,
            {"transaction_id": input.transaction_id, "agent_id": input.agent_id, "customer_id": input.customer_id, "amount": input.amount, "type": "airtime_data"},
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        await workflow.execute_activity(
            send_transaction_notifications,
            {"transaction_id": input.transaction_id, "agent_id": input.agent_id, "customer_id": input.customer_id, "amount": input.amount, "type": "airtime_data", "receipt_url": receipt.get("url")},
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        return {"status": "completed", "transaction_id": input.transaction_id, "ledger_id": ledger_result.get("ledger_id"), "commission": commission_result.get("amount"), "receipt_url": receipt.get("url")}

@workflow.defn
class QRPaymentWorkflow:
    """Story 7: QR Code Payment (Merchant)"""
    
    @workflow.run
    async def run(self, input: TransactionInput) -> Dict[str, Any]:
        """Execute QR payment workflow"""
        
        # Step 1: Validate customer balance
        balance_check = await workflow.execute_activity(
            validate_customer_balance,
            {"customer_id": input.customer_id, "amount": input.amount},
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        if not balance_check["sufficient"]:
            return {"status": "failed", "reason": "Insufficient balance"}
        
        # Step 2: Fraud detection
        fraud_check = await workflow.execute_activity(
            check_fraud,
            {"transaction_id": input.transaction_id, "agent_id": input.agent_id, "customer_id": input.customer_id, "amount": input.amount, "type": "qr_payment"},
            start_to_close_timeout=timedelta(seconds=5)
        )
        
        if fraud_check["risk_score"] > 0.8:
            return {"status": "blocked", "reason": "High fraud risk"}
        
        # Step 3: PIN verification
        pin_verification = await workflow.execute_activity(
            verify_customer_pin,
            {"customer_id": input.customer_id, "transaction_id": input.transaction_id},
            start_to_close_timeout=timedelta(minutes=2)
        )
        
        if not pin_verification["verified"]:
            return {"status": "failed", "reason": "PIN verification failed"}
        
        # Step 4: Process ledger transaction
        merchant_id = input.metadata.get("merchant_id") if input.metadata else input.agent_id
        ledger_result = await workflow.execute_activity(
            process_ledger_transaction,
            {"transaction_id": input.transaction_id, "debit_account": input.customer_id, "credit_account": merchant_id, "amount": input.amount, "currency": input.currency},
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        if not ledger_result["success"]:
            return {"status": "failed", "reason": "Ledger processing failed"}
        
        # Step 5: Generate receipt and send notifications
        receipt = await workflow.execute_activity(
            generate_receipt,
            {"transaction_id": input.transaction_id, "agent_id": input.agent_id, "customer_id": input.customer_id, "amount": input.amount, "type": "qr_payment"},
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        await workflow.execute_activity(
            send_transaction_notifications,
            {"transaction_id": input.transaction_id, "agent_id": input.agent_id, "customer_id": input.customer_id, "amount": input.amount, "type": "qr_payment", "receipt_url": receipt.get("url")},
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        return {"status": "completed", "transaction_id": input.transaction_id, "ledger_id": ledger_result.get("ledger_id"), "receipt_url": receipt.get("url")}

@workflow.defn
class CommissionTrackingWorkflow:
    """Story 9: Commission Earning & Tracking"""
    
    @workflow.run
    async def run(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute commission tracking workflow"""
        agent_id = input.get("agent_id")
        period = input.get("period", "daily")
        
        # Step 1: Calculate commissions for the period
        commission_result = await workflow.execute_activity(
            calculate_and_credit_commission,
            {"agent_id": agent_id, "period": period, "transaction_type": "commission_summary"},
            start_to_close_timeout=timedelta(minutes=5)
        )
        
        # Step 2: Update analytics
        await workflow.execute_activity(
            update_transaction_analytics,
            {"agent_id": agent_id, "type": "commission_tracking", "period": period, "amount": commission_result.get("total", 0)},
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        # Step 3: Send notification
        await workflow.execute_activity(
            send_notification,
            {"recipient_id": agent_id, "type": "commission_summary", "channels": ["push", "email"], "data": commission_result},
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        return {"status": "completed", "agent_id": agent_id, "commission_summary": commission_result}

@workflow.defn
class AgentHierarchyWorkflow:
    """Story 10: Agent Hierarchy & Downline Management"""
    
    @workflow.run
    async def run(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute agent hierarchy workflow"""
        agent_id = input.get("agent_id")
        action = input.get("action", "view")
        
        if action == "assign":
            # Assign agent to hierarchy
            result = await workflow.execute_activity(
                assign_to_hierarchy,
                {"agent_id": agent_id, "parent_id": input.get("parent_id"), "tier": input.get("tier")},
                start_to_close_timeout=timedelta(seconds=30)
            )
            return {"status": "completed", "action": "assign", "result": result}
        
        # Default: return hierarchy info
        return {"status": "completed", "action": action, "agent_id": agent_id}

@workflow.defn
class SavingsAccountWorkflow:
    """Story 11: Savings Account Creation"""
    
    @workflow.run
    async def run(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute savings account workflow"""
        customer_id = input.get("customer_id")
        
        # Step 1: Validate customer
        customer_validation = await workflow.execute_activity(
            validate_customer_account,
            customer_id,
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        if not customer_validation["valid"]:
            return {"status": "failed", "reason": "Invalid customer account"}
        
        # Step 2: Create savings account
        account_result = await workflow.execute_activity(
            create_agent_account,
            {"agent_id": customer_id, "account_type": "savings", "name": input.get("name"), "phone": input.get("phone"), "email": input.get("email")},
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        # Step 3: Send notification
        await workflow.execute_activity(
            send_notification,
            {"recipient_id": customer_id, "type": "savings_account_created", "channels": ["sms", "email"]},
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        return {"status": "completed", "customer_id": customer_id, "account_id": account_result.get("account_id")}

@workflow.defn
class MultiCurrencyWorkflow:
    """Story 13: Multi-Currency Wallet"""
    
    @workflow.run
    async def run(self, input: TransactionInput) -> Dict[str, Any]:
        """Execute multi-currency workflow"""
        
        # Step 1: Validate source balance
        balance_check = await workflow.execute_activity(
            validate_customer_balance,
            {"customer_id": input.customer_id, "amount": input.amount},
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        if not balance_check["sufficient"]:
            return {"status": "failed", "reason": "Insufficient balance"}
        
        # Step 2: Process currency conversion in ledger
        target_currency = input.metadata.get("target_currency") if input.metadata else "USD"
        ledger_result = await workflow.execute_activity(
            process_ledger_transaction,
            {"transaction_id": input.transaction_id, "debit_account": f"{input.customer_id}_{input.currency}", "credit_account": f"{input.customer_id}_{target_currency}", "amount": input.amount, "currency": input.currency, "target_currency": target_currency},
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        if not ledger_result["success"]:
            return {"status": "failed", "reason": "Currency conversion failed"}
        
        # Step 3: Generate receipt
        receipt = await workflow.execute_activity(
            generate_receipt,
            {"transaction_id": input.transaction_id, "customer_id": input.customer_id, "amount": input.amount, "type": "currency_conversion"},
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        return {"status": "completed", "transaction_id": input.transaction_id, "ledger_id": ledger_result.get("ledger_id"), "receipt_url": receipt.get("url")}

@workflow.defn
class MerchantDashboardWorkflow:
    """Story 14: Merchant Dashboard & Analytics"""
    
    @workflow.run
    async def run(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute merchant dashboard workflow"""
        merchant_id = input.get("merchant_id")
        
        # Update analytics
        await workflow.execute_activity(
            update_transaction_analytics,
            {"merchant_id": merchant_id, "type": "dashboard_refresh"},
            start_to_close_timeout=timedelta(minutes=2)
        )
        
        return {"status": "completed", "merchant_id": merchant_id}

@workflow.defn
class RecurringPaymentWorkflow:
    """Story 15: Automated Recurring Payments"""
    
    @workflow.run
    async def run(self, input: TransactionInput) -> Dict[str, Any]:
        """Execute recurring payment workflow"""
        
        # Step 1: Validate customer balance
        balance_check = await workflow.execute_activity(
            validate_customer_balance,
            {"customer_id": input.customer_id, "amount": input.amount},
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        if not balance_check["sufficient"]:
            return {"status": "failed", "reason": "Insufficient balance for recurring payment"}
        
        # Step 2: Process ledger transaction
        recipient_id = input.metadata.get("recipient_id") if input.metadata else "recurring_account"
        ledger_result = await workflow.execute_activity(
            process_ledger_transaction,
            {"transaction_id": input.transaction_id, "debit_account": input.customer_id, "credit_account": recipient_id, "amount": input.amount, "currency": input.currency},
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        if not ledger_result["success"]:
            return {"status": "failed", "reason": "Recurring payment processing failed"}
        
        # Step 3: Schedule next payment
        await workflow.execute_activity(
            schedule_loan_collections,
            {"customer_id": input.customer_id, "amount": input.amount, "frequency": input.metadata.get("frequency") if input.metadata else "monthly", "repayment_schedule": []},
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        # Step 4: Send notification
        await workflow.execute_activity(
            send_transaction_notifications,
            {"transaction_id": input.transaction_id, "customer_id": input.customer_id, "amount": input.amount, "type": "recurring_payment"},
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        return {"status": "completed", "transaction_id": input.transaction_id, "ledger_id": ledger_result.get("ledger_id")}

@workflow.defn
class ReferralProgramWorkflow:
    """Story 16: Referral Program"""
    
    @workflow.run
    async def run(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute referral program workflow"""
        referrer_id = input.get("referrer_id")
        referee_id = input.get("referee_id")
        
        # Step 1: Assign referee to referrer's hierarchy
        await workflow.execute_activity(
            assign_to_hierarchy,
            {"agent_id": referee_id, "referral_code": referrer_id},
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        # Step 2: Credit referral bonus
        bonus_amount = input.get("bonus_amount", 1000)
        await workflow.execute_activity(
            calculate_and_credit_commission,
            {"agent_id": referrer_id, "transaction_type": "referral_bonus", "amount": bonus_amount},
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        # Step 3: Send notifications
        await workflow.execute_activity(
            send_notification,
            {"recipient_id": referrer_id, "type": "referral_bonus", "channels": ["push", "sms"]},
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        return {"status": "completed", "referrer_id": referrer_id, "referee_id": referee_id, "bonus_amount": bonus_amount}

@workflow.defn
class LoyaltyPointsWorkflow:
    """Story 17: Loyalty Points & Rewards"""
    
    @workflow.run
    async def run(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute loyalty points workflow"""
        customer_id = input.get("customer_id")
        action = input.get("action", "earn")
        points = input.get("points", 0)
        
        # Update analytics with loyalty points
        await workflow.execute_activity(
            update_transaction_analytics,
            {"customer_id": customer_id, "type": "loyalty_points", "action": action, "points": points},
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        # Send notification
        await workflow.execute_activity(
            send_notification,
            {"recipient_id": customer_id, "type": f"loyalty_points_{action}", "channels": ["push"]},
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        return {"status": "completed", "customer_id": customer_id, "action": action, "points": points}

@workflow.defn
class FloatManagementWorkflow:
    """Story 18: Agent Float Management"""
    
    @workflow.run
    async def run(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute float management workflow"""
        agent_id = input.get("agent_id")
        action = input.get("action", "check")
        amount = input.get("amount", 0)
        
        if action == "topup":
            # Process float top-up
            ledger_result = await workflow.execute_activity(
                process_ledger_transaction,
                {"transaction_id": f"float-{agent_id}-{workflow.now()}", "debit_account": "float_pool", "credit_account": agent_id, "amount": amount, "currency": "NGN"},
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=3)
            )
            
            if not ledger_result["success"]:
                return {"status": "failed", "reason": "Float top-up failed"}
            
            return {"status": "completed", "action": "topup", "agent_id": agent_id, "amount": amount}
        
        # Check float balance
        float_check = await workflow.execute_activity(
            validate_agent_float,
            {"agent_id": agent_id, "amount": 0},
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        return {"status": "completed", "action": "check", "agent_id": agent_id, "float_balance": float_check.get("float_balance")}

@workflow.defn
class TransactionReceiptWorkflow:
    """Story 19: Transaction Receipt & History"""
    
    @workflow.run
    async def run(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute transaction receipt workflow"""
        transaction_id = input.get("transaction_id")
        
        # Get transaction details
        transaction = await workflow.execute_activity(
            get_transaction_details,
            transaction_id,
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        # Generate receipt
        receipt = await workflow.execute_activity(
            generate_receipt,
            {"transaction_id": transaction_id, "amount": transaction.get("amount"), "type": transaction.get("type")},
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        return {"status": "completed", "transaction_id": transaction_id, "receipt_url": receipt.get("url"), "transaction": transaction}

@workflow.defn
class BudgetPlanningWorkflow:
    """Story 20: Budget Planning & Tracking"""
    
    @workflow.run
    async def run(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute budget planning workflow"""
        customer_id = input.get("customer_id")
        
        # Update analytics
        await workflow.execute_activity(
            update_transaction_analytics,
            {"customer_id": customer_id, "type": "budget_planning", "budget": input.get("budget")},
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        return {"status": "completed", "customer_id": customer_id}

@workflow.defn
class RealTimeMonitoringWorkflow:
    """Story 21: Real-Time Transaction Monitoring"""
    
    @workflow.run
    async def run(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute real-time monitoring workflow"""
        
        # Update analytics
        await workflow.execute_activity(
            update_transaction_analytics,
            {"type": "real_time_monitoring", "metrics": input.get("metrics")},
            start_to_close_timeout=timedelta(minutes=1)
        )
        
        return {"status": "completed"}

@workflow.defn
class ComplianceReportingWorkflow:
    """Story 22: Compliance Reporting"""
    
    @workflow.run
    async def run(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute compliance reporting workflow"""
        report_type = input.get("report_type", "daily")
        
        # Update analytics
        await workflow.execute_activity(
            update_transaction_analytics,
            {"type": "compliance_reporting", "report_type": report_type},
            start_to_close_timeout=timedelta(minutes=5)
        )
        
        return {"status": "completed", "report_type": report_type}

@workflow.defn
class AgentPerformanceWorkflow:
    """Story 23: Agent Performance Analytics"""
    
    @workflow.run
    async def run(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute agent performance workflow"""
        agent_id = input.get("agent_id")
        
        # Update analytics
        await workflow.execute_activity(
            update_transaction_analytics,
            {"agent_id": agent_id, "type": "agent_performance"},
            start_to_close_timeout=timedelta(minutes=2)
        )
        
        return {"status": "completed", "agent_id": agent_id}

@workflow.defn
class CustomerSegmentationWorkflow:
    """Story 24: Customer Segmentation & Targeting"""
    
    @workflow.run
    async def run(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute customer segmentation workflow"""
        
        # Update analytics
        await workflow.execute_activity(
            update_transaction_analytics,
            {"type": "customer_segmentation", "criteria": input.get("criteria")},
            start_to_close_timeout=timedelta(minutes=5)
        )
        
        return {"status": "completed"}

@workflow.defn
class FinancialForecastingWorkflow:
    """Story 25: Financial Forecasting & Insights"""
    
    @workflow.run
    async def run(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute financial forecasting workflow"""
        
        # Update analytics
        await workflow.execute_activity(
            update_transaction_analytics,
            {"type": "financial_forecasting", "period": input.get("period")},
            start_to_close_timeout=timedelta(minutes=10)
        )
        
        return {"status": "completed"}

@workflow.defn
class CustomerSupportChatWorkflow:
    """Story 26: Customer Support Chat"""
    
    @workflow.run
    async def run(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute customer support chat workflow"""
        customer_id = input.get("customer_id")
        
        # Notify support team
        await workflow.execute_activity(
            notify_support_team,
            {"customer_id": customer_id, "issue": input.get("issue"), "ticket_id": input.get("ticket_id")},
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        return {"status": "completed", "customer_id": customer_id}

@workflow.defn
class Account2FAWorkflow:
    """Story 27: Account Security & 2FA"""
    
    @workflow.run
    async def run(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute 2FA workflow"""
        customer_id = input.get("customer_id")
        action = input.get("action", "verify")
        
        if action == "verify":
            # Verify PIN/OTP
            verification = await workflow.execute_activity(
                verify_customer_pin,
                {"customer_id": customer_id, "transaction_id": input.get("transaction_id")},
                start_to_close_timeout=timedelta(minutes=2)
            )
            
            return {"status": "completed", "verified": verification.get("verified")}
        
        # Send 2FA notification
        await workflow.execute_activity(
            send_notification,
            {"recipient_id": customer_id, "type": "2fa_code", "channels": ["sms"]},
            start_to_close_timeout=timedelta(seconds=30)
        )
        
        return {"status": "completed", "action": action}

@workflow.defn
class TransactionLimitsWorkflow:
    """Story 28: Transaction Limits Management"""
    
    @workflow.run
    async def run(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute transaction limits workflow"""
        customer_id = input.get("customer_id")
        
        # Check limits
        limits = await workflow.execute_activity(
            check_transaction_limits,
            {"customer_id": customer_id, "amount": 0, "transaction_type": "check"},
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        return {"status": "completed", "customer_id": customer_id, "limits": limits}

@workflow.defn
class OfflineTransactionWorkflow:
    """Story 29: Offline Transaction Mode"""
    
    @workflow.run
    async def run(self, input: TransactionInput) -> Dict[str, Any]:
        """Execute offline transaction workflow - sync offline transactions"""
        
        # Step 1: Validate the offline transaction
        customer_validation = await workflow.execute_activity(
            validate_customer_account,
            input.customer_id,
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        if not customer_validation["valid"]:
            return {"status": "failed", "reason": "Invalid customer account"}
        
        # Step 2: Process ledger transaction
        ledger_result = await workflow.execute_activity(
            process_ledger_transaction,
            {"transaction_id": input.transaction_id, "debit_account": input.customer_id, "credit_account": input.agent_id, "amount": input.amount, "currency": input.currency, "offline": True},
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        if not ledger_result["success"]:
            return {"status": "failed", "reason": "Offline transaction sync failed"}
        
        # Step 3: Generate receipt
        receipt = await workflow.execute_activity(
            generate_receipt,
            {"transaction_id": input.transaction_id, "agent_id": input.agent_id, "customer_id": input.customer_id, "amount": input.amount, "type": "offline_sync"},
            start_to_close_timeout=timedelta(seconds=10)
        )
        
        return {"status": "completed", "transaction_id": input.transaction_id, "ledger_id": ledger_result.get("ledger_id"), "receipt_url": receipt.get("url")}

@workflow.defn
class PlatformHealthMonitoringWorkflow:
    """Story 30: Platform Health Monitoring"""
    
    @workflow.run
    async def run(self, input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute platform health monitoring workflow"""
        
        # Update analytics with health metrics
        await workflow.execute_activity(
            update_transaction_analytics,
            {"type": "platform_health", "metrics": input.get("metrics")},
            start_to_close_timeout=timedelta(minutes=1)
        )
        
        return {"status": "completed"}

# ============================================================================
# Workflow Registry
# ============================================================================

WORKFLOW_REGISTRY = {
    "agent_onboarding": AgentOnboardingWorkflow,
    "cash_in": CashInWorkflow,
    "cash_out": CashOutWorkflow,
    "p2p_transfer": P2PTransferWorkflow,
    "bill_payment": BillPaymentWorkflow,
    "airtime_data": AirtimeDataPurchaseWorkflow,
    "qr_payment": QRPaymentWorkflow,
    "loan_application": LoanApplicationWorkflow,
    "commission_tracking": CommissionTrackingWorkflow,
    "agent_hierarchy": AgentHierarchyWorkflow,
    "savings_account": SavingsAccountWorkflow,
    "dispute_resolution": DisputeResolutionWorkflow,
    "multi_currency": MultiCurrencyWorkflow,
    "merchant_dashboard": MerchantDashboardWorkflow,
    "recurring_payment": RecurringPaymentWorkflow,
    "referral_program": ReferralProgramWorkflow,
    "loyalty_points": LoyaltyPointsWorkflow,
    "float_management": FloatManagementWorkflow,
    "transaction_receipt": TransactionReceiptWorkflow,
    "budget_planning": BudgetPlanningWorkflow,
    "real_time_monitoring": RealTimeMonitoringWorkflow,
    "compliance_reporting": ComplianceReportingWorkflow,
    "agent_performance": AgentPerformanceWorkflow,
    "customer_segmentation": CustomerSegmentationWorkflow,
    "financial_forecasting": FinancialForecastingWorkflow,
    "customer_support": CustomerSupportChatWorkflow,
    "account_2fa": Account2FAWorkflow,
    "transaction_limits": TransactionLimitsWorkflow,
    "offline_transaction": OfflineTransactionWorkflow,
    "platform_health": PlatformHealthMonitoringWorkflow,
}

