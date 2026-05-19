import sys as _sys, os as _os
_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
Voice Assistant Service
AI-powered voice assistant integration for Remittance Platform
Supports Google Assistant, Alexa, Siri, and custom voice interfaces
"""
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("voice-assistant-service")
app.include_router(metrics_router)

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import logging
import os
import uuid
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Voice Assistant Service",
    description="AI-powered voice assistant integration service",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
class Config:
    GOOGLE_ASSISTANT_KEY = os.getenv("GOOGLE_ASSISTANT_KEY", "")
    ALEXA_SKILL_ID = os.getenv("ALEXA_SKILL_ID", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./voice_assistant.db")

config = Config()

# Enums
class AssistantPlatform(str, Enum):
    GOOGLE_ASSISTANT = "google_assistant"
    ALEXA = "alexa"
    SIRI = "siri"
    CUSTOM = "custom"

class IntentType(str, Enum):
    BALANCE_INQUIRY = "balance_inquiry"
    TRANSACTION_HISTORY = "transaction_history"
    TRANSFER_MONEY = "transfer_money"
    PAY_BILL = "pay_bill"
    AGENT_INFO = "agent_info"
    HELP = "help"
    UNKNOWN = "unknown"

class SessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    EXPIRED = "expired"

# Models
class VoiceSession(BaseModel):
    id: Optional[str] = None
    agent_id: str
    platform: AssistantPlatform
    user_id: str
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    status: SessionStatus = SessionStatus.ACTIVE
    context: Dict[str, Any] = {}

class VoiceCommand(BaseModel):
    id: Optional[str] = None
    session_id: str
    command_text: str
    intent: IntentType
    entities: Dict[str, Any] = {}
    confidence: float = 0.0
    timestamp: Optional[datetime] = None

class VoiceResponse(BaseModel):
    id: Optional[str] = None
    command_id: str
    response_text: str
    response_audio_url: Optional[str] = None
    should_end_session: bool = False
    timestamp: Optional[datetime] = None

class IntentRequest(BaseModel):
    session_id: str
    text: str
    platform: AssistantPlatform
    user_id: str
    context: Dict[str, Any] = {}

class IntentResponse(BaseModel):
    intent: IntentType
    entities: Dict[str, Any]
    confidence: float
    response_text: str
    should_end_session: bool = False

class VoiceSkill(BaseModel):
    id: Optional[str] = None
    name: str
    description: str
    platform: AssistantPlatform
    intents: List[str]
    is_active: bool = True
    created_at: Optional[datetime] = None

# In-memory storage
sessions_db: Dict[str, VoiceSession] = {}
commands_db: Dict[str, VoiceCommand] = {}
responses_db: Dict[str, VoiceResponse] = {}
skills_db: Dict[str, VoiceSkill] = {}

# Intent Processing Functions

def process_balance_inquiry(entities: Dict[str, Any], context: Dict[str, Any]) -> str:
    """Process balance inquiry intent"""
    account_type = entities.get("account_type", "main")
    return f"Your {account_type} account balance is 5,000 dollars and 50 cents."

def process_transaction_history(entities: Dict[str, Any], context: Dict[str, Any]) -> str:
    """Process transaction history intent"""
    period = entities.get("period", "recent")
    return f"Here are your {period} transactions: You received 1,000 dollars on Monday, paid 200 dollars for utilities on Tuesday, and transferred 500 dollars on Wednesday."

def process_transfer_money(entities: Dict[str, Any], context: Dict[str, Any]) -> str:
    """Process money transfer intent"""
    amount = entities.get("amount", "")
    recipient = entities.get("recipient", "")
    return f"I'll transfer {amount} dollars to {recipient}. Please confirm by saying 'yes' or 'confirm'."

def process_pay_bill(entities: Dict[str, Any], context: Dict[str, Any]) -> str:
    """Process bill payment intent"""
    biller = entities.get("biller", "")
    amount = entities.get("amount", "")
    return f"I'll pay {amount} dollars to {biller}. Please confirm by saying 'yes' or 'confirm'."

def process_agent_info(entities: Dict[str, Any], context: Dict[str, Any]) -> str:
    """Process agent info request"""
    return "You are an authorized agent with ID A-12345. Your commission rate is 2.5% and you have 150 active customers."

def process_help(entities: Dict[str, Any], context: Dict[str, Any]) -> str:
    """Process help request"""
    return "I can help you with: checking your balance, viewing transaction history, transferring money, paying bills, and getting agent information. What would you like to do?"

# Intent Classification
def classify_intent(text: str) -> tuple[IntentType, Dict[str, Any], float]:
    """Classify intent from text (simple keyword-based, replace with ML model in production)"""
    text_lower = text.lower()
    
    # Balance inquiry
    if any(word in text_lower for word in ["balance", "how much", "account"]):
        return IntentType.BALANCE_INQUIRY, {}, 0.85
    
    # Transaction history
    if any(word in text_lower for word in ["transaction", "history", "recent", "last"]):
        return IntentType.TRANSACTION_HISTORY, {}, 0.80
    
    # Transfer money
    if any(word in text_lower for word in ["transfer", "send money", "send"]):
        return IntentType.TRANSFER_MONEY, {}, 0.75
    
    # Pay bill
    if any(word in text_lower for word in ["pay bill", "payment", "pay"]):
        return IntentType.PAY_BILL, {}, 0.70
    
    # Agent info
    if any(word in text_lower for word in ["agent info", "my info", "commission"]):
        return IntentType.AGENT_INFO, {}, 0.85
    
    # Help
    if any(word in text_lower for word in ["help", "what can you do", "assist"]):
        return IntentType.HELP, {}, 0.90
    
    return IntentType.UNKNOWN, {}, 0.0

# API Endpoints

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "voice-assistant-service",
        "timestamp": datetime.utcnow().isoformat(),
        "platforms_configured": {
            "google_assistant": bool(config.GOOGLE_ASSISTANT_KEY),
            "alexa": bool(config.ALEXA_SKILL_ID),
            "openai": bool(config.OPENAI_API_KEY)
        }
    }

@app.post("/sessions", response_model=VoiceSession)
async def create_session(session: VoiceSession):
    """Create a new voice assistant session"""
    try:
        session.id = str(uuid.uuid4())
        session.started_at = datetime.utcnow()
        
        sessions_db[session.id] = session
        
        logger.info(f"Created voice session {session.id} for agent {session.agent_id}")
        return session
    except Exception as e:
        logger.error(f"Error creating session: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions/{session_id}", response_model=VoiceSession)
async def get_session(session_id: str):
    """Get a voice session"""
    if session_id not in sessions_db:
        raise HTTPException(status_code=404, detail="Session not found")
    return sessions_db[session_id]

@app.post("/sessions/{session_id}/end")
async def end_session(session_id: str):
    """End a voice session"""
    if session_id not in sessions_db:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = sessions_db[session_id]
    session.ended_at = datetime.utcnow()
    session.status = SessionStatus.COMPLETED
    
    logger.info(f"Ended voice session {session_id}")
    return {"message": "Session ended successfully"}

@app.post("/intent", response_model=IntentResponse)
async def process_intent(request: IntentRequest):
    """Process voice intent and generate response"""
    try:
        # Verify session exists
        if request.session_id not in sessions_db:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Classify intent
        intent, entities, confidence = classify_intent(request.text)
        
        # Store command
        command = VoiceCommand(
            id=str(uuid.uuid4()),
            session_id=request.session_id,
            command_text=request.text,
            intent=intent,
            entities=entities,
            confidence=confidence,
            timestamp=datetime.utcnow()
        )
        commands_db[command.id] = command
        
        # Process intent and generate response
        if intent == IntentType.BALANCE_INQUIRY:
            response_text = process_balance_inquiry(entities, request.context)
        elif intent == IntentType.TRANSACTION_HISTORY:
            response_text = process_transaction_history(entities, request.context)
        elif intent == IntentType.TRANSFER_MONEY:
            response_text = process_transfer_money(entities, request.context)
        elif intent == IntentType.PAY_BILL:
            response_text = process_pay_bill(entities, request.context)
        elif intent == IntentType.AGENT_INFO:
            response_text = process_agent_info(entities, request.context)
        elif intent == IntentType.HELP:
            response_text = process_help(entities, request.context)
        else:
            response_text = "I'm sorry, I didn't understand that. Can you please rephrase?"
        
        # Store response
        response = VoiceResponse(
            id=str(uuid.uuid4()),
            command_id=command.id,
            response_text=response_text,
            timestamp=datetime.utcnow()
        )
        responses_db[response.id] = response
        
        logger.info(f"Processed intent {intent} for session {request.session_id}")
        
        return IntentResponse(
            intent=intent,
            entities=entities,
            confidence=confidence,
            response_text=response_text,
            should_end_session=False
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing intent: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/commands", response_model=VoiceCommand)
async def create_command(command: VoiceCommand):
    """Create a voice command record"""
    try:
        command.id = str(uuid.uuid4())
        command.timestamp = datetime.utcnow()
        
        commands_db[command.id] = command
        
        logger.info(f"Created command {command.id} for session {command.session_id}")
        return command
    except Exception as e:
        logger.error(f"Error creating command: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/commands", response_model=List[VoiceCommand])
async def list_commands(session_id: Optional[str] = None):
    """List voice commands"""
    try:
        commands = list(commands_db.values())
        
        if session_id:
            commands = [c for c in commands if c.session_id == session_id]
        
        return commands
    except Exception as e:
        logger.error(f"Error listing commands: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/skills", response_model=VoiceSkill)
async def create_skill(skill: VoiceSkill):
    """Create a voice assistant skill"""
    try:
        skill.id = str(uuid.uuid4())
        skill.created_at = datetime.utcnow()
        
        skills_db[skill.id] = skill
        
        logger.info(f"Created skill {skill.name} for platform {skill.platform}")
        return skill
    except Exception as e:
        logger.error(f"Error creating skill: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/skills", response_model=List[VoiceSkill])
async def list_skills(platform: Optional[AssistantPlatform] = None):
    """List voice assistant skills"""
    try:
        skills = list(skills_db.values())
        
        if platform:
            skills = [s for s in skills if s.platform == platform]
        
        return skills
    except Exception as e:
        logger.error(f"Error listing skills: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhooks/google-assistant")
async def google_assistant_webhook(data: Dict[str, Any]):
    """Handle Google Assistant webhook"""
    try:
        logger.info(f"Received Google Assistant webhook")
        
        # Process Google Assistant request format
        query_text = data.get("queryResult", {}).get("queryText", "")
        
        # Create or get session
        session_id = data.get("session", "").split("/")[-1]
        
        # Process intent
        # Return Google Assistant response format
        
        return {
            "fulfillmentText": "Response from Remittance Platform",
            "fulfillmentMessages": []
        }
    except Exception as e:
        logger.error(f"Error processing Google Assistant webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/webhooks/alexa")
async def alexa_webhook(data: Dict[str, Any]):
    """Handle Alexa webhook"""
    try:
        logger.info(f"Received Alexa webhook")
        
        # Process Alexa request format
        request_type = data.get("request", {}).get("type", "")
        
        # Return Alexa response format
        return {
            "version": "1.0",
            "response": {
                "outputSpeech": {
                    "type": "PlainText",
                    "text": "Response from Remittance Platform"
                },
                "shouldEndSession": False
            }
        }
    except Exception as e:
        logger.error(f"Error processing Alexa webhook: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/analytics/{agent_id}")
async def get_voice_analytics(agent_id: str):
    """Get voice assistant analytics for an agent"""
    try:
        agent_sessions = [s for s in sessions_db.values() if s.agent_id == agent_id]
        session_ids = [s.id for s in agent_sessions]
        
        agent_commands = [c for c in commands_db.values() if c.session_id in session_ids]
        
        intent_counts = {}
        for command in agent_commands:
            intent = command.intent
            intent_counts[intent] = intent_counts.get(intent, 0) + 1
        
        return {
            "total_sessions": len(agent_sessions),
            "active_sessions": len([s for s in agent_sessions if s.status == SessionStatus.ACTIVE]),
            "total_commands": len(agent_commands),
            "intent_distribution": intent_counts,
            "average_confidence": sum(c.confidence for c in agent_commands) / len(agent_commands) if agent_commands else 0,
            "platforms_used": list(set(s.platform for s in agent_sessions))
        }
    except Exception as e:
        logger.error(f"Error getting analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8084)

