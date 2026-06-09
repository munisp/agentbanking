"""
Real Stripe Payment Processor Integration
Replaces mock payment processing with actual Stripe API calls
"""

import stripe
import asyncio
import logging
import os
from typing import Dict, Any, Optional
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class StripeConfig:
    secret_key: str
    webhook_secret: str
    api_version: str = "2023-10-16"
    connect_timeout: int = 30
    read_timeout: int = 30

class TransactionStatus:
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"
    PENDING = "PENDING"
    ERROR = "ERROR"

class PaymentResponse:
    def __init__(self, transaction_id: str, status: str, amount: float, currency: str,
                 authorization_code: str = None, error_message: str = None,
                 processor_response: Dict = None, receipt_data: Dict = None):
        self.transaction_id = transaction_id
        self.status = status
        self.amount = amount
        self.currency = currency
        self.authorization_code = authorization_code
        self.error_message = error_message
        self.processor_response = processor_response or {}
        self.receipt_data = receipt_data or {}

class StripeProcessor:
    def __init__(self, config: StripeConfig):
        self.config = config
        stripe.api_key = config.secret_key
        stripe.api_version = config.api_version
        
    async def process_card_payment(self, payment_request) -> PaymentResponse:
        """Process card payment through Stripe"""
        try:
            # Convert amount to cents (Stripe uses smallest currency unit)
            amount_cents = int(payment_request.amount * 100)
            
            # Create payment intent
            payment_intent = await self._create_payment_intent(
                amount=amount_cents,
                currency=payment_request.currency.lower(),
                payment_method_types=['card'],
                metadata={
                    'merchant_id': payment_request.merchant_id,
                    'terminal_id': payment_request.terminal_id,
                    'transaction_reference': getattr(payment_request, 'transaction_reference', '')
                }
            )
            
            # For card present transactions, confirm immediately
            if payment_request.payment_method in ['card_chip', 'card_swipe', 'card_contactless']:
                confirmed_intent = await self._confirm_payment_intent(
                    payment_intent.id,
                    payment_method_data=self._build_payment_method_data(payment_request)
                )
                
                if confirmed_intent.status == 'succeeded':
                    return PaymentResponse(
                        transaction_id=confirmed_intent.id,
                        status=TransactionStatus.APPROVED,
                        amount=payment_request.amount,
                        currency=payment_request.currency,
                        authorization_code=confirmed_intent.charges.data[0].id,
                        processor_response={
                            'stripe_payment_intent_id': confirmed_intent.id,
                            'stripe_charge_id': confirmed_intent.charges.data[0].id,
                            'network_transaction_id': getattr(confirmed_intent.charges.data[0], 'network_transaction_id', ''),
                            'receipt_url': getattr(confirmed_intent.charges.data[0], 'receipt_url', '')
                        },
                        receipt_data=self._generate_stripe_receipt(confirmed_intent, payment_request)
                    )
                else:
                    return PaymentResponse(
                        transaction_id=confirmed_intent.id,
                        status=TransactionStatus.DECLINED,
                        amount=payment_request.amount,
                        currency=payment_request.currency,
                        error_message=self._get_decline_reason(confirmed_intent)
                    )
            
            # For other payment methods, return pending status
            return PaymentResponse(
                transaction_id=payment_intent.id,
                status=TransactionStatus.PENDING,
                amount=payment_request.amount,
                currency=payment_request.currency,
                processor_response={'stripe_payment_intent_id': payment_intent.id}
            )
            
        except stripe.error.CardError as e:
            # Card was declined
            return PaymentResponse(
                transaction_id=None,
                status=TransactionStatus.DECLINED,
                amount=payment_request.amount,
                currency=payment_request.currency,
                error_message=e.user_message,
                processor_response={'stripe_error': e.json_body}
            )
            
        except stripe.error.RateLimitError as e:
            # Rate limit exceeded
            logger.error(f"Stripe rate limit exceeded: {e}")
            return PaymentResponse(
                transaction_id=None,
                status=TransactionStatus.ERROR,
                amount=payment_request.amount,
                currency=payment_request.currency,
                error_message="Service temporarily unavailable"
            )
            
        except stripe.error.InvalidRequestError as e:
            # Invalid parameters
            logger.error(f"Stripe invalid request: {e}")
            return PaymentResponse(
                transaction_id=None,
                status=TransactionStatus.ERROR,
                amount=payment_request.amount,
                currency=payment_request.currency,
                error_message="Invalid payment request"
            )
            
        except Exception as e:
            logger.error(f"Stripe payment processing error: {e}")
            return PaymentResponse(
                transaction_id=None,
                status=TransactionStatus.ERROR,
                amount=payment_request.amount,
                currency=payment_request.currency,
                error_message="Payment processing failed"
            )
    
    async def _create_payment_intent(self, **kwargs) -> stripe.PaymentIntent:
        """Create Stripe payment intent asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            lambda: stripe.PaymentIntent.create(**kwargs)
        )
    
    async def _confirm_payment_intent(self, payment_intent_id: str, **kwargs) -> stripe.PaymentIntent:
        """Confirm Stripe payment intent asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: stripe.PaymentIntent.confirm(payment_intent_id, **kwargs)
        )
    
    def _build_payment_method_data(self, payment_request) -> Dict[str, Any]:
        """Build payment method data for Stripe"""
        if payment_request.payment_method == 'card_chip':
            return {
                'type': 'card',
                'card': {
                    'present': True,
                    'read_method': 'contact_emv'
                }
            }
        elif payment_request.payment_method == 'card_contactless':
            return {
                'type': 'card',
                'card': {
                    'present': True,
                    'read_method': 'contactless_emv'
                }
            }
        elif payment_request.payment_method == 'card_swipe':
            return {
                'type': 'card',
                'card': {
                    'present': True,
                    'read_method': 'magnetic_stripe_track2'
                }
            }
        else:
            return {'type': 'card'}
    
    def _get_decline_reason(self, payment_intent: stripe.PaymentIntent) -> str:
        """Extract decline reason from Stripe response"""
        if payment_intent.last_payment_error:
            return payment_intent.last_payment_error.message
        return "Payment was declined"
    
    def _generate_stripe_receipt(self, payment_intent: stripe.PaymentIntent, 
                                payment_request) -> Dict[str, Any]:
        """Generate receipt data from Stripe response"""
        charge = payment_intent.charges.data[0]
        
        return {
            'transaction_id': payment_intent.id,
            'charge_id': charge.id,
            'amount': payment_request.amount,
            'currency': payment_request.currency.upper(),
            'payment_method': payment_request.payment_method,
            'card_brand': getattr(charge.payment_method_details.card, 'brand', None) if charge.payment_method_details.card else None,
            'card_last4': getattr(charge.payment_method_details.card, 'last4', None) if charge.payment_method_details.card else None,
            'authorization_code': charge.id,
            'network_transaction_id': getattr(charge, 'network_transaction_id', ''),
            'receipt_url': getattr(charge, 'receipt_url', ''),
            'timestamp': payment_intent.created,
            'merchant_id': payment_request.merchant_id,
            'terminal_id': payment_request.terminal_id,
            'status': 'approved'
        }
    
    async def refund_payment(self, transaction_id: str, amount: Optional[Decimal] = None) -> Dict[str, Any]:
        """Process refund through Stripe"""
        try:
            refund_data = {'payment_intent': transaction_id}
            if amount:
                refund_data['amount'] = int(amount * 100)
            
            loop = asyncio.get_event_loop()
            refund = await loop.run_in_executor(
                None,
                lambda: stripe.Refund.create(**refund_data)
            )
            
            return {
                'success': True,
                'refund_id': refund.id,
                'amount': Decimal(refund.amount) / 100,
                'status': refund.status
            }
            
        except Exception as e:
            logger.error(f"Stripe refund error: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def handle_webhook(self, payload: str, signature: str) -> Dict[str, Any]:
        """Handle Stripe webhook events"""
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.config.webhook_secret
            )
            
            # Handle different event types
            if event['type'] == 'payment_intent.succeeded':
                return await self._handle_payment_success(event['data']['object'])
            elif event['type'] == 'payment_intent.payment_failed':
                return await self._handle_payment_failure(event['data']['object'])
            elif event['type'] == 'charge.dispute.created':
                return await self._handle_chargeback(event['data']['object'])
            else:
                logger.info(f"Unhandled Stripe webhook event: {event['type']}")
                return {'handled': False}
                
        except ValueError as e:
            logger.error(f"Invalid Stripe webhook payload: {e}")
            return {'error': 'Invalid payload'}
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid Stripe webhook signature: {e}")
            return {'error': 'Invalid signature'}
    
    async def _handle_payment_success(self, payment_intent: Dict[str, Any]) -> Dict[str, Any]:
        """Handle successful payment webhook"""
        # Update transaction status in database
        # Send confirmation notifications
        # Update analytics
        logger.info(f"Payment succeeded: {payment_intent['id']}")
        return {'handled': True, 'action': 'payment_confirmed'}
    
    async def _handle_payment_failure(self, payment_intent: Dict[str, Any]) -> Dict[str, Any]:
        """Handle failed payment webhook"""
        # Update transaction status
        # Send failure notifications
        logger.warning(f"Payment failed: {payment_intent['id']}")
        return {'handled': True, 'action': 'payment_failed'}
    
    async def _handle_chargeback(self, dispute: Dict[str, Any]) -> Dict[str, Any]:
        """Handle chargeback webhook"""
        # Create dispute record
        # Send alert notifications
        # Update fraud scoring
        logger.warning(f"Chargeback created: {dispute['id']}")
        return {'handled': True, 'action': 'chargeback_created'}

    async def get_payment_status(self, transaction_id: str) -> Dict[str, Any]:
        """Get payment status from Stripe"""
        try:
            loop = asyncio.get_event_loop()
            payment_intent = await loop.run_in_executor(
                None,
                lambda: stripe.PaymentIntent.retrieve(transaction_id)
            )
            
            return {
                'transaction_id': payment_intent.id,
                'status': payment_intent.status,
                'amount': payment_intent.amount / 100,
                'currency': payment_intent.currency.upper(),
                'created': payment_intent.created,
                'last_payment_error': payment_intent.last_payment_error
            }
            
        except Exception as e:
            logger.error(f"Failed to get payment status: {e}")
            return {'error': str(e)}

    async def create_customer(self, customer_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create Stripe customer"""
        try:
            loop = asyncio.get_event_loop()
            customer = await loop.run_in_executor(
                None,
                lambda: stripe.Customer.create(**customer_data)
            )
            
            return {
                'success': True,
                'customer_id': customer.id,
                'customer': customer
            }
            
        except Exception as e:
            logger.error(f"Failed to create customer: {e}")
            return {'success': False, 'error': str(e)}

    async def create_payment_method(self, payment_method_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create Stripe payment method"""
        try:
            loop = asyncio.get_event_loop()
            payment_method = await loop.run_in_executor(
                None,
                lambda: stripe.PaymentMethod.create(**payment_method_data)
            )
            
            return {
                'success': True,
                'payment_method_id': payment_method.id,
                'payment_method': payment_method
            }
            
        except Exception as e:
            logger.error(f"Failed to create payment method: {e}")
            return {'success': False, 'error': str(e)}
