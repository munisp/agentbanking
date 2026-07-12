#!/usr/bin/env python3
"""
Payment Processing Service
Multi-corridor payment processing with TigerBeetle integration
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
import uuid
import time
from datetime import datetime
from typing import Dict, Any, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# ─── Security Hardening (CVE-2024-34069, CVE-2026-27205) ─────────────────────
import os as _os
_flask_env = _os.getenv("FLASK_ENV", _os.getenv("APP_ENV", "production")).lower()
if _flask_env != "development":
    app.config["DEBUG"] = False
    app.config["TESTING"] = False
    _os.environ["WERKZEUG_DEBUG_PIN"] = "off"
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SECRET_KEY"] = _os.getenv("FLASK_SECRET_KEY", _os.urandom(32).hex())

@app.after_request
def _add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers.pop("Server", None)
    return response
# ─────────────────────────────────────────────────────────────────────────────

CORS(app)

# Payment corridors configuration
PAYMENT_CORRIDORS = {
    "PAPSS": {
        "name": "Pan-African Payment and Settlement System",
        "currencies": ["NGN", "GHS", "KES", "ZAR"],
        "fee_rate": 0.005,
        "processing_time": "2-5 minutes"
    },
    "CIPS": {
        "name": "Cross-border Interbank Payment System",
        "currencies": ["CNY", "USD", "EUR"],
        "fee_rate": 0.003,
        "processing_time": "1-3 minutes"
    },
    "PIX": {
        "name": "Brazilian Instant Payment System",
        "currencies": ["BRL"],
        "fee_rate": 0.001,
        "processing_time": "10-30 seconds"
    },
    "UPI": {
        "name": "Unified Payments Interface",
        "currencies": ["INR"],
        "fee_rate": 0.002,
        "processing_time": "5-15 seconds"
    },
    "MOJALOOP": {
        "name": "Open Source Payment Platform",
        "currencies": ["USD", "EUR", "GBP"],
        "fee_rate": 0.004,
        "processing_time": "30-60 seconds"
    }
}

class PaymentProcessor:
    def __init__(self) -> None:
        self.transactions = {}
    
    def validate_payment_request(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate payment request"""
        required_fields = ['sender_id', 'recipient_id', 'amount', 'currency', 'corridor']
        
        for field in required_fields:
            if field not in payment_data:
                return {"valid": False, "error": f"Missing required field: {field}"}
        
        # Validate corridor
        corridor = payment_data.get('corridor')
        if corridor not in PAYMENT_CORRIDORS:
            return {"valid": False, "error": f"Unsupported corridor: {corridor}"}
        
        # Validate currency for corridor
        currency = payment_data.get('currency')
        supported_currencies = PAYMENT_CORRIDORS[corridor]['currencies']
        if currency not in supported_currencies:
            return {"valid": False, "error": f"Currency {currency} not supported in {corridor}"}
        
        # Validate amount
        amount = payment_data.get('amount', 0)
        if amount <= 0:
            return {"valid": False, "error": "Amount must be positive"}
        
        return {"valid": True}
    
    def calculate_fees(self, amount: float, corridor: str) -> Dict[str, float]:
        """Calculate payment fees"""
        corridor_config = PAYMENT_CORRIDORS.get(corridor, {})
        fee_rate = corridor_config.get('fee_rate', 0.005)
        
        fee_amount = amount * fee_rate
        total_amount = amount + fee_amount
        
        return {
            "base_amount": amount,
            "fee_amount": fee_amount,
            "total_amount": total_amount,
            "fee_rate": fee_rate
        }
    
    def process_payment(self, payment_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process payment through selected corridor"""
        transaction_id = str(uuid.uuid4())
        
        # Validate request
        validation = self.validate_payment_request(payment_data)
        if not validation['valid']:
            return {
                "success": False,
                "transaction_id": transaction_id,
                "error": validation['error']
            }
        
        # Calculate fees
        fees = self.calculate_fees(payment_data['amount'], payment_data['corridor'])
        
        # Create transaction record
        transaction = {
            "transaction_id": transaction_id,
            "sender_id": payment_data['sender_id'],
            "recipient_id": payment_data['recipient_id'],
            "corridor": payment_data['corridor'],
            "currency": payment_data['currency'],
            "amount": payment_data['amount'],
            "fees": fees,
            "status": "processing",
            "created_at": datetime.utcnow().isoformat(),
            "processing_time": PAYMENT_CORRIDORS[payment_data['corridor']]['processing_time']
        }
        
        self.transactions[transaction_id] = transaction
        
        logger.info(f"Payment initiated: {transaction_id} via {payment_data['corridor']}")
        
        return {
            "success": True,
            "transaction_id": transaction_id,
            "status": "processing",
            "fees": fees,
            "estimated_completion": transaction['processing_time']
        }

# Initialize processor
payment_processor = PaymentProcessor()

@app.route('/health', methods=['GET'])
def health_check() -> None:
    """Health check endpoint"""
    return jsonify({
        "success": True,
        "service": "Payment Processing Service",
        "status": "healthy",
        "corridors": list(PAYMENT_CORRIDORS.keys()),
        "timestamp": datetime.utcnow().isoformat()
    })

@app.route('/api/v1/corridors', methods=['GET'])
def get_corridors() -> None:
    """Get available payment corridors"""
    return jsonify({
        "success": True,
        "corridors": PAYMENT_CORRIDORS
    })

@app.route('/api/v1/payment', methods=['POST'])
def initiate_payment() -> Tuple:
    """Initiate a payment transaction"""
    try:
        payment_data = request.get_json()
        if not payment_data:
            return jsonify({"success": False, "error": "No payment data provided"}), 400
        
        result = payment_processor.process_payment(payment_data)
        
        if result['success']:
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Payment processing error: {e}")
        return jsonify({
            "success": False,
            "error": "Internal server error"
        }), 500

@app.route('/api/v1/payment/<transaction_id>/status', methods=['GET'])
def get_payment_status(transaction_id) -> Tuple:
    """Get payment transaction status"""
    transaction = payment_processor.transactions.get(transaction_id)
    
    if not transaction:
        return jsonify({
            "success": False,
            "error": "Transaction not found"
        }), 404
    
    return jsonify({
        "success": True,
        "transaction": transaction
    })

@app.route('/api/v1/payment/calculate-fees', methods=['POST'])
def calculate_fees() -> Tuple:
    """Calculate fees for a payment"""
    try:
        data = request.get_json()
        amount = data.get('amount')
        corridor = data.get('corridor')
        
        if not amount or not corridor:
            return jsonify({
                "success": False,
                "error": "Amount and corridor are required"
            }), 400
        
        if corridor not in PAYMENT_CORRIDORS:
            return jsonify({
                "success": False,
                "error": f"Unsupported corridor: {corridor}"
            }), 400
        
        fees = payment_processor.calculate_fees(amount, corridor)
        
        return jsonify({
            "success": True,
            "fees": fees,
            "corridor_info": PAYMENT_CORRIDORS[corridor]
        })
        
    except Exception as e:
        logger.error(f"Fee calculation error: {e}")
        return jsonify({
            "success": False,
            "error": "Internal server error"
        }), 500

if __name__ == '__main__':
    logger.info("Starting Payment Processing Service...")
    app.run(host='0.0.0.0', port=5002, debug=False)
