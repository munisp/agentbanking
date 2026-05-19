import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
"""
Telegram Order Management Service
Complete Telegram Bot integration for e-commerce orders
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
import httpx
import os
import json
import asyncio

app = FastAPI(title="Telegram Order Service", version="1.0.0")

from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
apply_middleware(app)
setup_logging("telegram-order-service")
app.include_router(metrics_router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
ECOMMERCE_API_URL = os.getenv("ECOMMERCE_API_URL", "http://localhost:8030")

# Models
class Product(BaseModel):
    id: str
    name: str
    price: float
    description: str
    image_url: Optional[str] = None
    stock: int

class OrderItem(BaseModel):
    product_id: str
    product_name: str
    quantity: int
    price: float

class TelegramOrder(BaseModel):
    chat_id: int
    user_id: int
    username: str
    items: List[OrderItem]
    total: float
    status: str = "pending"
    created_at: datetime = datetime.now()

# In-memory storage
orders_db: Dict[str, TelegramOrder] = {}
user_carts: Dict[int, List[OrderItem]] = {}
user_states: Dict[int, str] = {}  # Track conversation state

# Helper Functions
async def send_telegram_message(chat_id: int, text: str, reply_markup: Optional[dict] = None):
    """Send message via Telegram Bot API"""
    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML"
            }
            if reply_markup:
                payload["reply_markup"] = json.dumps(reply_markup)
            
            response = await client.post(
                f"{TELEGRAM_API_URL}/sendMessage",
                json=payload
            )
            return response.json()
    except Exception as e:
        print(f"Error sending Telegram message: {e}")
        return None

async def send_telegram_photo(chat_id: int, photo_url: str, caption: str, reply_markup: Optional[dict] = None):
    """Send photo via Telegram Bot API"""
    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "chat_id": chat_id,
                "photo": photo_url,
                "caption": caption,
                "parse_mode": "HTML"
            }
            if reply_markup:
                payload["reply_markup"] = json.dumps(reply_markup)
            
            response = await client.post(
                f"{TELEGRAM_API_URL}/sendPhoto",
                json=payload
            )
            return response.json()
    except Exception as e:
        print(f"Error sending Telegram photo: {e}")
        return None

async def get_products():
    """Fetch products from e-commerce service"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{ECOMMERCE_API_URL}/products")
            if response.status_code == 200:
                return response.json().get("products", [])
    except:
        pass
    
    # Fallback to sample products
    return [
        {"id": "1", "name": "Premium Rice (50kg)", "price": 45000, "description": "High-quality rice", "stock": 50},
        {"id": "2", "name": "Cooking Oil (5L)", "price": 8500, "description": "Pure vegetable oil", "stock": 120},
        {"id": "3", "name": "Detergent Powder (2kg)", "price": 3200, "description": "Powerful cleaning", "stock": 80},
        {"id": "4", "name": "Tomato Paste (70g x 50)", "price": 12000, "description": "Rich tomato flavor", "stock": 60},
        {"id": "5", "name": "Sugar (2kg)", "price": 1800, "description": "Pure white sugar", "stock": 100},
        {"id": "6", "name": "Bathing Soap (Pack of 12)", "price": 2400, "description": "Fresh fragrance", "stock": 150}
    ]

def create_main_menu_keyboard():
    """Create main menu inline keyboard"""
    return {
        "inline_keyboard": [
            [{"text": "🛍️ Browse Products", "callback_data": "browse_products"}],
            [{"text": "🛒 View Cart", "callback_data": "view_cart"}],
            [{"text": "📦 My Orders", "callback_data": "my_orders"}],
            [{"text": "ℹ️ Help", "callback_data": "help"}]
        ]
    }

def create_products_keyboard(products: List[dict], page: int = 0):
    """Create products inline keyboard with pagination"""
    keyboard = []
    items_per_page = 5
    start = page * items_per_page
    end = start + items_per_page
    
    for product in products[start:end]:
        keyboard.append([{
            "text": f"{product['name']} - ₦{product['price']:,.0f}",
            "callback_data": f"product_{product['id']}"
        }])
    
    # Pagination buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append({"text": "⬅️ Previous", "callback_data": f"page_{page-1}"})
    if end < len(products):
        nav_buttons.append({"text": "Next ➡️", "callback_data": f"page_{page+1}"})
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([{"text": "🏠 Main Menu", "callback_data": "main_menu"}])
    
    return {"inline_keyboard": keyboard}

def create_product_detail_keyboard(product_id: str):
    """Create product detail inline keyboard"""
    return {
        "inline_keyboard": [
            [
                {"text": "➖", "callback_data": f"qty_dec_{product_id}"},
                {"text": "1", "callback_data": f"qty_show_{product_id}"},
                {"text": "➕", "callback_data": f"qty_inc_{product_id}"}
            ],
            [{"text": "🛒 Add to Cart", "callback_data": f"add_cart_{product_id}"}],
            [{"text": "⬅️ Back to Products", "callback_data": "browse_products"}],
            [{"text": "🏠 Main Menu", "callback_data": "main_menu"}]
        ]
    }

def create_cart_keyboard():
    """Create cart inline keyboard"""
    return {
        "inline_keyboard": [
            [{"text": "✅ Checkout", "callback_data": "checkout"}],
            [{"text": "🗑️ Clear Cart", "callback_data": "clear_cart"}],
            [{"text": "🛍️ Continue Shopping", "callback_data": "browse_products"}],
            [{"text": "🏠 Main Menu", "callback_data": "main_menu"}]
        ]
    }

async def handle_start_command(chat_id: int, username: str):
    """Handle /start command"""
    welcome_message = f"""
👋 <b>Welcome to HealthPlus Pharmacy, {username}!</b>

I'm your personal shopping assistant. I can help you:

🛍️ Browse our product catalog
🛒 Add items to your cart
📦 Track your orders
💬 Get customer support

What would you like to do?
"""
    await send_telegram_message(chat_id, welcome_message, create_main_menu_keyboard())

async def handle_browse_products(chat_id: int):
    """Handle browse products action"""
    products = await get_products()
    message = "🛍️ <b>Our Products</b>\n\nSelect a product to view details:"
    await send_telegram_message(chat_id, message, create_products_keyboard(products))

async def handle_product_detail(chat_id: int, product_id: str):
    """Handle product detail view"""
    products = await get_products()
    product = next((p for p in products if p['id'] == product_id), None)
    
    if not product:
        await send_telegram_message(chat_id, "❌ Product not found")
        return
    
    message = f"""
<b>{product['name']}</b>

💰 Price: ₦{product['price']:,.0f}
📦 In Stock: {product['stock']} units

{product['description']}

Select quantity and add to cart:
"""
    
    if product.get('image_url'):
        await send_telegram_photo(chat_id, product['image_url'], message, create_product_detail_keyboard(product_id))
    else:
        await send_telegram_message(chat_id, message, create_product_detail_keyboard(product_id))

async def handle_add_to_cart(chat_id: int, user_id: int, product_id: str, quantity: int = 1):
    """Handle add to cart action"""
    products = await get_products()
    product = next((p for p in products if p['id'] == product_id), None)
    
    if not product:
        await send_telegram_message(chat_id, "❌ Product not found")
        return
    
    if chat_id not in user_carts:
        user_carts[chat_id] = []
    
    # Check if product already in cart
    existing_item = next((item for item in user_carts[chat_id] if item.product_id == product_id), None)
    
    if existing_item:
        existing_item.quantity += quantity
    else:
        user_carts[chat_id].append(OrderItem(
            product_id=product_id,
            product_name=product['name'],
            quantity=quantity,
            price=product['price']
        ))
    
    message = f"✅ Added {quantity}x {product['name']} to cart!"
    await send_telegram_message(chat_id, message, create_main_menu_keyboard())

async def handle_view_cart(chat_id: int):
    """Handle view cart action"""
    if chat_id not in user_carts or not user_carts[chat_id]:
        await send_telegram_message(chat_id, "🛒 Your cart is empty", create_main_menu_keyboard())
        return
    
    cart_items = user_carts[chat_id]
    total = sum(item.quantity * item.price for item in cart_items)
    
    message = "🛒 <b>Your Cart</b>\n\n"
    for item in cart_items:
        message += f"• {item.product_name}\n"
        message += f"  {item.quantity}x ₦{item.price:,.0f} = ₦{item.quantity * item.price:,.0f}\n\n"
    
    message += f"<b>Total: ₦{total:,.0f}</b>"
    
    await send_telegram_message(chat_id, message, create_cart_keyboard())

async def handle_checkout(chat_id: int, user_id: int, username: str):
    """Handle checkout action"""
    if chat_id not in user_carts or not user_carts[chat_id]:
        await send_telegram_message(chat_id, "🛒 Your cart is empty", create_main_menu_keyboard())
        return
    
    cart_items = user_carts[chat_id]
    total = sum(item.quantity * item.price for item in cart_items)
    
    # Create order
    order_id = f"TG-{datetime.now().strftime('%Y%m%d%H%M%S')}-{user_id}"
    order = TelegramOrder(
        chat_id=chat_id,
        user_id=user_id,
        username=username,
        items=cart_items,
        total=total,
        status="confirmed"
    )
    orders_db[order_id] = order
    
    # Clear cart
    user_carts[chat_id] = []
    
    # Send confirmation
    message = f"""
🎉 <b>Order Confirmed!</b>

Order ID: <code>{order_id}</code>
Total: ₦{total:,.0f}

📦 Your order will be delivered within 24 hours.

We'll send you tracking updates via Telegram.

Thank you for shopping with us! 🙏
"""
    
    await send_telegram_message(chat_id, message, create_main_menu_keyboard())
    
    # Send order to e-commerce service
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{ECOMMERCE_API_URL}/orders",
                json={
                    "order_id": order_id,
                    "channel": "telegram",
                    "customer": {"name": username, "telegram_id": user_id},
                    "items": [item.dict() for item in cart_items],
                    "total": total
                }
            )
    except:
        pass

async def handle_my_orders(chat_id: int, user_id: int):
    """Handle my orders action"""
    user_orders = [order for order in orders_db.values() if order.user_id == user_id]
    
    if not user_orders:
        await send_telegram_message(chat_id, "📦 You have no orders yet", create_main_menu_keyboard())
        return
    
    message = "📦 <b>Your Orders</b>\n\n"
    for order_id, order in list(orders_db.items())[-5:]:  # Last 5 orders
        if order.user_id == user_id:
            message += f"Order: <code>{order_id}</code>\n"
            message += f"Total: ₦{order.total:,.0f}\n"
            message += f"Status: {order.status.upper()}\n"
            message += f"Date: {order.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
    
    await send_telegram_message(chat_id, message, create_main_menu_keyboard())

async def handle_help(chat_id: int):
    """Handle help action"""
    help_message = """
ℹ️ <b>How to Use This Bot</b>

<b>Commands:</b>
/start - Start the bot
/help - Show this help message

<b>Features:</b>
🛍️ Browse Products - View our catalog
🛒 View Cart - See items in your cart
📦 My Orders - Track your orders
💬 Support - Contact customer service

<b>How to Order:</b>
1. Browse products
2. Add items to cart
3. Review your cart
4. Checkout

<b>Need Help?</b>
Contact us: +234 803 123 4567
Email: support@healthplus.ng
"""
    await send_telegram_message(chat_id, help_message, create_main_menu_keyboard())

# API Endpoints

@app.get("/")
async def root():
    return {"service": "Telegram Order Service", "status": "running", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    """Handle Telegram webhook updates"""
    try:
        data = await request.json()
        
        # Handle message
        if "message" in data:
            message = data["message"]
            chat_id = message["chat"]["id"]
            user_id = message["from"]["id"]
            username = message["from"].get("username", message["from"].get("first_name", "User"))
            text = message.get("text", "")
            
            if text == "/start":
                await handle_start_command(chat_id, username)
            elif text == "/help":
                await handle_help(chat_id)
            else:
                await send_telegram_message(chat_id, "Please use the menu buttons below:", create_main_menu_keyboard())
        
        # Handle callback query (button press)
        elif "callback_query" in data:
            query = data["callback_query"]
            chat_id = query["message"]["chat"]["id"]
            user_id = query["from"]["id"]
            username = query["from"].get("username", query["from"].get("first_name", "User"))
            callback_data = query["data"]
            
            # Answer callback query
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{TELEGRAM_API_URL}/answerCallbackQuery",
                    json={"callback_query_id": query["id"]}
                )
            
            # Handle different callbacks
            if callback_data == "main_menu":
                await handle_start_command(chat_id, username)
            elif callback_data == "browse_products":
                await handle_browse_products(chat_id)
            elif callback_data.startswith("product_"):
                product_id = callback_data.split("_")[1]
                await handle_product_detail(chat_id, product_id)
            elif callback_data.startswith("add_cart_"):
                product_id = callback_data.split("_")[2]
                await handle_add_to_cart(chat_id, user_id, product_id)
            elif callback_data == "view_cart":
                await handle_view_cart(chat_id)
            elif callback_data == "checkout":
                await handle_checkout(chat_id, user_id, username)
            elif callback_data == "clear_cart":
                user_carts[chat_id] = []
                await send_telegram_message(chat_id, "🗑️ Cart cleared", create_main_menu_keyboard())
            elif callback_data == "my_orders":
                await handle_my_orders(chat_id, user_id)
            elif callback_data == "help":
                await handle_help(chat_id)
        
        return {"status": "ok"}
    
    except Exception as e:
        print(f"Webhook error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/orders")
async def get_orders():
    """Get all Telegram orders"""
    return {
        "orders": [{"order_id": oid, **order.dict()} for oid, order in orders_db.items()],
        "count": len(orders_db)
    }

@app.post("/send-notification/{chat_id}")
async def send_notification(chat_id: int, message: str):
    """Send notification to user"""
    result = await send_telegram_message(chat_id, message)
    return {"status": "sent" if result else "failed"}

@app.post("/set-webhook")
async def set_webhook(webhook_url: str):
    """Set Telegram webhook URL"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{TELEGRAM_API_URL}/setWebhook",
                json={"url": webhook_url}
            )
            return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats")
async def get_stats():
    """Get Telegram channel statistics"""
    total_orders = len(orders_db)
    total_revenue = sum(order.total for order in orders_db.values())
    active_users = len(set(order.user_id for order in orders_db.values()))
    
    return {
        "total_orders": total_orders,
        "total_revenue": total_revenue,
        "active_users": active_users,
        "avg_order_value": total_revenue / total_orders if total_orders > 0 else 0
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8041)

