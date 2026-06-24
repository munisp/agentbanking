import os
import sys as _sys, os as _os

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

# --- PostgreSQL Persistence ---
import asyncpg
from typing import Optional

_pg_pool: Optional[asyncpg.Pool] = None

async def get_pg_pool() -> Optional[asyncpg.Pool]:
    global _pg_pool
    if _pg_pool is None:
        try:
            _pg_pool = await asyncpg.create_pool(
                dsn=os.environ.get("DATABASE_URL", "postgresql://localhost:5432/agentbanking"),
                min_size=2, max_size=10, command_timeout=10
            )
            await _pg_pool.execute("""
                CREATE TABLE IF NOT EXISTS service_state (
                    key TEXT PRIMARY KEY,
                    value JSONB NOT NULL DEFAULT '{}',
                    service TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        except Exception:
            _pg_pool = None
    return _pg_pool

async def pg_get(key: str, service: str):
    pool = await get_pg_pool()
    if pool:
        row = await pool.fetchrow(
            "SELECT value FROM service_state WHERE key = $1 AND service = $2", key, service
        )
        return row["value"] if row else None
    return None

async def pg_set(key: str, value, service: str):
    pool = await get_pg_pool()
    if pool:
        import json
        await pool.execute(
            "INSERT INTO service_state (key, value, service, updated_at) VALUES ($1, $2::jsonb, $3, NOW()) "
            "ON CONFLICT (key) DO UPDATE SET value = $2::jsonb, updated_at = NOW()",
            key, json.dumps(value) if not isinstance(value, str) else value, service
        )
# --- End PostgreSQL Persistence ---


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
Multi-lingual Translation Service
Focused on Nigerian languages: Yoruba, Igbo, Hausa, Pidgin, and English
Production-ready with AI-powered translation
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app, enable_auth=True)
setup_logging("translation-service")
app.include_router(metrics_router)

from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import uvicorn
import httpx

app = FastAPI(

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/translation_service")

@app.on_event("startup")
async def _init_pg_pool():
    await get_pg_pool()


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
        conn.execute("INSERT INTO audit_log (action, entity_id, data) VALUES (%s, %s, %s)", (action, entity_id, data))
        conn.commit()
        conn.close()
    except Exception:
        pass
    title="Translation Service",
    description="Multi-lingual translation for Nigerian languages",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS","http://localhost:5173,http://localhost:5174,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supported languages
SUPPORTED_LANGUAGES = {
    "en": "English",
    "yo": "Yoruba",
    "ig": "Igbo",
    "ha": "Hausa",
    "pcm": "Nigerian Pidgin"
}

# Common banking phrases in Nigerian languages
BANKING_PHRASES = {
    # Account balance
    "check_balance": {
        "en": "What is my account balance?",
        "yo": "Kini iye owo mi to wa ninu account mi?",
        "ig": "Kedu ego m nwere n'akaụntụ m?",
        "ha": "Nawa ne kudin da ke cikin asusuna?",
        "pcm": "How much money dey for my account?"
    },
    # Transfer money
    "transfer": {
        "en": "I want to transfer money",
        "yo": "Mo fe fi owo ranṣẹ",
        "ig": "Achọrọ m izipu ego",
        "ha": "Ina son in tura kudi",
        "pcm": "I wan send money"
    },
    # Transaction history
    "history": {
        "en": "Show my transaction history",
        "yo": "Fi itan iṣowo mi han mi",
        "ig": "Gosi m akụkọ azụmahịa m",
        "ha": "Nuna min tarihin ciniki na",
        "pcm": "Show me my transaction history"
    },
    # Fraud alert
    "fraud_alert": {
        "en": "Fraud alert! Suspicious transaction detected",
        "yo": "Ikilọ jibiti! A rii iṣowo ti o jẹ afurasi",
        "ig": "Ọkwa aghụghọ! Achọpụtala azụmahịa na-enyo enyo",
        "ha": "Faɗakarwa na zamba! An gano ciniki mai shakka",
        "pcm": "Fraud alert! We see suspicious transaction"
    },
    # Account locked
    "account_locked": {
        "en": "Your account has been locked for security",
        "yo": "A ti tii account rẹ fun aabo",
        "ig": "E mechiri akaụntụ gị maka nchekwa",
        "ha": "An kulle asusun ku don tsaro",
        "pcm": "We don lock your account for security"
    },
    # Welcome message
    "welcome": {
        "en": "Welcome to Remittance Platform! How can I help you today?",
        "yo": "Ẹ ku abọ si Remittance Platform! Bawo ni mo ṣe le ran ọ lọwọ loni?",
        "ig": "Nnọọ na Remittance Platform! Kedu ka m ga-esi nyere gị aka taa?",
        "ha": "Barka da zuwa Remittance Platform! Ta yaya zan iya taimaka muku yau?",
        "pcm": "Welcome to Remittance Platform! How I fit help you today?"
    },
    # Successful transaction
    "success": {
        "en": "Transaction successful!",
        "yo": "Iṣowo ṣaṣeyọri!",
        "ig": "Azụmahịa gara nke ọma!",
        "ha": "Ciniki ya yi nasara!",
        "pcm": "Transaction don successful!"
    },
    # Failed transaction
    "failed": {
        "en": "Transaction failed. Please try again.",
        "yo": "Iṣowo kuna. Jọwọ gbiyanju lẹẹkansi.",
        "ig": "Azụmahịa dara. Biko nwaa ọzọ.",
        "ha": "Ciniki ya kasa. Don Allah sake gwadawa.",
        "pcm": "Transaction no work. Abeg try again."
    },
    # Insufficient funds
    "insufficient_funds": {
        "en": "Insufficient funds in your account",
        "yo": "Owo ti o wa ninu account rẹ ko to",
        "ig": "Ego adịghị n'akaụntụ gị",
        "ha": "Kuɗin da ke cikin asusun ku bai isa ba",
        "pcm": "Money wey dey your account no reach"
    },
    # Help
    "help": {
        "en": "Type 'balance' to check balance, 'transfer' to send money, 'history' for transactions",
        "yo": "Tẹ 'balance' lati ṣayẹwo iye owo, 'transfer' lati fi owo ranṣẹ, 'history' fun awọn iṣowo",
        "ig": "Pịnye 'balance' iji lelee ego, 'transfer' izipu ego, 'history' maka azụmahịa",
        "ha": "Rubuta 'balance' don duba kuɗi, 'transfer' don tura kuɗi, 'history' don ganin ciniki",
        "pcm": "Type 'balance' to check money, 'transfer' to send money, 'history' for transactions"
    }
}

# Common words/phrases dictionary
COMMON_WORDS = {
    "yes": {"en": "yes", "yo": "bẹẹni", "ig": "ee", "ha": "i", "pcm": "yes"},
    "no": {"en": "no", "yo": "rara", "ig": "mba", "ha": "a'a", "pcm": "no"},
    "thank_you": {"en": "thank you", "yo": "e ṣeun", "ig": "daalụ", "ha": "na gode", "pcm": "thank you"},
    "please": {"en": "please", "yo": "jọwọ", "ig": "biko", "ha": "don allah", "pcm": "abeg"},
    "money": {"en": "money", "yo": "owo", "ig": "ego", "ha": "kuɗi", "pcm": "money"},
    "account": {"en": "account", "yo": "account", "ig": "akaụntụ", "ha": "asusun", "pcm": "account"},
    "bank": {"en": "bank", "yo": "ile-ifowopamọ", "ig": "ụlọ akụ", "ha": "banki", "pcm": "bank"},
    "agent": {"en": "agent", "yo": "aṣoju", "ig": "onye nnọchiteanya", "ha": "wakili", "pcm": "agent"},
}

# Models
class TranslationRequest(BaseModel):
    text: str
    source_language: str
    target_language: str
    context: Optional[str] = "general"  # banking, general, fraud, etc.

class DetectLanguageRequest(BaseModel):
    text: str

class BatchTranslationRequest(BaseModel):
    texts: List[str]
    source_language: str
    target_language: str

# Statistics
stats = {
    "translations": 0,
    "detections": 0,
    "start_time": datetime.now()
}

@app.get("/")
async def root():
    return {
        "service": "translation-service",
        "version": "1.0.0",
        "supported_languages": SUPPORTED_LANGUAGES,
        "status": "operational"
    }

@app.get("/health")
async def health_check():
    uptime = (datetime.now() - stats["start_time"]).total_seconds()
    return {
        "status": "healthy",
        "uptime_seconds": int(uptime),
        "translations": stats["translations"],
        "detections": stats["detections"]
    }

@app.get("/languages")
async def get_languages():
    """Get list of supported languages"""
    return {
        "supported_languages": SUPPORTED_LANGUAGES,
        "total": len(SUPPORTED_LANGUAGES)
    }

@app.post("/translate")
async def translate(request: TranslationRequest):
    """Translate text between supported languages"""
    
    # Validate languages
    if request.source_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Unsupported source language: {request.source_language}")
    
    if request.target_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Unsupported target language: {request.target_language}")
    
    # Check if it's a banking phrase
    text_lower = request.text.lower().strip()
    
    # Try to find matching banking phrase
    for phrase_key, translations in BANKING_PHRASES.items():
        for lang, phrase in translations.items():
            if phrase.lower() == text_lower or text_lower in phrase.lower():
                # Found a match, return translation
                stats["translations"] += 1
                return {
                    "original_text": request.text,
                    "translated_text": translations[request.target_language],
                    "source_language": request.source_language,
                    "target_language": request.target_language,
                    "confidence": 0.95,
                    "method": "phrase_match",
                    "phrase_key": phrase_key
                }
    
    # Try word-by-word translation for common words
    words = text_lower.split()
    translated_words = []
    
    for word in words:
        found = False
        for word_key, translations in COMMON_WORDS.items():
            if word in translations.values() or word == word_key:
                translated_words.append(translations[request.target_language])
                found = True
                break
        if not found:
            # If word not found, keep original
            translated_words.append(word)
    
    translated_text = " ".join(translated_words)
    
    # If we couldn't translate anything meaningful, use Ollama for AI translation
    if translated_text.lower() == text_lower:
        # Call Ollama service for AI-powered translation
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:8092/chat",
                    json={
                        "model": "llama2",
                        "messages": [
                            {
                                "role": "system",
                                "content": f"You are a translator. Translate from {SUPPORTED_LANGUAGES[request.source_language]} to {SUPPORTED_LANGUAGES[request.target_language]}. Only provide the translation, no explanations."
                            },
                            {
                                "role": "user",
                                "content": request.text
                            }
                        ]
                    },
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    translated_text = result.get("response", translated_text)
                    method = "ai_translation"
                    confidence = 0.85
                else:
                    method = "word_match"
                    confidence = 0.60
        except:
            method = "word_match"
            confidence = 0.60
    else:
        method = "word_match"
        confidence = 0.75
    
    stats["translations"] += 1
    
    return {
        "original_text": request.text,
        "translated_text": translated_text,
        "source_language": request.source_language,
        "target_language": request.target_language,
        "confidence": confidence,
        "method": method
    }

@app.post("/detect")
async def detect_language(request: DetectLanguageRequest):
    """Detect the language of given text"""
    
    text_lower = request.text.lower().strip()
    
    # Check against known phrases
    language_scores = {lang: 0 for lang in SUPPORTED_LANGUAGES.keys()}
    
    # Check banking phrases
    for phrase_key, translations in BANKING_PHRASES.items():
        for lang, phrase in translations.items():
            if phrase.lower() in text_lower or text_lower in phrase.lower():
                language_scores[lang] += 10
    
    # Check common words
    words = text_lower.split()
    for word in words:
        for word_key, translations in COMMON_WORDS.items():
            for lang, translation in translations.items():
                if word == translation.lower():
                    language_scores[lang] += 1
    
    # Find language with highest score
    detected_language = max(language_scores, key=language_scores.get)
    confidence = min(language_scores[detected_language] / 10.0, 1.0)
    
    # If confidence is too low, default to English
    if confidence < 0.3:
        detected_language = "en"
        confidence = 0.5
    
    stats["detections"] += 1
    
    return {
        "text": request.text,
        "detected_language": detected_language,
        "language_name": SUPPORTED_LANGUAGES[detected_language],
        "confidence": confidence,
        "all_scores": {
            SUPPORTED_LANGUAGES[lang]: score 
            for lang, score in language_scores.items()
        }
    }

@app.post("/batch-translate")
async def batch_translate(request: BatchTranslationRequest):
    """Translate multiple texts at once"""
    
    results = []
    
    for text in request.texts:
        translation_request = TranslationRequest(
            text=text,
            source_language=request.source_language,
            target_language=request.target_language
        )
        
        result = await translate(translation_request)
        results.append(result)
    
    return {
        "translations": results,
        "total": len(results),
        "source_language": request.source_language,
        "target_language": request.target_language
    }

@app.get("/phrases/{category}")
async def get_phrases(category: str):
    """Get all phrases for a specific category"""
    
    if category == "all":
        return {
            "phrases": BANKING_PHRASES,
            "total": len(BANKING_PHRASES)
        }
    
    if category in BANKING_PHRASES:
        return {
            "category": category,
            "translations": BANKING_PHRASES[category]
        }
    
    raise HTTPException(status_code=404, detail=f"Category not found: {category}")

@app.get("/stats")
async def get_stats():
    """Get service statistics"""
    uptime = (datetime.now() - stats["start_time"]).total_seconds()
    
    return {
        "uptime_seconds": int(uptime),
        "total_translations": stats["translations"],
        "total_detections": stats["detections"],
        "supported_languages": len(SUPPORTED_LANGUAGES),
        "banking_phrases": len(BANKING_PHRASES),
        "common_words": len(COMMON_WORDS)
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8095)

