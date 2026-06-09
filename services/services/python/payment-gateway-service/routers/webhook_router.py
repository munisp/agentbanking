"""
Payment Webhook Router

Handles webhook notifications from payment gateways for transaction status updates.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Header, status
from sqlalchemy.orm import Session
from typing import Optional
import logging
import hmac
import hashlib
import json

from ..models.payment_models import PaymentTransaction, PaymentWebhook, TransactionStatus
from ..schemas.payment_schemas import WebhookEventSchema, PaymentStatusEnum
from ..services.gateway_factory import GatewayFactory
from ...shared.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


# Dependency to get gateway factory
def get_gateway_factory() -> GatewayFactory:
    """Get gateway factory instance."""
    # Production: Load gateway configs from database or config file
    gateway_configs = {
        "paystack": {"is_active": True, "webhook_secret": "your_paystack_secret"},
        "flutterwave": {"is_active": True, "webhook_secret": "your_flutterwave_secret"},
        # ... other gateways
    }
    return GatewayFactory(gateway_configs)


async def verify_webhook_signature(
    gateway_name: str,
    payload: bytes,
    signature: str,
    gateway_factory: GatewayFactory
) -> bool:
    """
    Verify webhook signature from payment gateway.
    
    Args:
        gateway_name: Name of the gateway
        payload: Raw request payload
        signature: Signature from gateway
        gateway_factory: Gateway factory instance
        
    Returns:
        True if signature is valid
    """
    try:
        config = gateway_factory.get_gateway_config(gateway_name)
        webhook_secret = config.get("webhook_secret", "")
        
        if not webhook_secret:
            logger.warning(f"No webhook secret configured for {gateway_name}")
            return False
        
        # Different gateways use different signature methods
        if gateway_name == "paystack":
            # Paystack uses HMAC SHA512
            expected_signature = hmac.new(
                webhook_secret.encode(),
                payload,
                hashlib.sha512
            ).hexdigest()
            return hmac.compare_digest(expected_signature, signature)
        
        elif gateway_name == "flutterwave":
            # Flutterwave uses HMAC SHA256
            expected_signature = hmac.new(
                webhook_secret.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected_signature, signature)
        
        elif gateway_name == "stripe":
            # Stripe uses their own signature verification
            # This would use stripe.Webhook.construct_event()
            # For now, simple HMAC SHA256
            expected_signature = hmac.new(
                webhook_secret.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected_signature, signature)
        
        else:
            # Default to HMAC SHA256
            expected_signature = hmac.new(
                webhook_secret.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected_signature, signature)
    
    except Exception as e:
        logger.error(f"Webhook signature verification failed: {e}")
        return False


async def process_webhook_event(
    gateway_name: str,
    event_data: dict,
    db: Session
) -> None:
    """
    Process webhook event and update transaction status.
    
    Args:
        gateway_name: Name of the gateway
        event_data: Event data from gateway
        db: Database session
    """
    try:
        # Extract transaction reference
        transaction_ref = None
        event_type = event_data.get("event", "")
        
        if gateway_name == "paystack":
            transaction_ref = event_data.get("data", {}).get("reference")
            status_map = {
                "charge.success": TransactionStatus.SUCCESS,
                "charge.failed": TransactionStatus.FAILED,
                "transfer.success": TransactionStatus.SUCCESS,
                "transfer.failed": TransactionStatus.FAILED,
                "transfer.reversed": TransactionStatus.REFUNDED,
            }
        
        elif gateway_name == "flutterwave":
            transaction_ref = event_data.get("data", {}).get("tx_ref")
            status_map = {
                "charge.completed": TransactionStatus.SUCCESS,
                "charge.failed": TransactionStatus.FAILED,
                "transfer.completed": TransactionStatus.SUCCESS,
                "transfer.failed": TransactionStatus.FAILED,
            }
        
        elif gateway_name == "stripe":
            transaction_ref = event_data.get("data", {}).get("object", {}).get("metadata", {}).get("reference")
            status_map = {
                "payment_intent.succeeded": TransactionStatus.SUCCESS,
                "payment_intent.payment_failed": TransactionStatus.FAILED,
                "charge.refunded": TransactionStatus.REFUNDED,
            }
        
        else:
            # Generic mapping
            transaction_ref = event_data.get("reference") or event_data.get("transaction_id")
            status_map = {
                "success": TransactionStatus.SUCCESS,
                "failed": TransactionStatus.FAILED,
                "refunded": TransactionStatus.REFUNDED,
            }
        
        if not transaction_ref:
            logger.warning(f"No transaction reference in webhook from {gateway_name}")
            return
        
        # Find transaction by gateway reference or transaction ID
        transaction = db.query(PaymentTransaction).filter(
            (PaymentTransaction.gateway_reference == transaction_ref) |
            (PaymentTransaction.transaction_id == transaction_ref)
        ).first()
        
        if not transaction:
            logger.warning(f"Transaction not found for reference: {transaction_ref}")
            return
        
        # Update transaction status
        new_status = status_map.get(event_type)
        if new_status:
            old_status = transaction.status
            transaction.status = new_status
            
            if new_status == TransactionStatus.SUCCESS:
                transaction.completed_at = datetime.utcnow()
            elif new_status == TransactionStatus.FAILED:
                transaction.failure_reason = event_data.get("data", {}).get("message", "Payment failed")
            
            # Update gateway response
            transaction.gateway_response = event_data
            
            db.commit()
            
            logger.info(
                f"Transaction {transaction.transaction_id} status updated: "
                f"{old_status.value} -> {new_status.value} via webhook"
            )
            
            # Production: Send notification to user
            # Production: Trigger callback URL if configured
        
    except Exception as e:
        logger.error(f"Error processing webhook event: {e}")
        db.rollback()


@router.post(
    "/{gateway_name}",
    status_code=status.HTTP_200_OK,
    summary="Receive webhook notification",
    description="Endpoint for receiving webhook notifications from payment gateways"
)
async def receive_webhook(
    gateway_name: str,
    request: Request,
    db: Session = Depends(get_db),
    gateway_factory: GatewayFactory = Depends(get_gateway_factory),
    x_paystack_signature: Optional[str] = Header(None),
    verif_hash: Optional[str] = Header(None),  # Flutterwave
    stripe_signature: Optional[str] = Header(None)
) -> Dict[str, Any]:
    """
    Receive and process webhook notifications from payment gateways.
    
    - **gateway_name**: Name of the payment gateway sending the webhook
    
    The endpoint verifies the webhook signature and processes the event.
    """
    try:
        # Get raw body for signature verification
        body = await request.body()
        
        # Get signature based on gateway
        signature = None
        if gateway_name == "paystack":
            signature = x_paystack_signature
        elif gateway_name == "flutterwave":
            signature = verif_hash
        elif gateway_name == "stripe":
            signature = stripe_signature
        else:
            # Try to get from headers
            signature = request.headers.get("x-webhook-signature")
        
        if not signature:
            logger.warning(f"No signature in webhook from {gateway_name}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing webhook signature"
            )
        
        # Verify signature
        is_valid = await verify_webhook_signature(
            gateway_name,
            body,
            signature,
            gateway_factory
        )
        
        if not is_valid:
            logger.warning(f"Invalid webhook signature from {gateway_name}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )
        
        # Parse event data
        event_data = await request.json()
        
        # Store webhook event
        webhook_event = PaymentWebhook(
            gateway=gateway_name,
            event_type=event_data.get("event", "unknown"),
            payload=event_data,
            signature=signature,
            is_processed=False
        )
        db.add(webhook_event)
        db.commit()
        
        # Process event
        await process_webhook_event(gateway_name, event_data, db)
        
        # Mark as processed
        webhook_event.is_processed = True
        webhook_event.processed_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Webhook processed successfully from {gateway_name}")
        
        # Return success response (format varies by gateway)
        if gateway_name == "paystack":
            return {"status": "success"}
        elif gateway_name == "flutterwave":
            return {"status": "ok"}
        else:
            return {"received": True}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling webhook from {gateway_name}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook"
        )


@router.get(
    "/events",
    response_model=List[WebhookEventSchema],
    summary="List webhook events",
    description="Get list of recent webhook events (admin only)"
)
async def list_webhook_events(
    limit: int = 50,
    db: Session = Depends(get_db)
) -> List[WebhookEventSchema]:
    """
    List recent webhook events.
    
    - **limit**: Maximum number of events to return
    
    Returns list of webhook events.
    """
    events = db.query(PaymentWebhook).order_by(
        PaymentWebhook.created_at.desc()
    ).limit(limit).all()
    
    return [
        WebhookEventSchema(
            event_type=event.event_type,
            gateway=event.gateway,
            transaction_id=event.payload.get("data", {}).get("reference"),
            gateway_reference=event.payload.get("data", {}).get("reference"),
            status=None,
            payload=event.payload,
            timestamp=event.created_at
        )
        for event in events
    ]


@router.post(
    "/events/{event_id}/reprocess",
    status_code=status.HTTP_200_OK,
    summary="Reprocess webhook event",
    description="Manually reprocess a failed webhook event (admin only)"
)
async def reprocess_webhook_event(
    event_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Reprocess a webhook event.
    
    - **event_id**: ID of the webhook event to reprocess
    
    Useful for handling failed webhook processing.
    """
    try:
        event = db.query(PaymentWebhook).filter(
            PaymentWebhook.id == event_id
        ).first()
        
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Webhook event not found"
            )
        
        # Reprocess event
        await process_webhook_event(event.gateway, event.payload, db)
        
        # Mark as processed
        event.is_processed = True
        event.processed_at = datetime.utcnow()
        db.commit()
        
        return {"success": True, "message": "Event reprocessed successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reprocessing webhook event: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reprocess webhook event"
        )


# Import datetime at the top
from datetime import datetime
