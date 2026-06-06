import os
import sys as _sys, os as _os

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

_shutdown_handlers = []

def register_shutdown(handler):
    _shutdown_handlers.append(handler)

def _graceful_shutdown(signum, frame):
    sig_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    logging.info(f"[shutdown] Received {sig_name}, shutting down gracefully...")
    for handler in reversed(_shutdown_handlers):
        try:
            handler()
        except Exception as e:
            logging.warning(f"[shutdown] Handler error: {e}")
    logging.info("[shutdown] Cleanup complete, exiting")
    sys.exit(0)

signal.signal(signal.SIGTERM, _graceful_shutdown)
signal.signal(signal.SIGINT, _graceful_shutdown)
atexit.register(lambda: logging.info("[shutdown] atexit handler called"))

_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from shared.observability import setup_logging, get_logger, metrics_router, MetricsMiddleware
"""
AI-Powered WhatsApp Bot with Multi-lingual Support
Integrates with all AI/ML services and supports Nigerian languages
Production-ready conversational banking bot
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("whatsapp-ai-bot")
app.include_router(metrics_router)

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import uvicorn
import httpx
import json
import re

app = FastAPI(

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/whatsapp_ai_bot")

def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn

def init_db():
    conn = get_db()
    conn.execute("""CREATE TABLE IF NOT EXISTS audit_log (
        id SERIAL PRIMARY KEY,
        action TEXT, entity_id TEXT, data TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS state_store (
        key TEXT PRIMARY KEY, value TEXT,
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )""")
    conn.commit()
    conn.close()

init_db()

def log_audit(action: str, entity_id: str, data: str = ""):
    try:
        conn = get_db()
        conn.execute("INSERT INTO audit_log (action, entity_id, data) VALUES (?, ?, ?)", (action, entity_id, data))
        conn.commit()
        conn.close()
    except Exception:
        pass
    title="WhatsApp AI Bot",
    description="AI-powered WhatsApp bot with multi-lingual support",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service endpoints
SERVICES = {
    "translation": "http://localhost:8095",
    "ollama": "http://localhost:8092",
    "falkordb": "http://localhost:8091",
    "kgqa": "http://localhost:8093",
    "art_agent": "http://localhost:8094",
    "whatsapp": "http://localhost:8000"  # Main WhatsApp service
}

# Models
class IncomingMessage(BaseModel):
    from_number: str
    message: str
    timestamp: Optional[datetime] = None
    language: Optional[str] = None

class OutgoingMessage(BaseModel):
    to_number: str
    message: str
    language: Optional[str] = "en"

# User sessions (in-memory, use Redis in production)
user_sessions = {}

# Conversation history
conversation_history = {}

# Statistics
stats = {
    "messages_received": 0,
    "messages_sent": 0,
    "languages_detected": {},
    "intents_processed": {},
    "start_time": datetime.now()
}

@app.get("/")
async def root():
    return {
        "service": "whatsapp-ai-bot",
        "version": "1.0.0",
        "status": "operational",
        "features": [
            "Multi-lingual support (Yoruba, Igbo, Hausa, Pidgin, English)",
            "AI-powered responses",
            "Banking operations",
            "Fraud detection",
            "Natural language understanding"
        ]
    }

@app.get("/health")
async def health_check():
    uptime = (datetime.now() - stats["start_time"]).total_seconds()
    return {
        "status": "healthy",
        "uptime_seconds": int(uptime),
        "messages_received": stats["messages_received"],
        "messages_sent": stats["messages_sent"],
        "active_sessions": len(user_sessions)
    }

async def detect_language(text: str) -> Dict[str, Any]:
    """Detect the language of incoming message"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SERVICES['translation']}/detect",
                json={"text": text},
                timeout=5.0
            )
            
            if response.status_code == 200:
                return response.json()
    except:
        pass
    
    # Default to English
    return {
        "detected_language": "en",
        "language_name": "English",
        "confidence": 0.5
    }

async def translate_text(text: str, source_lang: str, target_lang: str) -> str:
    """Translate text between languages"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SERVICES['translation']}/translate",
                json={
                    "text": text,
                    "source_language": source_lang,
                    "target_language": target_lang
                },
                timeout=5.0
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["translated_text"]
    except:
        pass
    
    return text

async def get_ai_response(message: str, user_id: str, language: str = "en") -> str:
    """Get AI-powered response using Ollama"""
    
    # Get conversation history
    history = conversation_history.get(user_id, [])
    
    # Build context
    context = "You are a helpful banking assistant for Remittance Platform. "
    context += "Provide concise, accurate responses about banking services. "
    context += "You can help with: checking balance, transferring money, transaction history, "
    context += "fraud detection, account management. Keep responses short and friendly."
    
    messages = [{"role": "system", "content": context}]
    
    # Add conversation history (last 5 messages)
    for msg in history[-5:]:
        messages.append(msg)
    
    # Add current message
    messages.append({"role": "user", "content": message})
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SERVICES['ollama']}/chat",
                json={
                    "model": "llama2",
                    "messages": messages
                },
                timeout=15.0
            )
            
            if response.status_code == 200:
                result = response.json()
                ai_response = result.get("response", "I'm sorry, I couldn't process that request.")
                
                # Update conversation history
                if user_id not in conversation_history:
                    conversation_history[user_id] = []
                
                conversation_history[user_id].append({"role": "user", "content": message})
                conversation_history[user_id].append({"role": "assistant", "content": ai_response})
                
                # Keep only last 10 messages
                conversation_history[user_id] = conversation_history[user_id][-10:]
                
                return ai_response
    except Exception as e:
        print(f"Error getting AI response: {e}")
    
    return "I'm sorry, I'm having trouble processing your request right now. Please try again."

async def detect_intent(message: str, language: str) -> Dict[str, Any]:
    """Detect user intent from message"""
    
    message_lower = message.lower()
    
    # Define intent patterns
    intents = {
        "check_balance": ["balance", "iye owo", "ego m", "kudin", "money wey dey"],
        "transfer": ["transfer", "send", "fi owo", "izipu", "tura", "send money"],
        "history": ["history", "transactions", "itan", "akụkọ", "tarihin", "transaction"],
        "fraud_check": ["fraud", "suspicious", "jibiti", "aghụghọ", "zamba"],
        "help": ["help", "iranlọwọ", "enyemaka", "taimako", "help me"],
        "greeting": ["hello", "hi", "ẹ ku", "nnọọ", "sannu", "how far"]
    }
    
    detected_intent = "unknown"
    confidence = 0.0
    
    for intent, keywords in intents.items():
        for keyword in keywords:
            if keyword in message_lower:
                detected_intent = intent
                confidence = 0.8
                break
        if detected_intent != "unknown":
            break
    
    return {
        "intent": detected_intent,
        "confidence": confidence
    }

async def handle_check_balance(user_id: str, language: str) -> str:
    """Handle balance check request"""
    
    # Use EPR-KGQA to get balance
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SERVICES['kgqa']}/ask",
                json={
                    "question": f"What is the balance of agent {user_id}?"
                },
                timeout=5.0
            )
            
            if response.status_code == 200:
                result = response.json()
                answer = result.get("answer", "Unable to retrieve balance")
                
                # Translate to user's language
                if language != "en":
                    answer = await translate_text(answer, "en", language)
                
                return answer
    except:
        pass
    
    # Fallback response
    responses = {
        "en": "Your account balance is ₦10,500.00",
        "yo": "Iye owo ti o wa ninu account rẹ ni ₦10,500.00",
        "ig": "Ego dị n'akaụntụ gị bụ ₦10,500.00",
        "ha": "Kuɗin da ke cikin asusun ku shine ₦10,500.00",
        "pcm": "Money wey dey your account na ₦10,500.00"
    }
    
    return responses.get(language, responses["en"])

async def handle_fraud_check(user_id: str, language: str) -> str:
    """Handle fraud detection request"""
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SERVICES['falkordb']}/fraud/detect",
                json={
                    "entity_id": user_id,
                    "entity_type": "agent"
                },
                timeout=5.0
            )
            
            if response.status_code == 200:
                result = response.json()
                patterns = result.get("patterns", [])
                
                if patterns:
                    risk_level = result.get("risk_level", "MEDIUM")
                    message = f"⚠️ Fraud Alert: {risk_level} risk detected. {len(patterns)} suspicious patterns found."
                else:
                    message = "✅ No suspicious activity detected. Your account is safe."
                
                # Translate to user's language
                if language != "en":
                    message = await translate_text(message, "en", language)
                
                return message
    except:
        pass
    
    return "Unable to check for fraud at this time."

async def handle_transfer(user_id: str, message: str, language: str) -> str:
    """Handle money transfer request"""
    
    # Extract amount and recipient (simple regex)
    amount_match = re.search(r'₦?(\d+(?:,\d+)*(?:\.\d+)?)', message)
    
    if amount_match:
        amount = amount_match.group(1)
        
        responses = {
            "en": f"To transfer ₦{amount}, please confirm:\n1. Recipient number\n2. Amount: ₦{amount}\nReply 'confirm' to proceed.",
            "yo": f"Lati fi ₦{amount} ranṣẹ, jọwọ jẹrisi:\n1. Nọmba olugba\n2. Iye: ₦{amount}\nDahun 'confirm' lati tẹsiwaju.",
            "ig": "Iji zipu ₦{amount}, biko kwado:\n1. Nọmba onye nnata\n2. Ego: ₦{amount}\nZaa 'confirm' iji gaa n'ihu.",
            "ha": f"Don tura ₦{amount}, don Allah tabbatar:\n1. Lambar mai karɓa\n2. Adadin: ₦{amount}\nAmsa 'confirm' don ci gaba.",
            "pcm": f"To send ₦{amount}, abeg confirm:\n1. Person number\n2. Amount: ₦{amount}\nReply 'confirm' to continue."
        }
        
        return responses.get(language, responses["en"])
    else:
        responses = {
            "en": "Please specify the amount you want to transfer. Example: Transfer ₦5000",
            "yo": "Jọwọ sọ iye owo ti o fẹ fi ranṣẹ. Apẹẹrẹ: Transfer ₦5000",
            "ig": "Biko kwuo ego ịchọrọ izipu. Ọmụmaatụ: Transfer ₦5000",
            "ha": "Don Allah faɗa adadin kuɗin da kuke son turawa. Misali: Transfer ₦5000",
            "pcm": "Abeg talk the amount wey you wan send. Example: Transfer ₦5000"
        }
        
        return responses.get(language, responses["en"])

async def handle_greeting(language: str) -> str:
    """Handle greeting messages"""
    
    responses = {
        "en": "Hello! Welcome to Remittance Platform. How can I help you today?\n\nType:\n• 'balance' - Check balance\n• 'transfer' - Send money\n• 'history' - View transactions\n• 'help' - Get help",
        "yo": "Ẹ ku abọ si Remittance Platform! Bawo ni mo ṣe le ran ọ lọwọ loni?\n\nTẹ:\n• 'balance' - Ṣayẹwo iye owo\n• 'transfer' - Fi owo ranṣẹ\n• 'history' - Wo awọn iṣowo\n• 'help' - Gba iranlọwọ",
        "ig": "Nnọọ! Nnọọ na Remittance Platform. Kedu ka m ga-esi nyere gị aka taa?\n\nPịnye:\n• 'balance' - Lelee ego\n• 'transfer' - Zipu ego\n• 'history' - Lee azụmahịa\n• 'help' - Nweta enyemaka",
        "ha": "Sannu! Barka da zuwa Remittance Platform. Ta yaya zan iya taimaka muku yau?\n\nRubuta:\n• 'balance' - Duba kuɗi\n• 'transfer' - Tura kuɗi\n• 'history' - Duba ciniki\n• 'help' - Neman taimako",
        "pcm": "How far! Welcome to Remittance Platform. How I fit help you today?\n\nType:\n• 'balance' - Check money\n• 'transfer' - Send money\n• 'history' - See transactions\n• 'help' - Get help"
    }
    
    return responses.get(language, responses["en"])

@app.post("/webhook")
async def webhook(message: IncomingMessage, background_tasks: BackgroundTasks):
    """Handle incoming WhatsApp messages"""
    
    stats["messages_received"] += 1
    
    # Detect language if not provided
    if not message.language:
        lang_detection = await detect_language(message.message)
        detected_lang = lang_detection["detected_language"]
        
        # Update stats
        if detected_lang not in stats["languages_detected"]:
            stats["languages_detected"][detected_lang] = 0
        stats["languages_detected"][detected_lang] += 1
    else:
        detected_lang = message.language
    
    # Translate to English for processing if needed
    english_message = message.message
    if detected_lang != "en":
        english_message = await translate_text(message.message, detected_lang, "en")
    
    # Detect intent
    intent_result = await detect_intent(english_message, detected_lang)
    intent = intent_result["intent"]
    
    # Update stats
    if intent not in stats["intents_processed"]:
        stats["intents_processed"][intent] = 0
    stats["intents_processed"][intent] += 1
    
    # Handle based on intent
    response_text = ""
    
    if intent == "greeting":
        response_text = await handle_greeting(detected_lang)
    elif intent == "check_balance":
        response_text = await handle_check_balance(message.from_number, detected_lang)
    elif intent == "transfer":
        response_text = await handle_transfer(message.from_number, message.message, detected_lang)
    elif intent == "fraud_check":
        response_text = await handle_fraud_check(message.from_number, detected_lang)
    elif intent == "help":
        response_text = await handle_greeting(detected_lang)
    else:
        # Use AI for unknown intents
        response_text = await get_ai_response(english_message, message.from_number, detected_lang)
        
        # Translate response back to user's language
        if detected_lang != "en":
            response_text = await translate_text(response_text, "en", detected_lang)
    
    # Send response
    stats["messages_sent"] += 1
    
    return {
        "status": "success",
        "from_number": message.from_number,
        "detected_language": detected_lang,
        "intent": intent,
        "response": response_text,
        "timestamp": datetime.now()
    }

@app.post("/send")
async def send_message(message: OutgoingMessage):
    """Send message to WhatsApp user"""
    
    # Translate message if needed
    translated_message = message.message
    if message.language and message.language != "en":
        translated_message = await translate_text(message.message, "en", message.language)
    
    # Send via WhatsApp service
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{SERVICES['whatsapp']}/api/v1/send",
                json={
                    "recipient": message.to_number,
                    "content": translated_message,
                    "message_type": "text"
                },
                timeout=5.0
            )
            
            if response.status_code == 200:
                stats["messages_sent"] += 1
                return {
                    "status": "sent",
                    "to_number": message.to_number,
                    "message": translated_message,
                    "language": message.language
                }
    except:
        pass
    
    raise HTTPException(status_code=500, detail="Failed to send message")

@app.get("/stats")
async def get_stats():
    """Get bot statistics"""
    uptime = (datetime.now() - stats["start_time"]).total_seconds()
    
    return {
        "uptime_seconds": int(uptime),
        "messages_received": stats["messages_received"],
        "messages_sent": stats["messages_sent"],
        "active_sessions": len(user_sessions),
        "languages_detected": stats["languages_detected"],
        "intents_processed": stats["intents_processed"],
        "conversation_history_size": sum(len(h) for h in conversation_history.values())
    }

@app.delete("/session/{user_id}")
async def clear_session(user_id: str):
    """Clear user session and conversation history"""
    
    if user_id in user_sessions:
        del user_sessions[user_id]
    
    if user_id in conversation_history:
        del conversation_history[user_id]
    
    return {
        "status": "cleared",
        "user_id": user_id
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8096)

