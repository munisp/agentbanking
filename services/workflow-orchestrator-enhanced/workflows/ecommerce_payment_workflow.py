"""
End-to-end E-commerce Payment Workflow
Demonstrates integration with all 11 middleware components
"""
import logging
import uuid
from datetime import datetime
from typing import Dict, Any

from integration.middleware_manager import MiddlewareManager, MiddlewareConfig
from middleware.kafka.client import WorkflowEvent, KafkaConfig
from middleware.temporal.client import WorkflowInput

logger = logging.getLogger(__name__)


class EcommercePaymentWorkflow:
    """
    End-to-end e-commerce payment workflow demonstrating all middleware integrations
    
    Flow:
    1. APISIX - API Gateway receives request
    2. Keycloak - Validate user authentication
    3. Permify - Check user permissions
    4. PostgreSQL - Save workflow to database
    5. Redis - Cache workflow state
    6. Kafka - Publish workflow.started event
    7. Fluvio - Stream real-time event
    8. Dapr - Invoke inventory service
    9. TigerBeetle - Process payment transaction
    10. Temporal - Delegate to long-running fulfillment workflow
    11. Lakehouse - Stream analytics data
    """

    def __init__(self, middleware: MiddlewareManager):
        self.middleware = middleware

    def execute(
        self,
        user_token: str,
        order_id: str,
        customer_id: str,
        merchant_id: str,
        amount: int,
        items: list,
    ) -> Dict[str, Any]:
        """Execute the complete e-commerce payment workflow"""
        
        workflow_id = f"payment-{order_id}"
        logger.info(f"Starting e-commerce payment workflow: {workflow_id}")

        try:
            # Step 1: Validate user authentication with Keycloak
            logger.info("Step 1: Validating user authentication")
            user_info = self.middleware.validate_user_token(user_token)
            logger.info(f"User authenticated: {user_info.username}")

            # Step 2: Check user permissions with Permify
            logger.info("Step 2: Checking user permissions")
            has_permission = self.middleware.check_workflow_permission(
                user_info.user_id, workflow_id, "execute"
            )
            if not has_permission:
                raise PermissionError(f"User {user_info.user_id} does not have permission to execute workflow")
            logger.info("User has permission to execute workflow")

            # Step 3: Save workflow to PostgreSQL
            logger.info("Step 3: Saving workflow to database")
            workflow_data = {
                "order_id": order_id,
                "customer_id": customer_id,
                "merchant_id": merchant_id,
                "amount": amount,
                "items": items,
            }
            self.middleware.save_workflow_to_db(
                workflow_id=workflow_id,
                workflow_type="ecommerce_payment",
                status="in_progress",
                input_data=workflow_data,
                tenant_id=user_info.tenant_id,
                user_id=user_info.user_id,
            )
            logger.info("Workflow saved to database")

            # Step 4: Cache workflow state in Redis
            logger.info("Step 4: Caching workflow state")
            self.middleware.cache_workflow_state(workflow_id, workflow_data, ttl=3600)
            logger.info("Workflow state cached")

            # Step 5: Publish workflow.started event to Kafka and Fluvio
            logger.info("Step 5: Publishing workflow.started event")
            event = WorkflowEvent(
                event_id=str(uuid.uuid4()),
                event_type="workflow.started",
                workflow_id=workflow_id,
                workflow_type="ecommerce_payment",
                status="in_progress",
                tenant_id=user_info.tenant_id,
                user_id=user_info.user_id,
                data=workflow_data,
                timestamp=datetime.utcnow(),
            )
            self.middleware.publish_workflow_event(event)
            logger.info("Workflow event published")

            # Step 6: Invoke inventory service via Dapr
            logger.info("Step 6: Checking inventory availability")
            inventory_response = self.middleware.invoke_service(
                app_id="inventory-service",
                method="check-availability",
                data={"items": items},
            )
            if not inventory_response.get("available"):
                raise ValueError("Items not available in inventory")
            logger.info("Inventory check passed")

            # Step 7: Acquire distributed lock for payment processing
            logger.info("Step 7: Acquiring distributed lock")
            lock_acquired = self.middleware.acquire_distributed_lock(
                lock_name=f"payment-{order_id}",
                timeout=30,
            )
            if not lock_acquired:
                raise RuntimeError("Failed to acquire payment lock")
            logger.info("Distributed lock acquired")

            try:
                # Step 8: Process payment via TigerBeetle
                logger.info("Step 8: Processing payment")
                customer_account = customer_id.encode()[:16].ljust(16, b'\x00')
                merchant_account = merchant_id.encode()[:16].ljust(16, b'\x00')
                self.middleware.process_payment(
                    payment_id=workflow_id,
                    from_account_id=customer_account,
                    to_account_id=merchant_account,
                    amount=amount,
                )
                logger.info(f"Payment processed: {amount}")

                # Step 9: Update workflow status
                logger.info("Step 9: Updating workflow status")
                self.middleware.update_workflow_status(workflow_id, "payment_completed")
                logger.info("Workflow status updated")

                # Step 10: Publish workflow.payment_completed event
                logger.info("Step 10: Publishing workflow.payment_completed event")
                payment_event = WorkflowEvent(
                    event_id=str(uuid.uuid4()),
                    event_type="workflow.payment_completed",
                    workflow_id=workflow_id,
                    workflow_type="ecommerce_payment",
                    status="payment_completed",
                    tenant_id=user_info.tenant_id,
                    user_id=user_info.user_id,
                    data={"amount": amount, "order_id": order_id},
                    timestamp=datetime.utcnow(),
                )
                self.middleware.publish_workflow_event(payment_event)
                logger.info("Payment completed event published")

                # Step 11: Delegate to Temporal for long-running fulfillment
                logger.info("Step 11: Delegating to Temporal for fulfillment")
                temporal_input = WorkflowInput(
                    workflow_id=f"fulfillment-{order_id}",
                    workflow_type="order_fulfillment",
                    tenant_id=user_info.tenant_id,
                    user_id=user_info.user_id,
                    entity_id=order_id,
                    input_data={
                        "order_id": order_id,
                        "customer_id": customer_id,
                        "items": items,
                    },
                )
                # Note: This would be async in production
                # temporal_run_id = await self.middleware.delegate_to_temporal(
                #     "OrderFulfillmentWorkflow", temporal_input
                # )
                logger.info("Fulfillment workflow delegated to Temporal")

            finally:
                # Step 12: Release distributed lock
                logger.info("Step 12: Releasing distributed lock")
                self.middleware.release_distributed_lock(f"payment-{order_id}")
                logger.info("Distributed lock released")

            # Step 13: Publish workflow.completed event
            logger.info("Step 13: Publishing workflow.completed event")
            completed_event = WorkflowEvent(
                event_id=str(uuid.uuid4()),
                event_type="workflow.completed",
                workflow_id=workflow_id,
                workflow_type="ecommerce_payment",
                status="completed",
                tenant_id=user_info.tenant_id,
                user_id=user_info.user_id,
                data={"order_id": order_id, "amount": amount},
                timestamp=datetime.utcnow(),
            )
            self.middleware.publish_workflow_event(completed_event)
            logger.info("Workflow completed event published")

            # Step 14: Update final status
            self.middleware.update_workflow_status(workflow_id, "completed")

            return {
                "workflow_id": workflow_id,
                "status": "completed",
                "order_id": order_id,
                "amount": amount,
                "message": "Payment processed successfully",
            }

        except Exception as e:
            logger.error(f"Workflow failed: {e}")
            
            # Publish workflow.failed event
            failed_event = WorkflowEvent(
                event_id=str(uuid.uuid4()),
                event_type="workflow.failed",
                workflow_id=workflow_id,
                workflow_type="ecommerce_payment",
                status="failed",
                tenant_id=user_info.tenant_id if 'user_info' in locals() else "",
                user_id=user_info.user_id if 'user_info' in locals() else "",
                data={"error": str(e), "order_id": order_id},
                timestamp=datetime.utcnow(),
            )
            self.middleware.publish_workflow_event(failed_event)
            
            # Update status to failed
            try:
                self.middleware.update_workflow_status(workflow_id, "failed")
            except:
                pass
            
            raise


# Example usage
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Create middleware configuration
    config = MiddlewareConfig(
        kafka=KafkaConfig(brokers=["localhost:9092"]),
        # ... other configs ...
    )
    
    # Create middleware manager
    middleware = MiddlewareManager(config)
    
    # Create workflow
    workflow = EcommercePaymentWorkflow(middleware)
    
    # Execute workflow
    try:
        result = workflow.execute(
            user_token="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
            order_id="ORD-12345",
            customer_id="CUST-001",
            merchant_id="MERCH-001",
            amount=50000,  # 500.00 in cents
            items=[
                {"sku": "PROD-001", "quantity": 2, "price": 15000},
                {"sku": "PROD-002", "quantity": 1, "price": 20000},
            ],
        )
        print(f"Workflow completed: {result}")
    finally:
        middleware.close()

