"""
Email Service API Router
Complete REST API endpoints for email operations
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from pydantic import BaseModel, EmailStr
from typing import List, Optional, Dict
from datetime import datetime
import logging

from .email_service import send_email, EmailRequest, EmailRecipient, EmailAttachment
from .models import EmailLog, EmailTemplate as EmailTemplateModel
from .config import get_db

router = APIRouter(prefix="/api/v1/email", tags=["email"])
logger = logging.getLogger(__name__)

# Request/Response Models
class SendEmailRequest(BaseModel):
    to: List[EmailRecipient]
    subject: str
    template: str
    data: Dict
    attachments: Optional[List[EmailAttachment]] = None
    cc: Optional[List[EmailRecipient]] = None
    bcc: Optional[List[EmailRecipient]] = None
    priority: Optional[str] = "normal"  # low, normal, high
    scheduled_at: Optional[datetime] = None

class SendEmailResponse(BaseModel):
    success: bool
    message_id: str
    status: str
    sent_at: datetime

class EmailStatusResponse(BaseModel):
    message_id: str
    status: str
    sent_at: Optional[datetime]
    delivered_at: Optional[datetime]
    opened_at: Optional[datetime]
    clicked_at: Optional[datetime]
    bounced: bool
    error_message: Optional[str]

class EmailTemplateRequest(BaseModel):
    name: str
    subject: str
    html_content: str
    text_content: Optional[str]
    variables: List[str]
    category: str

# Endpoints

@router.post("/send", response_model=SendEmailResponse)
async def send_email_endpoint(
    request: SendEmailRequest,
    background_tasks: BackgroundTasks,
    db = Depends(get_db)
):
    """
    Send an email using a template
    
    - **to**: List of recipients
    - **subject**: Email subject
    - **template**: Template name to use
    - **data**: Template variables
    - **attachments**: Optional file attachments
    - **priority**: Email priority (low, normal, high)
    - **scheduled_at**: Optional scheduled send time
    """
    try:
        # Create email request
        email_req = EmailRequest(
            to=request.to,
            subject=request.subject,
            template=request.template,
            data=request.data,
            attachments=request.attachments,
            cc=request.cc,
            bcc=request.bcc
        )
        
        # Generate message ID
        import uuid
        message_id = str(uuid.uuid4())
        
        # Log email
        email_log = EmailLog(
            message_id=message_id,
            to_addresses=[r.email for r in request.to],
            subject=request.subject,
            template=request.template,
            status="queued",
            priority=request.priority,
            scheduled_at=request.scheduled_at
        )
        db.add(email_log)
        db.commit()
        
        # Send email in background or schedule
        if request.scheduled_at and request.scheduled_at > datetime.utcnow():
            # Schedule for later
            background_tasks.add_task(schedule_email, email_req, message_id, request.scheduled_at, db)
            status = "scheduled"
        else:
            # Send immediately in background
            background_tasks.add_task(send_email_background, email_req, message_id, db)
            status = "queued"
        
        return SendEmailResponse(
            success=True,
            message_id=message_id,
            status=status,
            sent_at=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

@router.get("/status/{message_id}", response_model=EmailStatusResponse)
async def get_email_status(message_id: str, db = Depends(get_db)):
    """
    Get the status of a sent email
    
    - **message_id**: The unique message identifier
    """
    email_log = db.query(EmailLog).filter(EmailLog.message_id == message_id).first()
    
    if not email_log:
        raise HTTPException(status_code=404, detail="Email not found")
    
    return EmailStatusResponse(
        message_id=email_log.message_id,
        status=email_log.status,
        sent_at=email_log.sent_at,
        delivered_at=email_log.delivered_at,
        opened_at=email_log.opened_at,
        clicked_at=email_log.clicked_at,
        bounced=email_log.bounced,
        error_message=email_log.error_message
    )

@router.get("/history")
async def get_email_history(
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    db = Depends(get_db)
):
    """
    Get email sending history
    
    - **skip**: Number of records to skip
    - **limit**: Maximum number of records to return
    - **status**: Filter by status (queued, sent, delivered, bounced, failed)
    """
    query = db.query(EmailLog)
    
    if status:
        query = query.filter(EmailLog.status == status)
    
    emails = query.order_by(EmailLog.created_at.desc()).offset(skip).limit(limit).all()
    
    return {
        "total": query.count(),
        "emails": emails
    }

@router.post("/templates", response_model=dict)
async def create_email_template(
    template: EmailTemplateRequest,
    db = Depends(get_db)
):
    """
    Create a new email template
    
    - **name**: Template name (unique identifier)
    - **subject**: Default subject line
    - **html_content**: HTML template content
    - **text_content**: Plain text fallback
    - **variables**: List of template variables
    - **category**: Template category
    """
    # Check if template exists
    existing = db.query(EmailTemplateModel).filter(EmailTemplateModel.name == template.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Template already exists")
    
    # Create template
    db_template = EmailTemplateModel(
        name=template.name,
        subject=template.subject,
        html_content=template.html_content,
        text_content=template.text_content,
        variables=template.variables,
        category=template.category
    )
    
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    
    return {
        "success": True,
        "template_id": db_template.id,
        "name": db_template.name
    }

@router.get("/templates")
async def list_email_templates(
    category: Optional[str] = None,
    db = Depends(get_db)
):
    """
    List all email templates
    
    - **category**: Filter by category
    """
    query = db.query(EmailTemplateModel)
    
    if category:
        query = query.filter(EmailTemplateModel.category == category)
    
    templates = query.all()
    
    return {
        "total": len(templates),
        "templates": templates
    }

@router.get("/templates/{template_name}")
async def get_email_template(template_name: str, db = Depends(get_db)):
    """
    Get a specific email template
    
    - **template_name**: Template name
    """
    template = db.query(EmailTemplateModel).filter(EmailTemplateModel.name == template_name).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    return template

@router.put("/templates/{template_name}")
async def update_email_template(
    template_name: str,
    template: EmailTemplateRequest,
    db = Depends(get_db)
):
    """
    Update an existing email template
    
    - **template_name**: Template name to update
    """
    db_template = db.query(EmailTemplateModel).filter(EmailTemplateModel.name == template_name).first()
    
    if not db_template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    # Update fields
    db_template.subject = template.subject
    db_template.html_content = template.html_content
    db_template.text_content = template.text_content
    db_template.variables = template.variables
    db_template.category = template.category
    db_template.updated_at = datetime.utcnow()
    
    db.commit()
    
    return {
        "success": True,
        "message": "Template updated successfully"
    }

@router.delete("/templates/{template_name}")
async def delete_email_template(template_name: str, db = Depends(get_db)):
    """
    Delete an email template
    
    - **template_name**: Template name to delete
    """
    template = db.query(EmailTemplateModel).filter(EmailTemplateModel.name == template_name).first()
    
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    
    db.delete(template)
    db.commit()
    
    return {
        "success": True,
        "message": "Template deleted successfully"
    }

@router.post("/test")
async def send_test_email(
    to_email: EmailStr,
    template_name: str,
    background_tasks: BackgroundTasks
):
    """
    Send a test email
    
    - **to_email**: Recipient email address
    - **template_name**: Template to test
    """
    test_data = {
        "customer_name": "Test User",
        "order_id": "TEST-12345",
        "items": [{"name": "Test Item", "quantity": 1, "price": 100}],
        "total": 100
    }
    
    email_req = EmailRequest(
        to=[EmailRecipient(email=to_email, name="Test User")],
        subject="Test Email",
        template=template_name,
        data=test_data
    )
    
    background_tasks.add_task(send_email, email_req)
    
    return {
        "success": True,
        "message": f"Test email queued to {to_email}"
    }

# Background task functions

async def send_email_background(email_req: EmailRequest, message_id: str, db):
    """Send email in background and update status"""
    try:
        await send_email(email_req)
        
        # Update status
        email_log = db.query(EmailLog).filter(EmailLog.message_id == message_id).first()
        if email_log:
            email_log.status = "sent"
            email_log.sent_at = datetime.utcnow()
            db.commit()
            
    except Exception as e:
        logger.error(f"Error sending email {message_id}: {str(e)}")
        
        # Update status to failed
        email_log = db.query(EmailLog).filter(EmailLog.message_id == message_id).first()
        if email_log:
            email_log.status = "failed"
            email_log.error_message = str(e)
            db.commit()

async def schedule_email(email_req: EmailRequest, message_id: str, scheduled_at: datetime, db):
    """Schedule email for later sending"""
    import asyncio
    from datetime import datetime
    
    # Calculate delay
    delay = (scheduled_at - datetime.utcnow()).total_seconds()
    
    if delay > 0:
        await asyncio.sleep(delay)
    
    # Send email
    await send_email_background(email_req, message_id, db)

