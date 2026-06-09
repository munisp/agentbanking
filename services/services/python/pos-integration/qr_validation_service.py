"""
QR Code Validation and Processing Service
Enhanced QR code validation, processing, and security features
"""

import asyncio
import json
import logging
import hashlib
import hmac
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import os

import qrcode
import io
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field, validator
import aioredis
from sqlalchemy.orm import Session

from pos_service import POSService, SessionLocal, PaymentMethod, TransactionStatus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QRValidationRequest(BaseModel):
    qr_data: Dict[str, Any]

class QRValidationResponse(BaseModel):
    valid: bool
    merchant_name: Optional[str] = None
    description: Optional[str] = None
    error: Optional[str] = None
    security_score: Optional[float] = None
    risk_factors: Optional[List[str]] = None

class QRPaymentRequest(BaseModel):
    qr_data: Dict[str, Any]
    customer_pin: str = Field(..., min_length=4, max_length=6)
    payment_method: str = "qr_code"
    agent_id: str
    notes: Optional[str] = None

class QRPaymentResponse(BaseModel):
    success: bool
    transaction_id: Optional[str] = None
    error: Optional[str] = None
    receipt_data: Optional[Dict[str, Any]] = None
    security_alerts: Optional[List[str]] = None

class QRGenerationRequest(BaseModel):
    amount: float = Field(..., gt=0)
    currency: str = Field(..., min_length=3, max_length=3)
    merchant_id: str
    terminal_id: str
    description: Optional[str] = None
    expires_in_minutes: int = Field(default=5, ge=1, le=60)
    reference: Optional[str] = None

@dataclass
class QRSecurityConfig:
    max_amount_without_verification: float = 1000.0
    require_pin_for_amounts_above: float = 100.0
    max_daily_qr_transactions: int = 50
    qr_expiry_minutes: int = 5
    enable_digital_signature: bool = True
    enable_fraud_detection: bool = True

class QRValidationService:
    def __init__(self):
        self.pos_service = POSService()
        self.security_config = QRSecurityConfig()
        self.redis_client = None
        self.encryption_key = self._generate_encryption_key()
        self.fraud_patterns = self._load_fraud_patterns()
        
    async def init_redis(self):
        """Initialize Redis connection"""
        try:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
            self.redis_client = aioredis.from_url(redis_url)
            await self.redis_client.ping()
            logger.info("Redis connection initialized for QR validation")
        except Exception as e:
            logger.error(f"Failed to initialize Redis: {e}")

    def _generate_encryption_key(self) -> bytes:
        """Generate encryption key for QR code security"""
        password = os.getenv("QR_ENCRYPTION_PASSWORD", "default_qr_password").encode()
        salt = os.getenv("QR_ENCRYPTION_SALT", "default_salt").encode()
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        return key

    def _load_fraud_patterns(self) -> Dict[str, Any]:
        """Load fraud detection patterns"""
        return {
            "suspicious_amounts": [999.99, 1000.00, 1500.00, 2000.00],
            "high_risk_merchants": [],
            "velocity_limits": {
                "max_transactions_per_minute": 5,
                "max_amount_per_hour": 5000.0,
            },
            "geographic_restrictions": {
                "blocked_countries": [],
                "require_verification_countries": ["XX", "YY"],
            }
        }

    def _calculate_qr_hash(self, qr_data: Dict[str, Any]) -> str:
        """Calculate secure hash for QR code"""
        # Sort keys for consistent hashing
        sorted_data = json.dumps(qr_data, sort_keys=True)
        return hashlib.sha256(sorted_data.encode()).hexdigest()

    def _create_digital_signature(self, qr_data: Dict[str, Any]) -> str:
        """Create digital signature for QR code"""
        secret_key = os.getenv("QR_SIGNATURE_SECRET", "default_secret_key").encode()
        message = json.dumps(qr_data, sort_keys=True).encode()
        signature = hmac.new(secret_key, message, hashlib.sha256).hexdigest()
        return signature

    def _verify_digital_signature(self, qr_data: Dict[str, Any], signature: str) -> bool:
        """Verify digital signature of QR code"""
        try:
            expected_signature = self._create_digital_signature(qr_data)
            return hmac.compare_digest(signature, expected_signature)
        except Exception as e:
            logger.error(f"Signature verification failed: {e}")
            return False

    async def _check_fraud_patterns(self, qr_data: Dict[str, Any], agent_id: str) -> List[str]:
        """Check for fraud patterns in QR payment"""
        risk_factors = []
        
        try:
            amount = qr_data.get("amount", 0)
            merchant_id = qr_data.get("merchant_id", "")
            
            # Check suspicious amounts
            if amount in self.fraud_patterns["suspicious_amounts"]:
                risk_factors.append("suspicious_amount")
            
            # Check high-risk merchants
            if merchant_id in self.fraud_patterns["high_risk_merchants"]:
                risk_factors.append("high_risk_merchant")
            
            # Check velocity limits if Redis is available
            if self.redis_client:
                # Check transactions per minute
                minute_key = f"qr_velocity:{agent_id}:{int(time.time() // 60)}"
                minute_count = await self.redis_client.incr(minute_key)
                await self.redis_client.expire(minute_key, 60)
                
                if minute_count > self.fraud_patterns["velocity_limits"]["max_transactions_per_minute"]:
                    risk_factors.append("high_velocity_transactions")
                
                # Check amount per hour
                hour_key = f"qr_amount:{agent_id}:{int(time.time() // 3600)}"
                hour_amount = await self.redis_client.get(hour_key)
                hour_amount = float(hour_amount or 0) + amount
                await self.redis_client.set(hour_key, hour_amount, ex=3600)
                
                if hour_amount > self.fraud_patterns["velocity_limits"]["max_amount_per_hour"]:
                    risk_factors.append("high_velocity_amount")
            
            # Check for duplicate transactions
            qr_hash = self._calculate_qr_hash(qr_data)
            if self.redis_client:
                duplicate_key = f"qr_hash:{qr_hash}"
                is_duplicate = await self.redis_client.get(duplicate_key)
                if is_duplicate:
                    risk_factors.append("duplicate_transaction")
                else:
                    await self.redis_client.set(duplicate_key, "1", ex=300)  # 5 minutes
            
        except Exception as e:
            logger.error(f"Fraud pattern check failed: {e}")
            risk_factors.append("fraud_check_error")
        
        return risk_factors

    def _calculate_security_score(self, qr_data: Dict[str, Any], risk_factors: List[str]) -> float:
        """Calculate security score for QR code (0-100)"""
        base_score = 100.0
        
        # Deduct points for risk factors
        risk_penalties = {
            "expired": -50,
            "invalid_signature": -40,
            "suspicious_amount": -20,
            "high_risk_merchant": -30,
            "high_velocity_transactions": -25,
            "high_velocity_amount": -25,
            "duplicate_transaction": -60,
            "invalid_format": -40,
            "fraud_check_error": -10,
        }
        
        for risk_factor in risk_factors:
            penalty = risk_penalties.get(risk_factor, -10)
            base_score += penalty
        
        # Bonus points for security features
        if qr_data.get("signature"):
            base_score += 10
        if qr_data.get("encrypted_data"):
            base_score += 15
        
        return max(0.0, min(100.0, base_score))

    async def validate_qr_code(self, qr_data: Dict[str, Any]) -> QRValidationResponse:
        """Validate QR code data"""
        try:
            risk_factors = []
            
            # Basic format validation
            required_fields = ["transaction_id", "amount", "currency", "merchant_id", "terminal_id", "expires_at"]
            for field in required_fields:
                if field not in qr_data:
                    risk_factors.append("invalid_format")
                    return QRValidationResponse(
                        valid=False,
                        error=f"Missing required field: {field}",
                        security_score=0.0,
                        risk_factors=risk_factors
                    )
            
            # Validate data types
            try:
                amount = float(qr_data["amount"])
                if amount <= 0:
                    raise ValueError("Invalid amount")
            except (ValueError, TypeError):
                risk_factors.append("invalid_format")
                return QRValidationResponse(
                    valid=False,
                    error="Invalid amount format",
                    security_score=0.0,
                    risk_factors=risk_factors
                )
            
            # Check expiration
            try:
                expires_at = datetime.fromisoformat(qr_data["expires_at"].replace('Z', '+00:00'))
                if expires_at <= datetime.utcnow():
                    risk_factors.append("expired")
                    return QRValidationResponse(
                        valid=False,
                        error="QR code has expired",
                        security_score=0.0,
                        risk_factors=risk_factors
                    )
            except (ValueError, TypeError):
                risk_factors.append("invalid_format")
                return QRValidationResponse(
                    valid=False,
                    error="Invalid expiration format",
                    security_score=0.0,
                    risk_factors=risk_factors
                )
            
            # Verify digital signature if present
            if qr_data.get("signature") and self.security_config.enable_digital_signature:
                signature = qr_data.pop("signature")  # Remove signature for verification
                if not self._verify_digital_signature(qr_data, signature):
                    risk_factors.append("invalid_signature")
                    return QRValidationResponse(
                        valid=False,
                        error="Invalid digital signature",
                        security_score=0.0,
                        risk_factors=risk_factors
                    )
                qr_data["signature"] = signature  # Restore signature
            
            # Get merchant information
            db = SessionLocal()
            try:
                # This would typically query a merchant database
                merchant_name = f"Merchant {qr_data['merchant_id']}"
                description = qr_data.get("description", "QR Payment")
                
                # Fraud detection
                if self.security_config.enable_fraud_detection:
                    fraud_risks = await self._check_fraud_patterns(qr_data, "system")
                    risk_factors.extend(fraud_risks)
                
                # Calculate security score
                security_score = self._calculate_security_score(qr_data, risk_factors)
                
                # Determine if validation passes
                is_valid = security_score >= 50.0 and "expired" not in risk_factors
                
                return QRValidationResponse(
                    valid=is_valid,
                    merchant_name=merchant_name,
                    description=description,
                    security_score=security_score,
                    risk_factors=risk_factors,
                    error=None if is_valid else "Security validation failed"
                )
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"QR validation error: {e}")
            return QRValidationResponse(
                valid=False,
                error="Validation service error",
                security_score=0.0,
                risk_factors=["validation_error"]
            )

    async def process_qr_payment(self, payment_request: QRPaymentRequest) -> QRPaymentResponse:
        """Process QR code payment"""
        try:
            # First validate the QR code
            validation = await self.validate_qr_code(payment_request.qr_data)
            
            if not validation.valid:
                return QRPaymentResponse(
                    success=False,
                    error=validation.error,
                    security_alerts=validation.risk_factors
                )
            
            # Check if additional verification is needed
            amount = payment_request.qr_data["amount"]
            security_alerts = []
            
            if amount > self.security_config.max_amount_without_verification:
                security_alerts.append("high_amount_transaction")
            
            if validation.security_score < 70.0:
                security_alerts.append("low_security_score")
            
            # Process payment through POS service
            pos_payment_request = {
                "amount": amount,
                "currency": payment_request.qr_data["currency"],
                "payment_method": PaymentMethod.QR_CODE,
                "merchant_id": payment_request.qr_data["merchant_id"],
                "terminal_id": payment_request.qr_data["terminal_id"],
                "transaction_reference": payment_request.qr_data["transaction_id"],
                "customer_data": {
                    "agent_id": payment_request.agent_id,
                    "customer_pin": payment_request.customer_pin,
                },
                "metadata": {
                    "qr_validation_score": validation.security_score,
                    "risk_factors": validation.risk_factors,
                    "notes": payment_request.notes,
                }
            }
            
            # Convert to PaymentRequest dataclass
            from pos_service import PaymentRequest
            payment_req = PaymentRequest(**pos_payment_request)
            
            # Process payment
            payment_response = await self.pos_service._process_qr_payment(payment_req, None)
            
            if payment_response.status == TransactionStatus.APPROVED:
                return QRPaymentResponse(
                    success=True,
                    transaction_id=payment_response.transaction_id,
                    receipt_data=payment_response.receipt_data,
                    security_alerts=security_alerts
                )
            else:
                return QRPaymentResponse(
                    success=False,
                    error=payment_response.error_message or "Payment processing failed",
                    security_alerts=security_alerts
                )
                
        except Exception as e:
            logger.error(f"QR payment processing error: {e}")
            return QRPaymentResponse(
                success=False,
                error="Payment processing service error"
            )

    async def generate_secure_qr_code(self, request: QRGenerationRequest) -> Dict[str, Any]:
        """Generate secure QR code with enhanced security features"""
        try:
            # Create QR data
            expires_at = datetime.utcnow() + timedelta(minutes=request.expires_in_minutes)
            
            qr_data = {
                "transaction_id": str(uuid.uuid4()),
                "amount": request.amount,
                "currency": request.currency.upper(),
                "merchant_id": request.merchant_id,
                "terminal_id": request.terminal_id,
                "expires_at": expires_at.isoformat() + "Z",
                "created_at": datetime.utcnow().isoformat() + "Z",
                "version": "2.0",
            }
            
            if request.description:
                qr_data["description"] = request.description
            
            if request.reference:
                qr_data["reference"] = request.reference
            
            # Add security features
            if self.security_config.enable_digital_signature:
                signature = self._create_digital_signature(qr_data)
                qr_data["signature"] = signature
            
            # Generate QR code image
            qr_string = json.dumps(qr_data, sort_keys=True)
            
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,  # Medium error correction
                box_size=12,
                border=4,
            )
            qr.add_data(qr_string)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            # Store QR code hash for duplicate detection
            if self.redis_client:
                qr_hash = self._calculate_qr_hash(qr_data)
                await self.redis_client.set(
                    f"qr_generated:{qr_hash}", 
                    json.dumps(qr_data), 
                    ex=request.expires_in_minutes * 60
                )
            
            return {
                "qr_code": f"data:image/png;base64,{img_str}",
                "qr_data": qr_data,
                "expires_at": expires_at.isoformat(),
                "security_features": {
                    "digital_signature": self.security_config.enable_digital_signature,
                    "fraud_detection": self.security_config.enable_fraud_detection,
                    "expiry_minutes": request.expires_in_minutes,
                }
            }
            
        except Exception as e:
            logger.error(f"QR generation error: {e}")
            raise HTTPException(status_code=500, detail="QR code generation failed")

# Create service instance
qr_service = QRValidationService()

# FastAPI app for QR validation endpoints
app = FastAPI(title="QR Validation Service", version="1.0.0")

@app.on_event("startup")
async def startup_event():
    await qr_service.init_redis()

@app.post("/qr/validate", response_model=QRValidationResponse)
async def validate_qr_endpoint(request: QRValidationRequest):
    """Validate QR code data"""
    return await qr_service.validate_qr_code(request.qr_data)

@app.post("/qr/process-payment", response_model=QRPaymentResponse)
async def process_qr_payment_endpoint(request: QRPaymentRequest):
    """Process QR code payment"""
    return await qr_service.process_qr_payment(request)

@app.post("/qr/generate")
async def generate_qr_endpoint(request: QRGenerationRequest):
    """Generate secure QR code"""
    return await qr_service.generate_secure_qr_code(request)

@app.get("/qr/health")
async def qr_health_check():
    """Health check for QR validation service"""
    return {
        "status": "healthy",
        "service": "QR Validation Service",
        "timestamp": datetime.utcnow().isoformat(),
        "redis_connected": qr_service.redis_client is not None,
        "security_features": {
            "digital_signature": qr_service.security_config.enable_digital_signature,
            "fraud_detection": qr_service.security_config.enable_fraud_detection,
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "qr_validation_service:app",
        host="0.0.0.0",
        port=8071,
        reload=False,
        log_level="info"
    )
