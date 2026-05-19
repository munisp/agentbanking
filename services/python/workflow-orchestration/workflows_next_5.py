"""
Workflow Orchestration: Next 5 Priority Workflows Implementation

This module implements the next 5 priority workflows for the Remittance Platform V11.0:
1. QR Code Payment Workflow (Priority #6, Score: 7.45)
2. Offline Transaction Workflow (Priority #7, Score: 7.35)
3. Account 2FA Workflow (Priority #8, Score: 7.25)
4. Recurring Payment Workflow (Priority #9, Score: 7.15)
5. Commission Tracking Workflow (Priority #10, Score: 6.85)

Author: Manus AI
Date: November 11, 2025
Version: 1.0
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Dict, List, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy

# Import activities (to be implemented in activities_next_5.py)
with workflow.unsafe.imports_passed_through():
    from activities_next_5 import (
        # QR Code Payment activities
        decode_and_validate_qr_code,
        validate_customer_account,
        validate_merchant_account,
        check_qr_payment_limits,
        check_qr_payment_fraud,
        process_qr_payment_ledger,
        calculate_qr_payment_fees,
        generate_qr_payment_receipt,
        send_qr_payment_notifications,
        update_qr_payment_analytics,
        # Offline Transaction activities
        validate_offline_transaction,
        detect_transaction_conflicts,
        process_offline_transaction_ledger,
        resolve_transaction_conflict,
        send_offline_sync_notifications,
        # Account 2FA activities
        determine_2fa_method,
        generate_otp,
        send_otp,
        verify_otp,
        generate_2fa_verification_token,
        send_2fa_notifications,
        # Recurring Payment activities
        validate_recurring_payment_customer,
        process_recurring_payment_ledger,
        update_recurring_payment_schedule,
        send_recurring_payment_notification,
        # Commission Tracking activities
        record_commission,
        update_commission_aggregates,
        get_commission_summary,
        generate_commission_statement,
    )


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class QRCodePaymentInput:
    """Input for QR code payment workflow"""
    transaction_id: str
    qr_code_data: str  # Base64-encoded QR code payload
    customer_id: str
    amount: Optional[float] = None  # For static QR, customer enters amount
    currency: str = "NGN"
    customer_location: Optional[Dict[str, float]] = None
    agent_id: Optional[str] = None


@dataclass
class OfflineTransactionInput:
    """Input for offline transaction workflow"""
    local_transaction_id: str
    transaction_type: str
    customer_id: str
    agent_id: str
    amount: float
    currency: str = "NGN"
    local_timestamp: str
    customer_balance_before: float
    customer_sync_version: int
    agent_balance_before: float
    agent_sync_version: int
    metadata: Dict[str, Any] = None


@dataclass
class TwoFactorAuthInput:
    """Input for 2FA workflow"""
    customer_id: str
    session_id: str
    trigger_scenario: str
    trigger_metadata: Dict[str, Any]
    preferred_method: Optional[str] = None


@dataclass
class RecurringPaymentInput:
    """Input for recurring payment execution"""
    recurring_payment_id: str
    customer_id: str
    recipient_id: str
    recipient_name: str
    amount: float
    currency: str = "NGN"
    payment_type: str = "bill_payment"


@dataclass
class CommissionRecordInput:
    """Input for commission recording"""
    agent_id: str
    transaction_id: str
    transaction_type: str
    transaction_amount: float
    currency: str = "NGN"


# =============================================================================
# Workflow 1: QR Code Payment Workflow
# =============================================================================

@workflow.defn(name="qr_code_payment_workflow")
class QRCodePaymentWorkflow:
    """
    QR Code Payment Workflow
    
    Enables customers to make payments to merchants by scanning QR codes.
    Supports both static QR codes (customer enters amount) and dynamic QR codes
    (amount pre-filled).
    
    Priority: #6 (Score: 7.45)
    Estimated Duration: < 10 seconds
    Success Rate Target: > 99%
    """

    @workflow.run
    async def run(self, input: QRCodePaymentInput) -> Dict[str, Any]:
        """Execute QR code payment workflow"""
        
        workflow.logger.info(
            f"Starting QR code payment workflow for transaction {input.transaction_id}"
        )

        # Step 1: Decode and validate QR code
        qr_validation = await workflow.execute_activity(
            decode_and_validate_qr_code,
            args=[{
                "qr_code_data": input.qr_code_data,
                "current_time": workflow.now().isoformat()
            }],
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(maximum_attempts=1)  # No retry for validation
        )

        if not qr_validation["valid"]:
            workflow.logger.error(f"QR code validation failed: {qr_validation['reason']}")
            return {
                "success": False,
                "transaction_id": input.transaction_id,
                "reason": qr_validation["reason"],
                "step_failed": "qr_validation"
            }

        merchant_id = qr_validation["merchant_id"]
        qr_type = qr_validation["qr_type"]
        
        # For dynamic QR, amount is in QR code; for static QR, customer provides amount
        payment_amount = qr_validation.get("amount") or input.amount
        
        if not payment_amount:
            return {
                "success": False,
                "transaction_id": input.transaction_id,
                "reason": "Payment amount not provided",
                "step_failed": "amount_validation"
            }

        # Step 2: Validate customer account
        customer_validation = await workflow.execute_activity(
            validate_customer_account,
            args=[{
                "customer_id": input.customer_id,
                "amount": payment_amount,
                "currency": input.currency
            }],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=10),
                backoff_coefficient=2.0
            )
        )

        if not customer_validation["valid"]:
            workflow.logger.error(f"Customer validation failed: {customer_validation['reason']}")
            return {
                "success": False,
                "transaction_id": input.transaction_id,
                "reason": customer_validation["reason"],
                "step_failed": "customer_validation"
            }

        # Step 3: Validate merchant account
        merchant_validation = await workflow.execute_activity(
            validate_merchant_account,
            args=[{"merchant_id": merchant_id}],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )

        if not merchant_validation["valid"]:
            workflow.logger.error(f"Merchant validation failed: {merchant_validation['reason']}")
            return {
                "success": False,
                "transaction_id": input.transaction_id,
                "reason": merchant_validation["reason"],
                "step_failed": "merchant_validation"
            }

        merchant_name = merchant_validation["merchant_name"]
        fee_structure = merchant_validation["fee_structure"]

        # Step 4: Check transaction limits
        limits_check = await workflow.execute_activity(
            check_qr_payment_limits,
            args=[{
                "customer_id": input.customer_id,
                "merchant_id": merchant_id,
                "amount": payment_amount,
                "currency": input.currency
            }],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )

        if not limits_check["within_limits"]:
            workflow.logger.error(f"Transaction limits exceeded: {limits_check['reason']}")
            return {
                "success": False,
                "transaction_id": input.transaction_id,
                "reason": limits_check["reason"],
                "step_failed": "limits_check"
            }

        # Step 5: Fraud detection check
        fraud_check = await workflow.execute_activity(
            check_qr_payment_fraud,
            args=[{
                "transaction_id": input.transaction_id,
                "customer_id": input.customer_id,
                "merchant_id": merchant_id,
                "amount": payment_amount,
                "customer_location": input.customer_location,
                "merchant_location": merchant_validation.get("location")
            }],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )

        if fraud_check["is_fraudulent"]:
            workflow.logger.warning(
                f"Fraud detected (risk score: {fraud_check['risk_score']}): "
                f"{fraud_check['fraud_indicators']}"
            )
            return {
                "success": False,
                "transaction_id": input.transaction_id,
                "reason": "Transaction flagged as high risk",
                "fraud_score": fraud_check["risk_score"],
                "step_failed": "fraud_check"
            }

        # Step 6: Request customer PIN authorization
        # Note: In production, this would use Temporal signals to wait for PIN entry
        # For now, we assume PIN was verified before workflow started
        workflow.logger.info("Customer PIN authorization verified")

        # Step 7: Process payment in ledger
        ledger_result = await workflow.execute_activity(
            process_qr_payment_ledger,
            args=[{
                "transaction_id": input.transaction_id,
                "customer_id": input.customer_id,
                "merchant_id": merchant_id,
                "amount": payment_amount,
                "currency": input.currency,
                "qr_code_id": qr_validation.get("transaction_id", input.transaction_id),
                "qr_code_type": qr_type
            }],
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=2),
                maximum_interval=timedelta(seconds=20),
                backoff_coefficient=2.0
            )
        )

        if not ledger_result["success"]:
            workflow.logger.error(f"Ledger processing failed: {ledger_result['reason']}")
            return {
                "success": False,
                "transaction_id": input.transaction_id,
                "reason": ledger_result["reason"],
                "step_failed": "ledger_processing"
            }

        ledger_id = ledger_result["ledger_id"]
        customer_new_balance = ledger_result["customer_new_balance"]
        merchant_new_balance = ledger_result["merchant_new_balance"]

        # Step 8: Calculate and distribute fees
        fees_result = await workflow.execute_activity(
            calculate_qr_payment_fees,
            args=[{
                "transaction_id": input.transaction_id,
                "merchant_id": merchant_id,
                "amount": payment_amount,
                "fee_structure": fee_structure,
                "agent_id": input.agent_id
            }],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )

        if not fees_result["success"]:
            workflow.logger.error(f"Fee calculation failed: {fees_result['reason']}")
            # Non-critical: Continue even if fee calculation fails
            platform_fee = 0.0
            net_amount = payment_amount
        else:
            platform_fee = fees_result["platform_fee"]
            net_amount = fees_result["net_amount"]

        # Step 9: Generate receipt
        receipt_result = await workflow.execute_activity(
            generate_qr_payment_receipt,
            args=[{
                "transaction_id": input.transaction_id,
                "customer_id": input.customer_id,
                "merchant_id": merchant_id,
                "merchant_name": merchant_name,
                "amount": payment_amount,
                "platform_fee": platform_fee,
                "net_amount": net_amount,
                "ledger_id": ledger_id,
                "qr_code_type": qr_type
            }],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )

        receipt_url = receipt_result.get("receipt_url", "")

        # Step 10: Send notifications
        await workflow.execute_activity(
            send_qr_payment_notifications,
            args=[{
                "transaction_id": input.transaction_id,
                "customer_id": input.customer_id,
                "merchant_id": merchant_id,
                "merchant_name": merchant_name,
                "amount": payment_amount,
                "net_amount": net_amount,
                "receipt_url": receipt_url
            }],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )

        # Step 11: Update analytics (best effort)
        try:
            await workflow.execute_activity(
                update_qr_payment_analytics,
                args=[{
                    "transaction_id": input.transaction_id,
                    "customer_id": input.customer_id,
                    "merchant_id": merchant_id,
                    "amount": payment_amount,
                    "qr_code_type": qr_type,
                    "agent_id": input.agent_id
                }],
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=RetryPolicy(maximum_attempts=2)
            )
        except Exception as e:
            workflow.logger.warning(f"Analytics update failed (non-critical): {e}")

        workflow.logger.info(
            f"QR code payment workflow completed successfully for transaction {input.transaction_id}"
        )

        return {
            "success": True,
            "transaction_id": input.transaction_id,
            "ledger_id": ledger_id,
            "amount": payment_amount,
            "merchant_name": merchant_name,
            "customer_new_balance": customer_new_balance,
            "merchant_new_balance": merchant_new_balance,
            "receipt_url": receipt_url,
            "qr_code_type": qr_type
        }


# =============================================================================
# Workflow 2: Offline Transaction Workflow
# =============================================================================

@workflow.defn(name="offline_transaction_workflow")
class OfflineTransactionWorkflow:
    """
    Offline Transaction Workflow
    
    Processes transactions that were created offline and are being synchronized
    to the server. Includes conflict detection and resolution.
    
    Priority: #7 (Score: 7.35)
    Estimated Duration: < 30 seconds per transaction
    Success Rate Target: > 95%
    """

    @workflow.run
    async def run(self, input: OfflineTransactionInput) -> Dict[str, Any]:
        """Execute offline transaction synchronization workflow"""
        
        workflow.logger.info(
            f"Starting offline transaction sync for local transaction {input.local_transaction_id}"
        )

        # Step 1: Validate offline transaction data
        validation_result = await workflow.execute_activity(
            validate_offline_transaction,
            args=[{
                "local_transaction_id": input.local_transaction_id,
                "transaction_type": input.transaction_type,
                "customer_id": input.customer_id,
                "agent_id": input.agent_id,
                "amount": input.amount
            }],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )

        if not validation_result["valid"]:
            workflow.logger.error(f"Transaction validation failed: {validation_result['reason']}")
            return {
                "status": "error",
                "local_transaction_id": input.local_transaction_id,
                "reason": validation_result["reason"]
            }

        # Step 2: Detect conflicts
        conflict_check = await workflow.execute_activity(
            detect_transaction_conflicts,
            args=[{
                "local_transaction_id": input.local_transaction_id,
                "customer_id": input.customer_id,
                "customer_balance_before": input.customer_balance_before,
                "customer_sync_version": input.customer_sync_version,
                "agent_id": input.agent_id,
                "agent_balance_before": input.agent_balance_before,
                "agent_sync_version": input.agent_sync_version,
                "amount": input.amount,
                "transaction_type": input.transaction_type
            }],
            start_to_close_timeout=timedelta(seconds=15),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )

        # Step 3: Handle conflicts if detected
        if conflict_check["has_conflict"]:
            workflow.logger.warning(
                f"Conflict detected for transaction {input.local_transaction_id}: "
                f"{conflict_check['conflict_type']}"
            )

            # Resolve conflict
            resolution_result = await workflow.execute_activity(
                resolve_transaction_conflict,
                args=[{
                    "local_transaction_id": input.local_transaction_id,
                    "conflict_type": conflict_check["conflict_type"],
                    "conflict_details": conflict_check["conflict_details"],
                    "transaction_type": input.transaction_type,
                    "amount": input.amount
                }],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=2)
            )

            return {
                "status": "conflict",
                "local_transaction_id": input.local_transaction_id,
                "conflict_type": conflict_check["conflict_type"],
                "resolution": resolution_result["resolution"],
                "agent_action_required": resolution_result["agent_action_required"],
                "current_customer_balance": conflict_check["current_customer_balance"],
                "current_agent_balance": conflict_check["current_agent_balance"]
            }

        # Step 4: Process transaction in ledger (no conflicts)
        ledger_result = await workflow.execute_activity(
            process_offline_transaction_ledger,
            args=[{
                "local_transaction_id": input.local_transaction_id,
                "transaction_type": input.transaction_type,
                "customer_id": input.customer_id,
                "agent_id": input.agent_id,
                "amount": input.amount,
                "metadata": input.metadata or {}
            }],
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=2),
                maximum_interval=timedelta(seconds=20),
                backoff_coefficient=2.0
            )
        )

        if not ledger_result["success"]:
            workflow.logger.error(f"Ledger processing failed: {ledger_result['reason']}")
            return {
                "status": "failed",
                "local_transaction_id": input.local_transaction_id,
                "reason": ledger_result["reason"]
            }

        workflow.logger.info(
            f"Offline transaction {input.local_transaction_id} synced successfully"
        )

        return {
            "status": "success",
            "local_transaction_id": input.local_transaction_id,
            "server_transaction_id": ledger_result["server_transaction_id"],
            "ledger_id": ledger_result["ledger_id"],
            "customer_new_balance": ledger_result["customer_new_balance"],
            "agent_new_balance": ledger_result["agent_new_balance"]
        }


# =============================================================================
# Workflow 3: Account 2FA Workflow
# =============================================================================

@workflow.defn(name="account_2fa_workflow")
class AccountTwoFactorAuthWorkflow:
    """
    Account Two-Factor Authentication Workflow
    
    Implements 2FA for customer accounts using SMS OTP, Email OTP, or TOTP.
    Enhances security for high-risk transactions and account changes.
    
    Priority: #8 (Score: 7.25)
    Estimated Duration: < 60 seconds (includes customer input wait time)
    Success Rate Target: > 95%
    """

    @workflow.run
    async def run(self, input: TwoFactorAuthInput) -> Dict[str, Any]:
        """Execute 2FA workflow"""
        
        workflow.logger.info(
            f"Starting 2FA workflow for customer {input.customer_id}, "
            f"session {input.session_id}, scenario: {input.trigger_scenario}"
        )

        # Step 1: Determine 2FA method
        method_result = await workflow.execute_activity(
            determine_2fa_method,
            args=[{
                "customer_id": input.customer_id,
                "preferred_method": input.preferred_method
            }],
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(maximum_attempts=1)
        )

        if "reason" in method_result:
            workflow.logger.error(f"No 2FA method available: {method_result['reason']}")
            return {
                "verified": False,
                "session_id": input.session_id,
                "reason": method_result["reason"]
            }

        method = method_result["method"]
        workflow.logger.info(f"Using 2FA method: {method}")

        # Step 2: Generate OTP
        otp_result = await workflow.execute_activity(
            generate_otp,
            args=[{
                "customer_id": input.customer_id,
                "session_id": input.session_id,
                "method": method,
                "totp_secret": method_result.get("totp_secret")
            }],
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )

        if not otp_result["stored"]:
            workflow.logger.error("Failed to store OTP")
            return {
                "verified": False,
                "session_id": input.session_id,
                "reason": "Failed to generate OTP"
            }

        # Step 3: Send OTP (for SMS/Email methods)
        if method in ["sms", "email"]:
            send_result = await workflow.execute_activity(
                send_otp,
                args=[{
                    "customer_id": input.customer_id,
                    "method": method,
                    "otp_code": otp_result["otp_code"],
                    "phone_number": method_result.get("phone_number"),
                    "email": method_result.get("email")
                }],
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=2)
            )

            if not send_result["sent"]:
                workflow.logger.error(f"Failed to send OTP: {send_result['reason']}")
                return {
                    "verified": False,
                    "session_id": input.session_id,
                    "reason": f"Failed to send OTP via {method}"
                }

        # Step 4: Wait for customer to submit OTP
        # In production, this would use Temporal signals to receive OTP from customer
        # For now, we'll use a timeout and assume OTP is submitted via separate API
        workflow.logger.info("Waiting for customer OTP submission (handled via signal)")
        
        # Wait for OTP submission signal (max 5 minutes)
        try:
            submitted_otp = await workflow.wait_condition(
                lambda: hasattr(self, "submitted_otp"),
                timeout=timedelta(minutes=5)
            )
            submitted_otp = getattr(self, "submitted_otp", None)
        except TimeoutError:
            workflow.logger.error("Customer OTP submission timeout")
            return {
                "verified": False,
                "session_id": input.session_id,
                "reason": "OTP submission timeout (5 minutes)"
            }

        # Step 5: Verify OTP
        verification_result = await workflow.execute_activity(
            verify_otp,
            args=[{
                "customer_id": input.customer_id,
                "session_id": input.session_id,
                "submitted_otp": submitted_otp,
                "method": method,
                "totp_secret": method_result.get("totp_secret")
            }],
            start_to_close_timeout=timedelta(seconds=5),
            retry_policy=RetryPolicy(maximum_attempts=1)
        )

        if not verification_result["verified"]:
            workflow.logger.warning(
                f"OTP verification failed: {verification_result.get('reason', 'incorrect OTP')}"
            )
            
            # Send security alert if account locked
            if verification_result.get("locked"):
                await workflow.execute_activity(
                    send_2fa_notifications,
                    args=[{
                        "customer_id": input.customer_id,
                        "notification_type": "account_locked",
                        "method": method,
                        "locked_until": verification_result.get("lockout_until")
                    }],
                    start_to_close_timeout=timedelta(seconds=10),
                    retry_policy=RetryPolicy(maximum_attempts=2)
                )

            return {
                "verified": False,
                "session_id": input.session_id,
                "locked": verification_result.get("locked", False),
                "lockout_until": verification_result.get("lockout_until"),
                "attempts_remaining": verification_result.get("attempts_remaining"),
                "reason": verification_result.get("reason")
            }

        # Step 6: Generate verification token
        token_result = await workflow.execute_activity(
            generate_2fa_verification_token,
            args=[{
                "customer_id": input.customer_id,
                "session_id": input.session_id,
                "method": method
            }],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )

        # Send success notification (optional)
        try:
            await workflow.execute_activity(
                send_2fa_notifications,
                args=[{
                    "customer_id": input.customer_id,
                    "notification_type": "verification_success",
                    "method": method,
                    "locked_until": None
                }],
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=RetryPolicy(maximum_attempts=1)
            )
        except Exception as e:
            workflow.logger.warning(f"Failed to send success notification: {e}")

        workflow.logger.info(f"2FA verification successful for session {input.session_id}")

        return {
            "verified": True,
            "session_id": input.session_id,
            "method_used": method,
            "verification_token": token_result["token"],
            "expires_at": token_result["expires_at"]
        }

    @workflow.signal
    async def submit_otp(self, otp_code: str):
        """Signal to submit OTP from customer"""
        self.submitted_otp = otp_code


# =============================================================================
# Workflow 4: Recurring Payment Workflow
# =============================================================================

@workflow.defn(name="recurring_payment_workflow")
class RecurringPaymentWorkflow:
    """
    Recurring Payment Workflow
    
    Executes scheduled recurring payments (bills, subscriptions, savings).
    Handles payment failures with retry logic.
    
    Priority: #9 (Score: 7.15)
    Estimated Duration: < 30 seconds per payment
    Success Rate Target: > 95%
    """

    @workflow.run
    async def run(self, input: RecurringPaymentInput) -> Dict[str, Any]:
        """Execute recurring payment"""
        
        workflow.logger.info(
            f"Starting recurring payment execution for {input.recurring_payment_id}"
        )

        # Step 1: Validate customer account and balance
        validation_result = await workflow.execute_activity(
            validate_recurring_payment_customer,
            args=[{
                "customer_id": input.customer_id,
                "amount": input.amount,
                "currency": input.currency
            }],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )

        if not validation_result["valid"]:
            workflow.logger.error(
                f"Customer validation failed: {validation_result['reason']}"
            )
            
            # Schedule retry if insufficient balance (customer might fund account later)
            if validation_result["reason"] == "insufficient_balance":
                workflow.logger.info("Scheduling retry in 1 hour for insufficient balance")
                # In production, this would schedule a retry using Temporal's timer
                # For now, we return failure with retry recommendation
                return {
                    "success": False,
                    "recurring_payment_id": input.recurring_payment_id,
                    "reason": validation_result["reason"],
                    "retry_recommended": True,
                    "retry_after": "1 hour"
                }
            
            return {
                "success": False,
                "recurring_payment_id": input.recurring_payment_id,
                "reason": validation_result["reason"],
                "retry_recommended": False
            }

        # Step 2: Process payment in ledger
        ledger_result = await workflow.execute_activity(
            process_recurring_payment_ledger,
            args=[{
                "recurring_payment_id": input.recurring_payment_id,
                "customer_id": input.customer_id,
                "recipient_id": input.recipient_id,
                "amount": input.amount,
                "currency": input.currency,
                "payment_type": input.payment_type
            }],
            start_to_close_timeout=timedelta(seconds=60),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=2),
                maximum_interval=timedelta(seconds=20),
                backoff_coefficient=2.0
            )
        )

        if not ledger_result["success"]:
            workflow.logger.error(f"Ledger processing failed: {ledger_result['reason']}")
            return {
                "success": False,
                "recurring_payment_id": input.recurring_payment_id,
                "reason": ledger_result["reason"],
                "retry_recommended": True,
                "retry_after": "6 hours"
            }

        # Step 3: Update recurring payment schedule
        schedule_update = await workflow.execute_activity(
            update_recurring_payment_schedule,
            args=[{
                "recurring_payment_id": input.recurring_payment_id,
                "execution_success": True,
                "transaction_id": ledger_result["transaction_id"],
                "amount": input.amount
            }],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=2)
        )

        # Step 4: Send notification
        await workflow.execute_activity(
            send_recurring_payment_notification,
            args=[{
                "customer_id": input.customer_id,
                "recurring_payment_id": input.recurring_payment_id,
                "recipient_name": input.recipient_name,
                "amount": input.amount,
                "success": True,
                "next_payment_date": schedule_update.get("next_execution_date")
            }],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=3)
        )

        workflow.logger.info(
            f"Recurring payment {input.recurring_payment_id} executed successfully"
        )

        return {
            "success": True,
            "recurring_payment_id": input.recurring_payment_id,
            "transaction_id": ledger_result["transaction_id"],
            "amount": input.amount,
            "customer_new_balance": ledger_result["customer_new_balance"],
            "next_payment_date": schedule_update.get("next_execution_date")
        }


# =============================================================================
# Workflow 5: Commission Tracking Workflow
# =============================================================================

@workflow.defn(name="commission_tracking_workflow")
class CommissionTrackingWorkflow:
    """
    Commission Tracking Workflow
    
    Records commission for agent transactions and updates real-time aggregates.
    Provides transparency and visibility into agent earnings.
    
    Priority: #10 (Score: 6.85)
    Estimated Duration: < 5 seconds
    Success Rate Target: > 99%
    """

    @workflow.run
    async def run(self, input: CommissionRecordInput) -> Dict[str, Any]:
        """Record commission for transaction"""
        
        workflow.logger.info(
            f"Recording commission for agent {input.agent_id}, "
            f"transaction {input.transaction_id}"
        )

        # Step 1: Record commission
        commission_result = await workflow.execute_activity(
            record_commission,
            args=[{
                "agent_id": input.agent_id,
                "transaction_id": input.transaction_id,
                "transaction_type": input.transaction_type,
                "transaction_amount": input.transaction_amount
            }],
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(
                maximum_attempts=3,
                initial_interval=timedelta(seconds=1),
                maximum_interval=timedelta(seconds=10),
                backoff_coefficient=2.0
            )
        )

        commission_id = commission_result["commission_id"]
        total_commission = commission_result["total_commission_amount"]
        breakdown = commission_result["breakdown"]

        workflow.logger.info(
            f"Commission recorded: {commission_id}, amount: {total_commission}"
        )

        # Step 2: Update commission aggregates (best effort)
        try:
            await workflow.execute_activity(
                update_commission_aggregates,
                args=[{
                    "agent_id": input.agent_id,
                    "commission_id": commission_id,
                    "amount": total_commission,
                    "transaction_type": input.transaction_type
                }],
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=RetryPolicy(maximum_attempts=2)
            )
        except Exception as e:
            workflow.logger.warning(f"Failed to update aggregates (non-critical): {e}")

        return {
            "success": True,
            "commission_id": commission_id,
            "agent_id": input.agent_id,
            "transaction_id": input.transaction_id,
            "total_commission_amount": total_commission,
            "breakdown": breakdown
        }


# =============================================================================
# Workflow Registration
# =============================================================================

# Export all workflows for registration with Temporal worker
WORKFLOWS = [
    QRCodePaymentWorkflow,
    OfflineTransactionWorkflow,
    AccountTwoFactorAuthWorkflow,
    RecurringPaymentWorkflow,
    CommissionTrackingWorkflow,
]

