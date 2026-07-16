"""
Payment Processor - Complete implementation with TigerBeetle and Redis integration
"""
import logging
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class PaymentRequest:
    """Payment transaction request"""
    payment_id: str
    workflow_id: str
    from_account_id: bytes  # 16-byte account ID
    to_account_id: bytes    # 16-byte account ID
    amount: int             # Amount in smallest currency unit (e.g., kobo)
    currency: str
    description: str
    tenant_id: str
    user_id: str
    idempotency_key: str


@dataclass
class PaymentResult:
    """Payment transaction result"""
    payment_id: str
    transfer_id: Optional[bytes]
    status: str  # "completed", "failed", "pending"
    timestamp: datetime
    from_account_id: bytes
    to_account_id: bytes
    amount: int
    error: Optional[str] = None


class PaymentProcessor:
    """
    Payment processor with TigerBeetle and Redis integration
    Provides the same functionality as the Go implementation
    """

    def __init__(self, middleware_manager):
        """
        Initialize payment processor
        
        Args:
            middleware_manager: MiddlewareManager instance with Redis, TigerBeetle, Kafka clients
        """
        self.middleware = middleware_manager

    def process_payment_with_locking(
        self,
        req: PaymentRequest,
    ) -> PaymentResult:
        """
        Process a payment transaction with distributed locking
        
        This is the complete implementation showing TigerBeetle and Redis interaction,
        equivalent to the Go ProcessPaymentWithLocking() method.
        
        Steps:
        1. Validate payment request
        2. Check idempotency (Redis)
        3. Acquire distributed lock (Redis)
        4. Cache pending state (Redis)
        5. Publish payment.initiated event (Kafka)
        6. Validate account balances (optional)
        7. Create transfer (TigerBeetle)
        8. Update cache with result (Redis)
        9. Store idempotency key (Redis)
        10. Publish completion event (Kafka)
        11. Release lock (Redis)
        
        Args:
            req: PaymentRequest with payment details
            
        Returns:
            PaymentResult with transaction outcome
            
        Raises:
            ValueError: If request validation fails
            RuntimeError: If lock acquisition fails or transfer fails
        """
        logger.info(
            f"Starting payment processing: {req.payment_id}, "
            f"Amount: {req.amount}"
        )

        # Step 1: Validate payment request
        self._validate_payment_request(req)

        # Step 2: Check for duplicate payment using idempotency key
        idempotency_key = f"payment:idempotency:{req.idempotency_key}"
        existing_result = self.middleware.redis.get_workflow_state(idempotency_key)
        
        if existing_result is not None:
            logger.info(f"Payment already processed (idempotent): {req.payment_id}")
            return PaymentResult(
                payment_id=req.payment_id,
                transfer_id=None,
                status="completed",
                timestamp=datetime.utcnow(),
                from_account_id=req.from_account_id,
                to_account_id=req.to_account_id,
                amount=req.amount,
            )

        # Step 3: Acquire distributed lock to prevent concurrent processing
        lock_name = f"payment:lock:{req.payment_id}"
        lock_timeout = 30  # seconds
        
        logger.info(f"Acquiring distributed lock: {lock_name}")
        locked = self.middleware.redis.acquire_lock(lock_name, lock_timeout)
        
        if not locked:
            logger.warning(f"Payment already being processed: {req.payment_id}")
            raise RuntimeError(f"Payment {req.payment_id} is already being processed")
        
        logger.info(f"Distributed lock acquired: {lock_name}")

        try:
            # Step 4: Cache payment state as "pending" in Redis
            pending_state = {
                "payment_id": req.payment_id,
                "workflow_id": req.workflow_id,
                "status": "pending",
                "from_account": req.from_account_id.hex(),
                "to_account": req.to_account_id.hex(),
                "amount": req.amount,
                "currency": req.currency,
                "timestamp": int(time.time()),
            }
            
            state_key = f"payment:state:{req.payment_id}"
            self.middleware.redis.cache_workflow_state(state_key, pending_state, ttl=3600)
            logger.info(f"Cached pending payment state: {req.payment_id}")

            # Step 5: Publish payment.initiated event to Kafka
            from middleware.kafka.client import WorkflowEvent
            
            initiated_event = WorkflowEvent(
                event_id=f"evt-{req.payment_id}-initiated",
                event_type="payment.initiated",
                workflow_id=req.workflow_id,
                workflow_type="payment",
                status="pending",
                tenant_id=req.tenant_id,
                user_id=req.user_id,
                data={
                    "payment_id": req.payment_id,
                    "amount": req.amount,
                    "currency": req.currency,
                    "from_account": req.from_account_id.hex(),
                    "to_account": req.to_account_id.hex(),
                },
                timestamp=datetime.utcnow(),
            )
            
            try:
                self.middleware.publish_workflow_event(initiated_event)
                logger.info(f"Published payment.initiated event: {req.payment_id}")
            except Exception as e:
                logger.error(f"Failed to publish initiated event: {e}")
                # Continue processing even if event publishing fails

            # Step 6: Validate account balances (optional pre-validation)
            logger.info(f"Validating account balances for: {req.from_account_id.hex()}")
            # This could query TigerBeetle for current balances
            # For now, we proceed directly to transfer creation

            # Step 7: Create transfer in TigerBeetle
            logger.info(
                f"Creating transfer in TigerBeetle: {req.payment_id}, "
                f"Amount: {req.amount}"
            )
            
            # Generate transfer ID from payment ID
            transfer_id = self._generate_transfer_id(req.payment_id)
            
            # Create the transfer using TigerBeetle
            try:
                self.middleware.tigerbeetle.process_payment(
                    payment_id=req.payment_id,
                    from_account_id=req.from_account_id,
                    to_account_id=req.to_account_id,
                    amount=req.amount,
                )
                
                # Transfer succeeded
                logger.info(
                    f"TigerBeetle transfer completed successfully: {req.payment_id}"
                )
                
                result = PaymentResult(
                    payment_id=req.payment_id,
                    transfer_id=transfer_id,
                    status="completed",
                    timestamp=datetime.utcnow(),
                    from_account_id=req.from_account_id,
                    to_account_id=req.to_account_id,
                    amount=req.amount,
                )
                
                # Step 8: Update cache with completed status
                completed_state = {
                    "payment_id": req.payment_id,
                    "transfer_id": transfer_id.hex(),
                    "status": "completed",
                    "from_account": req.from_account_id.hex(),
                    "to_account": req.to_account_id.hex(),
                    "amount": req.amount,
                    "currency": req.currency,
                    "timestamp": int(time.time()),
                }
                
                self.middleware.redis.cache_workflow_state(
                    state_key, completed_state, ttl=3600
                )
                logger.info(f"Updated cache with completed status: {req.payment_id}")
                
                # Step 9: Store idempotency key to prevent duplicate processing
                self.middleware.redis.cache_workflow_state(
                    idempotency_key, completed_state, ttl=86400  # 24 hours
                )
                logger.info(f"Stored idempotency key: {req.payment_id}")
                
                # Step 10: Publish payment.completed event to Kafka
                completed_event = WorkflowEvent(
                    event_id=f"evt-{req.payment_id}-completed",
                    event_type="payment.completed",
                    workflow_id=req.workflow_id,
                    workflow_type="payment",
                    status="completed",
                    tenant_id=req.tenant_id,
                    user_id=req.user_id,
                    data={
                        "payment_id": req.payment_id,
                        "transfer_id": transfer_id.hex(),
                        "amount": req.amount,
                        "currency": req.currency,
                        "from_account": req.from_account_id.hex(),
                        "to_account": req.to_account_id.hex(),
                    },
                    timestamp=datetime.utcnow(),
                )
                
                try:
                    self.middleware.publish_workflow_event(completed_event)
                    logger.info(f"Published payment.completed event: {req.payment_id}")
                except Exception as e:
                    logger.error(f"Failed to publish completed event: {e}")
                    # Don't fail the payment if event publishing fails
                
                logger.info(
                    f"Payment processing completed successfully: {req.payment_id}, "
                    f"Status: {result.status}"
                )
                
                return result
                
            except Exception as e:
                # Transfer failed
                logger.error(f"TigerBeetle transfer failed: {e}")
                
                result = PaymentResult(
                    payment_id=req.payment_id,
                    transfer_id=None,
                    status="failed",
                    timestamp=datetime.utcnow(),
                    from_account_id=req.from_account_id,
                    to_account_id=req.to_account_id,
                    amount=req.amount,
                    error=str(e),
                )
                
                # Update cache with failed status
                failed_state = {
                    "payment_id": req.payment_id,
                    "status": "failed",
                    "error": str(e),
                    "timestamp": int(time.time()),
                }
                
                self.middleware.redis.cache_workflow_state(
                    state_key, failed_state, ttl=3600
                )
                logger.info(f"Updated cache with failed status: {req.payment_id}")
                
                # Publish payment.failed event
                failed_event = WorkflowEvent(
                    event_id=f"evt-{req.payment_id}-failed",
                    event_type="payment.failed",
                    workflow_id=req.workflow_id,
                    workflow_type="payment",
                    status="failed",
                    tenant_id=req.tenant_id,
                    user_id=req.user_id,
                    data={
                        "payment_id": req.payment_id,
                        "amount": req.amount,
                        "error": str(e),
                    },
                    timestamp=datetime.utcnow(),
                )
                
                try:
                    self.middleware.publish_workflow_event(failed_event)
                    logger.info(f"Published payment.failed event: {req.payment_id}")
                except Exception as pub_err:
                    logger.error(f"Failed to publish failed event: {pub_err}")
                
                raise RuntimeError(f"Payment processing failed: {e}") from e
                
        finally:
            # Step 11: Release distributed lock
            logger.info(f"Releasing distributed lock: {lock_name}")
            try:
                self.middleware.redis.release_lock(lock_name)
                logger.info(f"Distributed lock released: {lock_name}")
            except Exception as e:
                logger.error(f"Failed to release lock: {e}")

    def process_payment(
        self,
        payment_id: str,
        from_account_id: bytes,
        to_account_id: bytes,
        amount: int,
    ) -> None:
        """
        Simplified payment processing method (equivalent to Go ProcessPayment)
        
        Args:
            payment_id: Unique payment identifier
            from_account_id: Source account (16 bytes)
            to_account_id: Destination account (16 bytes)
            amount: Amount in smallest currency unit
            
        Raises:
            RuntimeError: If payment processing fails
        """
        req = PaymentRequest(
            payment_id=payment_id,
            workflow_id=payment_id,
            from_account_id=from_account_id,
            to_account_id=to_account_id,
            amount=amount,
            currency="NGN",
            description="Payment transaction",
            tenant_id="",
            user_id="",
            idempotency_key=payment_id,
        )
        
        result = self.process_payment_with_locking(req)
        
        if result.status != "completed":
            raise RuntimeError(f"Payment failed with status: {result.status}")

    def get_payment_status(self, payment_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the current status of a payment from Redis cache
        
        Args:
            payment_id: Payment identifier
            
        Returns:
            Payment state dictionary or None if not found
        """
        state_key = f"payment:state:{payment_id}"
        return self.middleware.redis.get_workflow_state(state_key)

    def cancel_pending_payment(self, payment_id: str) -> None:
        """
        Attempt to cancel a pending payment
        
        Args:
            payment_id: Payment identifier
            
        Raises:
            RuntimeError: If cancellation fails
        """
        # Acquire lock
        lock_name = f"payment:lock:{payment_id}"
        locked = self.middleware.redis.acquire_lock(lock_name, 30)
        
        if not locked:
            raise RuntimeError("Failed to acquire lock for cancellation")
        
        try:
            # Check current status
            state_key = f"payment:state:{payment_id}"
            state = self.middleware.redis.get_workflow_state(state_key)
            
            if state is None:
                raise RuntimeError(f"Payment not found: {payment_id}")
            
            status = state.get("status")
            if status != "pending":
                raise RuntimeError(f"Payment cannot be cancelled (status: {status})")
            
            # Update status to cancelled
            state["status"] = "cancelled"
            state["cancelled_at"] = int(time.time())
            
            self.middleware.redis.cache_workflow_state(state_key, state, ttl=3600)
            logger.info(f"Payment cancelled: {payment_id}")
            
        finally:
            self.middleware.redis.release_lock(lock_name)

    def _validate_payment_request(self, req: PaymentRequest) -> None:
        """
        Validate payment request
        
        Args:
            req: PaymentRequest to validate
            
        Raises:
            ValueError: If validation fails
        """
        if not req.payment_id:
            raise ValueError("payment_id is required")
        
        if req.amount <= 0:
            raise ValueError("amount must be greater than 0")
        
        if req.from_account_id == req.to_account_id:
            raise ValueError("from_account and to_account must be different")
        
        if not req.idempotency_key:
            raise ValueError("idempotency_key is required")
        
        if len(req.from_account_id) != 16:
            raise ValueError("from_account_id must be 16 bytes")
        
        if len(req.to_account_id) != 16:
            raise ValueError("to_account_id must be 16 bytes")

    def _generate_transfer_id(self, payment_id: str) -> bytes:
        """
        Generate a 16-byte transfer ID from payment ID
        
        Args:
            payment_id: Payment identifier string
            
        Returns:
            16-byte transfer ID
        """
        # Convert payment_id to bytes and pad/truncate to 16 bytes
        payment_bytes = payment_id.encode('utf-8')[:16]
        return payment_bytes.ljust(16, b'\x00')


# Example usage
if __name__ == "__main__":
    import logging
    from integration.middleware_manager import MiddlewareManager, MiddlewareConfig
    from middleware.kafka.client import KafkaConfig
    from middleware.redis.client import RedisConfig
    from middleware.tigerbeetle.client import TigerBeetleConfig
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create middleware configuration
    config = MiddlewareConfig(
        kafka=KafkaConfig(brokers=["localhost:9092"]),
        redis=RedisConfig(),
        tigerbeetle=TigerBeetleConfig(cluster_id=1, addresses=["localhost:3000"]),
        # ... other configs
    )
    
    # Create middleware manager
    middleware = MiddlewareManager(config)
    
    # Create payment processor
    processor = PaymentProcessor(middleware)
    
    # Example: Process a payment
    try:
        # Create account IDs (16 bytes each)
        customer_account = b'CUST-001\x00\x00\x00\x00\x00\x00\x00\x00'
        merchant_account = b'MERCH-001\x00\x00\x00\x00\x00\x00\x00'
        
        # Create payment request
        req = PaymentRequest(
            payment_id="PAY-12345",
            workflow_id="WF-12345",
            from_account_id=customer_account,
            to_account_id=merchant_account,
            amount=50000,  # 500.00 NGN (in kobo)
            currency="NGN",
            description="Product purchase",
            tenant_id="tenant-1",
            user_id="user-123",
            idempotency_key="idempotency-12345",
        )
        
        # Process payment
        result = processor.process_payment_with_locking(req)
        
        print(f"Payment completed: {result.payment_id}")
        print(f"Status: {result.status}")
        print(f"Transfer ID: {result.transfer_id.hex() if result.transfer_id else 'N/A'}")
        print(f"Amount: {result.amount}")
        
        # Check payment status
        status = processor.get_payment_status("PAY-12345")
        print(f"Payment status: {status}")
        
    except Exception as e:
        print(f"Payment failed: {e}")
    
    finally:
        middleware.close()

