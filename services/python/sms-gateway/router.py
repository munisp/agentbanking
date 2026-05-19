"""
SMS Gateway Router - Exposes SMS banking endpoints via FastAPI router
"""

from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sms-gateway", tags=["sms-gateway"])


class SMSIncoming(BaseModel):
    sender: str
    message: str
    message_id: Optional[str] = None
    timestamp: Optional[str] = None


class SMSSend(BaseModel):
    recipient: str
    message: str


class SMSProcessRequest(BaseModel):
    phone: str
    message: str
    message_id: Optional[str] = None


@router.post("/webhook")
async def sms_webhook(request: Request):
    """Receive incoming SMS from provider webhook"""
    try:
        from sms_gateway.sms_gateway_service import app as sms_app
        body = await request.json()
        return {"status": "received", "message_id": body.get("message_id", ""), "provider": os.getenv("SMS_PROVIDER", "africas_talking")}
    except Exception as e:
        logger.error(f"SMS webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process")
async def process_sms(req: SMSProcessRequest):
    """Process an SMS banking command"""
    try:
        from sms_gateway.sms_gateway_service import SMSCommandParser, SMSCommandExecutor
        command = SMSCommandParser.parse(req.message)
        if not command:
            return {"status": "error", "response": "Invalid command format. Send HELP for available commands."}
        executor = SMSCommandExecutor()
        response = await executor.execute(req.phone, command, req.message_id or "")
        return {"status": "success", "response": response, "command_type": command.command_type}
    except Exception as e:
        logger.error(f"SMS process error: {e}")
        return {"status": "error", "response": f"Processing error: {str(e)}"}


@router.post("/send")
async def send_sms(req: SMSSend):
    """Send an SMS message"""
    try:
        from sms_gateway.sms_gateway_service import SMSSender
        result = await SMSSender.send(req.recipient, req.message)
        return {"status": "sent", "result": result}
    except Exception as e:
        logger.error(f"SMS send error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health():
    """SMS gateway health check"""
    return {
        "service": "sms-gateway",
        "status": "healthy",
        "provider": os.getenv("SMS_PROVIDER", "africas_talking"),
        "sender_id": os.getenv("SMS_SENDER_ID", "AgentBank")
    }


@router.get("/metrics")
async def metrics():
    """SMS gateway metrics"""
    return {
        "service": "sms-gateway",
        "status": "operational",
        "supported_commands": [
            "BAL", "TRF", "AIR", "BILL", "STMT", "PIN", "REG", "OTP", "HELP"
        ]
    }


@router.get("/commands")
async def list_commands():
    """List available SMS commands"""
    return {
        "commands": [
            {"code": "BAL", "format": "BAL <PIN>", "description": "Check account balance"},
            {"code": "TRF", "format": "TRF <AMOUNT> <ACCOUNT> <PIN>", "description": "Transfer funds"},
            {"code": "AIR", "format": "AIR <AMOUNT> <PHONE> <PIN>", "description": "Buy airtime"},
            {"code": "BILL", "format": "BILL <TYPE> <ACCOUNT> <AMOUNT> <PIN>", "description": "Pay bills"},
            {"code": "STMT", "format": "STMT <DAYS> <PIN>", "description": "Get mini statement"},
            {"code": "PIN", "format": "PIN <OLD> <NEW> <CONFIRM>", "description": "Change PIN"},
            {"code": "REG", "format": "REG <NAME> <NIN>", "description": "Register account"},
            {"code": "OTP", "format": "OTP <CODE> <TXN_ID>", "description": "Verify OTP"},
            {"code": "HELP", "format": "HELP", "description": "Show available commands"},
        ]
    }
