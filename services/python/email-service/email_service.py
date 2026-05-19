import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Enhanced Email Service
Professional email communication with rich templates and automation
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("enhanced-email-service")
app.include_router(metrics_router)

from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
import os
import jinja2

app = FastAPI(title="Enhanced Email Service", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@healthplus.ng")
FROM_NAME = os.getenv("FROM_NAME", "HealthPlus Pharmacy")

# Jinja2 template environment
template_loader = jinja2.DictLoader({})
template_env = jinja2.Environment(loader=template_loader)

# Models
class EmailRecipient(BaseModel):
    email: EmailStr
    name: Optional[str] = None

class EmailAttachment(BaseModel):
    filename: str
    content: str  # Base64 encoded
    mime_type: str = "application/octet-stream"

class EmailTemplate(str):
    ORDER_CONFIRMATION = "order_confirmation"
    SHIPPING_UPDATE = "shipping_update"
    DELIVERY_CONFIRMATION = "delivery_confirmation"
    ABANDONED_CART = "abandoned_cart"
    WELCOME = "welcome"
    NEWSLETTER = "newsletter"
    PROMOTIONAL = "promotional"
    PASSWORD_RESET = "password_reset"
    INVOICE = "invoice"

class EmailRequest(BaseModel):
    to: List[EmailRecipient]
    subject: str
    template: str
    data: Dict
    attachments: Optional[List[EmailAttachment]] = None
    cc: Optional[List[EmailRecipient]] = None
    bcc: Optional[List[EmailRecipient]] = None

# Email Templates (HTML)
EMAIL_TEMPLATES = {
    "order_confirmation": """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Order Confirmation</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; }
        .content { padding: 30px; background: #f9f9f9; }
        .order-details { background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }
        .item { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #eee; }
        .total { font-size: 1.2em; font-weight: bold; margin-top: 20px; padding-top: 20px; border-top: 2px solid #667eea; }
        .button { display: inline-block; background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }
        .footer { text-align: center; padding: 20px; color: #666; font-size: 0.9em; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎉 Order Confirmed!</h1>
    </div>
    <div class="content">
        <p>Hi {{ customer_name }},</p>
        <p>Thank you for your order! We're excited to get your items ready.</p>
        
        <div class="order-details">
            <h2>Order #{{ order_id }}</h2>
            <p><strong>Order Date:</strong> {{ order_date }}</p>
            
            <h3>Items:</h3>
            {% for item in items %}
            <div class="item">
                <span>{{ item.name }} x{{ item.quantity }}</span>
                <span>₦{{ "%.2f"|format(item.total) }}</span>
            </div>
            {% endfor %}
            
            <div class="total">
                <div style="display: flex; justify-content: space-between;">
                    <span>Total:</span>
                    <span>₦{{ "%.2f"|format(total) }}</span>
                </div>
            </div>
            
            <p><strong>Delivery Address:</strong><br>{{ delivery_address }}</p>
            <p><strong>Estimated Delivery:</strong> {{ estimated_delivery }}</p>
        </div>
        
        <a href="{{ tracking_url }}" class="button">Track Your Order</a>
        
        <p>We'll send you another email when your order ships.</p>
    </div>
    <div class="footer">
        <p>Questions? Contact us at {{ support_email }} or {{ support_phone }}</p>
        <p>© 2025 {{ company_name }}. All rights reserved.</p>
    </div>
</body>
</html>
""",
    
    "shipping_update": """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; }
        .header { background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 30px; text-align: center; }
        .content { padding: 30px; background: #f9f9f9; }
        .tracking-box { background: white; padding: 20px; border-radius: 8px; margin: 20px 0; text-align: center; }
        .tracking-number { font-size: 1.5em; font-weight: bold; color: #10b981; margin: 10px 0; }
        .button { display: inline-block; background: #10b981; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }
        .footer { text-align: center; padding: 20px; color: #666; font-size: 0.9em; }
    </style>
</head>
<body>
    <div class="header">
        <h1>📦 Your Order is On The Way!</h1>
    </div>
    <div class="content">
        <p>Hi {{ customer_name }},</p>
        <p>Great news! Your order has been shipped and is on its way to you.</p>
        
        <div class="tracking-box">
            <p><strong>Tracking Number:</strong></p>
            <div class="tracking-number">{{ tracking_number }}</div>
            <p><strong>Estimated Delivery:</strong> {{ estimated_delivery }}</p>
            <a href="{{ tracking_url }}" class="button">Track Package</a>
        </div>
        
        <p><strong>Order #{{ order_id }}</strong></p>
        <p>Delivery Address: {{ delivery_address }}</p>
    </div>
    <div class="footer">
        <p>© 2025 {{ company_name }}. All rights reserved.</p>
    </div>
</body>
</html>
""",
    
    "abandoned_cart": """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; }
        .header { background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); color: white; padding: 30px; text-align: center; }
        .content { padding: 30px; background: #f9f9f9; }
        .cart-items { background: white; padding: 20px; border-radius: 8px; margin: 20px 0; }
        .item { display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #eee; }
        .button { display: inline-block; background: #f59e0b; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }
        .discount { background: #fef3c7; padding: 15px; border-radius: 5px; margin: 20px 0; text-align: center; }
        .footer { text-align: center; padding: 20px; color: #666; font-size: 0.9em; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛒 You Left Something Behind!</h1>
    </div>
    <div class="content">
        <p>Hi {{ customer_name }},</p>
        <p>We noticed you left some items in your cart. Don't worry, we saved them for you!</p>
        
        <div class="cart-items">
            <h3>Your Cart:</h3>
            {% for item in items %}
            <div class="item">
                <span>{{ item.name }} x{{ item.quantity }}</span>
                <span>₦{{ "%.2f"|format(item.price) }}</span>
            </div>
            {% endfor %}
        </div>
        
        {% if discount_code %}
        <div class="discount">
            <p><strong>Special Offer Just For You!</strong></p>
            <p>Use code <strong>{{ discount_code }}</strong> for {{ discount_percent }}% off</p>
        </div>
        {% endif %}
        
        <a href="{{ checkout_url }}" class="button">Complete Your Order</a>
        
        <p>Hurry! Items in your cart are selling fast.</p>
    </div>
    <div class="footer">
        <p>© 2025 {{ company_name }}. All rights reserved.</p>
    </div>
</body>
</html>
""",
    
    "welcome": """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px; text-align: center; }
        .content { padding: 30px; background: #f9f9f9; }
        .features { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin: 20px 0; }
        .feature { background: white; padding: 15px; border-radius: 8px; text-align: center; }
        .button { display: inline-block; background: #667eea; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; margin: 20px 0; }
        .footer { text-align: center; padding: 20px; color: #666; font-size: 0.9em; }
    </style>
</head>
<body>
    <div class="header">
        <h1>👋 Welcome to {{ company_name }}!</h1>
    </div>
    <div class="content">
        <p>Hi {{ customer_name }},</p>
        <p>Thank you for joining us! We're excited to have you as part of our community.</p>
        
        <div class="features">
            <div class="feature">
                <h3>🚚</h3>
                <p>Fast Delivery</p>
            </div>
            <div class="feature">
                <h3>💯</h3>
                <p>Quality Products</p>
            </div>
            <div class="feature">
                <h3>💰</h3>
                <p>Best Prices</p>
            </div>
            <div class="feature">
                <h3>🔒</h3>
                <p>Secure Payment</p>
            </div>
        </div>
        
        <a href="{{ shop_url }}" class="button">Start Shopping</a>
        
        <p>Need help? Our support team is here for you 24/7.</p>
    </div>
    <div class="footer">
        <p>Contact: {{ support_email }} | {{ support_phone }}</p>
        <p>© 2025 {{ company_name }}. All rights reserved.</p>
    </div>
</body>
</html>
"""
}

# Helper Functions
def render_template(template_name: str, data: Dict) -> str:
    """Render email template with data"""
    if template_name not in EMAIL_TEMPLATES:
        raise ValueError(f"Template '{template_name}' not found")
    
    template = template_env.from_string(EMAIL_TEMPLATES[template_name])
    return template.render(**data)

async def send_email(
    to: List[EmailRecipient],
    subject: str,
    html_content: str,
    attachments: Optional[List[EmailAttachment]] = None,
    cc: Optional[List[EmailRecipient]] = None,
    bcc: Optional[List[EmailRecipient]] = None
) -> bool:
    """Send email via SMTP"""
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{FROM_NAME} <{FROM_EMAIL}>"
        msg['To'] = ", ".join([f"{r.name} <{r.email}>" if r.name else r.email for r in to])
        msg['Subject'] = subject
        
        if cc:
            msg['Cc'] = ", ".join([f"{r.name} <{r.email}>" if r.name else r.email for r in cc])
        
        # Attach HTML content
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        # Attach files if any
        if attachments:
            import base64
            from email.mime.base import MIMEBase
            from email import encoders
            
            for attachment in attachments:
                # Decode base64 content
                file_data = base64.b64decode(attachment.content)
                
                # Create MIME attachment
                part = MIMEBase(*attachment.mime_type.split('/'))
                part.set_payload(file_data)
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename="{attachment.filename}"'
                )
                msg.attach(part)
        
        # Send email
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            if SMTP_USERNAME and SMTP_PASSWORD:
                server.login(SMTP_USERNAME, SMTP_PASSWORD)
            
            recipients = [r.email for r in to]
            if cc:
                recipients.extend([r.email for r in cc])
            if bcc:
                recipients.extend([r.email for r in bcc])
            
            server.sendmail(FROM_EMAIL, recipients, msg.as_string())
        
        return True
    
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

# API Endpoints

@app.get("/")
async def root():
    return {"service": "Enhanced Email Service", "status": "running", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/send")
async def send_email_endpoint(email_req: EmailRequest, background_tasks: BackgroundTasks):
    """Send email using template"""
    try:
        # Render template
        html_content = render_template(email_req.template, email_req.data)
        
        # Send email in background
        background_tasks.add_task(
            send_email,
            email_req.to,
            email_req.subject,
            html_content,
            email_req.attachments,
            email_req.cc,
            email_req.bcc
        )
        
        return {"status": "queued", "message": "Email queued for sending"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/templates")
async def list_templates():
    """List available email templates"""
    return {
        "templates": list(EMAIL_TEMPLATES.keys()),
        "count": len(EMAIL_TEMPLATES)
    }

@app.post("/preview/{template_name}")
async def preview_template(template_name: str, data: Dict):
    """Preview email template with data"""
    try:
        html_content = render_template(template_name, data)
        return {"html": html_content}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Automated email workflows
@app.post("/workflows/order-confirmation")
async def send_order_confirmation(
    order_id: str,
    customer_email: str,
    customer_name: str,
    items: List[Dict],
    total: float,
    delivery_address: str,
    background_tasks: BackgroundTasks
):
    """Send order confirmation email"""
    data = {
        "customer_name": customer_name,
        "order_id": order_id,
        "order_date": datetime.now().strftime("%B %d, %Y"),
        "items": items,
        "total": total,
        "delivery_address": delivery_address,
        "estimated_delivery": "2-3 business days",
        "tracking_url": f"https://track.example.com/{order_id}",
        "support_email": "support@healthplus.ng",
        "support_phone": "+234 803 123 4567",
        "company_name": "HealthPlus Pharmacy"
    }
    
    html_content = render_template("order_confirmation", data)
    
    background_tasks.add_task(
        send_email,
        [EmailRecipient(email=customer_email, name=customer_name)],
        f"Order Confirmation - #{order_id}",
        html_content
    )
    
    return {"status": "queued"}

@app.post("/workflows/shipping-update")
async def send_shipping_update(
    order_id: str,
    customer_email: str,
    customer_name: str,
    tracking_number: str,
    delivery_address: str,
    background_tasks: BackgroundTasks
):
    """Send shipping update email"""
    data = {
        "customer_name": customer_name,
        "order_id": order_id,
        "tracking_number": tracking_number,
        "delivery_address": delivery_address,
        "estimated_delivery": "Tomorrow",
        "tracking_url": f"https://track.example.com/{tracking_number}",
        "company_name": "HealthPlus Pharmacy"
    }
    
    html_content = render_template("shipping_update", data)
    
    background_tasks.add_task(
        send_email,
        [EmailRecipient(email=customer_email, name=customer_name)],
        f"Your Order #{order_id} Has Shipped!",
        html_content
    )
    
    return {"status": "queued"}

@app.post("/workflows/abandoned-cart")
async def send_abandoned_cart(
    customer_email: str,
    customer_name: str,
    items: List[Dict],
    cart_url: str,
    discount_code: Optional[str] = None,
    discount_percent: Optional[int] = None,
    background_tasks: BackgroundTasks = None
):
    """Send abandoned cart email"""
    data = {
        "customer_name": customer_name,
        "items": items,
        "checkout_url": cart_url,
        "discount_code": discount_code,
        "discount_percent": discount_percent,
        "company_name": "HealthPlus Pharmacy"
    }
    
    html_content = render_template("abandoned_cart", data)
    
    background_tasks.add_task(
        send_email,
        [EmailRecipient(email=customer_email, name=customer_name)],
        "You Left Something in Your Cart!",
        html_content
    )
    
    return {"status": "queued"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8042)

