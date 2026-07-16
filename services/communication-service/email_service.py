"""
Email Notification Service
Handles all email communications for the platform
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import asyncpg
import asyncio
import logging
from jinja2 import Template
import os

# Configuration
app = FastAPI(title="Email Notification Service")
logger = logging.getLogger(__name__)

# Database connection pool
db_pool = None

# SMTP Configuration
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@remittance.com")
FROM_NAME = os.getenv("FROM_NAME", "Remittance Platform")

# Models
class EmailRecipient(BaseModel):
    email: EmailStr
    name: Optional[str] = None

class EmailAttachment(BaseModel):
    filename: str
    content: bytes
    content_type: str = "application/octet-stream"

class EmailRequest(BaseModel):
    to: List[EmailRecipient]
    subject: str
    body: str
    html_body: Optional[str] = None
    cc: Optional[List[EmailRecipient]] = None
    bcc: Optional[List[EmailRecipient]] = None
    reply_to: Optional[EmailStr] = None
    attachments: Optional[List[Dict[str, Any]]] = None
    template: Optional[str] = None
    template_data: Optional[Dict[str, Any]] = None
    priority: str = "normal"  # high, normal, low

class EmailStatus(BaseModel):
    id: int
    to_email: str
    subject: str
    status: str
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime

# Email Templates
EMAIL_TEMPLATES = {
    "welcome": """
    <html>
    <body>
        <h1>Welcome to Remittance Platform, {{ name }}!</h1>
        <p>Thank you for joining us. We're excited to have you on board.</p>
        <p>Your account has been successfully created.</p>
        <p>Best regards,<br>The Remittance Platform Team</p>
    </body>
    </html>
    """,
    
    "password_reset": """
    <html>
    <body>
        <h1>Password Reset Request</h1>
        <p>Hi {{ name }},</p>
        <p>We received a request to reset your password. Click the link below to reset it:</p>
        <p><a href="{{ reset_link }}">Reset Password</a></p>
        <p>This link will expire in {{ expiry_hours }} hours.</p>
        <p>If you didn't request this, please ignore this email.</p>
        <p>Best regards,<br>The Remittance Platform Team</p>
    </body>
    </html>
    """,
    
    "order_confirmation": """
    <html>
    <body>
        <h1>Order Confirmation</h1>
        <p>Hi {{ customer_name }},</p>
        <p>Thank you for your order! Your order #{{ order_number }} has been confirmed.</p>
        <h2>Order Details:</h2>
        <ul>
        {% for item in items %}
            <li>{{ item.name }} - Quantity: {{ item.quantity }} - ${{ item.price }}</li>
        {% endfor %}
        </ul>
        <p><strong>Total: ${{ total }}</strong></p>
        <p>We'll send you another email when your order ships.</p>
        <p>Best regards,<br>The Remittance Platform Team</p>
    </body>
    </html>
    """,
    
    "order_shipped": """
    <html>
    <body>
        <h1>Your Order Has Shipped!</h1>
        <p>Hi {{ customer_name }},</p>
        <p>Great news! Your order #{{ order_number }} has been shipped.</p>
        <p><strong>Tracking Number:</strong> {{ tracking_number }}</p>
        <p><strong>Carrier:</strong> {{ carrier }}</p>
        <p>You can track your shipment using the tracking number above.</p>
        <p>Estimated delivery: {{ estimated_delivery }}</p>
        <p>Best regards,<br>The Remittance Platform Team</p>
    </body>
    </html>
    """,
    
    "order_delivered": """
    <html>
    <body>
        <h1>Your Order Has Been Delivered!</h1>
        <p>Hi {{ customer_name }},</p>
        <p>Your order #{{ order_number }} has been delivered.</p>
        <p>We hope you enjoy your purchase!</p>
        <p>If you have any questions or concerns, please don't hesitate to contact us.</p>
        <p>Best regards,<br>The Remittance Platform Team</p>
    </body>
    </html>
    """,
    
    "payment_received": """
    <html>
    <body>
        <h1>Payment Received</h1>
        <p>Hi {{ customer_name }},</p>
        <p>We've received your payment of ${{ amount }} for order #{{ order_number }}.</p>
        <p><strong>Payment Method:</strong> {{ payment_method }}</p>
        <p><strong>Transaction ID:</strong> {{ transaction_id }}</p>
        <p>Thank you for your payment!</p>
        <p>Best regards,<br>The Remittance Platform Team</p>
    </body>
    </html>
    """,
    
    "low_inventory_alert": """
    <html>
    <body>
        <h1>Low Inventory Alert</h1>
        <p>Hi Team,</p>
        <p>The following items are running low on inventory:</p>
        <ul>
        {% for item in items %}
            <li>{{ item.sku }} - {{ item.name }}: {{ item.quantity }} units remaining (Reorder point: {{ item.reorder_point }})</li>
        {% endfor %}
        </ul>
        <p>Please review and reorder as necessary.</p>
        <p>Best regards,<br>Inventory System</p>
    </body>
    </html>
    """,
    
    "mfa_code": """
    <html>
    <body>
        <h1>Your Verification Code</h1>
        <p>Hi {{ name }},</p>
        <p>Your verification code is: <strong>{{ code }}</strong></p>
        <p>This code will expire in {{ expiry_minutes }} minutes.</p>
        <p>If you didn't request this code, please ignore this email.</p>
        <p>Best regards,<br>The Remittance Platform Team</p>
    </body>
    </html>
    """
}

# Database initialization
async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(
        host=os.getenv('DB_HOST', 'localhost'),
        port=5432,
        database='remittance',
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', ''),
        min_size=5,
        max_size=20
    )
    
    # Create tables
    async with db_pool.acquire() as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS email_queue (
                id SERIAL PRIMARY KEY,
                to_email VARCHAR(255) NOT NULL,
                to_name VARCHAR(255),
                subject VARCHAR(500) NOT NULL,
                body TEXT NOT NULL,
                html_body TEXT,
                status VARCHAR(50) DEFAULT 'pending',
                priority VARCHAR(20) DEFAULT 'normal',
                attempts INTEGER DEFAULT 0,
                max_attempts INTEGER DEFAULT 3,
                sent_at TIMESTAMP,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS email_logs (
                id SERIAL PRIMARY KEY,
                email_queue_id INTEGER REFERENCES email_queue(id),
                to_email VARCHAR(255) NOT NULL,
                subject VARCHAR(500) NOT NULL,
                status VARCHAR(50) NOT NULL,
                error_message TEXT,
                sent_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Create indexes
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_email_queue_status ON email_queue(status)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_email_queue_priority ON email_queue(priority)')
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_email_logs_sent_at ON email_logs(sent_at)')

# Helper functions
def render_template(template_name: str, data: Dict[str, Any]) -> str:
    """Render email template with data"""
    if template_name not in EMAIL_TEMPLATES:
        raise ValueError(f"Template '{template_name}' not found")
    
    template = Template(EMAIL_TEMPLATES[template_name])
    return template.render(**data)

async def send_email_smtp(
    to_email: str,
    to_name: Optional[str],
    subject: str,
    body: str,
    html_body: Optional[str] = None,
    attachments: Optional[List[Dict]] = None
) -> bool:
    """Send email via SMTP"""
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{FROM_NAME} <{FROM_EMAIL}>"
        msg['To'] = f"{to_name} <{to_email}>" if to_name else to_email
        msg['Subject'] = subject
        
        # Add text body
        msg.attach(MIMEText(body, 'plain'))
        
        # Add HTML body if provided
        if html_body:
            msg.attach(MIMEText(html_body, 'html'))
        
        # Add attachments if provided
        if attachments:
            for attachment in attachments:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment['content'])
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {attachment["filename"]}'
                )
                msg.attach(part)
        
        # Connect to SMTP server and send
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            if SMTP_USER and SMTP_PASSWORD:
                server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"Email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False

async def process_email_queue():
    """Background task to process email queue"""
    while True:
        try:
            await asyncio.sleep(10)  # Check every 10 seconds
            
            async with db_pool.acquire() as conn:
                # Get pending emails (prioritize high priority)
                emails = await conn.fetch(
                    """
                    SELECT * FROM email_queue
                    WHERE status = 'pending'
                    AND attempts < max_attempts
                    ORDER BY 
                        CASE priority
                            WHEN 'high' THEN 1
                            WHEN 'normal' THEN 2
                            WHEN 'low' THEN 3
                        END,
                        created_at
                    LIMIT 10
                    """,
                )
                
                for email in emails:
                    # Update status to processing
                    await conn.execute(
                        """
                        UPDATE email_queue
                        SET status = 'processing', attempts = attempts + 1
                        WHERE id = $1
                        """,
                        email['id']
                    )
                    
                    # Send email
                    success = await send_email_smtp(
                        email['to_email'],
                        email['to_name'],
                        email['subject'],
                        email['body'],
                        email['html_body']
                    )
                    
                    if success:
                        # Mark as sent
                        await conn.execute(
                            """
                            UPDATE email_queue
                            SET status = 'sent', sent_at = NOW(), updated_at = NOW()
                            WHERE id = $1
                            """,
                            email['id']
                        )
                        
                        # Log success
                        await conn.execute(
                            """
                            INSERT INTO email_logs (
                                email_queue_id, to_email, subject, status
                            )
                            VALUES ($1, $2, $3, 'sent')
                            """,
                            email['id'], email['to_email'], email['subject']
                        )
                    else:
                        # Mark as failed if max attempts reached
                        if email['attempts'] + 1 >= email['max_attempts']:
                            await conn.execute(
                                """
                                UPDATE email_queue
                                SET status = 'failed', 
                                    error_message = 'Max attempts reached',
                                    updated_at = NOW()
                                WHERE id = $1
                                """,
                                email['id']
                            )
                        else:
                            # Reset to pending for retry
                            await conn.execute(
                                """
                                UPDATE email_queue
                                SET status = 'pending', updated_at = NOW()
                                WHERE id = $1
                                """,
                                email['id']
                            )
                        
                        # Log failure
                        await conn.execute(
                            """
                            INSERT INTO email_logs (
                                email_queue_id, to_email, subject, status, error_message
                            )
                            VALUES ($1, $2, $3, 'failed', 'SMTP send failed')
                            """,
                            email['id'], email['to_email'], email['subject']
                        )
                        
        except Exception as e:
            logger.error(f"Error processing email queue: {e}")

# API Endpoints

@app.on_event("startup")
async def startup():
    await init_db()
    # Start background email processor
    asyncio.create_task(process_email_queue())

@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()

@app.post("/email/send")
async def send_email(request: EmailRequest):
    """Queue email for sending"""
    async with db_pool.acquire() as conn:
        # Render template if specified
        html_body = request.html_body
        if request.template and request.template_data:
            html_body = render_template(request.template, request.template_data)
        
        # Queue email for each recipient
        email_ids = []
        for recipient in request.to:
            email_id = await conn.fetchval(
                """
                INSERT INTO email_queue (
                    to_email, to_name, subject, body, html_body, priority
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                recipient.email,
                recipient.name,
                request.subject,
                request.body,
                html_body,
                request.priority
            )
            email_ids.append(email_id)
        
        return {
            "message": f"Email queued for {len(request.to)} recipient(s)",
            "email_ids": email_ids
        }

@app.post("/email/send-immediate")
async def send_email_immediate(request: EmailRequest):
    """Send email immediately (bypass queue)"""
    html_body = request.html_body
    if request.template and request.template_data:
        html_body = render_template(request.template, request.template_data)
    
    results = []
    for recipient in request.to:
        success = await send_email_smtp(
            recipient.email,
            recipient.name,
            request.subject,
            request.body,
            html_body
        )
        results.append({
            "email": recipient.email,
            "success": success
        })
    
    return {"results": results}

@app.get("/email/status/{email_id}")
async def get_email_status(email_id: int):
    """Get email status"""
    async with db_pool.acquire() as conn:
        email = await conn.fetchrow(
            "SELECT * FROM email_queue WHERE id = $1",
            email_id
        )
        
        if not email:
            raise HTTPException(status_code=404, detail="Email not found")
        
        return EmailStatus(**dict(email))

@app.get("/email/logs")
async def get_email_logs(limit: int = 50):
    """Get email logs"""
    async with db_pool.acquire() as conn:
        logs = await conn.fetch(
            """
            SELECT * FROM email_logs
            ORDER BY sent_at DESC
            LIMIT $1
            """,
            limit
        )
        
        return [dict(log) for log in logs]

@app.get("/email/queue")
async def get_email_queue(status: Optional[str] = None):
    """Get email queue"""
    async with db_pool.acquire() as conn:
        if status:
            emails = await conn.fetch(
                """
                SELECT * FROM email_queue
                WHERE status = $1
                ORDER BY created_at DESC
                LIMIT 100
                """,
                status
            )
        else:
            emails = await conn.fetch(
                """
                SELECT * FROM email_queue
                ORDER BY created_at DESC
                LIMIT 100
                """
            )
        
        return [EmailStatus(**dict(email)) for email in emails]

@app.delete("/email/queue/{email_id}")
async def cancel_email(email_id: int):
    """Cancel queued email"""
    async with db_pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE email_queue
            SET status = 'cancelled', updated_at = NOW()
            WHERE id = $1 AND status = 'pending'
            """,
            email_id
        )
        
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Email not found or already processed")
        
        return {"message": "Email cancelled"}

@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "service": "email",
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8085)

