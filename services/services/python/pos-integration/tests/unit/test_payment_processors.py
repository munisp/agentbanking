"""
Unit Tests for Payment Processors
Comprehensive test coverage for Stripe, Square, and Mock processors
"""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from decimal import Decimal
from datetime import datetime

# Import the modules to test
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from payment_processors import (
    StripeProcessor, StripeConfig,
    SquareProcessor, SquareConfig,
    PaymentProcessorFactory, ProcessorType,
    PaymentResponse, TransactionStatus
)

class MockPaymentRequest:
    """Mock payment request for testing"""
    def __init__(self, **kwargs):
        self.amount = kwargs.get('amount', 100.0)
        self.currency = kwargs.get('currency', 'USD')
        self.payment_method = kwargs.get('payment_method', 'card_chip')
        self.merchant_id = kwargs.get('merchant_id', 'MERCHANT_123')
        self.terminal_id = kwargs.get('terminal_id', 'TERMINAL_456')
        self.transaction_reference = kwargs.get('transaction_reference', 'REF_789')

class TestStripeProcessor:
    """Test cases for Stripe Payment Processor"""
    
    @pytest.fixture
    def stripe_config(self):
        """Create Stripe configuration for testing"""
        return StripeConfig(
            secret_key="sk_test_123456789",
            webhook_secret="whsec_test_123456789",
            api_version="2023-10-16"
        )
    
    @pytest.fixture
    def stripe_processor(self, stripe_config):
        """Create Stripe processor instance for testing"""
        return StripeProcessor(stripe_config)
    
    @pytest.fixture
    def payment_request(self):
        """Create mock payment request"""
        return MockPaymentRequest(
            amount=100.50,
            currency='USD',
            payment_method='card_chip'
        )
    
    @pytest.mark.asyncio
    @patch('stripe.PaymentIntent.create')
    @patch('stripe.PaymentIntent.confirm')
    async def test_successful_card_payment(self, mock_confirm, mock_create, stripe_processor, payment_request):
        """Test successful card payment processing"""
        # Mock Stripe API responses
        mock_payment_intent = MagicMock()
        mock_payment_intent.id = "pi_test_123456789"
        mock_payment_intent.status = "requires_confirmation"
        mock_create.return_value = mock_payment_intent
        
        mock_confirmed_intent = MagicMock()
        mock_confirmed_intent.id = "pi_test_123456789"
        mock_confirmed_intent.status = "succeeded"
        mock_confirmed_intent.charges.data = [MagicMock()]
        mock_confirmed_intent.charges.data[0].id = "ch_test_123456789"
        mock_confirmed_intent.charges.data[0].network_transaction_id = "ntwk_123"
        mock_confirmed_intent.charges.data[0].receipt_url = "https://stripe.com/receipt"
        mock_confirmed_intent.charges.data[0].payment_method_details.card.brand = "visa"
        mock_confirmed_intent.charges.data[0].payment_method_details.card.last4 = "4242"
        mock_confirmed_intent.created = int(datetime.now().timestamp())
        mock_confirm.return_value = mock_confirmed_intent
        
        # Process payment
        result = await stripe_processor.process_card_payment(payment_request)
        
        # Verify result
        assert isinstance(result, PaymentResponse)
        assert result.status == TransactionStatus.APPROVED
        assert result.transaction_id == "pi_test_123456789"
        assert result.amount == 100.50
        assert result.currency == 'USD'
        assert result.authorization_code == "ch_test_123456789"
        assert 'stripe_payment_intent_id' in result.processor_response
        assert result.receipt_data is not None
        
        # Verify Stripe API calls
        mock_create.assert_called_once()
        mock_confirm.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('stripe.PaymentIntent.create')
    @patch('stripe.PaymentIntent.confirm')
    async def test_declined_card_payment(self, mock_confirm, mock_create, stripe_processor, payment_request):
        """Test declined card payment"""
        # Mock Stripe API responses
        mock_payment_intent = MagicMock()
        mock_payment_intent.id = "pi_test_declined"
        mock_create.return_value = mock_payment_intent
        
        mock_confirmed_intent = MagicMock()
        mock_confirmed_intent.id = "pi_test_declined"
        mock_confirmed_intent.status = "requires_payment_method"
        mock_confirmed_intent.last_payment_error.message = "Your card was declined."
        mock_confirm.return_value = mock_confirmed_intent
        
        # Process payment
        result = await stripe_processor.process_card_payment(payment_request)
        
        # Verify result
        assert result.status == TransactionStatus.DECLINED
        assert result.error_message == "Your card was declined."
    
    @pytest.mark.asyncio
    @patch('stripe.PaymentIntent.create')
    async def test_stripe_card_error(self, mock_create, stripe_processor, payment_request):
        """Test Stripe card error handling"""
        import stripe
        
        # Mock Stripe card error
        mock_create.side_effect = stripe.error.CardError(
            message="Your card was declined.",
            param="card",
            code="card_declined",
            json_body={'error': {'message': 'Your card was declined.'}}
        )
        
        # Process payment
        result = await stripe_processor.process_card_payment(payment_request)
        
        # Verify error handling
        assert result.status == TransactionStatus.DECLINED
        assert result.error_message == "Your card was declined."
        assert result.transaction_id is None
    
    @pytest.mark.asyncio
    @patch('stripe.Refund.create')
    async def test_refund_payment(self, mock_refund_create, stripe_processor):
        """Test payment refund"""
        # Mock Stripe refund response
        mock_refund = MagicMock()
        mock_refund.id = "re_test_123456789"
        mock_refund.amount = 10050  # $100.50 in cents
        mock_refund.status = "succeeded"
        mock_refund_create.return_value = mock_refund
        
        # Process refund
        result = await stripe_processor.refund_payment("pi_test_123456789", Decimal("100.50"))
        
        # Verify result
        assert result['success'] is True
        assert result['refund_id'] == "re_test_123456789"
        assert result['amount'] == Decimal("100.50")
        assert result['status'] == "succeeded"
    
    @pytest.mark.asyncio
    async def test_webhook_handling(self, stripe_processor):
        """Test Stripe webhook handling"""
        # Mock webhook payload
        payload = json.dumps({
            'type': 'payment_intent.succeeded',
            'data': {
                'object': {
                    'id': 'pi_test_123456789',
                    'status': 'succeeded'
                }
            }
        })
        signature = "test_signature"
        
        with patch('stripe.Webhook.construct_event') as mock_construct:
            mock_event = {
                'type': 'payment_intent.succeeded',
                'data': {'object': {'id': 'pi_test_123456789'}}
            }
            mock_construct.return_value = mock_event
            
            # Handle webhook
            result = await stripe_processor.handle_webhook(payload, signature)
            
            # Verify result
            assert result['handled'] is True
            assert result['action'] == 'payment_confirmed'

class TestSquareProcessor:
    """Test cases for Square Payment Processor"""
    
    @pytest.fixture
    def square_config(self):
        """Create Square configuration for testing"""
        return SquareConfig(
            access_token="sq0atp-test-123456789",
            application_id="sq0idp-test-123456789",
            environment="sandbox",
            location_id="LOCATION_123"
        )
    
    @pytest.fixture
    def square_processor(self, square_config):
        """Create Square processor instance for testing"""
        return SquareProcessor(square_config)
    
    @pytest.fixture
    def payment_request(self):
        """Create mock payment request"""
        return MockPaymentRequest(
            amount=75.25,
            currency='USD',
            payment_method='card_contactless'
        )
    
    @pytest.mark.asyncio
    async def test_successful_square_payment(self, square_processor, payment_request):
        """Test successful Square payment processing"""
        # Mock aiohttp response
        mock_response_data = {
            "payment": {
                "id": "sq_payment_123456789",
                "status": "COMPLETED",
                "amount_money": {"amount": 7525, "currency": "USD"},
                "receipt_number": "RECEIPT_123",
                "receipt_url": "https://squareup.com/receipt",
                "created_at": "2023-01-01T12:00:00Z",
                "card_details": {
                    "card": {"card_brand": "VISA", "last_4": "1234"},
                    "entry_method": "CONTACTLESS",
                    "cvv_status": "CVV_ACCEPTED",
                    "avs_status": "AVS_ACCEPTED"
                }
            }
        }
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_response_data)
            mock_post.return_value.__aenter__.return_value = mock_response
            
            # Process payment
            result = await square_processor.process_card_payment(payment_request)
            
            # Verify result
            assert result.status == "APPROVED"
            assert result.transaction_id == "sq_payment_123456789"
            assert result.amount == 75.25
            assert result.authorization_code == "RECEIPT_123"
            assert 'square_payment_id' in result.processor_response
    
    @pytest.mark.asyncio
    async def test_square_payment_error(self, square_processor, payment_request):
        """Test Square payment error handling"""
        # Mock error response
        mock_error_response = {
            "errors": [{
                "category": "PAYMENT_METHOD_ERROR",
                "code": "CARD_DECLINED",
                "detail": "The card was declined."
            }]
        }
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 400
            mock_response.json = AsyncMock(return_value=mock_error_response)
            mock_post.return_value.__aenter__.return_value = mock_response
            
            # Process payment
            result = await square_processor.process_card_payment(payment_request)
            
            # Verify error handling
            assert result.status == "DECLINED"
            assert result.error_message == "The card was declined."
    
    @pytest.mark.asyncio
    async def test_square_refund(self, square_processor):
        """Test Square refund processing"""
        # Mock refund response
        mock_refund_response = {
            "refund": {
                "id": "sq_refund_123456789",
                "status": "COMPLETED",
                "amount_money": {"amount": 5000, "currency": "USD"}
            }
        }
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_refund_response)
            mock_post.return_value.__aenter__.return_value = mock_response
            
            # Mock get payment status
            with patch.object(square_processor, 'get_payment_status') as mock_get_status:
                mock_get_status.return_value = {
                    'amount': 50.0,
                    'currency': 'USD'
                }
                
                # Process refund
                result = await square_processor.refund_payment("sq_payment_123", Decimal("50.0"))
                
                # Verify result
                assert result['success'] is True
                assert result['refund_id'] == "sq_refund_123456789"
                assert result['amount'] == Decimal("50.0")

class TestPaymentProcessorFactory:
    """Test cases for Payment Processor Factory"""
    
    @pytest.fixture
    def factory(self):
        """Create payment processor factory for testing"""
        return PaymentProcessorFactory()
    
    def test_factory_initialization(self, factory):
        """Test factory initialization with different configurations"""
        # Test with no environment variables (should use mock)
        with patch.dict(os.environ, {}, clear=True):
            factory.initialize_processors({})
            
            # Should have mock processor
            assert ProcessorType.MOCK in factory.get_available_processors()
            processor = factory.get_processor()
            assert processor is not None
    
    def test_factory_with_stripe_config(self, factory):
        """Test factory with Stripe configuration"""
        with patch.dict(os.environ, {
            'STRIPE_SECRET_KEY': 'sk_test_123456789',
            'STRIPE_WEBHOOK_SECRET': 'whsec_test_123456789'
        }):
            factory.initialize_processors({})
            
            # Should have Stripe processor
            assert ProcessorType.STRIPE in factory.get_available_processors()
            stripe_processor = factory.get_processor(ProcessorType.STRIPE)
            assert isinstance(stripe_processor, StripeProcessor)
    
    def test_factory_with_square_config(self, factory):
        """Test factory with Square configuration"""
        with patch.dict(os.environ, {
            'SQUARE_ACCESS_TOKEN': 'sq0atp-test-123456789',
            'SQUARE_APPLICATION_ID': 'sq0idp-test-123456789'
        }):
            factory.initialize_processors({})
            
            # Should have Square processor
            assert ProcessorType.SQUARE in factory.get_available_processors()
            square_processor = factory.get_processor(ProcessorType.SQUARE)
            assert isinstance(square_processor, SquareProcessor)
    
    def test_processor_routing(self, factory):
        """Test intelligent processor routing"""
        # Initialize with both processors
        with patch.dict(os.environ, {
            'STRIPE_SECRET_KEY': 'sk_test_123456789',
            'SQUARE_ACCESS_TOKEN': 'sq0atp-test-123456789',
            'SQUARE_APPLICATION_ID': 'sq0idp-test-123456789'
        }):
            factory.initialize_processors({})
            
            # Test card present routing (should prefer Square)
            card_request = MockPaymentRequest(payment_method='card_chip')
            processor = factory.get_best_processor_for_payment(card_request)
            assert isinstance(processor, SquareProcessor)
            
            # Test digital wallet routing (should prefer Stripe)
            wallet_request = MockPaymentRequest(payment_method='digital_wallet')
            processor = factory.get_best_processor_for_payment(wallet_request)
            assert isinstance(processor, StripeProcessor)
    
    def test_processor_health_check(self, factory):
        """Test processor health check"""
        factory.initialize_processors({})
        
        health_status = factory.get_processor_health()
        
        # Should have health status for all processors
        assert len(health_status) > 0
        
        for processor_type, status in health_status.items():
            assert 'status' in status
            assert 'available' in status
            assert 'type' in status

class TestMockProcessor:
    """Test cases for Mock Payment Processor"""
    
    @pytest.fixture
    def mock_processor(self):
        """Create mock processor instance"""
        from payment_processors.processor_factory import MockProcessor
        return MockProcessor()
    
    @pytest.fixture
    def payment_request(self):
        """Create mock payment request"""
        return MockPaymentRequest(amount=50.0, currency='USD')
    
    @pytest.mark.asyncio
    async def test_mock_payment_success(self, mock_processor, payment_request):
        """Test mock payment processing (success case)"""
        # Mock random to always approve
        with patch('random.random', return_value=0.5):  # 50% < 90% approval rate
            result = await mock_processor.process_card_payment(payment_request)
            
            assert result.status == TransactionStatus.APPROVED
            assert result.amount == 50.0
            assert result.currency == 'USD'
            assert result.transaction_id.startswith('mock_')
            assert result.receipt_data['test_mode'] is True
    
    @pytest.mark.asyncio
    async def test_mock_payment_decline(self, mock_processor, payment_request):
        """Test mock payment processing (decline case)"""
        # Mock random to always decline
        with patch('random.random', return_value=0.95):  # 95% > 90% approval rate
            result = await mock_processor.process_card_payment(payment_request)
            
            assert result.status == TransactionStatus.DECLINED
            assert result.error_message == "Insufficient funds (mock decline)"
    
    @pytest.mark.asyncio
    async def test_mock_refund(self, mock_processor):
        """Test mock refund processing"""
        result = await mock_processor.refund_payment("mock_txn_123", 25.0)
        
        assert result['success'] is True
        assert result['refund_id'].startswith('refund_')
        assert result['amount'] == 25.0
        assert result['status'] == 'completed'

# Test utilities and fixtures
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
