from flask import Blueprint, request, jsonify, current_app
import logging
import uuid
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json
from decimal import Decimal

# Import PAPSS-specific services
from src.services.papss_tigerbeetle_service import PAPSSTigerBeetleService
from src.services.african_fx_service import AfricanForeignExchangeService
from src.services.mobile_money_service import MobileMoneyService
from src.services.african_compliance_service import AfricanComplianceService
from src.services.regional_settlement_service import RegionalSettlementService
from src.models.papss_payment import PAPSSPayment, PaymentStatus, PaymentType, AfricanCurrency, TradeCorridorType

papss_bp = Blueprint('papss', __name__)
logger = logging.getLogger(__name__)

# Initialize services
tigerbeetle_service = PAPSSTigerBeetleService()
african_fx_service = AfricanForeignExchangeService()
mobile_money_service = MobileMoneyService()
african_compliance_service = AfricanComplianceService()
regional_settlement_service = RegionalSettlementService()

@papss_bp.route('/payments', methods=['POST'])
def create_pan_african_payment() -> Tuple:
    """
    Create a new PAPSS Pan-African payment with TigerBeetle ledger integration
    
    Expected payload:
    {
        "sender": {
            "country": "NG",
            "bank_code": "NRP (Nigerian Remittance Platform)NNGLA",
            "account_number": "1234567890",
            "name": "Sender Name",
            "address": "Lagos, Nigeria",
            "phone": "+234801234567",
            "id_number": "12345678901"
        },
        "receiver": {
            "country": "KE",
            "bank_code": "CBKEKENX",
            "account_number": "9876543210",
            "name": "Receiver Name",
            "address": "Nairobi, Kenya",
            "phone": "+254701234567",
            "id_number": "98765432109"
        },
        "amount": 500000,
        "source_currency": "NGN",
        "target_currency": "KES",
        "payment_type": "personal|commercial|trade_finance|mobile_money",
        "payment_method": "bank_transfer|mobile_money|trade_finance",
        "purpose_code": "SALA|TRAD|SUPP|FAMI|OTHR",
        "reference": "PAPSS-2024-001",
        "instructions": "Payment for goods",
        "trade_corridor": "EAC|ECOWAS|SADC|CEMAC",
        "mobile_money_info": {
            "sender_operator": "OPAY",
            "receiver_operator": "MPESA",
            "sender_phone": "+234801234567",
            "receiver_phone": "+254701234567"
        },
        "regulatory_info": {
            "export_license": "optional",
            "import_permit": "optional",
            "tax_id": "optional",
            "trade_agreement": "AfCFTA|ECOWAS|EAC|SADC"
        }
    }
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['sender', 'receiver', 'amount', 'source_currency', 'target_currency']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Validate sender and receiver information
        sender_fields = ['country', 'bank_code', 'account_number', 'name']
        receiver_fields = ['country', 'bank_code', 'account_number', 'name']
        
        for field in sender_fields:
            if field not in data['sender']:
                return jsonify({'error': f'Missing sender field: {field}'}), 400
        
        for field in receiver_fields:
            if field not in data['receiver']:
                return jsonify({'error': f'Missing receiver field: {field}'}), 400
        
        # Generate payment ID
        payment_id = str(uuid.uuid4())
        
        # Validate African currencies
        african_currencies = list(current_app.config['AFRICAN_CURRENCIES'].keys())
        if data['source_currency'] not in african_currencies:
            return jsonify({'error': f'Unsupported source currency. Supported: {african_currencies}'}), 400
        
        if data['target_currency'] not in african_currencies:
            return jsonify({'error': f'Unsupported target currency. Supported: {african_currencies}'}), 400
        
        # Validate amount limits
        if data['amount'] <= 0:
            return jsonify({'error': 'Amount must be greater than zero'}), 400
        
        if data['amount'] > current_app.config['PAPSS_MAX_TRANSACTION_AMOUNT']:
            return jsonify({'error': 'Amount exceeds maximum transaction limit'}), 400
        
        # Determine trade corridor
        trade_corridor = determine_trade_corridor(
            data['sender']['country'], 
            data['receiver']['country'],
            data.get('trade_corridor')
        )
        
        if not trade_corridor:
            return jsonify({'error': 'No supported trade corridor found for this country pair'}), 400
        
        # African compliance screening
        compliance_result = african_compliance_service.screen_african_payment({
            'sender': data['sender'],
            'receiver': data['receiver'],
            'amount': data['amount'],
            'currencies': [data['source_currency'], data['target_currency']],
            'countries': [data['sender']['country'], data['receiver']['country']],
            'trade_corridor': trade_corridor,
            'purpose_code': data.get('purpose_code', 'OTHR')
        })
        
        if not compliance_result['approved']:
            logger.warning(f"PAPSS payment {payment_id} blocked by compliance: {compliance_result['reasons']}")
            return jsonify({
                'error': 'Payment blocked by African compliance screening',
                'reasons': compliance_result['reasons'],
                'reference_id': payment_id
            }), 403
        
        # Get African FX rate if currency conversion is needed
        fx_rate = 1.0
        fx_amount = data['amount']
        
        if data['source_currency'] != data['target_currency']:
            fx_result = african_fx_service.get_african_exchange_rate(
                data['source_currency'], 
                data['target_currency']
            )
            
            if not fx_result['success']:
                return jsonify({
                    'error': 'Unable to obtain African exchange rate',
                    'details': fx_result['error']
                }), 500
            
            fx_rate = fx_result['rate']
            fx_amount = int(data['amount'] * fx_rate)
        
        # Calculate PAPSS fees
        fees = calculate_papss_fees(
            data['amount'], 
            data['source_currency'], 
            data['target_currency'],
            data.get('payment_type', 'commercial'),
            data.get('payment_method', 'bank_transfer'),
            trade_corridor
        )
        
        # Handle mobile money payments
        mobile_money_info = None
        if data.get('payment_method') == 'mobile_money':
            mobile_money_info = data.get('mobile_money_info', {})
            
            # Validate mobile money operators
            mm_validation = mobile_money_service.validate_mobile_money_payment(
                sender_country=data['sender']['country'],
                receiver_country=data['receiver']['country'],
                sender_operator=mobile_money_info.get('sender_operator'),
                receiver_operator=mobile_money_info.get('receiver_operator'),
                amount=data['amount']
            )
            
            if not mm_validation['valid']:
                return jsonify({
                    'error': 'Mobile money validation failed',
                    'details': mm_validation['error']
                }), 400
        
        # Create PAPSS payment record
        payment = PAPSSPayment(
            id=payment_id,
            sender_info=data['sender'],
            receiver_info=data['receiver'],
            amount=data['amount'],
            source_currency=AfricanCurrency(data['source_currency']),
            target_currency=AfricanCurrency(data['target_currency']),
            fx_rate=fx_rate,
            converted_amount=fx_amount,
            payment_type=PaymentType(data.get('payment_type', 'commercial')),
            payment_method=data.get('payment_method', 'bank_transfer'),
            purpose_code=data.get('purpose_code', 'OTHR'),
            reference=data.get('reference', ''),
            instructions=data.get('instructions', ''),
            trade_corridor=TradeCorridorType(trade_corridor),
            mobile_money_info=mobile_money_info,
            regulatory_info=data.get('regulatory_info', {}),
            fees=fees,
            compliance_score=compliance_result['score'],
            status=PaymentStatus.PENDING,
            created_at=datetime.utcnow()
        )
        
        # Process payment through TigerBeetle
        tigerbeetle_result = tigerbeetle_service.process_pan_african_payment(
            payment_id=payment_id,
            sender_account=payment.sender_info['account_number'],
            receiver_account=payment.receiver_info['account_number'],
            sender_country=payment.sender_info['country'],
            receiver_country=payment.receiver_info['country'],
            amount=payment.amount,
            source_currency=payment.source_currency.value,
            target_currency=payment.target_currency.value,
            fx_rate=payment.fx_rate,
            trade_corridor=payment.trade_corridor.value,
            payment_method=payment.payment_method
        )
        
        if not tigerbeetle_result['success']:
            logger.error(f"TigerBeetle processing failed for PAPSS payment {payment_id}: {tigerbeetle_result['error']}")
            return jsonify({
                'error': 'PAPSS payment processing failed',
                'details': tigerbeetle_result['error']
            }), 500
        
        # Handle mobile money processing
        if payment.payment_method == 'mobile_money':
            mm_result = mobile_money_service.initiate_cross_border_mobile_money(
                payment_id=payment_id,
                sender_info=payment.sender_info,
                receiver_info=payment.receiver_info,
                mobile_money_info=payment.mobile_money_info,
                amount=payment.converted_amount,
                currency=payment.target_currency.value
            )
            
            if not mm_result['success']:
                logger.error(f"Mobile money processing failed for payment {payment_id}: {mm_result['error']}")
                # Continue processing but mark as pending mobile money confirmation
                payment.mobile_money_status = 'pending'
            else:
                payment.mobile_money_reference = mm_result['reference']
                payment.mobile_money_status = 'initiated'
        
        # Initiate regional settlement
        settlement_result = regional_settlement_service.initiate_settlement(
            payment_id=payment_id,
            sender_central_bank=get_central_bank_code(payment.sender_info['country']),
            receiver_central_bank=get_central_bank_code(payment.receiver_info['country']),
            amount=payment.converted_amount,
            currency=payment.target_currency.value,
            trade_corridor=payment.trade_corridor.value
        )
        
        # Update payment status
        payment.status = PaymentStatus.PROCESSING
        payment.tigerbeetle_transfer_ids = tigerbeetle_result['transfer_ids']
        payment.settlement_reference = settlement_result.get('reference')
        payment.updated_at = datetime.utcnow()
        
        # Save to database (simulated)
        logger.info(f"Created PAPSS payment {payment_id} for {data['amount']} {data['source_currency']} -> {fx_amount} {data['target_currency']} via {trade_corridor}")
        
        return jsonify({
            'id': payment_id,
            'status': payment.status.value,
            'amount': payment.amount,
            'source_currency': payment.source_currency.value,
            'target_currency': payment.target_currency.value,
            'fx_rate': payment.fx_rate,
            'converted_amount': payment.converted_amount,
            'trade_corridor': payment.trade_corridor.value,
            'payment_method': payment.payment_method,
            'fees': payment.fees,
            'settlement_reference': payment.settlement_reference,
            'mobile_money_reference': getattr(payment, 'mobile_money_reference', None),
            'estimated_settlement_time': (datetime.utcnow() + timedelta(minutes=current_app.config['PAPSS_SETTLEMENT_WINDOW'])).isoformat(),
            'created_at': payment.created_at.isoformat()
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating PAPSS payment: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@papss_bp.route('/payments/<payment_id>/status', methods=['GET'])
def get_papss_payment_status(payment_id: str) -> Tuple:
    """Get PAPSS payment status and settlement information"""
    try:
        # Get payment from database (simulated)
        payment = get_papss_payment_by_id(payment_id)
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404
        
        # Check regional settlement status
        settlement_status = regional_settlement_service.check_settlement_status(
            payment.settlement_reference,
            payment.sender_info['country'],
            payment.receiver_info['country'],
            payment.trade_corridor.value
        )
        
        # Check mobile money status if applicable
        mobile_money_status = None
        if payment.payment_method == 'mobile_money' and hasattr(payment, 'mobile_money_reference'):
            mobile_money_status = mobile_money_service.check_mobile_money_status(
                payment.mobile_money_reference,
                payment.sender_info['country'],
                payment.receiver_info['country']
            )
        
        # Update payment status if settlement is complete
        if settlement_status['settled'] and payment.status != PaymentStatus.COMPLETED:
            payment.status = PaymentStatus.COMPLETED
            payment.settled_at = datetime.utcnow()
            payment.final_settlement_reference = settlement_status['reference']
            
            # Update TigerBeetle with final settlement
            tigerbeetle_service.complete_pan_african_settlement(
                payment_id,
                payment.tigerbeetle_transfer_ids,
                settlement_status
            )
            
            logger.info(f"PAPSS payment {payment_id} settled successfully via {payment.trade_corridor.value}")
        
        elif settlement_status.get('failed'):
            payment.status = PaymentStatus.FAILED
            payment.failure_reason = settlement_status.get('reason', 'Regional settlement failed')
            payment.updated_at = datetime.utcnow()
            
            logger.error(f"PAPSS payment {payment_id} settlement failed: {payment.failure_reason}")
        
        return jsonify({
            'id': payment_id,
            'status': payment.status.value,
            'amount': payment.amount,
            'source_currency': payment.source_currency.value,
            'target_currency': payment.target_currency.value,
            'fx_rate': payment.fx_rate,
            'converted_amount': payment.converted_amount,
            'trade_corridor': payment.trade_corridor.value,
            'payment_method': payment.payment_method,
            'settlement_reference': payment.settlement_reference,
            'final_settlement_reference': getattr(payment, 'final_settlement_reference', None),
            'mobile_money_reference': getattr(payment, 'mobile_money_reference', None),
            'mobile_money_status': mobile_money_status,
            'created_at': payment.created_at.isoformat(),
            'settled_at': payment.settled_at.isoformat() if hasattr(payment, 'settled_at') and payment.settled_at else None,
            'failure_reason': getattr(payment, 'failure_reason', None),
            'settlement_status': settlement_status
        })
        
    except Exception as e:
        logger.error(f"Error getting PAPSS payment status for {payment_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@papss_bp.route('/payments/<payment_id>/cancel', methods=['POST'])
def cancel_papss_payment(payment_id: str) -> Tuple:
    """Cancel a PAPSS payment (only if not yet settled)"""
    try:
        data = request.get_json()
        reason = data.get('reason', 'Customer request')
        
        # Get payment from database
        payment = get_papss_payment_by_id(payment_id)
        if not payment:
            return jsonify({'error': 'Payment not found'}), 404
        
        if payment.status in [PaymentStatus.COMPLETED, PaymentStatus.FAILED, PaymentStatus.CANCELLED]:
            return jsonify({'error': f'Cannot cancel payment with status: {payment.status.value}'}), 400
        
        # Check if payment can be cancelled with regional settlement system
        cancellation_result = regional_settlement_service.request_cancellation(
            payment.settlement_reference,
            payment.sender_info['country'],
            payment.receiver_info['country'],
            payment.trade_corridor.value,
            reason
        )
        
        if not cancellation_result['success']:
            return jsonify({
                'error': 'Payment cannot be cancelled',
                'reason': cancellation_result['reason']
            }), 400
        
        # Cancel mobile money transaction if applicable
        if payment.payment_method == 'mobile_money' and hasattr(payment, 'mobile_money_reference'):
            mm_cancellation = mobile_money_service.cancel_mobile_money_transaction(
                payment.mobile_money_reference,
                payment.sender_info['country'],
                payment.receiver_info['country'],
                reason
            )
            
            if not mm_cancellation['success']:
                logger.warning(f"Mobile money cancellation failed for payment {payment_id}: {mm_cancellation['error']}")
        
        # Reverse TigerBeetle transfers
        reversal_result = tigerbeetle_service.reverse_pan_african_payment(
            payment_id,
            payment.tigerbeetle_transfer_ids,
            reason
        )
        
        if not reversal_result['success']:
            logger.error(f"Failed to reverse TigerBeetle transfers for PAPSS payment {payment_id}: {reversal_result['error']}")
            return jsonify({
                'error': 'Payment reversal failed',
                'details': reversal_result['error']
            }), 500
        
        # Update payment status
        payment.status = PaymentStatus.CANCELLED
        payment.cancellation_reason = reason
        payment.cancelled_at = datetime.utcnow()
        payment.reversal_reference = reversal_result['reversal_id']
        
        logger.info(f"PAPSS payment {payment_id} cancelled successfully")
        
        return jsonify({
            'id': payment_id,
            'status': payment.status.value,
            'cancellation_reason': payment.cancellation_reason,
            'cancelled_at': payment.cancelled_at.isoformat(),
            'reversal_reference': payment.reversal_reference
        })
        
    except Exception as e:
        logger.error(f"Error cancelling PAPSS payment {payment_id}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@papss_bp.route('/payments', methods=['GET'])
def list_papss_payments() -> Tuple:
    """List PAPSS payments with filtering and pagination"""
    try:
        # Get query parameters
        sender_country = request.args.get('sender_country')
        receiver_country = request.args.get('receiver_country')
        trade_corridor = request.args.get('trade_corridor')
        payment_method = request.args.get('payment_method')
        status = request.args.get('status')
        source_currency = request.args.get('source_currency')
        target_currency = request.args.get('target_currency')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        
        # Build filters
        filters = {}
        if sender_country:
            filters['sender_country'] = sender_country
        if receiver_country:
            filters['receiver_country'] = receiver_country
        if trade_corridor:
            filters['trade_corridor'] = trade_corridor
        if payment_method:
            filters['payment_method'] = payment_method
        if status:
            filters['status'] = status
        if source_currency:
            filters['source_currency'] = source_currency
        if target_currency:
            filters['target_currency'] = target_currency
        if start_date:
            filters['start_date'] = start_date
        if end_date:
            filters['end_date'] = end_date
        
        # Get payments from database (simulated)
        payments = get_papss_payments_with_filters(filters, limit, offset)
        total_count = get_papss_payments_count(filters)
        
        return jsonify({
            'payments': [papss_payment_to_dict(p) for p in payments],
            'pagination': {
                'total': total_count,
                'limit': limit,
                'offset': offset,
                'has_more': offset + limit < total_count
            }
        })
        
    except Exception as e:
        logger.error(f"Error listing PAPSS payments: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@papss_bp.route('/payments/analytics', methods=['GET'])
def papss_payment_analytics() -> Tuple:
    """Get PAPSS payment analytics and metrics"""
    try:
        # Get query parameters
        period = request.args.get('period', '7d')  # 1d, 7d, 30d, 90d
        trade_corridor = request.args.get('trade_corridor')
        currency = request.args.get('currency')
        
        # Calculate date range
        end_date = datetime.utcnow()
        if period == '1d':
            start_date = end_date - timedelta(days=1)
        elif period == '7d':
            start_date = end_date - timedelta(days=7)
        elif period == '30d':
            start_date = end_date - timedelta(days=30)
        elif period == '90d':
            start_date = end_date - timedelta(days=90)
        else:
            return jsonify({'error': 'Invalid period'}), 400
        
        # Get analytics data (simulated)
        analytics = get_papss_analytics(start_date, end_date, trade_corridor, currency)
        
        return jsonify(analytics)
        
    except Exception as e:
        logger.error(f"Error getting PAPSS analytics: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@papss_bp.route('/trade-corridors/<corridor_name>/status', methods=['GET'])
def get_trade_corridor_status(corridor_name: str) -> Tuple:
    """Get trade corridor operational status and metrics"""
    try:
        if corridor_name not in current_app.config['TRADE_CORRIDORS']:
            return jsonify({'error': 'Trade corridor not found'}), 404
        
        corridor_info = current_app.config['TRADE_CORRIDORS'][corridor_name]
        
        # Get corridor status (simulated)
        corridor_status = {
            'name': corridor_name,
            'countries': corridor_info['countries'],
            'currency_union': corridor_info['currency_union'],
            'annual_trade_volume_usd': corridor_info['trade_volume_usd'],
            'supported_payment_methods': corridor_info['payment_methods'],
            'operational_status': 'active',
            'settlement_time_avg_minutes': 3.5,
            'success_rate_percentage': 99.2,
            'daily_volume_usd': corridor_info['trade_volume_usd'] / 365,
            'active_participants': len(corridor_info['countries']) * 5,  # Estimated banks per country
            'last_settlement': (datetime.utcnow() - timedelta(minutes=2)).isoformat(),
            'next_settlement_window': (datetime.utcnow() + timedelta(minutes=current_app.config['PAPSS_SETTLEMENT_WINDOW'])).isoformat()
        }
        
        return jsonify(corridor_status)
        
    except Exception as e:
        logger.error(f"Error getting trade corridor status for {corridor_name}: {e}")
        return jsonify({'error': 'Internal server error'}), 500

# Helper functions
def determine_trade_corridor(sender_country: str, receiver_country: str, preferred_corridor: str = None) -> Optional[str]:
    """Determine the appropriate trade corridor for a payment"""
    trade_corridors = current_app.config['TRADE_CORRIDORS']
    
    # If preferred corridor is specified and valid, use it
    if preferred_corridor and preferred_corridor in trade_corridors:
        corridor_info = trade_corridors[preferred_corridor]
        if sender_country in corridor_info['countries'] and receiver_country in corridor_info['countries']:
            return preferred_corridor
    
    # Find corridors that include both countries
    matching_corridors = []
    for corridor_name, corridor_info in trade_corridors.items():
        if sender_country in corridor_info['countries'] and receiver_country in corridor_info['countries']:
            matching_corridors.append(corridor_name)
    
    if not matching_corridors:
        return None
    
    # Prefer corridors with higher trade volumes
    best_corridor = max(matching_corridors, key=lambda c: trade_corridors[c]['trade_volume_usd'])
    return best_corridor

def get_central_bank_code(country_code: str) -> str:
    """Get central bank code for a country"""
    central_banks = current_app.config['AFRICAN_CENTRAL_BANKS']
    return central_banks.get(country_code, {}).get('code', 'UNKNOWN')

def calculate_papss_fees(
    amount: int, 
    source_currency: str, 
    target_currency: str, 
    payment_type: str,
    payment_method: str,
    trade_corridor: str
) -> Dict[str, Any]:
    """Calculate PAPSS payment processing fees"""
    base_fee = 0
    percentage_fee = 0
    fx_fee = 0
    corridor_fee = 0
    mobile_money_fee = 0
    
    # Base fees by payment type (in cents)
    if payment_type == 'personal':
        base_fee = 500  # $5 equivalent
        percentage_fee = 0.005  # 0.5%
    elif payment_type == 'commercial':
        base_fee = 1000  # $10 equivalent
        percentage_fee = 0.003  # 0.3%
    elif payment_type == 'trade_finance':
        base_fee = 2500  # $25 equivalent
        percentage_fee = 0.002  # 0.2%
    
    # FX fees if currency conversion is needed
    if source_currency != target_currency:
        fx_fee = amount * 0.0025  # 0.25% FX spread for African currencies
    
    # Trade corridor fees
    corridor_fees = {
        'ECOWAS': 0.001,  # 0.1%
        'EAC': 0.0015,    # 0.15%
        'SADC': 0.0012,   # 0.12%
        'CEMAC': 0.0018   # 0.18%
    }
    corridor_fee = amount * corridor_fees.get(trade_corridor, 0.002)
    
    # Mobile money fees
    if payment_method == 'mobile_money':
        mobile_money_fee = amount * 0.015  # 1.5% for mobile money
    
    # Calculate total fees
    calculated_fee = base_fee + (amount * percentage_fee) + fx_fee + corridor_fee + mobile_money_fee
    
    # Regional settlement fee
    regional_settlement_fee = 250  # $2.50 equivalent
    
    total_fee = calculated_fee + regional_settlement_fee
    
    return {
        'base_fee': int(base_fee),
        'percentage_fee': percentage_fee,
        'fx_fee': int(fx_fee),
        'corridor_fee': int(corridor_fee),
        'mobile_money_fee': int(mobile_money_fee),
        'regional_settlement_fee': int(regional_settlement_fee),
        'calculated_fee': int(calculated_fee),
        'total': int(total_fee)
    }

def get_papss_payment_by_id(payment_id: str) -> Optional[PAPSSPayment]:
    """Get PAPSS payment by ID (simulated database query)"""
    # In production, this would query the actual database
    return PAPSSPayment(
        id=payment_id,
        sender_info={'country': 'NG', 'bank_code': 'NRP (Nigerian Remittance Platform)NNGLA', 'account_number': '1234567890', 'name': 'Test Sender'},
        receiver_info={'country': 'KE', 'bank_code': 'CBKEKENX', 'account_number': '9876543210', 'name': 'Test Receiver'},
        amount=500000,
        source_currency=AfricanCurrency.NGN,
        target_currency=AfricanCurrency.KES,
        fx_rate=0.095,
        converted_amount=47500,
        payment_type=PaymentType.COMMERCIAL,
        payment_method='bank_transfer',
        purpose_code='TRAD',
        reference='PAPSS-TEST-001',
        trade_corridor=TradeCorridorType.EAC,
        fees={'total': 1500},
        compliance_score=0.92,
        status=PaymentStatus.PROCESSING,
        created_at=datetime.utcnow()
    )

def get_papss_payments_with_filters(filters: Dict, limit: int, offset: int) -> List[PAPSSPayment]:
    """Get PAPSS payments with filters (simulated)"""
    # In production, this would query the database with filters
    return []

def get_papss_payments_count(filters: Dict) -> int:
    """Get total count of PAPSS payments matching filters"""
    # In production, this would count records in database
    return 0

def get_papss_analytics(start_date: datetime, end_date: datetime, trade_corridor: str = None, currency: str = None) -> Dict[str, Any]:
    """Get PAPSS analytics data"""
    # Simulate analytics data
    return {
        'period': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        },
        'summary': {
            'total_volume': 25000000,  # $250,000 equivalent
            'total_transactions': 85,
            'success_rate': 99.2,
            'average_settlement_time': 210,  # seconds
            'total_fees': 127500  # $1,275 equivalent
        },
        'trade_corridor_breakdown': [
            {'corridor': 'ECOWAS', 'volume': 12000000, 'count': 35, 'success_rate': 99.5},
            {'corridor': 'EAC', 'volume': 8000000, 'count': 25, 'success_rate': 98.8},
            {'corridor': 'SADC', 'volume': 4000000, 'count': 20, 'success_rate': 99.0},
            {'corridor': 'CEMAC', 'volume': 1000000, 'count': 5, 'success_rate': 100.0}
        ],
        'currency_breakdown': [
            {'currency': 'NGN', 'volume': 15000000, 'count': 45, 'success_rate': 99.3},
            {'currency': 'KES', 'volume': 5000000, 'count': 20, 'success_rate': 99.0},
            {'currency': 'GHS', 'volume': 3000000, 'count': 12, 'success_rate': 98.5},
            {'currency': 'ZAR', 'volume': 2000000, 'count': 8, 'success_rate': 100.0}
        ],
        'payment_method_breakdown': [
            {'method': 'bank_transfer', 'volume': 18000000, 'count': 55, 'avg_amount': 327273},
            {'method': 'mobile_money', 'volume': 5000000, 'count': 25, 'avg_amount': 200000},
            {'method': 'trade_finance', 'volume': 2000000, 'count': 5, 'avg_amount': 400000}
        ],
        'country_pairs': [
            {'sender': 'NG', 'receiver': 'KE', 'volume': 8000000, 'count': 25},
            {'sender': 'NG', 'receiver': 'GH', 'volume': 6000000, 'count': 20},
            {'sender': 'KE', 'receiver': 'UG', 'volume': 4000000, 'count': 15},
            {'sender': 'ZA', 'receiver': 'BW', 'volume': 3000000, 'count': 10}
        ]
    }

def papss_payment_to_dict(payment: PAPSSPayment) -> Dict[str, Any]:
    """Convert PAPSS payment object to dictionary"""
    return {
        'id': payment.id,
        'sender': payment.sender_info,
        'receiver': payment.receiver_info,
        'amount': payment.amount,
        'source_currency': payment.source_currency.value,
        'target_currency': payment.target_currency.value,
        'fx_rate': payment.fx_rate,
        'converted_amount': payment.converted_amount,
        'payment_type': payment.payment_type.value,
        'payment_method': payment.payment_method,
        'trade_corridor': payment.trade_corridor.value,
        'status': payment.status.value,
        'settlement_reference': getattr(payment, 'settlement_reference', None),
        'mobile_money_reference': getattr(payment, 'mobile_money_reference', None),
        'fees': payment.fees,
        'created_at': payment.created_at.isoformat(),
        'settled_at': payment.settled_at.isoformat() if hasattr(payment, 'settled_at') and payment.settled_at else None
    }

