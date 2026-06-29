import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Zapier/Make Integration Service
Expose APIs for no-code automation platforms
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("zapier-integration-service")
app.include_router(metrics_router)

from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

app = FastAPI(title="Zapier Integration Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class ZapierTrigger(BaseModel):
    event: str
    data: Dict[str, Any]
    timestamp: datetime = datetime.now()

class ZapierAction(BaseModel):
    action_type: str
    parameters: Dict[str, Any]

# Webhooks storage
webhooks: Dict[str, List[str]] = {}  # event_type -> [webhook_urls]
trigger_history: List[ZapierTrigger] = []

@app.get("/")
async def root():
    return {"service": "Zapier Integration", "status": "running"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

# Zapier Triggers
@app.post("/triggers/new-order")
async def trigger_new_order(order_data: Dict):
    """Trigger when new order is created"""
    trigger = ZapierTrigger(event="new_order", data=order_data)
    trigger_history.append(trigger)
    return {"status": "triggered", "trigger_id": len(trigger_history)}

@app.post("/triggers/order-shipped")
async def trigger_order_shipped(order_data: Dict):
    """Trigger when order is shipped"""
    trigger = ZapierTrigger(event="order_shipped", data=order_data)
    trigger_history.append(trigger)
    return {"status": "triggered"}

@app.post("/triggers/new-customer")
async def trigger_new_customer(customer_data: Dict):
    """Trigger when new customer registers"""
    trigger = ZapierTrigger(event="new_customer", data=customer_data)
    trigger_history.append(trigger)
    return {"status": "triggered"}

# Zapier Actions
@app.post("/actions/create-order")
async def action_create_order(order: ZapierAction):
    """Create order via Zapier"""
    return {"status": "created", "order_id": f"ZAP-{datetime.now().timestamp()}"}

@app.post("/actions/send-notification")
async def action_send_notification(notification: ZapierAction):
    """Send notification via Zapier"""
    return {"status": "sent"}

@app.post("/actions/update-inventory")
async def action_update_inventory(inventory: ZapierAction):
    """Update inventory via Zapier"""
    return {"status": "updated"}

# Webhook management
@app.post("/webhooks/subscribe")
async def subscribe_webhook(event_type: str, webhook_url: str):
    """Subscribe to event webhooks"""
    if event_type not in webhooks:
        webhooks[event_type] = []
    webhooks[event_type].append(webhook_url)
    return {"status": "subscribed", "event": event_type}

@app.get("/triggers/recent")
async def get_recent_triggers(limit: int = 10):
    """Get recent triggers for Zapier polling"""
    return {"triggers": trigger_history[-limit:]}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8043)
