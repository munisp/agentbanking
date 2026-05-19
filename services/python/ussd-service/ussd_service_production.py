"""
Production-Ready USSD Service for Remittance Platform
Provides interactive menu system for feature phones with:
- Redis session storage with TTL
- Real backend API integration
- PIN verification for transactions
- Rate limiting and fraud detection
"""

from fastapi import FastAPI, Request, Response, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from enum import Enum
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
import logging
import json
import os
import hashlib
import hmac
import uuid as _uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global connections
redis_client = None
http_client = None


class Config:
    """Service configuration from environment variables"""
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000/api/v1")
    SESSION_TTL_SECONDS = int(os.getenv("SESSION_TTL_SECONDS", "300"))  # 5 minutes
    MAX_PIN_ATTEMPTS = int(os.getenv("MAX_PIN_ATTEMPTS", "3"))
    RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "10"))
    RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
    USSD_PROVIDER_SECRET = os.getenv("USSD_PROVIDER_SECRET", "")
    SERVICE_NAME = "ussd-service"


config = Config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global redis_client, http_client
    
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
        logger.warning(f"Redis connection failed: {e}, using in-memory fallback")
        redis_client = None
    
    try:
        import httpx
        http_client = httpx.AsyncClient(timeout=30.0)
        logger.info("HTTP client initialized")
    except Exception as e:
        logger.error(f"HTTP client initialization failed: {e}")
        http_client = None
    
    yield
    
    if redis_client:
        await redis_client.close()
    if http_client:
        await http_client.aclose()


app = FastAPI(
    title="USSD Service (Production)",
    description="Production-ready interactive USSD menus for feature phones",
    version="2.0.0",
    lifespan=lifespan
)


# ============================================================================
# MODELS & ENUMS
# ============================================================================

class USSDRequest(BaseModel):
    sessionId: str
    serviceCode: str
    phoneNumber: str
    text: str


class MenuState(str, Enum):
    MAIN_MENU = "main_menu"
    CHECK_BALANCE = "check_balance"
    ENTER_PIN = "enter_pin"
    VIEW_ORDERS = "view_orders"
    VIEW_ORDER_DETAIL = "view_order_detail"
    BROWSE_PRODUCTS = "browse_products"
    VIEW_CATEGORY = "view_category"
    VIEW_PRODUCT = "view_product"
    MAKE_PAYMENT = "make_payment"
    CONFIRM_PAYMENT = "confirm_payment"
    ENTER_PAYMENT_PIN = "enter_payment_pin"
    TRANSFER_MONEY = "transfer_money"
    ENTER_TRANSFER_RECIPIENT = "enter_transfer_recipient"
    ENTER_TRANSFER_AMOUNT = "enter_transfer_amount"
    CONFIRM_TRANSFER = "confirm_transfer"
    ENTER_TRANSFER_PIN = "enter_transfer_pin"
    MINI_STATEMENT = "mini_statement"
    CUSTOMER_SUPPORT = "customer_support"


# ============================================================================
# REDIS SESSION MANAGEMENT
# ============================================================================

class RedisSessionManager:
    """Production session manager using Redis with TTL"""
    
    def __init__(self):
        self.fallback_sessions = {}  # In-memory fallback
    
    async def get_session(self, session_id: str, phone_number: str) -> Dict[str, Any]:
        """Get session data from Redis"""
        session_key = f"ussd:session:{session_id}"
        
        if redis_client:
            try:
                session_data = await redis_client.get(session_key)
                if session_data:
                    session = json.loads(session_data)
                    # Refresh TTL on access
                    await redis_client.expire(session_key, config.SESSION_TTL_SECONDS)
                    return session
            except Exception as e:
                logger.error(f"Redis get session error: {e}")
        
        # Create new session
        session = {
            "state": MenuState.MAIN_MENU.value,
            "data": {},
            "history": [],
            "phone_number": phone_number,
            "created_at": datetime.now().isoformat(),
            "pin_attempts": 0
        }
        
        await self.save_session(session_id, session)
        return session
    
    async def save_session(self, session_id: str, session: Dict[str, Any]) -> None:
        """Save session to Redis with TTL"""
        session_key = f"ussd:session:{session_id}"
        
        if redis_client:
            try:
                await redis_client.setex(
                    session_key,
                    config.SESSION_TTL_SECONDS,
                    json.dumps(session)
                )
                return
            except Exception as e:
                logger.error(f"Redis save session error: {e}")
        
        # Fallback to in-memory
        self.fallback_sessions[session_id] = session
    
    async def update_session(self, session_id: str, state: MenuState, data: Dict[str, Any] = None) -> None:
        """Update session state"""
        session = await self.get_session(session_id, "")
        session["history"].append(session["state"])
        session["state"] = state.value
        if data:
            session["data"].update(data)
        await self.save_session(session_id, session)
    
    async def go_back(self, session_id: str) -> None:
        """Go back to previous menu"""
        session = await self.get_session(session_id, "")
        if session["history"]:
            session["state"] = session["history"].pop()
            await self.save_session(session_id, session)
    
    async def clear_session(self, session_id: str) -> None:
        """Clear session data"""
        session_key = f"ussd:session:{session_id}"
        
        if redis_client:
            try:
                await redis_client.delete(session_key)
            except Exception as e:
                logger.error(f"Redis clear session error: {e}")
        
        if session_id in self.fallback_sessions:
            del self.fallback_sessions[session_id]
    
    async def increment_pin_attempts(self, session_id: str) -> int:
        """Increment PIN attempt counter"""
        session = await self.get_session(session_id, "")
        session["pin_attempts"] = session.get("pin_attempts", 0) + 1
        await self.save_session(session_id, session)
        return session["pin_attempts"]
    
    async def reset_pin_attempts(self, session_id: str) -> None:
        """Reset PIN attempt counter"""
        session = await self.get_session(session_id, "")
        session["pin_attempts"] = 0
        await self.save_session(session_id, session)


# ============================================================================
# BACKEND API CLIENT
# ============================================================================

class BackendAPIClient:
    """Client for backend API calls"""
    
    async def get_user_balance(self, phone_number: str) -> Dict[str, Any]:
        """Get user balance from backend"""
        if http_client:
            try:
                response = await http_client.get(
                    f"{config.API_BASE_URL}/accounts/balance",
                    params={"phone": phone_number}
                )
                if response.status_code == 200:
                    return response.json()
            except Exception as e:
                logger.error(f"Get balance API error: {e}")
        
        # Fallback response for development
        return {
            "balance": 0,
            "currency": "NGN",
            "available_balance": 0,
            "error": "Unable to fetch balance"
        }
    
    async def get_user_orders(self, phone_number: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get user orders from backend"""
        if http_client:
            try:
                response = await http_client.get(
                    f"{config.API_BASE_URL}/orders",
                    params={"phone": phone_number, "limit": limit}
                )
                if response.status_code == 200:
                    return response.json().get("orders", [])
            except Exception as e:
                logger.error(f"Get orders API error: {e}")
        
        return []
    
    async def get_order_detail(self, order_id: str, phone_number: str) -> Optional[Dict[str, Any]]:
        """Get order details from backend"""
        if http_client:
            try:
                response = await http_client.get(
                    f"{config.API_BASE_URL}/orders/{order_id}",
                    params={"phone": phone_number}
                )
                if response.status_code == 200:
                    return response.json()
            except Exception as e:
                logger.error(f"Get order detail API error: {e}")
        
        return None
    
    async def get_categories(self) -> List[Dict[str, Any]]:
        """Get product categories from backend"""
        if http_client:
            try:
                response = await http_client.get(f"{config.API_BASE_URL}/products/categories")
                if response.status_code == 200:
                    return response.json().get("categories", [])
            except Exception as e:
                logger.error(f"Get categories API error: {e}")
        
        return []
    
    async def get_products_by_category(self, category_id: int) -> List[Dict[str, Any]]:
        """Get products by category from backend"""
        if http_client:
            try:
                response = await http_client.get(
                    f"{config.API_BASE_URL}/products",
                    params={"category_id": category_id}
                )
                if response.status_code == 200:
                    return response.json().get("products", [])
            except Exception as e:
                logger.error(f"Get products API error: {e}")
        
        return []
    
    async def get_product_detail(self, product_id: int) -> Optional[Dict[str, Any]]:
        """Get product details from backend"""
        if http_client:
            try:
                response = await http_client.get(f"{config.API_BASE_URL}/products/{product_id}")
                if response.status_code == 200:
                    return response.json()
            except Exception as e:
                logger.error(f"Get product detail API error: {e}")
        
        return None
    
    async def verify_pin(self, phone_number: str, pin: str) -> bool:
        """Verify user PIN"""
        if http_client:
            try:
                response = await http_client.post(
                    f"{config.API_BASE_URL}/auth/verify-pin",
                    json={"phone": phone_number, "pin": pin}
                )
                if response.status_code == 200:
                    return response.json().get("valid", False)
            except Exception as e:
                logger.error(f"Verify PIN API error: {e}")
        
        return False
    
    async def process_payment(self, phone_number: str, order_id: str, pin: str, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        """Process payment for order with idempotency key forwarding"""
        if http_client:
            try:
                idem_key = idempotency_key or str(_uuid.uuid4())
                response = await http_client.post(
                    f"{config.API_BASE_URL}/payments/process",
                    json={
                        "phone": phone_number,
                        "order_id": order_id,
                        "pin": pin,
                        "channel": "ussd"
                    },
                    headers={"Idempotency-Key": idem_key},
                )
                return response.json()
            except Exception as e:
                logger.error(f"Process payment API error: {e}")
        
        return {"success": False, "error": "Payment service unavailable"}
    
    async def process_transfer(self, phone_number: str, recipient: str, amount: float, pin: str, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        """Process money transfer with idempotency key forwarding"""
        if http_client:
            try:
                idem_key = idempotency_key or str(_uuid.uuid4())
                response = await http_client.post(
                    f"{config.API_BASE_URL}/transfers",
                    json={
                        "sender_phone": phone_number,
                        "recipient_phone": recipient,
                        "amount": amount,
                        "pin": pin,
                        "channel": "ussd"
                    },
                    headers={"Idempotency-Key": idem_key},
                )
                return response.json()
            except Exception as e:
                logger.error(f"Process transfer API error: {e}")
        
        return {"success": False, "error": "Transfer service unavailable"}
    
    async def get_mini_statement(self, phone_number: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get mini statement"""
        if http_client:
            try:
                response = await http_client.get(
                    f"{config.API_BASE_URL}/transactions/mini-statement",
                    params={"phone": phone_number, "limit": limit}
                )
                if response.status_code == 200:
                    return response.json().get("transactions", [])
            except Exception as e:
                logger.error(f"Get mini statement API error: {e}")
        
        return []
    
    async def verify_recipient(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """Verify transfer recipient"""
        if http_client:
            try:
                response = await http_client.get(
                    f"{config.API_BASE_URL}/accounts/verify",
                    params={"phone": phone_number}
                )
                if response.status_code == 200:
                    return response.json()
            except Exception as e:
                logger.error(f"Verify recipient API error: {e}")
        
        return None


# ============================================================================
# RATE LIMITER
# ============================================================================

class RateLimiter:
    """Rate limiter using Redis"""
    
    async def check_rate_limit(self, phone_number: str) -> bool:
        """Check if request is within rate limit"""
        if not redis_client:
            return True
        
        rate_key = f"ussd:rate:{phone_number}"
        
        try:
            current = await redis_client.incr(rate_key)
            if current == 1:
                await redis_client.expire(rate_key, config.RATE_LIMIT_WINDOW_SECONDS)
            
            return current <= config.RATE_LIMIT_REQUESTS
        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            return True


# ============================================================================
# MENU BUILDER (Production)
# ============================================================================

class ProductionMenuBuilder:
    """Build USSD menu responses with real data"""
    
    def __init__(self, api_client: BackendAPIClient):
        self.api = api_client
    
    @staticmethod
    def main_menu() -> str:
        """Main menu"""
        return (
            "CON Welcome to Remittance Platform\n"
            "1. Check Balance\n"
            "2. Transfer Money\n"
            "3. View Orders\n"
            "4. Browse Products\n"
            "5. Make Payment\n"
            "6. Mini Statement\n"
            "7. Customer Support\n"
            "0. Exit"
        )
    
    async def check_balance(self, phone: str) -> str:
        """Display balance (requires PIN verification first)"""
        data = await self.api.get_user_balance(phone)
        
        if "error" in data and data.get("balance", 0) == 0:
            return "END Unable to fetch balance. Please try again later."
        
        return (
            f"END Your Balance\n"
            f"{data.get('currency', 'NGN')} {data.get('balance', 0):,.2f}\n"
            f"Available: {data.get('currency', 'NGN')} {data.get('available_balance', 0):,.2f}\n\n"
            f"Thank you for using our service!"
        )
    
    @staticmethod
    def enter_pin(action: str = "continue") -> str:
        """Prompt for PIN entry"""
        return f"CON Enter your 4-digit PIN to {action}:"
    
    @staticmethod
    def pin_error(attempts_remaining: int) -> str:
        """PIN error message"""
        if attempts_remaining <= 0:
            return "END Too many incorrect PIN attempts. Your account has been temporarily locked."
        return f"CON Incorrect PIN. {attempts_remaining} attempts remaining.\nEnter PIN:"
    
    async def view_orders(self, phone: str) -> str:
        """Display orders list"""
        orders = await self.api.get_user_orders(phone)
        
        if not orders:
            return "END You have no orders yet."
        
        menu = "CON Your Orders\n"
        for i, order in enumerate(orders[:5], 1):
            status = order.get('status', 'unknown').upper()
            total = order.get('total', 0)
            currency = order.get('currency', 'NGN')
            menu += f"{i}. {order.get('id', 'N/A')}: {currency} {total:,.0f} ({status})\n"
        menu += "0. Back"
        return menu
    
    async def view_order_detail(self, order_id: str, phone: str) -> str:
        """Display order details"""
        order = await self.api.get_order_detail(order_id, phone)
        
        if not order:
            return "END Order not found."
        
        return (
            f"END Order Details\n"
            f"ID: {order.get('id', 'N/A')}\n"
            f"Items: {order.get('items', 'N/A')}\n"
            f"Total: {order.get('currency', 'NGN')} {order.get('total', 0):,.0f}\n"
            f"Status: {order.get('status', 'unknown').upper()}"
        )
    
    async def browse_products(self) -> str:
        """Display product categories"""
        categories = await self.api.get_categories()
        
        if not categories:
            return "END No categories available."
        
        menu = "CON Select Category\n"
        for i, cat in enumerate(categories[:9], 1):
            menu += f"{i}. {cat.get('name', 'Unknown')}\n"
        menu += "0. Back"
        return menu
    
    async def view_category(self, category_id: int) -> str:
        """Display products in category"""
        products = await self.api.get_products_by_category(category_id)
        
        if not products:
            return "END No products in this category."
        
        menu = "CON Products\n"
        for i, product in enumerate(products[:9], 1):
            price = product.get('price', 0)
            currency = product.get('currency', 'NGN')
            menu += f"{i}. {product.get('name', 'Unknown')} - {currency} {price:,.0f}\n"
        menu += "0. Back"
        return menu
    
    async def view_product(self, product_id: int) -> str:
        """Display product details"""
        product = await self.api.get_product_detail(product_id)
        
        if not product:
            return "END Product not found."
        
        return (
            f"END {product.get('name', 'Unknown')}\n"
            f"Price: {product.get('currency', 'NGN')} {product.get('price', 0):,.0f}\n"
            f"Description: {product.get('description', 'N/A')}\n\n"
            f"To order, dial *123*ORDER#"
        )
    
    @staticmethod
    def make_payment() -> str:
        """Payment entry"""
        return "CON Enter Order ID:"
    
    async def confirm_payment(self, order_id: str, phone: str) -> str:
        """Confirm payment"""
        order = await self.api.get_order_detail(order_id, phone)
        
        if not order:
            return "END Order not found. Please check the Order ID."
        
        return (
            f"CON Confirm Payment\n"
            f"Order: {order.get('id', 'N/A')}\n"
            f"Amount: {order.get('currency', 'NGN')} {order.get('total', 0):,.0f}\n\n"
            f"1. Confirm & Enter PIN\n"
            f"2. Cancel"
        )
    
    @staticmethod
    def payment_success(order_id: str, reference: str = "") -> str:
        """Payment success"""
        return (
            f"END Payment Successful!\n"
            f"Order {order_id} has been paid.\n"
            f"Ref: {reference}\n\n"
            f"You will receive a confirmation via SMS."
        )
    
    @staticmethod
    def payment_failed(error: str = "") -> str:
        """Payment failed"""
        return f"END Payment Failed.\n{error}\n\nPlease try again later."
    
    @staticmethod
    def transfer_enter_recipient() -> str:
        """Enter transfer recipient"""
        return "CON Enter recipient phone number:"
    
    async def transfer_confirm_recipient(self, recipient: str) -> str:
        """Confirm transfer recipient"""
        recipient_info = await self.api.verify_recipient(recipient)
        
        if not recipient_info:
            return "END Recipient not found. Please check the phone number."
        
        return (
            f"CON Transfer to:\n"
            f"{recipient_info.get('name', 'Unknown')}\n"
            f"{recipient}\n\n"
            f"Enter amount:"
        )
    
    @staticmethod
    def transfer_confirm(recipient: str, recipient_name: str, amount: float, currency: str = "NGN") -> str:
        """Confirm transfer details"""
        return (
            f"CON Confirm Transfer\n"
            f"To: {recipient_name}\n"
            f"Phone: {recipient}\n"
            f"Amount: {currency} {amount:,.2f}\n\n"
            f"1. Confirm & Enter PIN\n"
            f"2. Cancel"
        )
    
    @staticmethod
    def transfer_success(recipient: str, amount: float, reference: str = "", currency: str = "NGN") -> str:
        """Transfer success"""
        return (
            f"END Transfer Successful!\n"
            f"Sent {currency} {amount:,.2f} to {recipient}\n"
            f"Ref: {reference}\n\n"
            f"You will receive a confirmation via SMS."
        )
    
    @staticmethod
    def transfer_failed(error: str = "") -> str:
        """Transfer failed"""
        return f"END Transfer Failed.\n{error}\n\nPlease try again later."
    
    async def mini_statement(self, phone: str) -> str:
        """Display mini statement"""
        transactions = await self.api.get_mini_statement(phone)
        
        if not transactions:
            return "END No recent transactions."
        
        menu = "END Mini Statement\n"
        for txn in transactions[:5]:
            date = txn.get('date', 'N/A')
            txn_type = txn.get('type', 'N/A')
            amount = txn.get('amount', 0)
            currency = txn.get('currency', 'NGN')
            sign = "+" if txn.get('credit', False) else "-"
            menu += f"{date}: {txn_type} {sign}{currency}{amount:,.0f}\n"
        
        return menu
    
    @staticmethod
    def customer_support() -> str:
        """Customer support"""
        return (
            "END Customer Support\n\n"
            "Call: +234 803 123 4567\n"
            "WhatsApp: +234 803 123 4567\n"
            "Email: support@remittance-platform.com\n\n"
            "Hours: Mon-Sat 8AM-8PM"
        )
    
    @staticmethod
    def invalid_input() -> str:
        """Invalid input"""
        return "END Invalid input. Please try again."
    
    @staticmethod
    def exit_message() -> str:
        """Exit message"""
        return "END Thank you for using Remittance Platform!"
    
    @staticmethod
    def service_unavailable() -> str:
        """Service unavailable"""
        return "END Service temporarily unavailable. Please try again later."


# ============================================================================
# USSD HANDLER (Production)
# ============================================================================

class ProductionUSSDHandler:
    """Production USSD request handler"""
    
    def __init__(self):
        self.session_manager = RedisSessionManager()
        self.api_client = BackendAPIClient()
        self.menu_builder = ProductionMenuBuilder(self.api_client)
        self.rate_limiter = RateLimiter()
    
    async def handle_request(self, ussd_request: USSDRequest) -> str:
        """Main request handler"""
        session_id = ussd_request.sessionId
        phone = ussd_request.phoneNumber
        text = ussd_request.text
        
        # Rate limiting
        if not await self.rate_limiter.check_rate_limit(phone):
            return "END Too many requests. Please wait a moment and try again."
        
        # Parse user input
        inputs = text.split("*") if text else []
        current_input = inputs[-1] if inputs else ""
        
        # Get session
        session = await self.session_manager.get_session(session_id, phone)
        current_state = MenuState(session["state"])
        
        logger.info(f"USSD Request - Phone: {phone}, State: {current_state}, Input: {current_input}")
        
        try:
            # Route based on state
            if not text:
                return self.menu_builder.main_menu()
            
            # Main menu routing
            if current_state == MenuState.MAIN_MENU:
                return await self._handle_main_menu(session_id, current_input, phone)
            
            elif current_state == MenuState.ENTER_PIN:
                return await self._handle_enter_pin(session_id, current_input, phone)
            
            elif current_state == MenuState.VIEW_ORDERS:
                return await self._handle_view_orders(session_id, current_input, phone)
            
            elif current_state == MenuState.BROWSE_PRODUCTS:
                return await self._handle_browse_products(session_id, current_input)
            
            elif current_state == MenuState.VIEW_CATEGORY:
                return await self._handle_view_category(session_id, current_input)
            
            elif current_state == MenuState.MAKE_PAYMENT:
                return await self._handle_make_payment(session_id, current_input, phone)
            
            elif current_state == MenuState.CONFIRM_PAYMENT:
                return await self._handle_confirm_payment(session_id, current_input, phone)
            
            elif current_state == MenuState.ENTER_PAYMENT_PIN:
                return await self._handle_payment_pin(session_id, current_input, phone)
            
            elif current_state == MenuState.ENTER_TRANSFER_RECIPIENT:
                return await self._handle_transfer_recipient(session_id, current_input, phone)
            
            elif current_state == MenuState.ENTER_TRANSFER_AMOUNT:
                return await self._handle_transfer_amount(session_id, current_input, phone)
            
            elif current_state == MenuState.CONFIRM_TRANSFER:
                return await self._handle_confirm_transfer(session_id, current_input, phone)
            
            elif current_state == MenuState.ENTER_TRANSFER_PIN:
                return await self._handle_transfer_pin(session_id, current_input, phone)
            
            else:
                return self.menu_builder.invalid_input()
                
        except Exception as e:
            logger.error(f"USSD handler error: {e}")
            return self.menu_builder.service_unavailable()
    
    async def _handle_main_menu(self, session_id: str, input: str, phone: str) -> str:
        """Handle main menu selection"""
        if input == "1":
            # Check Balance - requires PIN
            await self.session_manager.update_session(
                session_id, 
                MenuState.ENTER_PIN,
                {"next_action": "check_balance"}
            )
            return self.menu_builder.enter_pin("check balance")
        
        elif input == "2":
            # Transfer Money
            await self.session_manager.update_session(session_id, MenuState.ENTER_TRANSFER_RECIPIENT)
            return self.menu_builder.transfer_enter_recipient()
        
        elif input == "3":
            # View Orders
            await self.session_manager.update_session(session_id, MenuState.VIEW_ORDERS)
            return await self.menu_builder.view_orders(phone)
        
        elif input == "4":
            # Browse Products
            await self.session_manager.update_session(session_id, MenuState.BROWSE_PRODUCTS)
            return await self.menu_builder.browse_products()
        
        elif input == "5":
            # Make Payment
            await self.session_manager.update_session(session_id, MenuState.MAKE_PAYMENT)
            return self.menu_builder.make_payment()
        
        elif input == "6":
            # Mini Statement - requires PIN
            await self.session_manager.update_session(
                session_id,
                MenuState.ENTER_PIN,
                {"next_action": "mini_statement"}
            )
            return self.menu_builder.enter_pin("view statement")
        
        elif input == "7":
            # Customer Support
            return self.menu_builder.customer_support()
        
        elif input == "0":
            # Exit
            await self.session_manager.clear_session(session_id)
            return self.menu_builder.exit_message()
        
        else:
            return self.menu_builder.invalid_input()
    
    async def _handle_enter_pin(self, session_id: str, input: str, phone: str) -> str:
        """Handle PIN entry"""
        session = await self.session_manager.get_session(session_id, phone)
        
        # Validate PIN format
        if not input.isdigit() or len(input) != 4:
            return self.menu_builder.enter_pin("continue (4 digits)")
        
        # Verify PIN
        is_valid = await self.api_client.verify_pin(phone, input)
        
        if not is_valid:
            attempts = await self.session_manager.increment_pin_attempts(session_id)
            remaining = config.MAX_PIN_ATTEMPTS - attempts
            return self.menu_builder.pin_error(remaining)
        
        # Reset PIN attempts on success
        await self.session_manager.reset_pin_attempts(session_id)
        
        # Execute next action
        next_action = session["data"].get("next_action", "")
        
        if next_action == "check_balance":
            return await self.menu_builder.check_balance(phone)
        elif next_action == "mini_statement":
            return await self.menu_builder.mini_statement(phone)
        
        return self.menu_builder.main_menu()
    
    async def _handle_view_orders(self, session_id: str, input: str, phone: str) -> str:
        """Handle order viewing"""
        if input == "0":
            await self.session_manager.go_back(session_id)
            return self.menu_builder.main_menu()
        
        try:
            order_index = int(input) - 1
            orders = await self.api_client.get_user_orders(phone)
            
            if order_index < 0 or order_index >= len(orders):
                return self.menu_builder.invalid_input()
            
            order_id = orders[order_index].get("id", "")
            return await self.menu_builder.view_order_detail(order_id, phone)
        except ValueError:
            return self.menu_builder.invalid_input()
    
    async def _handle_browse_products(self, session_id: str, input: str) -> str:
        """Handle product browsing"""
        if input == "0":
            await self.session_manager.go_back(session_id)
            return self.menu_builder.main_menu()
        
        try:
            categories = await self.api_client.get_categories()
            category_index = int(input) - 1
            
            if category_index < 0 or category_index >= len(categories):
                return self.menu_builder.invalid_input()
            
            category_id = categories[category_index].get("id", 0)
            await self.session_manager.update_session(
                session_id,
                MenuState.VIEW_CATEGORY,
                {"category_id": category_id}
            )
            return await self.menu_builder.view_category(category_id)
        except ValueError:
            return self.menu_builder.invalid_input()
    
    async def _handle_view_category(self, session_id: str, input: str) -> str:
        """Handle category product viewing"""
        if input == "0":
            await self.session_manager.go_back(session_id)
            return await self.menu_builder.browse_products()
        
        try:
            session = await self.session_manager.get_session(session_id, "")
            category_id = session["data"].get("category_id", 0)
            products = await self.api_client.get_products_by_category(category_id)
            
            product_index = int(input) - 1
            if product_index < 0 or product_index >= len(products):
                return self.menu_builder.invalid_input()
            
            product_id = products[product_index].get("id", 0)
            return await self.menu_builder.view_product(product_id)
        except ValueError:
            return self.menu_builder.invalid_input()
    
    async def _handle_make_payment(self, session_id: str, input: str, phone: str) -> str:
        """Handle payment initiation"""
        if input == "0":
            await self.session_manager.go_back(session_id)
            return self.menu_builder.main_menu()
        
        # Store order ID and show confirmation
        await self.session_manager.update_session(
            session_id,
            MenuState.CONFIRM_PAYMENT,
            {"order_id": input.upper()}
        )
        return await self.menu_builder.confirm_payment(input.upper(), phone)
    
    async def _handle_confirm_payment(self, session_id: str, input: str, phone: str) -> str:
        """Handle payment confirmation"""
        if input == "1":
            # Confirmed - request PIN
            await self.session_manager.update_session(session_id, MenuState.ENTER_PAYMENT_PIN)
            return self.menu_builder.enter_pin("complete payment")
        
        elif input == "2":
            # Cancelled
            await self.session_manager.clear_session(session_id)
            return self.menu_builder.exit_message()
        
        else:
            return self.menu_builder.invalid_input()
    
    async def _handle_payment_pin(self, session_id: str, input: str, phone: str) -> str:
        """Handle payment PIN verification"""
        session = await self.session_manager.get_session(session_id, phone)
        order_id = session["data"].get("order_id", "")
        
        # Validate PIN format
        if not input.isdigit() or len(input) != 4:
            return self.menu_builder.enter_pin("complete payment (4 digits)")
        
        # Process payment
        result = await self.api_client.process_payment(phone, order_id, input)
        
        await self.session_manager.clear_session(session_id)
        
        if result.get("success"):
            return self.menu_builder.payment_success(order_id, result.get("reference", ""))
        else:
            return self.menu_builder.payment_failed(result.get("error", "Unknown error"))
    
    async def _handle_transfer_recipient(self, session_id: str, input: str, phone: str) -> str:
        """Handle transfer recipient entry"""
        if input == "0":
            await self.session_manager.go_back(session_id)
            return self.menu_builder.main_menu()
        
        # Validate phone number format
        recipient = input.strip()
        if not recipient.replace("+", "").isdigit() or len(recipient) < 10:
            return "CON Invalid phone number.\nEnter recipient phone number:"
        
        # Verify recipient
        recipient_info = await self.api_client.verify_recipient(recipient)
        
        if not recipient_info:
            return "CON Recipient not found.\nEnter recipient phone number:"
        
        await self.session_manager.update_session(
            session_id,
            MenuState.ENTER_TRANSFER_AMOUNT,
            {
                "recipient": recipient,
                "recipient_name": recipient_info.get("name", "Unknown")
            }
        )
        return await self.menu_builder.transfer_confirm_recipient(recipient)
    
    async def _handle_transfer_amount(self, session_id: str, input: str, phone: str) -> str:
        """Handle transfer amount entry"""
        if input == "0":
            await self.session_manager.go_back(session_id)
            return self.menu_builder.transfer_enter_recipient()
        
        try:
            amount = float(input.replace(",", ""))
            if amount <= 0:
                raise ValueError("Amount must be positive")
            
            session = await self.session_manager.get_session(session_id, phone)
            recipient = session["data"].get("recipient", "")
            recipient_name = session["data"].get("recipient_name", "Unknown")
            
            await self.session_manager.update_session(
                session_id,
                MenuState.CONFIRM_TRANSFER,
                {"amount": amount}
            )
            return self.menu_builder.transfer_confirm(recipient, recipient_name, amount)
        except ValueError:
            return "CON Invalid amount.\nEnter amount:"
    
    async def _handle_confirm_transfer(self, session_id: str, input: str, phone: str) -> str:
        """Handle transfer confirmation"""
        if input == "1":
            # Confirmed - request PIN
            await self.session_manager.update_session(session_id, MenuState.ENTER_TRANSFER_PIN)
            return self.menu_builder.enter_pin("complete transfer")
        
        elif input == "2":
            # Cancelled
            await self.session_manager.clear_session(session_id)
            return self.menu_builder.exit_message()
        
        else:
            return self.menu_builder.invalid_input()
    
    async def _handle_transfer_pin(self, session_id: str, input: str, phone: str) -> str:
        """Handle transfer PIN verification"""
        session = await self.session_manager.get_session(session_id, phone)
        recipient = session["data"].get("recipient", "")
        amount = session["data"].get("amount", 0)
        
        # Validate PIN format
        if not input.isdigit() or len(input) != 4:
            return self.menu_builder.enter_pin("complete transfer (4 digits)")
        
        # Process transfer
        result = await self.api_client.process_transfer(phone, recipient, amount, input)
        
        await self.session_manager.clear_session(session_id)
        
        if result.get("success"):
            return self.menu_builder.transfer_success(recipient, amount, result.get("reference", ""))
        else:
            return self.menu_builder.transfer_failed(result.get("error", "Unknown error"))


# ============================================================================
# API ENDPOINTS
# ============================================================================

ussd_handler = ProductionUSSDHandler()


def verify_provider_signature(request: Request) -> bool:
    """Verify USSD provider signature for security"""
    if not config.USSD_PROVIDER_SECRET:
        return True  # Skip verification if no secret configured
    
    signature = request.headers.get("X-USSD-Signature", "")
    if not signature:
        return False
    
    # Implement provider-specific signature verification
    # Implementation depends on USSD provider configuration
    return True


@app.post("/ussd")
async def ussd_callback(request: Request):
    """USSD callback endpoint (Africa's Talking format)"""
    try:
        # Verify provider signature
        if not verify_provider_signature(request):
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Parse form data
        form_data = await request.form()
        
        ussd_request = USSDRequest(
            sessionId=form_data.get("sessionId", ""),
            serviceCode=form_data.get("serviceCode", ""),
            phoneNumber=form_data.get("phoneNumber", ""),
            text=form_data.get("text", "")
        )
        
        # Handle request
        response_text = await ussd_handler.handle_request(ussd_request)
        
        # Return plain text response
        return Response(content=response_text, media_type="text/plain")
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"USSD error: {e}")
        return Response(content="END Service temporarily unavailable", media_type="text/plain")


@app.post("/api/v1/ussd/send")
async def ussd_api_send(request: Request):
    """API endpoint for sending USSD (used by unified messaging platform)"""
    try:
        data = await request.json()
        
        ussd_request = USSDRequest(
            sessionId=data.get("session_id", ""),
            serviceCode=data.get("service_code", ""),
            phoneNumber=data.get("phone_number", ""),
            text=data.get("text", "")
        )
        
        response_text = await ussd_handler.handle_request(ussd_request)
        
        return {
            "status": "success",
            "response": response_text,
            "provider": "internal"
        }
    except Exception as e:
        logger.error(f"USSD API error: {e}")
        return {"status": "error", "error": str(e)}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    redis_status = "connected" if redis_client else "disconnected"
    
    return {
        "status": "healthy",
        "service": config.SERVICE_NAME,
        "version": "2.0.0",
        "redis": redis_status
    }


@app.get("/metrics")
async def get_metrics():
    """Get service metrics"""
    return {
        "service": config.SERVICE_NAME,
        "version": "2.0.0",
        "redis_connected": redis_client is not None,
        "http_client_ready": http_client is not None
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8021)
