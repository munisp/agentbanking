"""
SMS Gateway Service for Remittance Platform
Parses and executes SMS banking commands with:
- PIN/OTP verification for all transactions
- Rate limiting and fraud detection
- Idempotency for duplicate message handling
- Integration with backend transaction services
"""

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import logging
import json
import os
import re
import hashlib
import hmac
import secrets

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global connections
redis_client = None
http_client = None
db_pool = None


class Config:
    """Service configuration from environment variables"""
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://banking_user:banking_pass@localhost:5432/remittance")
    API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
    
    # SMS Provider settings
    SMS_PROVIDER = os.getenv("SMS_PROVIDER", "africas_talking")
    SMS_API_KEY = os.getenv("SMS_API_KEY", "")
    SMS_SENDER_ID = os.getenv("SMS_SENDER_ID", "AgentBank")
    SMS_WEBHOOK_SECRET = os.getenv("SMS_WEBHOOK_SECRET", "")
    
    # Security settings
    MAX_PIN_ATTEMPTS = int(os.getenv("MAX_PIN_ATTEMPTS", "3"))
    PIN_LOCKOUT_MINUTES = int(os.getenv("PIN_LOCKOUT_MINUTES", "30"))
    OTP_EXPIRY_SECONDS = int(os.getenv("OTP_EXPIRY_SECONDS", "300"))
    RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "5"))
    RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
    IDEMPOTENCY_WINDOW_SECONDS = int(os.getenv("IDEMPOTENCY_WINDOW_SECONDS", "86400"))  # 24 hours
    
    SERVICE_NAME = "sms-gateway"


config = Config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global redis_client, http_client, db_pool
    
    # Initialize Redis
    try:
        import redis.asyncio as redis_lib
        redis_client = redis_lib.from_url(
            config.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
        await redis_client.ping()
        logger.info("Redis connection established")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}")
        redis_client = None
    
    # Initialize HTTP client
    try:
        import httpx
        http_client = httpx.AsyncClient(timeout=30.0)
        logger.info("HTTP client initialized")
    except Exception as e:
        logger.error(f"HTTP client initialization failed: {e}")
        http_client = None
    
    # Initialize database pool
    try:
        import asyncpg
        db_pool = await asyncpg.create_pool(
            config.DATABASE_URL,
            min_size=5,
            max_size=20
        )
        logger.info("Database pool created")
    except Exception as e:
        logger.warning(f"Database pool creation failed: {e}")
        db_pool = None
    
    yield
    
    # Cleanup
    if redis_client:
        await redis_client.close()
    if http_client:
        await http_client.aclose()
    if db_pool:
        await db_pool.close()


app = FastAPI(
    title="SMS Gateway Service",
    description="SMS banking command parser and executor",
    version="1.0.0",
    lifespan=lifespan
)


# ============================================================================
# MODELS
# ============================================================================

class IncomingSMS(BaseModel):
    """Incoming SMS message"""
    message_id: str
    sender: str
    recipient: str
    message: str
    timestamp: Optional[str] = None
    provider: Optional[str] = None


class SMSCommand(BaseModel):
    """Parsed SMS command"""
    command_type: str
    params: Dict[str, Any]
    requires_pin: bool
    requires_otp: bool


class SMSResponse(BaseModel):
    """SMS response to send"""
    recipient: str
    message: str
    reference: Optional[str] = None


# ============================================================================
# SMS COMMAND PARSER
# ============================================================================

class SMSCommandParser:
    """Parse SMS banking commands"""
    
    # Command patterns
    PATTERNS = {
        # Balance check: *BAL# or BAL
        "balance": r"^\*?BAL\*?(\d{4})?\#?$",
        
        # Transfer: *TRANSFER*recipient*amount*PIN# or TRANSFER recipient amount PIN
        "transfer": r"^\*?TRANSFER\*?(\+?\d{10,15})\*?(\d+(?:\.\d{2})?)\*?(\d{4})?\#?$",
        
        # Statement: *STMT*days# or STMT days
        "statement": r"^\*?STMT\*?(\d{1,2})?\*?(\d{4})?\#?$",
        
        # Airtime: *AIRTIME*phone*amount*PIN# or AIRTIME phone amount PIN
        "airtime": r"^\*?AIRTIME\*?(\+?\d{10,15})\*?(\d+)\*?(\d{4})?\#?$",
        
        # Bill payment: *BILL*biller_code*account*amount*PIN#
        "bill": r"^\*?BILL\*?(\w+)\*?(\w+)\*?(\d+(?:\.\d{2})?)\*?(\d{4})?\#?$",
        
        # PIN change: *PIN*old_pin*new_pin*confirm_pin#
        "pin_change": r"^\*?PIN\*?(\d{4})\*?(\d{4})\*?(\d{4})\#?$",
        
        # Help: HELP or *HELP#
        "help": r"^\*?HELP\#?$",
        
        # Register: *REG*name# or REG name
        "register": r"^\*?REG\*?(.+)\#?$",
        
        # OTP verification: *OTP*code#
        "otp_verify": r"^\*?OTP\*?(\d{6})\#?$",
    }
    
    @classmethod
    def parse(cls, message: str) -> Optional[SMSCommand]:
        """Parse SMS message into command"""
        message = message.strip().upper()
        
        for cmd_type, pattern in cls.PATTERNS.items():
            match = re.match(pattern, message, re.IGNORECASE)
            if match:
                return cls._build_command(cmd_type, match.groups())
        
        return None
    
    @classmethod
    def _build_command(cls, cmd_type: str, groups: tuple) -> SMSCommand:
        """Build command from regex groups"""
        params = {}
        requires_pin = False
        requires_otp = False
        
        if cmd_type == "balance":
            params["pin"] = groups[0] if groups[0] else None
            requires_pin = True
        
        elif cmd_type == "transfer":
            params["recipient"] = groups[0]
            params["amount"] = float(groups[1])
            params["pin"] = groups[2] if len(groups) > 2 else None
            requires_pin = True
            requires_otp = True  # High-value transfers need OTP
        
        elif cmd_type == "statement":
            params["days"] = int(groups[0]) if groups[0] else 7
            params["pin"] = groups[1] if len(groups) > 1 else None
            requires_pin = True
        
        elif cmd_type == "airtime":
            params["phone"] = groups[0]
            params["amount"] = float(groups[1])
            params["pin"] = groups[2] if len(groups) > 2 else None
            requires_pin = True
        
        elif cmd_type == "bill":
            params["biller_code"] = groups[0]
            params["account"] = groups[1]
            params["amount"] = float(groups[2])
            params["pin"] = groups[3] if len(groups) > 3 else None
            requires_pin = True
        
        elif cmd_type == "pin_change":
            params["old_pin"] = groups[0]
            params["new_pin"] = groups[1]
            params["confirm_pin"] = groups[2]
            requires_pin = True
        
        elif cmd_type == "help":
            pass
        
        elif cmd_type == "register":
            params["name"] = groups[0]
        
        elif cmd_type == "otp_verify":
            params["otp_code"] = groups[0]
        
        return SMSCommand(
            command_type=cmd_type,
            params=params,
            requires_pin=requires_pin,
            requires_otp=requires_otp
        )


# ============================================================================
# SECURITY SERVICES
# ============================================================================

class PINService:
    """PIN verification and management"""
    
    @staticmethod
    async def verify_pin(phone: str, pin: str) -> Dict[str, Any]:
        """Verify user PIN"""
        # Check lockout status
        lockout_key = f"sms:pin_lockout:{phone}"
        if redis_client:
            lockout = await redis_client.get(lockout_key)
            if lockout:
                return {"valid": False, "error": "Account temporarily locked", "locked": True}
        
        # Verify PIN via API
        if http_client:
            try:
                response = await http_client.post(
                    f"{config.API_BASE_URL}/auth/verify-pin",
                    json={"phone": phone, "pin": pin}
                )
                if response.status_code == 200:
                    result = response.json()
                    if result.get("valid"):
                        # Reset attempts on success
                        if redis_client:
                            await redis_client.delete(f"sms:pin_attempts:{phone}")
                        return {"valid": True}
            except Exception as e:
                logger.error(f"PIN verification API error: {e}")
        
        # Increment failed attempts
        if redis_client:
            attempts_key = f"sms:pin_attempts:{phone}"
            attempts = await redis_client.incr(attempts_key)
            await redis_client.expire(attempts_key, 3600)  # 1 hour
            
            if attempts >= config.MAX_PIN_ATTEMPTS:
                # Lock account
                await redis_client.setex(
                    lockout_key,
                    config.PIN_LOCKOUT_MINUTES * 60,
                    "locked"
                )
                return {"valid": False, "error": "Too many attempts. Account locked.", "locked": True}
            
            remaining = config.MAX_PIN_ATTEMPTS - attempts
            return {"valid": False, "error": f"Invalid PIN. {remaining} attempts remaining."}
        
        return {"valid": False, "error": "Invalid PIN"}
    
    @staticmethod
    async def change_pin(phone: str, old_pin: str, new_pin: str) -> Dict[str, Any]:
        """Change user PIN"""
        if http_client:
            try:
                response = await http_client.post(
                    f"{config.API_BASE_URL}/auth/change-pin",
                    json={
                        "phone": phone,
                        "old_pin": old_pin,
                        "new_pin": new_pin
                    }
                )
                return response.json()
            except Exception as e:
                logger.error(f"PIN change API error: {e}")
        
        return {"success": False, "error": "Service unavailable"}


class OTPService:
    """OTP generation and verification"""
    
    @staticmethod
    async def generate_otp(phone: str, transaction_type: str, transaction_id: str) -> str:
        """Generate and store OTP"""
        otp = ''.join([str(secrets.randbelow(10)) for _ in range(6)])
        
        if redis_client:
            otp_key = f"sms:otp:{phone}:{transaction_id}"
            otp_data = json.dumps({
                "otp": otp,
                "transaction_type": transaction_type,
                "transaction_id": transaction_id,
                "created_at": datetime.now().isoformat()
            })
            await redis_client.setex(otp_key, config.OTP_EXPIRY_SECONDS, otp_data)
        
        return otp
    
    @staticmethod
    async def verify_otp(phone: str, transaction_id: str, otp_code: str) -> Dict[str, Any]:
        """Verify OTP"""
        if redis_client:
            otp_key = f"sms:otp:{phone}:{transaction_id}"
            otp_data = await redis_client.get(otp_key)
            
            if not otp_data:
                return {"valid": False, "error": "OTP expired or not found"}
            
            data = json.loads(otp_data)
            if data["otp"] == otp_code:
                await redis_client.delete(otp_key)
                return {"valid": True, "transaction_id": transaction_id}
            
            return {"valid": False, "error": "Invalid OTP"}
        
        return {"valid": False, "error": "OTP service unavailable"}


class RateLimiter:
    """Rate limiting for SMS commands"""
    
    @staticmethod
    async def check_rate_limit(phone: str) -> bool:
        """Check if request is within rate limit"""
        if not redis_client:
            return True
        
        rate_key = f"sms:rate:{phone}"
        
        try:
            current = await redis_client.incr(rate_key)
            if current == 1:
                await redis_client.expire(rate_key, config.RATE_LIMIT_WINDOW_SECONDS)
            
            return current <= config.RATE_LIMIT_REQUESTS
        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            return True


class IdempotencyService:
    """Idempotency for duplicate message handling"""
    
    @staticmethod
    async def check_and_store(message_id: str, phone: str) -> Optional[str]:
        """Check if message was already processed, return cached response if so"""
        if not redis_client:
            return None
        
        idem_key = f"sms:idem:{message_id}"
        
        try:
            cached = await redis_client.get(idem_key)
            if cached:
                logger.info(f"Duplicate message detected: {message_id}")
                return cached
            return None
        except Exception as e:
            logger.error(f"Idempotency check error: {e}")
            return None
    
    @staticmethod
    async def store_response(message_id: str, response: str) -> None:
        """Store response for idempotency"""
        if not redis_client:
            return
        
        idem_key = f"sms:idem:{message_id}"
        
        try:
            await redis_client.setex(
                idem_key,
                config.IDEMPOTENCY_WINDOW_SECONDS,
                response
            )
        except Exception as e:
            logger.error(f"Idempotency store error: {e}")


class FraudDetection:
    """Basic fraud detection for SMS banking"""
    
    @staticmethod
    async def check_transaction(phone: str, amount: float, transaction_type: str) -> Dict[str, Any]:
        """Check transaction for fraud indicators"""
        if not redis_client:
            return {"allowed": True}
        
        # Check daily transaction limit
        daily_key = f"sms:daily_total:{phone}:{datetime.now().strftime('%Y%m%d')}"
        
        try:
            daily_total = await redis_client.get(daily_key)
            daily_total = float(daily_total) if daily_total else 0
            
            # Daily limit of 500,000 NGN
            daily_limit = 500000
            if daily_total + amount > daily_limit:
                return {
                    "allowed": False,
                    "error": f"Daily limit exceeded. Remaining: NGN {daily_limit - daily_total:,.2f}"
                }
            
            # Check velocity (too many transactions in short time)
            velocity_key = f"sms:velocity:{phone}"
            velocity = await redis_client.incr(velocity_key)
            if velocity == 1:
                await redis_client.expire(velocity_key, 300)  # 5 minutes
            
            if velocity > 10:  # Max 10 transactions per 5 minutes
                return {"allowed": False, "error": "Too many transactions. Please wait."}
            
            return {"allowed": True}
        except Exception as e:
            logger.error(f"Fraud check error: {e}")
            return {"allowed": True}
    
    @staticmethod
    async def record_transaction(phone: str, amount: float) -> None:
        """Record transaction for fraud tracking"""
        if not redis_client:
            return
        
        daily_key = f"sms:daily_total:{phone}:{datetime.now().strftime('%Y%m%d')}"
        
        try:
            await redis_client.incrbyfloat(daily_key, amount)
            await redis_client.expire(daily_key, 86400)  # 24 hours
        except Exception as e:
            logger.error(f"Transaction recording error: {e}")


# ============================================================================
# COMMAND EXECUTOR
# ============================================================================

class SMSCommandExecutor:
    """Execute SMS banking commands"""
    
    def __init__(self):
        self.pin_service = PINService()
        self.otp_service = OTPService()
        self.fraud_detection = FraudDetection()
    
    async def execute(self, phone: str, command: SMSCommand, message_id: str) -> str:
        """Execute parsed command"""
        cmd_type = command.command_type
        params = command.params
        
        # Handle PIN verification if required
        if command.requires_pin:
            pin = params.get("pin")
            if not pin:
                return self._format_response(
                    cmd_type,
                    "error",
                    "PIN required. Please include your 4-digit PIN."
                )
            
            pin_result = await self.pin_service.verify_pin(phone, pin)
            if not pin_result.get("valid"):
                return self._format_response(cmd_type, "error", pin_result.get("error", "Invalid PIN"))
        
        # Execute command
        if cmd_type == "balance":
            return await self._execute_balance(phone)
        
        elif cmd_type == "transfer":
            return await self._execute_transfer(phone, params, message_id)
        
        elif cmd_type == "statement":
            return await self._execute_statement(phone, params)
        
        elif cmd_type == "airtime":
            return await self._execute_airtime(phone, params, message_id)
        
        elif cmd_type == "bill":
            return await self._execute_bill_payment(phone, params, message_id)
        
        elif cmd_type == "pin_change":
            return await self._execute_pin_change(phone, params)
        
        elif cmd_type == "help":
            return self._get_help_message()
        
        elif cmd_type == "register":
            return await self._execute_register(phone, params)
        
        elif cmd_type == "otp_verify":
            return await self._execute_otp_verify(phone, params)
        
        return "Invalid command. Reply HELP for available commands."
    
    async def _execute_balance(self, phone: str) -> str:
        """Execute balance inquiry"""
        if http_client:
            try:
                response = await http_client.get(
                    f"{config.API_BASE_URL}/accounts/balance",
                    params={"phone": phone}
                )
                if response.status_code == 200:
                    data = response.json()
                    return (
                        f"Your Balance:\n"
                        f"{data.get('currency', 'NGN')} {data.get('balance', 0):,.2f}\n"
                        f"Available: {data.get('currency', 'NGN')} {data.get('available_balance', 0):,.2f}"
                    )
            except Exception as e:
                logger.error(f"Balance API error: {e}")
        
        return "Unable to fetch balance. Please try again later."
    
    async def _execute_transfer(self, phone: str, params: Dict[str, Any], message_id: str) -> str:
        """Execute money transfer"""
        recipient = params["recipient"]
        amount = params["amount"]
        
        # Fraud check
        fraud_result = await self.fraud_detection.check_transaction(phone, amount, "transfer")
        if not fraud_result.get("allowed"):
            return fraud_result.get("error", "Transaction not allowed")
        
        # For high-value transfers, require OTP
        if amount >= 50000:  # NGN 50,000 threshold
            otp = await self.otp_service.generate_otp(phone, "transfer", message_id)
            
            # Send OTP via SMS
            await self._send_otp_sms(phone, otp)
            
            # Store pending transaction
            if redis_client:
                pending_key = f"sms:pending_transfer:{phone}:{message_id}"
                await redis_client.setex(
                    pending_key,
                    config.OTP_EXPIRY_SECONDS,
                    json.dumps({"recipient": recipient, "amount": amount})
                )
            
            return (
                f"Transfer of NGN {amount:,.2f} to {recipient} requires OTP verification.\n"
                f"An OTP has been sent to your phone.\n"
                f"Reply: OTP*123456 to confirm."
            )
        
        # Execute transfer
        return await self._process_transfer(phone, recipient, amount, message_id)
    
    async def _process_transfer(self, phone: str, recipient: str, amount: float, reference: str) -> str:
        """Process the actual transfer"""
        if http_client:
            try:
                response = await http_client.post(
                    f"{config.API_BASE_URL}/transfers",
                    json={
                        "sender_phone": phone,
                        "recipient_phone": recipient,
                        "amount": amount,
                        "channel": "sms",
                        "reference": reference
                    }
                )
                result = response.json()
                
                if result.get("success"):
                    await self.fraud_detection.record_transaction(phone, amount)
                    return (
                        f"Transfer Successful!\n"
                        f"Sent NGN {amount:,.2f} to {recipient}\n"
                        f"Ref: {result.get('reference', reference)}\n"
                        f"New Balance: NGN {result.get('new_balance', 0):,.2f}"
                    )
                else:
                    return f"Transfer Failed: {result.get('error', 'Unknown error')}"
            except Exception as e:
                logger.error(f"Transfer API error: {e}")
        
        return "Transfer service unavailable. Please try again later."
    
    async def _execute_statement(self, phone: str, params: Dict[str, Any]) -> str:
        """Execute mini statement"""
        days = params.get("days", 7)
        
        if http_client:
            try:
                response = await http_client.get(
                    f"{config.API_BASE_URL}/transactions/mini-statement",
                    params={"phone": phone, "days": days}
                )
                if response.status_code == 200:
                    data = response.json()
                    transactions = data.get("transactions", [])
                    
                    if not transactions:
                        return f"No transactions in the last {days} days."
                    
                    msg = f"Last {days} days:\n"
                    for txn in transactions[:5]:
                        date = txn.get("date", "N/A")
                        txn_type = txn.get("type", "N/A")
                        amount = txn.get("amount", 0)
                        sign = "+" if txn.get("credit") else "-"
                        msg += f"{date}: {txn_type} {sign}NGN{amount:,.0f}\n"
                    
                    return msg
            except Exception as e:
                logger.error(f"Statement API error: {e}")
        
        return "Unable to fetch statement. Please try again later."
    
    async def _execute_airtime(self, phone: str, params: Dict[str, Any], message_id: str) -> str:
        """Execute airtime purchase"""
        target_phone = params["phone"]
        amount = params["amount"]
        
        # Fraud check
        fraud_result = await self.fraud_detection.check_transaction(phone, amount, "airtime")
        if not fraud_result.get("allowed"):
            return fraud_result.get("error", "Transaction not allowed")
        
        if http_client:
            try:
                response = await http_client.post(
                    f"{config.API_BASE_URL}/airtime/purchase",
                    json={
                        "phone": phone,
                        "target_phone": target_phone,
                        "amount": amount,
                        "channel": "sms",
                        "reference": message_id
                    }
                )
                result = response.json()
                
                if result.get("success"):
                    await self.fraud_detection.record_transaction(phone, amount)
                    return (
                        f"Airtime Purchase Successful!\n"
                        f"NGN {amount:,.0f} sent to {target_phone}\n"
                        f"Ref: {result.get('reference', message_id)}"
                    )
                else:
                    return f"Airtime Purchase Failed: {result.get('error', 'Unknown error')}"
            except Exception as e:
                logger.error(f"Airtime API error: {e}")
        
        return "Airtime service unavailable. Please try again later."
    
    async def _execute_bill_payment(self, phone: str, params: Dict[str, Any], message_id: str) -> str:
        """Execute bill payment"""
        biller_code = params["biller_code"]
        account = params["account"]
        amount = params["amount"]
        
        # Fraud check
        fraud_result = await self.fraud_detection.check_transaction(phone, amount, "bill")
        if not fraud_result.get("allowed"):
            return fraud_result.get("error", "Transaction not allowed")
        
        if http_client:
            try:
                response = await http_client.post(
                    f"{config.API_BASE_URL}/bills/pay",
                    json={
                        "phone": phone,
                        "biller_code": biller_code,
                        "account_number": account,
                        "amount": amount,
                        "channel": "sms",
                        "reference": message_id
                    }
                )
                result = response.json()
                
                if result.get("success"):
                    await self.fraud_detection.record_transaction(phone, amount)
                    return (
                        f"Bill Payment Successful!\n"
                        f"Paid NGN {amount:,.2f} to {biller_code}\n"
                        f"Account: {account}\n"
                        f"Ref: {result.get('reference', message_id)}"
                    )
                else:
                    return f"Bill Payment Failed: {result.get('error', 'Unknown error')}"
            except Exception as e:
                logger.error(f"Bill payment API error: {e}")
        
        return "Bill payment service unavailable. Please try again later."
    
    async def _execute_pin_change(self, phone: str, params: Dict[str, Any]) -> str:
        """Execute PIN change"""
        old_pin = params["old_pin"]
        new_pin = params["new_pin"]
        confirm_pin = params["confirm_pin"]
        
        if new_pin != confirm_pin:
            return "New PIN and confirmation do not match."
        
        if len(new_pin) != 4 or not new_pin.isdigit():
            return "PIN must be exactly 4 digits."
        
        result = await self.pin_service.change_pin(phone, old_pin, new_pin)
        
        if result.get("success"):
            return "PIN changed successfully!"
        else:
            return f"PIN change failed: {result.get('error', 'Unknown error')}"
    
    async def _execute_register(self, phone: str, params: Dict[str, Any]) -> str:
        """Execute user registration"""
        name = params.get("name", "")
        
        if http_client:
            try:
                response = await http_client.post(
                    f"{config.API_BASE_URL}/auth/register-sms",
                    json={
                        "phone": phone,
                        "name": name,
                        "channel": "sms"
                    }
                )
                result = response.json()
                
                if result.get("success"):
                    return (
                        f"Registration Successful!\n"
                        f"Welcome {name}!\n"
                        f"Your temporary PIN has been sent via SMS.\n"
                        f"Please change it using: PIN*oldpin*newpin*newpin"
                    )
                else:
                    return f"Registration Failed: {result.get('error', 'Unknown error')}"
            except Exception as e:
                logger.error(f"Registration API error: {e}")
        
        return "Registration service unavailable. Please try again later."
    
    async def _execute_otp_verify(self, phone: str, params: Dict[str, Any]) -> str:
        """Execute OTP verification for pending transaction"""
        otp_code = params["otp_code"]
        
        # Find pending transaction
        if redis_client:
            # Search for pending transfer
            pattern = f"sms:pending_transfer:{phone}:*"
            keys = []
            async for key in redis_client.scan_iter(pattern):
                keys.append(key)
            
            if not keys:
                return "No pending transaction found. OTP may have expired."
            
            # Get the most recent pending transaction
            pending_key = keys[0]
            message_id = pending_key.split(":")[-1]
            
            # Verify OTP
            otp_result = await self.otp_service.verify_otp(phone, message_id, otp_code)
            
            if otp_result.get("valid"):
                # Get pending transaction details
                pending_data = await redis_client.get(pending_key)
                if pending_data:
                    data = json.loads(pending_data)
                    await redis_client.delete(pending_key)
                    
                    # Execute the transfer
                    return await self._process_transfer(
                        phone,
                        data["recipient"],
                        data["amount"],
                        message_id
                    )
            else:
                return otp_result.get("error", "Invalid OTP")
        
        return "OTP verification failed. Please try again."
    
    async def _send_otp_sms(self, phone: str, otp: str) -> None:
        """Send OTP via SMS"""
        message = f"Your Remittance Platform OTP is: {otp}. Valid for 5 minutes. Do not share this code."
        await SMSSender.send(phone, message)
    
    def _get_help_message(self) -> str:
        """Get help message"""
        return (
            "Remittance Platform SMS Commands:\n"
            "BAL*PIN - Check balance\n"
            "TRANSFER*phone*amount*PIN - Send money\n"
            "STMT*days*PIN - Mini statement\n"
            "AIRTIME*phone*amount*PIN - Buy airtime\n"
            "BILL*code*account*amount*PIN - Pay bill\n"
            "PIN*old*new*confirm - Change PIN\n"
            "REG*name - Register"
        )
    
    def _format_response(self, cmd_type: str, status: str, message: str) -> str:
        """Format response message"""
        return message


# ============================================================================
# SMS SENDER
# ============================================================================

class SMSSender:
    """Send SMS via provider"""
    
    @staticmethod
    async def send(recipient: str, message: str) -> Dict[str, Any]:
        """Send SMS message"""
        if not http_client:
            logger.warning("HTTP client not available for SMS sending")
            return {"success": False, "error": "SMS service unavailable"}
        
        if config.SMS_PROVIDER == "africas_talking":
            return await SMSSender._send_africas_talking(recipient, message)
        elif config.SMS_PROVIDER == "twilio":
            return await SMSSender._send_twilio(recipient, message)
        else:
            logger.warning(f"Unknown SMS provider: {config.SMS_PROVIDER}")
            return {"success": False, "error": "SMS provider not configured"}
    
    @staticmethod
    async def _send_africas_talking(recipient: str, message: str) -> Dict[str, Any]:
        """Send via Africa's Talking"""
        try:
            response = await http_client.post(
                "https://api.africastalking.com/version1/messaging",
                headers={
                    "apiKey": config.SMS_API_KEY,
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                data={
                    "username": "sandbox",  # Use actual username in production
                    "to": recipient,
                    "message": message,
                    "from": config.SMS_SENDER_ID
                }
            )
            return {"success": response.status_code == 201, "response": response.json()}
        except Exception as e:
            logger.error(f"Africa's Talking SMS error: {e}")
            return {"success": False, "error": str(e)}
    
    @staticmethod
    async def _send_twilio(recipient: str, message: str) -> Dict[str, Any]:
        """Send via Twilio"""
        # Twilio implementation would go here
        return {"success": False, "error": "Twilio not implemented"}


# ============================================================================
# DATABASE OPERATIONS
# ============================================================================

class SMSLogRepository:
    """Log SMS transactions to database"""
    
    @staticmethod
    async def log_incoming(message_id: str, sender: str, message: str, command_type: str) -> None:
        """Log incoming SMS"""
        if not db_pool:
            return
        
        try:
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO sms_logs (message_id, phone, direction, message, command_type, created_at)
                    VALUES ($1, $2, 'incoming', $3, $4, NOW())
                    ON CONFLICT (message_id) DO NOTHING
                """, message_id, sender, message, command_type)
        except Exception as e:
            logger.error(f"SMS log error: {e}")
    
    @staticmethod
    async def log_outgoing(recipient: str, message: str, reference: str) -> None:
        """Log outgoing SMS"""
        if not db_pool:
            return
        
        try:
            async with db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO sms_logs (message_id, phone, direction, message, reference, created_at)
                    VALUES ($1, $2, 'outgoing', $3, $4, NOW())
                """, f"out_{reference}", recipient, message, reference)
        except Exception as e:
            logger.error(f"SMS log error: {e}")


# ============================================================================
# API ENDPOINTS
# ============================================================================

command_executor = SMSCommandExecutor()


def verify_webhook_signature(request: Request, body: bytes) -> bool:
    """Verify webhook signature from SMS provider"""
    if not config.SMS_WEBHOOK_SECRET:
        return True  # Skip verification if no secret configured
    
    signature = request.headers.get("X-SMS-Signature", "")
    if not signature:
        return False
    
    expected = hmac.new(
        config.SMS_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected)


@app.post("/webhook/sms")
async def sms_webhook(request: Request, background_tasks: BackgroundTasks):
    """Webhook endpoint for incoming SMS"""
    body = await request.body()
    
    # Verify signature
    if not verify_webhook_signature(request, body):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    try:
        # Parse incoming SMS (format depends on provider)
        data = await request.json()
        
        incoming = IncomingSMS(
            message_id=data.get("messageId", data.get("id", "")),
            sender=data.get("from", data.get("sender", "")),
            recipient=data.get("to", data.get("recipient", "")),
            message=data.get("text", data.get("message", "")),
            timestamp=data.get("timestamp"),
            provider=data.get("provider", config.SMS_PROVIDER)
        )
        
        # Process SMS
        response = await process_incoming_sms(incoming, background_tasks)
        
        return {"status": "success", "response": response}
    
    except Exception as e:
        logger.error(f"SMS webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/sms/process")
async def process_sms_api(incoming: IncomingSMS, background_tasks: BackgroundTasks):
    """API endpoint for processing SMS (used by unified messaging platform)"""
    response = await process_incoming_sms(incoming, background_tasks)
    return {"status": "success", "response": response}


async def process_incoming_sms(incoming: IncomingSMS, background_tasks: BackgroundTasks) -> str:
    """Process incoming SMS message"""
    phone = incoming.sender
    message = incoming.message
    message_id = incoming.message_id
    
    # Rate limiting
    if not await RateLimiter.check_rate_limit(phone):
        return "Too many requests. Please wait a moment and try again."
    
    # Idempotency check
    cached_response = await IdempotencyService.check_and_store(message_id, phone)
    if cached_response:
        return cached_response
    
    # Parse command
    command = SMSCommandParser.parse(message)
    
    if not command:
        response = "Invalid command. Reply HELP for available commands."
    else:
        # Log incoming SMS
        background_tasks.add_task(
            SMSLogRepository.log_incoming,
            message_id, phone, message, command.command_type
        )
        
        # Execute command
        response = await command_executor.execute(phone, command, message_id)
    
    # Store response for idempotency
    await IdempotencyService.store_response(message_id, response)
    
    # Send response SMS
    background_tasks.add_task(SMSSender.send, phone, response)
    background_tasks.add_task(SMSLogRepository.log_outgoing, phone, response, message_id)
    
    return response


@app.post("/api/v1/sms/send")
async def send_sms_api(response: SMSResponse):
    """API endpoint for sending SMS"""
    result = await SMSSender.send(response.recipient, response.message)
    return result


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    redis_status = "connected" if redis_client else "disconnected"
    db_status = "connected" if db_pool else "disconnected"
    
    return {
        "status": "healthy",
        "service": config.SERVICE_NAME,
        "version": "1.0.0",
        "redis": redis_status,
        "database": db_status
    }


@app.get("/metrics")
async def get_metrics():
    """Get service metrics"""
    return {
        "service": config.SERVICE_NAME,
        "version": "1.0.0",
        "redis_connected": redis_client is not None,
        "db_connected": db_pool is not None,
        "http_client_ready": http_client is not None
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8022)
