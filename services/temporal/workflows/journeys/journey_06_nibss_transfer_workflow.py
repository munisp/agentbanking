"""
NIBSS Transfer Temporal Workflow
Journey: journey_06_nibss_transfer
Production-ready workflow with error handling and compensation
"""

from temporalio import workflow
from temporalio.common import RetryPolicy
from datetime import timedelta
from typing import Dict, Any
import logging

# Import activities
with workflow.unsafe.imports_passed_through():
    from ...activities.journeys.journey_06_nibss_transfer_activities import (
        validate_input,
        transferservice_activity,
        nibssservice_activity,
        walletservice_activity,
        frauddetectionservice_activity,
        send_notification
    )

logger = logging.getLogger(__name__)

@workflow.defn(name="NIBSSTransferWorkflow")
class NIBSSTransferWorkflow:
    """
    Orchestrates NIBSS transfer process with the following steps:
    1. Validate input
    2. Check fraud detection
    3. Validate accounts
    4. Check wallet balance
    5. Initiate NIBSS transfer
    6. Update wallet balances
    7. Send notifications
    """
    
    def __init__(self):
        self.transfer_id: str = ""
        self.status: str = "pending"
        self.error_message: str = ""
    
    @workflow.run
    async def run(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main workflow execution
        
        Args:
            input_data: Transfer request data containing:
                - user_id: User ID
                - source_account: Source account number
                - destination_account: Destination account number
                - destination_bank_code: Bank code
                - amount: Transfer amount
                - currency: Currency code
                - narration: Transfer description
                - beneficiary_name: Beneficiary name
                
        Returns:
            Workflow result with transfer details
        """
        workflow.logger.info(f"Starting NIBSS transfer workflow for user: {input_data.get('user_id')}")
        
        # Retry policy for activities
        retry_policy = RetryPolicy(
            initial_interval=timedelta(seconds=1),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=30),
            maximum_attempts=3
        )
        
        try:
            # Step 1: Validate input
            workflow.logger.info("Step 1: Validating input")
            is_valid = await workflow.execute_activity(
                validate_input,
                input_data,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy
            )
            
            if not is_valid:
                raise ValueError("Input validation failed")
            
            # Step 2: Fraud detection check
            workflow.logger.info("Step 2: Performing fraud detection")
            fraud_check_result = await workflow.execute_activity(
                frauddetectionservice_activity,
                {
                    "user_id": input_data["user_id"],
                    "amount": input_data["amount"],
                    "destination_account": input_data["destination_account"],
                    "transaction_type": "nibss_transfer"
                },
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy
            )
            
            if not fraud_check_result.get("passed", False):
                self.status = "fraud_detected"
                self.error_message = "Transaction flagged by fraud detection"
                
                # Send fraud alert notification
                await workflow.execute_activity(
                    send_notification,
                    args=[input_data["user_id"], "fraud_alert"],
                    start_to_close_timeout=timedelta(seconds=10)
                )
                
                return {
                    "status": "failed",
                    "reason": "fraud_detected",
                    "message": self.error_message
                }
            
            # Step 3: Check wallet balance
            workflow.logger.info("Step 3: Checking wallet balance")
            wallet_check = await workflow.execute_activity(
                walletservice_activity,
                {
                    "action": "check_balance",
                    "user_id": input_data["user_id"],
                    "account": input_data["source_account"],
                    "required_amount": input_data["amount"]
                },
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy
            )
            
            if not wallet_check.get("sufficient", False):
                self.status = "insufficient_balance"
                self.error_message = "Insufficient balance"
                
                await workflow.execute_activity(
                    send_notification,
                    args=[input_data["user_id"], "insufficient_balance"],
                    start_to_close_timeout=timedelta(seconds=10)
                )
                
                return {
                    "status": "failed",
                    "reason": "insufficient_balance",
                    "message": self.error_message
                }
            
            # Step 4: Debit wallet (with saga compensation)
            workflow.logger.info("Step 4: Debiting wallet")
            debit_result = await workflow.execute_activity(
                walletservice_activity,
                {
                    "action": "debit",
                    "user_id": input_data["user_id"],
                    "account": input_data["source_account"],
                    "amount": input_data["amount"],
                    "reference": f"NIBSS_{workflow.info().workflow_id}"
                },
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=retry_policy
            )
            
            if not debit_result.get("success", False):
                self.status = "debit_failed"
                self.error_message = "Failed to debit wallet"
                return {
                    "status": "failed",
                    "reason": "debit_failed",
                    "message": self.error_message
                }
            
            # Step 5: Initiate NIBSS transfer
            workflow.logger.info("Step 5: Initiating NIBSS transfer")
            try:
                nibss_result = await workflow.execute_activity(
                    nibssservice_activity,
                    {
                        "action": "initiate_transfer",
                        "source_account": input_data["source_account"],
                        "destination_account": input_data["destination_account"],
                        "destination_bank_code": input_data["destination_bank_code"],
                        "amount": input_data["amount"],
                        "narration": input_data.get("narration", "Transfer"),
                        "beneficiary_name": input_data["beneficiary_name"],
                        "reference": f"NIBSS_{workflow.info().workflow_id}"
                    },
                    start_to_close_timeout=timedelta(seconds=60),
                    retry_policy=RetryPolicy(
                        initial_interval=timedelta(seconds=2),
                        backoff_coefficient=2.0,
                        maximum_interval=timedelta(seconds=60),
                        maximum_attempts=5
                    )
                )
                
                self.transfer_id = nibss_result.get("transaction_id", "")
                
                # Check if transfer was successful
                if nibss_result.get("status") != "00":  # NIBSS success code
                    # Compensate: Refund wallet
                    workflow.logger.warning("NIBSS transfer failed, compensating")
                    await workflow.execute_activity(
                        walletservice_activity,
                        {
                            "action": "credit",
                            "user_id": input_data["user_id"],
                            "account": input_data["source_account"],
                            "amount": input_data["amount"],
                            "reference": f"REFUND_{workflow.info().workflow_id}"
                        },
                        start_to_close_timeout=timedelta(seconds=30)
                    )
                    
                    self.status = "nibss_failed"
                    self.error_message = nibss_result.get("message", "NIBSS transfer failed")
                    
                    await workflow.execute_activity(
                        send_notification,
                        args=[input_data["user_id"], "transfer_failed"],
                        start_to_close_timeout=timedelta(seconds=10)
                    )
                    
                    return {
                        "status": "failed",
                        "reason": "nibss_failed",
                        "message": self.error_message,
                        "nibss_response": nibss_result
                    }
                
            except Exception as e:
                # Compensate: Refund wallet on NIBSS failure
                workflow.logger.error(f"NIBSS transfer exception: {str(e)}, compensating")
                await workflow.execute_activity(
                    walletservice_activity,
                    {
                        "action": "credit",
                        "user_id": input_data["user_id"],
                        "account": input_data["source_account"],
                        "amount": input_data["amount"],
                        "reference": f"REFUND_{workflow.info().workflow_id}"
                    },
                    start_to_close_timeout=timedelta(seconds=30)
                )
                
                self.status = "error"
                self.error_message = str(e)
                
                return {
                    "status": "failed",
                    "reason": "exception",
                    "message": str(e)
                }
            
            # Step 6: Record transaction
            workflow.logger.info("Step 6: Recording transaction")
            await workflow.execute_activity(
                transferservice_activity,
                {
                    "action": "record_transaction",
                    "user_id": input_data["user_id"],
                    "type": "nibss_transfer",
                    "amount": input_data["amount"],
                    "currency": input_data.get("currency", "NGN"),
                    "status": "completed",
                    "nibss_transaction_id": self.transfer_id,
                    "reference": f"NIBSS_{workflow.info().workflow_id}"
                },
                start_to_close_timeout=timedelta(seconds=30)
            )
            
            # Step 7: Send success notification
            workflow.logger.info("Step 7: Sending success notification")
            await workflow.execute_activity(
                send_notification,
                args=[input_data["user_id"], "transfer_success"],
                start_to_close_timeout=timedelta(seconds=10)
            )
            
            self.status = "completed"
            
            workflow.logger.info(f"NIBSS transfer workflow completed: {self.transfer_id}")
            
            return {
                "status": "completed",
                "transfer_id": self.transfer_id,
                "nibss_transaction_id": nibss_result.get("transaction_id"),
                "amount": input_data["amount"],
                "currency": input_data.get("currency", "NGN"),
                "timestamp": nibss_result.get("timestamp"),
                "message": "Transfer completed successfully"
            }
            
        except Exception as e:
            workflow.logger.error(f"Workflow error: {str(e)}")
            self.status = "error"
            self.error_message = str(e)
            
            return {
                "status": "failed",
                "reason": "workflow_error",
                "message": str(e)
            }
    
    @workflow.query
    def get_status(self) -> str:
        """Query current workflow status"""
        return self.status
    
    @workflow.query
    def get_transfer_id(self) -> str:
        """Query transfer ID"""
        return self.transfer_id
    
    @workflow.signal
    def cancel(self):
        """Signal to cancel the workflow"""
        workflow.logger.info("Cancel signal received")
        self.status = "cancelled"
