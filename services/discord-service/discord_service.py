import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Discord Order Management Service
Community-based commerce via Discord
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("discord-order-service")
app.include_router(metrics_router)

from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime
import httpx
import os

app = FastAPI(title="Discord Order Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Discord configuration
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
DISCORD_API_URL = "https://discord.com/api/v10"

# Models
class DiscordOrder(BaseModel):
    guild_id: str
    channel_id: str
    user_id: str
    username: str
    items: List[Dict]
    total: float
    status: str = "pending"

# Storage
orders_db: Dict[str, DiscordOrder] = {}

async def send_discord_message(channel_id: str, content: str = None, embed: Dict = None):
    """Send message to Discord channel"""
    try:
        async with httpx.AsyncClient() as client:
            payload = {}
            if content:
                payload["content"] = content
            if embed:
                payload["embeds"] = [embed]
            
            response = await client.post(
                f"{DISCORD_API_URL}/channels/{channel_id}/messages",
                headers={"Authorization": f"Bot {DISCORD_BOT_TOKEN}"},
                json=payload
            )
            return response.json()
    except Exception as e:
        print(f"Error sending Discord message: {e}")
        return None

def create_product_embed(product: Dict):
    """Create Discord embed for product"""
    return {
        "title": product["name"],
        "description": product["description"],
        "color": 5814783,  # Purple
        "fields": [
            {"name": "Price", "value": f"₦{product['price']:,.0f}", "inline": True},
            {"name": "Stock", "value": str(product["stock"]), "inline": True}
        ],
        "footer": {"text": "Use /order <product_id> <quantity> to order"}
    }

def create_order_confirmation_embed(order_id: str, items: List[Dict], total: float):
    """Create Discord embed for order confirmation"""
    items_text = "\n".join([f"• {item['name']} x{item['quantity']} - ₦{item['price']:,.0f}" for item in items])
    
    return {
        "title": "🎉 Order Confirmed!",
        "description": f"Order ID: `{order_id}`",
        "color": 3066993,  # Green
        "fields": [
            {"name": "Items", "value": items_text},
            {"name": "Total", "value": f"₦{total:,.0f}", "inline": True},
            {"name": "Status", "value": "Processing", "inline": True}
        ],
        "footer": {"text": "Thank you for your order!"}
    }

@app.get("/")
async def root():
    return {"service": "Discord Order Service", "status": "running"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/interactions")
async def handle_interaction(request: Request):
    """Handle Discord interactions (slash commands, buttons)"""
    data = await request.json()
    
    # Handle slash commands
    if data.get("type") == 2:  # APPLICATION_COMMAND
        command_name = data["data"]["name"]
        
        if command_name == "products":
            # Show products
            products = [
                {"id": "1", "name": "Premium Rice (50kg)", "price": 45000, "description": "High-quality rice", "stock": 50},
                {"id": "2", "name": "Cooking Oil (5L)", "price": 8500, "description": "Pure vegetable oil", "stock": 120}
            ]
            
            embeds = [create_product_embed(p) for p in products[:5]]
            
            return {
                "type": 4,  # CHANNEL_MESSAGE_WITH_SOURCE
                "data": {
                    "content": "🛍️ **Available Products**",
                    "embeds": embeds
                }
            }
        
        elif command_name == "order":
            # Create order
            options = {opt["name"]: opt["value"] for opt in data["data"].get("options", [])}
            product_id = options.get("product_id")
            quantity = options.get("quantity", 1)
            
            # Create order
            order_id = f"DC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            order = DiscordOrder(
                guild_id=data["guild_id"],
                channel_id=data["channel_id"],
                user_id=data["member"]["user"]["id"],
                username=data["member"]["user"]["username"],
                items=[{"name": "Product", "quantity": quantity, "price": 10000}],
                total=10000 * quantity
            )
            orders_db[order_id] = order
            
            embed = create_order_confirmation_embed(order_id, order.items, order.total)
            
            return {
                "type": 4,
                "data": {
                    "embeds": [embed]
                }
            }
    
    return {"type": 1}  # PONG

@app.post("/send-notification/{channel_id}")
async def send_notification(channel_id: str, message: str):
    """Send notification to Discord channel"""
    result = await send_discord_message(channel_id, content=message)
    return {"status": "sent" if result else "failed"}

@app.get("/orders")
async def get_orders():
    """Get all Discord orders"""
    return {"orders": list(orders_db.values()), "count": len(orders_db)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8044)
