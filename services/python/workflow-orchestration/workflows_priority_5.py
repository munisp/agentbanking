"""
Top 5 Priority Workflow Implementations
Based on prioritization analysis - highest business impact workflows
"""

from temporalio import workflow, activity
from temporalio.common import RetryPolicy
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import logging
import uuid
import re
import hashlib
import httpx

logger = logging.getLogger(__name__)

# ============================================================================
# Additional Data Classes for Priority Workflows
# ============================================================================

@dataclass
class P2PTransferInput:
    """Input for P2P transfer workflow"""
    transaction_id: str
    sender_id: str
    recipient_id: str
    amount: float
    currency: str = "NGN"
    note: Optional[str] = None
    agent_id: Optional[str] = None

@dataclass
class BillPaymentInput:
    """Input for bill payment workflow"""
    transaction_id: str
    customer_id: str
    agent_id: str
    biller_id: str
    biller_name: str
    account_number: str
    amount: float
    currency: str = "NGN"
    bill_type: str  # electricity, water, internet, cable_tv, etc.

@dataclass
class AirtimeDataInput:
    """Input for airtime/data purchase workflow"""
    transaction_id: str
    customer_id: str
    agent_id: str
    telco_provider: str  # MTN, Airtel, Glo, 9mobile
    phone_number: str
    product_type: str  # airtime, data
    product_id: Optional[str] = None  # For data bundles
    amount: float
    currency: str = "NGN"

@dataclass
class FloatManagementInput:
    """Input for float management workflow"""
    operation_id: str
    agent_id: str
    operation_type: str  # rebalance, deposit, withdrawal, transfer
    amount: float
    currency: str = "NGN"
    source_agent_id: Optional[str] = None  # For transfers
    target_agent_id: Optional[str] = None  # For transfers
    reason: Optional[str] = None

@dataclass
class SavingsAccountInput:
    """Input for savings account workflow"""
    account_id: str
    customer_id: str
    operation_type: str  # open, deposit, withdraw, close
    amount: Optional[float] = None
    account_type: str = "regular"  # regular, fixed, target
    interest_rate: Optional[float] = None
    term_months: Optional[int] = None
    target_amount: Optional[float] = None
    withdrawal_frequency: Optional[str] = None

# ============================================================================
# PRIORITY 1: P2P Transfer Workflow (Score: 8.25)
# User Story 4: P2P Money Transfer
# ============================================================================

@workflow.defn
class P2PTransferWorkflow:
    """
    Workflow for peer-to-peer money transfers
    Priority: #3 | Score: 8.25
    Estimate: 2-3 days
    
    Steps:
    1. Validate sender account and balance
    2. Validate recipient account
    3. Check transaction limits
    4. Fraud detection check
    5. Request sender PIN authorization
    6. Process transfer in ledger
    7. Calculate and credit agent commission (if applicable)
    8. Generate receipt
    9. Send notifications to both parties
    10. Update analytics
    """
    
    @workflow.run
    async def run(self, input: P2PTransferInput) -> Dict[str, Any]:
        """Execute P2P transfer workflow"""
        
        # Step 1: Validate sender account and balance
        sender_validation = await workflow.execute_activity(
            validate_sender_account,
            {
                "customer_id": input.sender_id,
                "amount": input.amount,
                "currency": input.currency
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        if not sender_validation["valid"]:
            return {
                "status": "failed",
                "reason": sender_validation.get("reason", "Sender validation failed")
            }
        
        # Step 2: Validate recipient account
        recipient_validation = await workflow.execute_activity(
            validate_recipient_account,
            {"customer_id": input.recipient_id},
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        if not recipient_validation["valid"]:
            return {
                "status": "failed",
                "reason": recipient_validation.get("reason", "Recipient validation failed")
            }
        
        # Step 3: Check transaction limits
        limits_check = await workflow.execute_activity(
            check_p2p_transaction_limits,
            {
                "customer_id": input.sender_id,
                "amount": input.amount,
                "currency": input.currency
            },
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )
        
        if not limits_check["within_limits"]:
            return {
                "status": "failed",
                "reason": "Transaction exceeds limits"
            }
        
        # Step 4: Fraud detection check
        fraud_check = await workflow.execute_activity(
            check_p2p_fraud,
            {
                "transaction_id": input.transaction_id,
                "sender_id": input.sender_id,
                "recipient_id": input.recipient_id,
                "amount": input.amount
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )
        
        if fraud_check["is_fraudulent"]:
            return {
                "status": "blocked",
                "reason": "Transaction flagged as potentially fraudulent"
            }
        
        # Step 5: Request sender PIN authorization
        pin_verification = await workflow.execute_activity(
            verify_sender_pin,
            {
                "customer_id": input.sender_id,
                "transaction_id": input.transaction_id
            },
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(maximum_attempts=1)
        )
        
        if not pin_verification["verified"]:
            return {
                "status": "failed",
                "reason": "PIN verification failed"
            }
        
        # Step 6: Process transfer in ledger
        ledger_result = await workflow.execute_activity(
            process_p2p_ledger_transaction,
            {
                "transaction_id": input.transaction_id,
                "sender_id": input.sender_id,
                "recipient_id": input.recipient_id,
                "amount": input.amount,
                "currency": input.currency,
                "note": input.note
            },
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                backoff_coefficient=2.0,
                initial_interval=timedelta(seconds=1)
            )
        )
        
        if not ledger_result["success"]:
            return {
                "status": "failed",
                "reason": "Ledger transaction failed"
            }
        
        # Step 7: Calculate and credit agent commission (if applicable)
        if input.agent_id:
            commission_result = await workflow.execute_activity(
                calculate_p2p_commission,
                {
                    "transaction_id": input.transaction_id,
                    "agent_id": input.agent_id,
                    "amount": input.amount
                },
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=3)
            )
        
        # Step 8: Generate receipt
        receipt = await workflow.execute_activity(
            generate_p2p_receipt,
            {
                "transaction_id": input.transaction_id,
                "sender_id": input.sender_id,
                "recipient_id": input.recipient_id,
                "amount": input.amount,
                "ledger_id": ledger_result["ledger_id"]
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )
        
        # Step 9: Send notifications
        await workflow.execute_activity(
            send_p2p_notifications,
            {
                "transaction_id": input.transaction_id,
                "sender_id": input.sender_id,
                "recipient_id": input.recipient_id,
                "amount": input.amount,
                "receipt_url": receipt["receipt_url"]
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        # Step 10: Update analytics
        await workflow.execute_activity(
            update_p2p_analytics,
            {
                "transaction_id": input.transaction_id,
                "sender_id": input.sender_id,
                "recipient_id": input.recipient_id,
                "amount": input.amount,
                "agent_id": input.agent_id
            },
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )
        
        return {
            "status": "completed",
            "transaction_id": input.transaction_id,
            "ledger_id": ledger_result["ledger_id"],
            "receipt_url": receipt["receipt_url"],
            "amount": input.amount,
            "sender_id": input.sender_id,
            "recipient_id": input.recipient_id
        }

# ============================================================================
# PRIORITY 2: Bill Payment Workflow (Score: 8.45)
# User Story 5: Bill Payment Services
# ============================================================================

@workflow.defn
class BillPaymentWorkflow:
    """
    Workflow for utility bill payments
    Priority: #1 | Score: 8.45
    Estimate: 3-4 days
    
    Steps:
    1. Validate customer account and balance
    2. Validate biller and account number
    3. Fetch bill details from biller
    4. Check transaction limits
    5. Fraud detection check
    6. Request customer PIN authorization
    7. Process payment in ledger
    8. Submit payment to biller
    9. Receive payment confirmation
    10. Calculate and credit agent commission
    11. Generate receipt
    12. Send notifications
    13. Update analytics
    """
    
    @workflow.run
    async def run(self, input: BillPaymentInput) -> Dict[str, Any]:
        """Execute bill payment workflow"""
        
        # Step 1: Validate customer account and balance
        customer_validation = await workflow.execute_activity(
            validate_customer_account,
            {
                "customer_id": input.customer_id,
                "amount": input.amount,
                "currency": input.currency
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        if not customer_validation["valid"]:
            return {
                "status": "failed",
                "reason": customer_validation.get("reason", "Customer validation failed")
            }
        
        # Step 2: Validate biller and account number
        biller_validation = await workflow.execute_activity(
            validate_biller_account,
            {
                "biller_id": input.biller_id,
                "account_number": input.account_number,
                "bill_type": input.bill_type
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        if not biller_validation["valid"]:
            return {
                "status": "failed",
                "reason": biller_validation.get("reason", "Biller validation failed")
            }
        
        # Step 3: Fetch bill details from biller
        bill_details = await workflow.execute_activity(
            fetch_bill_details,
            {
                "biller_id": input.biller_id,
                "account_number": input.account_number,
                "bill_type": input.bill_type
            },
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        # Verify amount matches bill
        if bill_details.get("amount_due") and abs(bill_details["amount_due"] - input.amount) > 0.01:
            return {
                "status": "failed",
                "reason": f"Amount mismatch. Bill amount: {bill_details['amount_due']}"
            }
        
        # Step 4: Check transaction limits
        limits_check = await workflow.execute_activity(
            check_transaction_limits,
            {
                "customer_id": input.customer_id,
                "amount": input.amount,
                "transaction_type": "bill_payment"
            },
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )
        
        if not limits_check["within_limits"]:
            return {
                "status": "failed",
                "reason": "Transaction exceeds limits"
            }
        
        # Step 5: Fraud detection check
        fraud_check = await workflow.execute_activity(
            check_fraud,
            {
                "transaction_id": input.transaction_id,
                "customer_id": input.customer_id,
                "amount": input.amount,
                "transaction_type": "bill_payment",
                "biller_id": input.biller_id
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )
        
        if fraud_check["is_fraudulent"]:
            return {
                "status": "blocked",
                "reason": "Transaction flagged as potentially fraudulent"
            }
        
        # Step 6: Request customer PIN authorization
        pin_verification = await workflow.execute_activity(
            verify_customer_pin,
            {
                "customer_id": input.customer_id,
                "transaction_id": input.transaction_id
            },
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(maximum_attempts=1)
        )
        
        if not pin_verification["verified"]:
            return {
                "status": "failed",
                "reason": "PIN verification failed"
            }
        
        # Step 7: Process payment in ledger
        ledger_result = await workflow.execute_activity(
            process_ledger_transaction,
            {
                "transaction_id": input.transaction_id,
                "customer_id": input.customer_id,
                "amount": input.amount,
                "transaction_type": "bill_payment",
                "metadata": {
                    "biller_id": input.biller_id,
                    "account_number": input.account_number,
                    "bill_type": input.bill_type
                }
            },
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                backoff_coefficient=2.0,
                initial_interval=timedelta(seconds=1)
            )
        )
        
        if not ledger_result["success"]:
            return {
                "status": "failed",
                "reason": "Ledger transaction failed"
            }
        
        # Step 8: Submit payment to biller
        biller_submission = await workflow.execute_activity(
            submit_bill_payment,
            {
                "transaction_id": input.transaction_id,
                "biller_id": input.biller_id,
                "account_number": input.account_number,
                "amount": input.amount,
                "bill_type": input.bill_type
            },
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                backoff_coefficient=2.0,
                initial_interval=timedelta(seconds=5)
            )
        )
        
        # Step 9: Receive payment confirmation
        if not biller_submission["success"]:
            # Initiate refund workflow
            await workflow.execute_activity(
                initiate_refund,
                {
                    "transaction_id": input.transaction_id,
                    "ledger_id": ledger_result["ledger_id"],
                    "reason": "Biller payment failed"
                },
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(maximum_attempts=3)
            )
            
            return {
                "status": "failed",
                "reason": "Biller payment failed, refund initiated"
            }
        
        # Step 10: Calculate and credit agent commission
        commission_result = await workflow.execute_activity(
            calculate_and_credit_commission,
            {
                "transaction_id": input.transaction_id,
                "agent_id": input.agent_id,
                "amount": input.amount,
                "transaction_type": "bill_payment"
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        # Step 11: Generate receipt
        receipt = await workflow.execute_activity(
            generate_receipt,
            {
                "transaction_id": input.transaction_id,
                "customer_id": input.customer_id,
                "amount": input.amount,
                "transaction_type": "bill_payment",
                "biller_name": input.biller_name,
                "account_number": input.account_number,
                "ledger_id": ledger_result["ledger_id"],
                "biller_reference": biller_submission["reference"]
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )
        
        # Step 12: Send notifications
        await workflow.execute_activity(
            send_transaction_notifications,
            {
                "transaction_id": input.transaction_id,
                "customer_id": input.customer_id,
                "agent_id": input.agent_id,
                "transaction_type": "bill_payment",
                "amount": input.amount,
                "receipt_url": receipt["receipt_url"]
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        # Step 13: Update analytics
        await workflow.execute_activity(
            update_transaction_analytics,
            {
                "transaction_id": input.transaction_id,
                "customer_id": input.customer_id,
                "agent_id": input.agent_id,
                "transaction_type": "bill_payment",
                "amount": input.amount,
                "biller_id": input.biller_id
            },
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )
        
        return {
            "status": "completed",
            "transaction_id": input.transaction_id,
            "ledger_id": ledger_result["ledger_id"],
            "biller_reference": biller_submission["reference"],
            "receipt_url": receipt["receipt_url"],
            "commission": commission_result.get("commission_amount", 0),
            "amount": input.amount
        }

# ============================================================================
# PRIORITY 3: Airtime & Data Purchase Workflow (Score: 8.35)
# User Story 6: Airtime & Data Top-Up
# ============================================================================

@workflow.defn
class AirtimeDataPurchaseWorkflow:
    """
    Workflow for airtime and data bundle purchases
    Priority: #2 | Score: 8.35
    Estimate: 2-3 days
    
    Steps:
    1. Validate customer account and balance
    2. Validate telco provider and phone number
    3. Fetch available products (for data)
    4. Check transaction limits
    5. Fraud detection check
    6. Request customer PIN authorization
    7. Process payment in ledger
    8. Submit purchase to telco provider
    9. Receive confirmation and voucher code
    10. Calculate and credit agent commission
    11. Generate receipt
    12. Send notifications with voucher details
    13. Update analytics
    """
    
    @workflow.run
    async def run(self, input: AirtimeDataInput) -> Dict[str, Any]:
        """Execute airtime/data purchase workflow"""
        
        # Step 1: Validate customer account and balance
        customer_validation = await workflow.execute_activity(
            validate_customer_account,
            {
                "customer_id": input.customer_id,
                "amount": input.amount,
                "currency": input.currency
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        if not customer_validation["valid"]:
            return {
                "status": "failed",
                "reason": customer_validation.get("reason", "Customer validation failed")
            }
        
        # Step 2: Validate telco provider and phone number
        telco_validation = await workflow.execute_activity(
            validate_telco_phone,
            {
                "telco_provider": input.telco_provider,
                "phone_number": input.phone_number
            },
            start_to_close_timeout=timedelta(seconds=20),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        if not telco_validation["valid"]:
            return {
                "status": "failed",
                "reason": telco_validation.get("reason", "Phone number validation failed")
            }
        
        # Step 3: Fetch available products (for data bundles)
        if input.product_type == "data" and input.product_id:
            product_details = await workflow.execute_activity(
                fetch_data_product_details,
                {
                    "telco_provider": input.telco_provider,
                    "product_id": input.product_id
                },
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=3)
            )
            
            # Verify amount matches product price
            if abs(product_details["price"] - input.amount) > 0.01:
                return {
                    "status": "failed",
                    "reason": f"Amount mismatch. Product price: {product_details['price']}"
                }
        
        # Step 4: Check transaction limits
        limits_check = await workflow.execute_activity(
            check_transaction_limits,
            {
                "customer_id": input.customer_id,
                "amount": input.amount,
                "transaction_type": "airtime_data"
            },
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )
        
        if not limits_check["within_limits"]:
            return {
                "status": "failed",
                "reason": "Transaction exceeds limits"
            }
        
        # Step 5: Fraud detection check
        fraud_check = await workflow.execute_activity(
            check_fraud,
            {
                "transaction_id": input.transaction_id,
                "customer_id": input.customer_id,
                "amount": input.amount,
                "transaction_type": "airtime_data",
                "phone_number": input.phone_number
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )
        
        if fraud_check["is_fraudulent"]:
            return {
                "status": "blocked",
                "reason": "Transaction flagged as potentially fraudulent"
            }
        
        # Step 6: Request customer PIN authorization
        pin_verification = await workflow.execute_activity(
            verify_customer_pin,
            {
                "customer_id": input.customer_id,
                "transaction_id": input.transaction_id
            },
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(maximum_attempts=1)
        )
        
        if not pin_verification["verified"]:
            return {
                "status": "failed",
                "reason": "PIN verification failed"
            }
        
        # Step 7: Process payment in ledger
        ledger_result = await workflow.execute_activity(
            process_ledger_transaction,
            {
                "transaction_id": input.transaction_id,
                "customer_id": input.customer_id,
                "amount": input.amount,
                "transaction_type": "airtime_data",
                "metadata": {
                    "telco_provider": input.telco_provider,
                    "phone_number": input.phone_number,
                    "product_type": input.product_type,
                    "product_id": input.product_id
                }
            },
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                backoff_coefficient=2.0,
                initial_interval=timedelta(seconds=1)
            )
        )
        
        if not ledger_result["success"]:
            return {
                "status": "failed",
                "reason": "Ledger transaction failed"
            }
        
        # Step 8: Submit purchase to telco provider
        telco_purchase = await workflow.execute_activity(
            submit_telco_purchase,
            {
                "transaction_id": input.transaction_id,
                "telco_provider": input.telco_provider,
                "phone_number": input.phone_number,
                "product_type": input.product_type,
                "product_id": input.product_id,
                "amount": input.amount
            },
            start_to_close_timeout=timedelta(minutes=3),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                backoff_coefficient=2.0,
                initial_interval=timedelta(seconds=5)
            )
        )
        
        # Step 9: Handle telco response
        if not telco_purchase["success"]:
            # Initiate refund
            await workflow.execute_activity(
                initiate_refund,
                {
                    "transaction_id": input.transaction_id,
                    "ledger_id": ledger_result["ledger_id"],
                    "reason": "Telco purchase failed"
                },
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(maximum_attempts=3)
            )
            
            return {
                "status": "failed",
                "reason": "Telco purchase failed, refund initiated"
            }
        
        # Step 10: Calculate and credit agent commission
        commission_result = await workflow.execute_activity(
            calculate_and_credit_commission,
            {
                "transaction_id": input.transaction_id,
                "agent_id": input.agent_id,
                "amount": input.amount,
                "transaction_type": "airtime_data"
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        # Step 11: Generate receipt
        receipt = await workflow.execute_activity(
            generate_receipt,
            {
                "transaction_id": input.transaction_id,
                "customer_id": input.customer_id,
                "amount": input.amount,
                "transaction_type": "airtime_data",
                "telco_provider": input.telco_provider,
                "phone_number": input.phone_number,
                "product_type": input.product_type,
                "ledger_id": ledger_result["ledger_id"],
                "telco_reference": telco_purchase["reference"]
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )
        
        # Step 12: Send notifications
        await workflow.execute_activity(
            send_transaction_notifications,
            {
                "transaction_id": input.transaction_id,
                "customer_id": input.customer_id,
                "agent_id": input.agent_id,
                "transaction_type": "airtime_data",
                "amount": input.amount,
                "receipt_url": receipt["receipt_url"],
                "voucher_code": telco_purchase.get("voucher_code")
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        # Step 13: Update analytics
        await workflow.execute_activity(
            update_transaction_analytics,
            {
                "transaction_id": input.transaction_id,
                "customer_id": input.customer_id,
                "agent_id": input.agent_id,
                "transaction_type": "airtime_data",
                "amount": input.amount,
                "telco_provider": input.telco_provider
            },
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )
        
        return {
            "status": "completed",
            "transaction_id": input.transaction_id,
            "ledger_id": ledger_result["ledger_id"],
            "telco_reference": telco_purchase["reference"],
            "voucher_code": telco_purchase.get("voucher_code"),
            "receipt_url": receipt["receipt_url"],
            "commission": commission_result.get("commission_amount", 0),
            "amount": input.amount
        }

# ============================================================================
# PRIORITY 4: Float Management Workflow (Score: 7.75)
# User Story 18: Agent Float Management
# ============================================================================

@workflow.defn
class FloatManagementWorkflow:
    """
    Workflow for agent cash float management and rebalancing
    Priority: #4 | Score: 7.75
    Estimate: 4-5 days
    
    Steps:
    1. Validate agent account
    2. Check current float balance
    3. Validate operation type and amount
    4. Check float limits and thresholds
    5. Request authorization (for large amounts)
    6. Process float operation in ledger
    7. Update float tracking system
    8. Update agent cash availability
    9. Generate float report
    10. Send notifications
    11. Update analytics and alerts
    """
    
    @workflow.run
    async def run(self, input: FloatManagementInput) -> Dict[str, Any]:
        """Execute float management workflow"""
        
        # Step 1: Validate agent account
        agent_validation = await workflow.execute_activity(
            validate_agent_account,
            {"agent_id": input.agent_id},
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        if not agent_validation["valid"]:
            return {
                "status": "failed",
                "reason": agent_validation.get("reason", "Agent validation failed")
            }
        
        # Step 2: Check current float balance
        float_balance = await workflow.execute_activity(
            get_agent_float_balance,
            {"agent_id": input.agent_id},
            start_to_close_timeout=timedelta(seconds=20),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        # Step 3: Validate operation type and amount
        operation_validation = await workflow.execute_activity(
            validate_float_operation,
            {
                "agent_id": input.agent_id,
                "operation_type": input.operation_type,
                "amount": input.amount,
                "current_balance": float_balance["balance"],
                "source_agent_id": input.source_agent_id,
                "target_agent_id": input.target_agent_id
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )
        
        if not operation_validation["valid"]:
            return {
                "status": "failed",
                "reason": operation_validation.get("reason", "Operation validation failed")
            }
        
        # Step 4: Check float limits and thresholds
        limits_check = await workflow.execute_activity(
            check_float_limits,
            {
                "agent_id": input.agent_id,
                "operation_type": input.operation_type,
                "amount": input.amount,
                "current_balance": float_balance["balance"]
            },
            start_to_close_timeout=timedelta(seconds=20),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )
        
        if not limits_check["within_limits"]:
            return {
                "status": "failed",
                "reason": limits_check.get("reason", "Operation exceeds limits")
            }
        
        # Step 5: Request authorization (for large amounts)
        if limits_check.get("requires_authorization"):
            # Wait for manual authorization
            workflow.logger.info(f"Waiting for authorization for operation {input.operation_id}")
            
            authorization = await workflow.wait_condition(
                lambda: workflow.get_signal("float_operation_authorized"),
                timeout=timedelta(hours=24)
            )
            
            if not authorization:
                return {
                    "status": "failed",
                    "reason": "Authorization timeout"
                }
        
        # Step 6: Process float operation in ledger
        ledger_result = await workflow.execute_activity(
            process_float_ledger_operation,
            {
                "operation_id": input.operation_id,
                "agent_id": input.agent_id,
                "operation_type": input.operation_type,
                "amount": input.amount,
                "currency": input.currency,
                "source_agent_id": input.source_agent_id,
                "target_agent_id": input.target_agent_id,
                "reason": input.reason
            },
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                backoff_coefficient=2.0,
                initial_interval=timedelta(seconds=1)
            )
        )
        
        if not ledger_result["success"]:
            return {
                "status": "failed",
                "reason": "Ledger operation failed"
            }
        
        # Step 7: Update float tracking system
        float_update = await workflow.execute_activity(
            update_float_tracking,
            {
                "operation_id": input.operation_id,
                "agent_id": input.agent_id,
                "operation_type": input.operation_type,
                "amount": input.amount,
                "previous_balance": float_balance["balance"],
                "new_balance": ledger_result["new_balance"],
                "ledger_id": ledger_result["ledger_id"]
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        # Step 8: Update agent cash availability
        await workflow.execute_activity(
            update_agent_cash_availability,
            {
                "agent_id": input.agent_id,
                "new_balance": ledger_result["new_balance"],
                "operation_type": input.operation_type
            },
            start_to_close_timeout=timedelta(seconds=20),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        # Step 9: Generate float report
        report = await workflow.execute_activity(
            generate_float_report,
            {
                "operation_id": input.operation_id,
                "agent_id": input.agent_id,
                "operation_type": input.operation_type,
                "amount": input.amount,
                "previous_balance": float_balance["balance"],
                "new_balance": ledger_result["new_balance"],
                "ledger_id": ledger_result["ledger_id"]
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )
        
        # Step 10: Send notifications
        await workflow.execute_activity(
            send_float_notifications,
            {
                "operation_id": input.operation_id,
                "agent_id": input.agent_id,
                "operation_type": input.operation_type,
                "amount": input.amount,
                "new_balance": ledger_result["new_balance"],
                "report_url": report["report_url"]
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        # Step 11: Update analytics and check for alerts
        await workflow.execute_activity(
            update_float_analytics,
            {
                "operation_id": input.operation_id,
                "agent_id": input.agent_id,
                "operation_type": input.operation_type,
                "amount": input.amount,
                "new_balance": ledger_result["new_balance"]
            },
            start_to_close_timeout=timedelta(seconds=20),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )
        
        # Check if rebalancing is needed
        if ledger_result["new_balance"] < float_balance.get("min_threshold", 0):
            await workflow.execute_activity(
                trigger_float_rebalance_alert,
                {
                    "agent_id": input.agent_id,
                    "current_balance": ledger_result["new_balance"],
                    "min_threshold": float_balance.get("min_threshold", 0)
                },
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=RetryPolicy(maximum_attempts=2)
            )
        
        return {
            "status": "completed",
            "operation_id": input.operation_id,
            "operation_type": input.operation_type,
            "amount": input.amount,
            "previous_balance": float_balance["balance"],
            "new_balance": ledger_result["new_balance"],
            "ledger_id": ledger_result["ledger_id"],
            "report_url": report["report_url"]
        }

# ============================================================================
# PRIORITY 5: Savings Account Workflow (Score: 7.55)
# User Story 11: Savings Account Management
# ============================================================================

@workflow.defn
class SavingsAccountWorkflow:
    """
    Workflow for savings account management
    Priority: #5 | Score: 7.55
    Estimate: 4-5 days
    
    Steps:
    1. Validate customer account
    2. Validate operation type and parameters
    3. Check account status and eligibility
    4. Calculate interest (if applicable)
    5. Check regulatory compliance
    6. Request customer authorization
    7. Process account operation in ledger
    8. Update savings account records
    9. Schedule interest payments (if applicable)
    10. Generate account statement
    11. Send notifications
    12. Update analytics
    """
    
    @workflow.run
    async def run(self, input: SavingsAccountInput) -> Dict[str, Any]:
        """Execute savings account workflow"""
        
        # Step 1: Validate customer account
        customer_validation = await workflow.execute_activity(
            validate_customer_account,
            {"customer_id": input.customer_id},
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        if not customer_validation["valid"]:
            return {
                "status": "failed",
                "reason": customer_validation.get("reason", "Customer validation failed")
            }
        
        # Step 2: Validate operation type and parameters
        operation_validation = await workflow.execute_activity(
            validate_savings_operation,
            {
                "account_id": input.account_id,
                "customer_id": input.customer_id,
                "operation_type": input.operation_type,
                "amount": input.amount,
                "account_type": input.account_type,
                "interest_rate": input.interest_rate,
                "term_months": input.term_months
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )
        
        if not operation_validation["valid"]:
            return {
                "status": "failed",
                "reason": operation_validation.get("reason", "Operation validation failed")
            }
        
        # Step 3: Check account status and eligibility
        if input.operation_type != "open":
            account_status = await workflow.execute_activity(
                check_savings_account_status,
                {"account_id": input.account_id},
                start_to_close_timeout=timedelta(seconds=20),
                retry_policy=RetryPolicy(maximum_attempts=3)
            )
            
            if not account_status["active"]:
                return {
                    "status": "failed",
                    "reason": "Account is not active"
                }
        
        # Step 4: Calculate interest (if applicable)
        interest_calculation = None
        if input.operation_type in ["withdraw", "close"]:
            interest_calculation = await workflow.execute_activity(
                calculate_savings_interest,
                {
                    "account_id": input.account_id,
                    "account_type": input.account_type,
                    "interest_rate": input.interest_rate,
                    "term_months": input.term_months
                },
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=3)
            )
        
        # Step 5: Check regulatory compliance
        compliance_check = await workflow.execute_activity(
            check_savings_compliance,
            {
                "customer_id": input.customer_id,
                "operation_type": input.operation_type,
                "amount": input.amount,
                "account_type": input.account_type
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )
        
        if not compliance_check["compliant"]:
            return {
                "status": "failed",
                "reason": compliance_check.get("reason", "Compliance check failed")
            }
        
        # Step 6: Request customer authorization
        if input.operation_type in ["withdraw", "close"]:
            authorization = await workflow.execute_activity(
                request_savings_authorization,
                {
                    "customer_id": input.customer_id,
                    "account_id": input.account_id,
                    "operation_type": input.operation_type,
                    "amount": input.amount
                },
                start_to_close_timeout=timedelta(minutes=3),
                retry_policy=RetryPolicy(maximum_attempts=1)
            )
            
            if not authorization["authorized"]:
                return {
                    "status": "failed",
                    "reason": "Authorization failed"
                }
        
        # Step 7: Process account operation in ledger
        ledger_result = await workflow.execute_activity(
            process_savings_ledger_operation,
            {
                "account_id": input.account_id,
                "customer_id": input.customer_id,
                "operation_type": input.operation_type,
                "amount": input.amount,
                "interest_amount": interest_calculation.get("interest_amount", 0) if interest_calculation else 0,
                "account_type": input.account_type
            },
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                backoff_coefficient=2.0,
                initial_interval=timedelta(seconds=1)
            )
        )
        
        if not ledger_result["success"]:
            return {
                "status": "failed",
                "reason": "Ledger operation failed"
            }
        
        # Step 8: Update savings account records
        account_update = await workflow.execute_activity(
            update_savings_account,
            {
                "account_id": input.account_id,
                "customer_id": input.customer_id,
                "operation_type": input.operation_type,
                "amount": input.amount,
                "new_balance": ledger_result["new_balance"],
                "account_type": input.account_type,
                "interest_rate": input.interest_rate,
                "term_months": input.term_months,
                "target_amount": input.target_amount,
                "withdrawal_frequency": input.withdrawal_frequency
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        # Step 9: Schedule interest payments (if applicable)
        if input.operation_type == "open" and input.interest_rate:
            await workflow.execute_activity(
                schedule_interest_payments,
                {
                    "account_id": input.account_id,
                    "interest_rate": input.interest_rate,
                    "account_type": input.account_type,
                    "term_months": input.term_months
                },
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=2)
            )
        
        # Step 10: Generate account statement
        statement = await workflow.execute_activity(
            generate_savings_statement,
            {
                "account_id": input.account_id,
                "customer_id": input.customer_id,
                "operation_type": input.operation_type,
                "amount": input.amount,
                "interest_amount": interest_calculation.get("interest_amount", 0) if interest_calculation else 0,
                "new_balance": ledger_result["new_balance"],
                "ledger_id": ledger_result["ledger_id"]
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )
        
        # Step 11: Send notifications
        await workflow.execute_activity(
            send_savings_notifications,
            {
                "account_id": input.account_id,
                "customer_id": input.customer_id,
                "operation_type": input.operation_type,
                "amount": input.amount,
                "new_balance": ledger_result["new_balance"],
                "statement_url": statement["statement_url"]
            },
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )
        
        # Step 12: Update analytics
        await workflow.execute_activity(
            update_savings_analytics,
            {
                "account_id": input.account_id,
                "customer_id": input.customer_id,
                "operation_type": input.operation_type,
                "amount": input.amount,
                "account_type": input.account_type,
                "new_balance": ledger_result["new_balance"]
            },
            start_to_close_timeout=timedelta(seconds=20),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )
        
        return {
            "status": "completed",
            "account_id": input.account_id,
            "operation_type": input.operation_type,
            "amount": input.amount,
            "interest_amount": interest_calculation.get("interest_amount", 0) if interest_calculation else 0,
            "new_balance": ledger_result["new_balance"],
            "ledger_id": ledger_result["ledger_id"],
            "statement_url": statement["statement_url"]
        }

# ============================================================================
# Activity Function Implementations for Priority Workflows
# ============================================================================

DAILY_P2P_LIMIT = 500000.00
DAILY_BILL_LIMIT = 1000000.00
DAILY_FLOAT_LIMIT = 5000000.00
P2P_COMMISSION_RATE = 0.005
BILL_COMMISSION_RATE = 0.01
AIRTIME_COMMISSION_RATE = 0.03
DATA_COMMISSION_RATE = 0.025

NIGERIAN_TELCO_PROVIDERS = {"MTN", "Airtel", "Glo", "9mobile"}
NIGERIAN_PHONE_PATTERN = re.compile(r"^(\+234|0)[789][01]\d{8}$")


@activity.defn
async def validate_sender_account(params: Dict[str, Any]) -> Dict[str, Any]:
    """Validate sender account and balance"""
    customer_id = params["customer_id"]
    amount = params["amount"]
    currency = params.get("currency", "NGN")
    logger.info(f"Validating sender account {customer_id} for {amount} {currency}")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                f"http://account-service:8080/accounts/{customer_id}",
                params={"currency": currency},
            )
            if resp.status_code == 404:
                return {"valid": False, "reason": "Sender account not found"}
            resp.raise_for_status()
            account = resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Account service error: {e}")
            return {"valid": False, "reason": "Account service unavailable"}
    if account.get("status") != "active":
        return {"valid": False, "reason": f"Account status: {account.get('status')}"}
    balance = float(account.get("available_balance", 0))
    if balance < amount:
        return {"valid": False, "reason": f"Insufficient balance: {balance} < {amount}"}
    if account.get("kyc_level", 0) < 1:
        return {"valid": False, "reason": "KYC verification required"}
    return {"valid": True, "balance": balance, "account_type": account.get("account_type")}


@activity.defn
async def validate_recipient_account(params: Dict[str, Any]) -> Dict[str, Any]:
    """Validate recipient account"""
    customer_id = params["customer_id"]
    logger.info(f"Validating recipient account {customer_id}")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"http://account-service:8080/accounts/{customer_id}")
            if resp.status_code == 404:
                return {"valid": False, "reason": "Recipient account not found"}
            resp.raise_for_status()
            account = resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Account service error: {e}")
            return {"valid": False, "reason": "Account service unavailable"}
    if account.get("status") != "active":
        return {"valid": False, "reason": f"Recipient account status: {account.get('status')}"}
    return {"valid": True, "account_name": account.get("account_name")}


@activity.defn
async def check_p2p_transaction_limits(params: Dict[str, Any]) -> Dict[str, Any]:
    """Check P2P transaction limits"""
    customer_id = params["customer_id"]
    amount = params["amount"]
    currency = params.get("currency", "NGN")
    logger.info(f"Checking P2P limits for {customer_id}: {amount} {currency}")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                f"http://limits-service:8080/limits/{customer_id}",
                params={"type": "p2p", "currency": currency},
            )
            resp.raise_for_status()
            limits = resp.json()
        except httpx.HTTPError:
            limits = {"daily_used": 0, "daily_limit": DAILY_P2P_LIMIT}
    daily_used = float(limits.get("daily_used", 0))
    daily_limit = float(limits.get("daily_limit", DAILY_P2P_LIMIT))
    within = (daily_used + amount) <= daily_limit
    return {
        "within_limits": within,
        "daily_used": daily_used,
        "daily_limit": daily_limit,
        "remaining": max(0, daily_limit - daily_used),
    }


@activity.defn
async def check_p2p_fraud(params: Dict[str, Any]) -> Dict[str, Any]:
    """Check P2P transaction for fraud"""
    logger.info(f"Fraud check for txn {params['transaction_id']}")
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                "http://fraud-detection-service:8080/check",
                json={
                    "transaction_id": params["transaction_id"],
                    "sender_id": params["sender_id"],
                    "recipient_id": params["recipient_id"],
                    "amount": params["amount"],
                    "type": "p2p_transfer",
                },
            )
            resp.raise_for_status()
            result = resp.json()
            return {
                "is_fraudulent": result.get("risk_score", 0) > 0.85,
                "risk_score": result.get("risk_score", 0),
                "risk_factors": result.get("risk_factors", []),
            }
        except httpx.HTTPError as e:
            logger.error(f"Fraud service error: {e}")
            return {"is_fraudulent": False, "risk_score": 0, "risk_factors": []}


@activity.defn
async def verify_sender_pin(params: Dict[str, Any]) -> Dict[str, Any]:
    """Verify sender PIN"""
    customer_id = params["customer_id"]
    transaction_id = params["transaction_id"]
    logger.info(f"PIN verification for {customer_id} on txn {transaction_id}")
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                "http://auth-service:8080/verify-pin",
                json={"customer_id": customer_id, "transaction_id": transaction_id},
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Auth service error: {e}")
            return {"verified": False, "reason": "PIN verification service unavailable"}


@activity.defn
async def process_p2p_ledger_transaction(params: Dict[str, Any]) -> Dict[str, Any]:
    """Process P2P transfer in ledger"""
    logger.info(f"Processing ledger txn {params['transaction_id']}")
    ledger_id = str(uuid.uuid4())
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                "http://tigerbeetle-service:8080/transfers",
                json={
                    "transfer_id": ledger_id,
                    "debit_account_id": params["sender_id"],
                    "credit_account_id": params["recipient_id"],
                    "amount": int(params["amount"] * 100),
                    "currency": params.get("currency", "NGN"),
                    "reference": params["transaction_id"],
                    "metadata": {"note": params.get("note", ""), "type": "p2p_transfer"},
                },
            )
            resp.raise_for_status()
            return {"success": True, "ledger_id": ledger_id}
        except httpx.HTTPError as e:
            logger.error(f"Ledger service error: {e}")
            return {"success": False, "error": str(e)}


@activity.defn
async def calculate_p2p_commission(params: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate P2P commission"""
    amount = params["amount"]
    commission = round(amount * P2P_COMMISSION_RATE, 2)
    logger.info(f"P2P commission for txn {params['transaction_id']}: {commission}")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                "http://commission-service:8080/credit",
                json={
                    "agent_id": params["agent_id"],
                    "transaction_id": params["transaction_id"],
                    "commission_amount": commission,
                    "commission_type": "p2p_transfer",
                },
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            logger.error(f"Commission service error: {e}")
    return {"commission_amount": commission, "agent_id": params["agent_id"]}


@activity.defn
async def generate_p2p_receipt(params: Dict[str, Any]) -> Dict[str, Any]:
    """Generate P2P receipt"""
    receipt_id = f"RCP-{params['transaction_id']}"
    logger.info(f"Generating receipt {receipt_id}")
    receipt = {
        "receipt_id": receipt_id,
        "transaction_id": params["transaction_id"],
        "sender_id": params["sender_id"],
        "recipient_id": params["recipient_id"],
        "amount": params["amount"],
        "ledger_id": params.get("ledger_id"),
        "timestamp": datetime.utcnow().isoformat(),
        "type": "p2p_transfer",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post("http://receipt-service:8080/receipts", json=receipt)
            resp.raise_for_status()
            return {"receipt_id": receipt_id, "receipt_url": f"/receipts/{receipt_id}"}
        except httpx.HTTPError:
            return {"receipt_id": receipt_id, "receipt_url": f"/receipts/{receipt_id}"}


@activity.defn
async def send_p2p_notifications(params: Dict[str, Any]) -> Dict[str, Any]:
    """Send P2P notifications"""
    logger.info(f"Sending P2P notifications for txn {params['transaction_id']}")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.post(
                "http://notification-service:8080/send-batch",
                json={
                    "notifications": [
                        {
                            "user_id": params["sender_id"],
                            "type": "transaction",
                            "title": "Transfer Sent",
                            "message": f"You sent {params['amount']} NGN",
                            "channels": ["push", "sms"],
                        },
                        {
                            "user_id": params["recipient_id"],
                            "type": "transaction",
                            "title": "Transfer Received",
                            "message": f"You received {params['amount']} NGN",
                            "channels": ["push", "sms"],
                        },
                    ]
                },
            )
        except httpx.HTTPError as e:
            logger.error(f"Notification service error: {e}")
    return {"sent": True}


@activity.defn
async def update_p2p_analytics(params: Dict[str, Any]) -> Dict[str, Any]:
    """Update P2P analytics"""
    logger.info(f"Updating analytics for txn {params['transaction_id']}")
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            await client.post(
                "http://analytics-service:8080/events",
                json={
                    "event_type": "p2p_transfer_completed",
                    "transaction_id": params["transaction_id"],
                    "sender_id": params["sender_id"],
                    "recipient_id": params["recipient_id"],
                    "amount": params["amount"],
                    "agent_id": params.get("agent_id"),
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
        except httpx.HTTPError as e:
            logger.warning(f"Analytics update failed (non-critical): {e}")
    return {"updated": True}


# Bill Payment Activities
@activity.defn
async def validate_biller_account(params: Dict[str, Any]) -> Dict[str, Any]:
    """Validate biller and account number"""
    biller_id = params["biller_id"]
    account_number = params["account_number"]
    bill_type = params["bill_type"]
    logger.info(f"Validating biller {biller_id} account {account_number}")
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.post(
                "http://biller-service:8080/validate",
                json={
                    "biller_id": biller_id,
                    "account_number": account_number,
                    "bill_type": bill_type,
                },
            )
            resp.raise_for_status()
            result = resp.json()
            return {
                "valid": result.get("valid", False),
                "customer_name": result.get("customer_name"),
                "biller_name": result.get("biller_name"),
            }
        except httpx.HTTPError as e:
            logger.error(f"Biller validation error: {e}")
            return {"valid": False, "reason": "Biller validation service unavailable"}


@activity.defn
async def fetch_bill_details(params: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch bill details from biller"""
    logger.info(f"Fetching bill for {params['biller_id']} acct {params['account_number']}")
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(
                f"http://biller-service:8080/billers/{params['biller_id']}/bills",
                params={
                    "account_number": params["account_number"],
                    "bill_type": params["bill_type"],
                },
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Bill fetch error: {e}")
            return {"amount_due": None, "due_date": None}


@activity.defn
async def submit_bill_payment(params: Dict[str, Any]) -> Dict[str, Any]:
    """Submit payment to biller"""
    logger.info(f"Submitting bill payment {params['transaction_id']} to {params['biller_id']}")
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            resp = await client.post(
                f"http://biller-service:8080/billers/{params['biller_id']}/pay",
                json={
                    "transaction_id": params["transaction_id"],
                    "account_number": params["account_number"],
                    "amount": params["amount"],
                    "bill_type": params["bill_type"],
                },
            )
            resp.raise_for_status()
            result = resp.json()
            return {
                "success": True,
                "reference": result.get("reference", params["transaction_id"]),
                "confirmation_code": result.get("confirmation_code"),
            }
        except httpx.HTTPError as e:
            logger.error(f"Bill payment submission error: {e}")
            return {"success": False, "error": str(e)}


@activity.defn
async def initiate_refund(params: Dict[str, Any]) -> Dict[str, Any]:
    """Initiate refund for failed transaction"""
    logger.info(f"Initiating refund for txn {params['transaction_id']}")
    refund_id = f"REF-{params['transaction_id']}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                "http://tigerbeetle-service:8080/refunds",
                json={
                    "refund_id": refund_id,
                    "original_ledger_id": params["ledger_id"],
                    "reason": params.get("reason", "Transaction failed"),
                },
            )
            resp.raise_for_status()
            return {"success": True, "refund_id": refund_id}
        except httpx.HTTPError as e:
            logger.error(f"Refund initiation error: {e}")
            return {"success": False, "error": str(e)}


# Airtime/Data Activities
@activity.defn
async def validate_telco_phone(params: Dict[str, Any]) -> Dict[str, Any]:
    """Validate telco provider and phone number"""
    provider = params.get("telco_provider", "")
    phone = params.get("phone_number", "")
    logger.info(f"Validating {provider} phone {phone}")
    if provider not in NIGERIAN_TELCO_PROVIDERS:
        return {"valid": False, "reason": f"Unsupported provider: {provider}"}
    if not NIGERIAN_PHONE_PATTERN.match(phone):
        return {"valid": False, "reason": "Invalid Nigerian phone number format"}
    return {"valid": True, "provider": provider, "phone_number": phone}


@activity.defn
async def fetch_data_product_details(params: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch data product details"""
    product_id = params.get("product_id")
    provider = params.get("telco_provider")
    logger.info(f"Fetching product {product_id} from {provider}")
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            resp = await client.get(
                f"http://telco-service:8080/providers/{provider}/products",
                params={"product_id": product_id} if product_id else {},
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Telco product fetch error: {e}")
            return {"products": [], "error": str(e)}


@activity.defn
async def submit_telco_purchase(params: Dict[str, Any]) -> Dict[str, Any]:
    """Submit purchase to telco provider"""
    logger.info(f"Submitting telco purchase {params['transaction_id']}")
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"http://telco-service:8080/providers/{params['telco_provider']}/purchase",
                json={
                    "transaction_id": params["transaction_id"],
                    "phone_number": params["phone_number"],
                    "product_type": params["product_type"],
                    "product_id": params.get("product_id"),
                    "amount": params["amount"],
                },
            )
            resp.raise_for_status()
            result = resp.json()
            return {
                "success": True,
                "reference": result.get("reference"),
                "voucher_code": result.get("voucher_code"),
            }
        except httpx.HTTPError as e:
            logger.error(f"Telco purchase error: {e}")
            return {"success": False, "error": str(e)}


# Float Management Activities
@activity.defn
async def validate_agent_account(params: Dict[str, Any]) -> Dict[str, Any]:
    """Validate agent account"""
    agent_id = params["agent_id"]
    logger.info(f"Validating agent {agent_id}")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"http://agent-service:8080/agents/{agent_id}")
            if resp.status_code == 404:
                return {"valid": False, "reason": "Agent not found"}
            resp.raise_for_status()
            agent = resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Agent service error: {e}")
            return {"valid": False, "reason": "Agent service unavailable"}
    if agent.get("status") != "active":
        return {"valid": False, "reason": f"Agent status: {agent.get('status')}"}
    return {"valid": True, "agent_tier": agent.get("tier"), "agent_name": agent.get("name")}


@activity.defn
async def get_agent_float_balance(params: Dict[str, Any]) -> Dict[str, Any]:
    """Get agent float balance"""
    agent_id = params["agent_id"]
    logger.info(f"Getting float balance for agent {agent_id}")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"http://float-service:8080/agents/{agent_id}/balance")
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Float service error: {e}")
            return {"balance": 0, "currency": "NGN", "error": str(e)}


@activity.defn
async def validate_float_operation(params: Dict[str, Any]) -> Dict[str, Any]:
    """Validate float operation"""
    op_type = params.get("operation_type")
    amount = params.get("amount", 0)
    balance = params.get("balance", 0)
    logger.info(f"Validating float op {op_type} for {amount}")
    if op_type == "withdrawal" and balance < amount:
        return {"valid": False, "reason": f"Insufficient float: {balance} < {amount}"}
    if amount <= 0:
        return {"valid": False, "reason": "Amount must be positive"}
    return {"valid": True}


@activity.defn
async def check_float_limits(params: Dict[str, Any]) -> Dict[str, Any]:
    """Check float limits"""
    agent_id = params["agent_id"]
    amount = params["amount"]
    logger.info(f"Checking float limits for agent {agent_id}")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(
                f"http://limits-service:8080/limits/{agent_id}",
                params={"type": "float"},
            )
            resp.raise_for_status()
            limits = resp.json()
        except httpx.HTTPError:
            limits = {"daily_used": 0, "daily_limit": DAILY_FLOAT_LIMIT}
    daily_used = float(limits.get("daily_used", 0))
    daily_limit = float(limits.get("daily_limit", DAILY_FLOAT_LIMIT))
    return {
        "within_limits": (daily_used + amount) <= daily_limit,
        "daily_used": daily_used,
        "daily_limit": daily_limit,
    }


@activity.defn
async def process_float_ledger_operation(params: Dict[str, Any]) -> Dict[str, Any]:
    """Process float operation in ledger"""
    logger.info(f"Processing float ledger op {params['operation_id']}")
    ledger_id = str(uuid.uuid4())
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                "http://tigerbeetle-service:8080/transfers",
                json={
                    "transfer_id": ledger_id,
                    "debit_account_id": params.get("source_agent_id", "float-pool"),
                    "credit_account_id": params.get("target_agent_id", params["agent_id"]),
                    "amount": int(params["amount"] * 100),
                    "currency": params.get("currency", "NGN"),
                    "reference": params["operation_id"],
                    "metadata": {"type": "float_operation", "op": params.get("operation_type")},
                },
            )
            resp.raise_for_status()
            return {"success": True, "ledger_id": ledger_id}
        except httpx.HTTPError as e:
            logger.error(f"Float ledger error: {e}")
            return {"success": False, "error": str(e)}


@activity.defn
async def update_float_tracking(params: Dict[str, Any]) -> Dict[str, Any]:
    """Update float tracking system"""
    logger.info(f"Updating float tracking for {params['agent_id']}")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.post(
                f"http://float-service:8080/agents/{params['agent_id']}/tracking",
                json={
                    "operation_id": params["operation_id"],
                    "operation_type": params["operation_type"],
                    "amount": params["amount"],
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
        except httpx.HTTPError as e:
            logger.warning(f"Float tracking update failed: {e}")
    return {"updated": True}


@activity.defn
async def update_agent_cash_availability(params: Dict[str, Any]) -> Dict[str, Any]:
    """Update agent cash availability"""
    logger.info(f"Updating cash availability for agent {params['agent_id']}")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.put(
                f"http://agent-service:8080/agents/{params['agent_id']}/cash-availability",
                json={
                    "operation_type": params["operation_type"],
                    "amount": params["amount"],
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
        except httpx.HTTPError as e:
            logger.warning(f"Cash availability update failed: {e}")
    return {"updated": True}


@activity.defn
async def generate_float_report(params: Dict[str, Any]) -> Dict[str, Any]:
    """Generate float report"""
    report_id = f"FLR-{params['operation_id']}"
    logger.info(f"Generating float report {report_id}")
    report = {
        "report_id": report_id,
        "agent_id": params["agent_id"],
        "operation_id": params["operation_id"],
        "operation_type": params["operation_type"],
        "amount": params["amount"],
        "new_balance": params.get("new_balance", 0),
        "timestamp": datetime.utcnow().isoformat(),
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.post("http://reporting-service:8080/reports", json=report)
        except httpx.HTTPError as e:
            logger.warning(f"Report generation failed: {e}")
    return {"report_id": report_id, "report_url": f"/reports/{report_id}"}


@activity.defn
async def send_float_notifications(params: Dict[str, Any]) -> Dict[str, Any]:
    """Send float notifications"""
    logger.info(f"Sending float notification for agent {params['agent_id']}")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.post(
                "http://notification-service:8080/send",
                json={
                    "user_id": params["agent_id"],
                    "type": "float",
                    "title": f"Float {params['operation_type'].title()}",
                    "message": f"Float {params['operation_type']} of {params['amount']} NGN processed",
                    "channels": ["push", "sms"],
                },
            )
        except httpx.HTTPError as e:
            logger.warning(f"Float notification failed: {e}")
    return {"sent": True}


@activity.defn
async def update_float_analytics(params: Dict[str, Any]) -> Dict[str, Any]:
    """Update float analytics"""
    logger.info(f"Updating float analytics for {params['operation_id']}")
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            await client.post(
                "http://analytics-service:8080/events",
                json={
                    "event_type": "float_operation",
                    "agent_id": params["agent_id"],
                    "operation_id": params["operation_id"],
                    "operation_type": params["operation_type"],
                    "amount": params["amount"],
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
        except httpx.HTTPError as e:
            logger.warning(f"Float analytics update failed: {e}")
    return {"updated": True}


@activity.defn
async def trigger_float_rebalance_alert(params: Dict[str, Any]) -> Dict[str, Any]:
    """Trigger float rebalance alert"""
    agent_id = params["agent_id"]
    balance = params.get("balance", 0)
    threshold = params.get("threshold", 10000)
    logger.info(f"Checking rebalance alert for agent {agent_id}: balance={balance}")
    if balance < threshold:
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                await client.post(
                    "http://notification-service:8080/send",
                    json={
                        "user_id": agent_id,
                        "type": "alert",
                        "title": "Low Float Balance",
                        "message": f"Float balance {balance} NGN below threshold {threshold} NGN",
                        "channels": ["push", "sms", "email"],
                        "priority": "high",
                    },
                )
            except httpx.HTTPError as e:
                logger.warning(f"Rebalance alert failed: {e}")
        return {"alert_sent": True, "balance": balance, "threshold": threshold}
    return {"alert_sent": False, "balance": balance, "threshold": threshold}


# Savings Account Activities
@activity.defn
async def validate_savings_operation(params: Dict[str, Any]) -> Dict[str, Any]:
    """Validate savings operation"""
    op_type = params.get("operation_type")
    amount = params.get("amount", 0)
    logger.info(f"Validating savings operation: {op_type}")
    valid_ops = {"open", "deposit", "withdraw", "close"}
    if op_type not in valid_ops:
        return {"valid": False, "reason": f"Invalid operation: {op_type}"}
    if op_type in ("deposit", "withdraw") and (amount is None or amount <= 0):
        return {"valid": False, "reason": "Amount must be positive for deposit/withdrawal"}
    return {"valid": True}


@activity.defn
async def check_savings_account_status(params: Dict[str, Any]) -> Dict[str, Any]:
    """Check savings account status"""
    account_id = params.get("account_id")
    logger.info(f"Checking savings account {account_id}")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.get(f"http://savings-service:8080/accounts/{account_id}")
            if resp.status_code == 404:
                return {"exists": False, "status": "not_found"}
            resp.raise_for_status()
            account = resp.json()
            return {
                "exists": True,
                "status": account.get("status", "unknown"),
                "balance": account.get("balance", 0),
                "account_type": account.get("account_type"),
                "interest_rate": account.get("interest_rate"),
            }
        except httpx.HTTPError as e:
            logger.error(f"Savings service error: {e}")
            return {"exists": False, "status": "error", "error": str(e)}


@activity.defn
async def calculate_savings_interest(params: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate savings interest"""
    balance = float(params.get("balance", 0))
    rate = float(params.get("interest_rate", 0.05))
    term_months = int(params.get("term_months", 12))
    logger.info(f"Calculating interest: balance={balance}, rate={rate}, months={term_months}")
    monthly_rate = rate / 12
    accrued = balance * monthly_rate * term_months
    maturity_amount = balance + accrued
    return {
        "principal": balance,
        "interest_rate": rate,
        "term_months": term_months,
        "accrued_interest": round(accrued, 2),
        "maturity_amount": round(maturity_amount, 2),
    }


@activity.defn
async def check_savings_compliance(params: Dict[str, Any]) -> Dict[str, Any]:
    """Check savings compliance"""
    customer_id = params.get("customer_id")
    operation_type = params.get("operation_type")
    amount = params.get("amount", 0)
    logger.info(f"Checking savings compliance for {customer_id}")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                "http://compliance-service:8080/check",
                json={
                    "customer_id": customer_id,
                    "operation_type": operation_type,
                    "amount": amount,
                    "product_type": "savings",
                },
            )
            resp.raise_for_status()
            result = resp.json()
            return {
                "compliant": result.get("compliant", True),
                "flags": result.get("flags", []),
            }
        except httpx.HTTPError:
            return {"compliant": True, "flags": []}


@activity.defn
async def request_savings_authorization(params: Dict[str, Any]) -> Dict[str, Any]:
    """Request savings authorization"""
    customer_id = params["customer_id"]
    logger.info(f"Requesting savings authorization for {customer_id}")
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                "http://auth-service:8080/authorize",
                json={
                    "customer_id": customer_id,
                    "operation": "savings",
                    "account_id": params.get("account_id"),
                },
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Authorization error: {e}")
            return {"authorized": False, "reason": "Authorization service unavailable"}


@activity.defn
async def process_savings_ledger_operation(params: Dict[str, Any]) -> Dict[str, Any]:
    """Process savings operation in ledger"""
    logger.info(f"Processing savings ledger op for {params['account_id']}")
    ledger_id = str(uuid.uuid4())
    op_type = params.get("operation_type")
    debit = params["customer_id"] if op_type == "deposit" else params["account_id"]
    credit = params["account_id"] if op_type == "deposit" else params["customer_id"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                "http://tigerbeetle-service:8080/transfers",
                json={
                    "transfer_id": ledger_id,
                    "debit_account_id": debit,
                    "credit_account_id": credit,
                    "amount": int(params.get("amount", 0) * 100),
                    "currency": "NGN",
                    "reference": params["account_id"],
                    "metadata": {"type": "savings", "op": op_type},
                },
            )
            resp.raise_for_status()
            return {"success": True, "ledger_id": ledger_id}
        except httpx.HTTPError as e:
            logger.error(f"Savings ledger error: {e}")
            return {"success": False, "error": str(e)}


@activity.defn
async def update_savings_account(params: Dict[str, Any]) -> Dict[str, Any]:
    """Update savings account records"""
    account_id = params["account_id"]
    logger.info(f"Updating savings account {account_id}")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.put(
                f"http://savings-service:8080/accounts/{account_id}",
                json={
                    "operation_type": params["operation_type"],
                    "amount": params.get("amount"),
                    "ledger_id": params.get("ledger_id"),
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            logger.error(f"Savings account update error: {e}")
            return {"updated": False, "error": str(e)}


@activity.defn
async def schedule_interest_payments(params: Dict[str, Any]) -> Dict[str, Any]:
    """Schedule interest payments"""
    account_id = params["account_id"]
    rate = params.get("interest_rate", 0.05)
    term = params.get("term_months", 12)
    logger.info(f"Scheduling interest for account {account_id}")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            resp = await client.post(
                "http://scheduler-service:8080/schedules",
                json={
                    "type": "interest_payment",
                    "account_id": account_id,
                    "interest_rate": rate,
                    "frequency": "monthly",
                    "duration_months": term,
                    "start_date": datetime.utcnow().isoformat(),
                },
            )
            resp.raise_for_status()
            result = resp.json()
            return {"schedule_id": result.get("schedule_id"), "scheduled": True}
        except httpx.HTTPError as e:
            logger.error(f"Interest scheduling error: {e}")
            return {"scheduled": False, "error": str(e)}


@activity.defn
async def generate_savings_statement(params: Dict[str, Any]) -> Dict[str, Any]:
    """Generate savings statement"""
    account_id = params["account_id"]
    statement_id = f"SST-{account_id}-{datetime.utcnow().strftime('%Y%m%d')}"
    logger.info(f"Generating savings statement {statement_id}")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.post(
                "http://reporting-service:8080/statements",
                json={
                    "statement_id": statement_id,
                    "account_id": account_id,
                    "customer_id": params["customer_id"],
                    "type": "savings",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
        except httpx.HTTPError as e:
            logger.warning(f"Statement generation failed: {e}")
    return {"statement_id": statement_id, "statement_url": f"/statements/{statement_id}"}


@activity.defn
async def send_savings_notifications(params: Dict[str, Any]) -> Dict[str, Any]:
    """Send savings notifications"""
    logger.info(f"Sending savings notification for {params['customer_id']}")
    op_type = params.get("operation_type", "update")
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.post(
                "http://notification-service:8080/send",
                json={
                    "user_id": params["customer_id"],
                    "type": "savings",
                    "title": f"Savings {op_type.title()}",
                    "message": f"Savings account {op_type} processed successfully",
                    "channels": ["push", "sms"],
                },
            )
        except httpx.HTTPError as e:
            logger.warning(f"Savings notification failed: {e}")
    return {"sent": True}


@activity.defn
async def update_savings_analytics(params: Dict[str, Any]) -> Dict[str, Any]:
    """Update savings analytics"""
    logger.info(f"Updating savings analytics for {params['account_id']}")
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            await client.post(
                "http://analytics-service:8080/events",
                json={
                    "event_type": f"savings_{params.get('operation_type', 'update')}",
                    "account_id": params["account_id"],
                    "customer_id": params["customer_id"],
                    "amount": params.get("amount"),
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
        except httpx.HTTPError as e:
            logger.warning(f"Savings analytics update failed: {e}")
    return {"updated": True}

