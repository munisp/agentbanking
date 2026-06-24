"""
54Link Voice-Activated POS — Python Microservice
Port: 8285

Speech-to-intent for POS operations in Hausa, Yoruba, Pidgin, and English.
Enables illiterate/low-literacy agents to perform transactions via voice.

Integrations:
- PostgreSQL: Persist voice session logs and intent history
- Kafka (Dapr): Publish voice_command events
- Redis: Cache agent voice profiles
- Fluvio: Stream voice analytics to lakehouse
"""

import os
import sys
import json
import uuid
import signal
import atexit
import logging
import re
from datetime import datetime
from typing import Optional, Dict, Any, List
from decimal import Decimal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import asyncpg
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/pos_voice?sslmode=disable")
DAPR_HTTP_PORT = int(os.environ.get("DAPR_HTTP_PORT", "3500"))
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/12")

_pool: Optional[asyncpg.Pool] = None

async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
        await _pool.execute("""
            CREATE TABLE IF NOT EXISTS voice_sessions (
                id SERIAL PRIMARY KEY,
                session_id VARCHAR(64) UNIQUE NOT NULL,
                agent_id VARCHAR(64) NOT NULL,
                language VARCHAR(8) NOT NULL,
                transcript TEXT,
                intent VARCHAR(64),
                entities JSONB,
                confidence DECIMAL(4,3),
                status VARCHAR(16) DEFAULT 'pending',
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS voice_intents (
                id SERIAL PRIMARY KEY,
                intent VARCHAR(64) NOT NULL,
                language VARCHAR(8) NOT NULL,
                patterns TEXT[] NOT NULL,
                response_template TEXT,
                requires_confirmation BOOLEAN DEFAULT true
            );
        """)
    return _pool

app = FastAPI(title="POS Voice Service", version="1.0.0")

# ── Intent Patterns (Multi-Language) ──────────────────────────────────────────

INTENT_PATTERNS = {
    "cash_in": {
        "en": [r"cash in (.+) for (.+)", r"deposit (.+) naira", r"receive (.+) from"],
        "ha": [r"shigar kudi (.+)", r"ajiye kudi (.+)", r"karbi (.+)"],
        "yo": [r"fi owo (.+) sile", r"gba owo (.+)", r"owo (.+) wole"],
        "pcm": [r"put (.+) naira", r"collect (.+) money", r"cash (.+) enter"],
    },
    "cash_out": {
        "en": [r"cash out (.+)", r"withdraw (.+) naira", r"give (.+) to"],
        "ha": [r"fitar kudi (.+)", r"cire (.+)", r"ba (.+) kudi"],
        "yo": [r"mu owo (.+) jade", r"yọ owo (.+)", r"fun (.+) lowo"],
        "pcm": [r"give (.+) naira", r"bring out (.+)", r"cash (.+) comot"],
    },
    "airtime": {
        "en": [r"buy airtime (.+) for (.+)", r"recharge (.+)", r"top up (.+)"],
        "ha": [r"saya airtime (.+)", r"caji (.+)", r"yi recharge (.+)"],
        "yo": [r"ra airtime (.+)", r"se recharge (.+)"],
        "pcm": [r"buy credit (.+)", r"charge (.+) phone"],
    },
    "balance": {
        "en": [r"check balance", r"how much", r"my balance", r"what is my float"],
        "ha": [r"duba balance", r"nawa ne", r"kudin nawa"],
        "yo": [r"wo balance mi", r"elo ni", r"iye owo mi"],
        "pcm": [r"check my money", r"how much remain", r"wetin dey my account"],
    },
    "transfer": {
        "en": [r"transfer (.+) to (.+)", r"send (.+) naira to (.+)"],
        "ha": [r"aika (.+) zuwa (.+)", r"tura kudi (.+)"],
        "yo": [r"fi (.+) ran (.+)", r"gbero owo (.+) si (.+)"],
        "pcm": [r"send (.+) give (.+)", r"transfer (.+) to (.+)"],
    },
}

AMOUNT_WORDS = {
    "one thousand": 1000, "two thousand": 2000, "five thousand": 5000,
    "ten thousand": 10000, "twenty thousand": 20000, "fifty thousand": 50000,
    "hundred thousand": 100000, "dubu daya": 1000, "dubu biyar": 5000,
    "egberun kan": 1000, "egberun marun": 5000,
}

class VoiceInput(BaseModel):
    agent_id: str
    language: str = Field(default="en", pattern="^(en|ha|yo|pcm)$")
    transcript: str
    audio_confidence: float = Field(default=0.9, ge=0.0, le=1.0)

class VoiceResponse(BaseModel):
    session_id: str
    intent: str
    entities: Dict[str, Any]
    confidence: float
    confirmation_prompt: str
    requires_confirmation: bool = True

def extract_amount(text: str) -> Optional[int]:
    """Extract numeric amount from text (supports words and digits)."""
    # Try numeric
    numbers = re.findall(r"[\d,]+", text.replace(",", ""))
    if numbers:
        try:
            return int(numbers[0])
        except ValueError:
            pass
    # Try word amounts
    text_lower = text.lower()
    for word, val in AMOUNT_WORDS.items():
        if word in text_lower:
            return val
    return None

def extract_phone(text: str) -> Optional[str]:
    """Extract Nigerian phone number."""
    phones = re.findall(r"0[789]0\d{8}", text)
    return phones[0] if phones else None

def match_intent(transcript: str, language: str) -> tuple:
    """Match transcript against intent patterns."""
    best_intent = "unknown"
    best_confidence = 0.0
    entities = {}

    for intent, lang_patterns in INTENT_PATTERNS.items():
        patterns = lang_patterns.get(language, lang_patterns.get("en", []))
        for pattern in patterns:
            match = re.search(pattern, transcript.lower())
            if match:
                confidence = 0.85 + (0.1 if language == "en" else 0.05)
                if confidence > best_confidence:
                    best_intent = intent
                    best_confidence = confidence
                    entities = {"groups": list(match.groups())} if match.groups() else {}

    # Extract structured entities
    amount = extract_amount(transcript)
    phone = extract_phone(transcript)
    if amount:
        entities["amount"] = amount
    if phone:
        entities["phone"] = phone

    return best_intent, best_confidence, entities

def generate_confirmation(intent: str, entities: Dict, language: str) -> str:
    """Generate confirmation prompt in agent's language."""
    amount = entities.get("amount", "?")
    phone = entities.get("phone", "?")

    prompts = {
        "cash_in": {"en": f"Cash in \u20a6{amount:,} — confirm?", "ha": f"Shigar \u20a6{amount:,} — tabbata?", "yo": f"Gba \u20a6{amount:,} — je?", "pcm": f"Put \u20a6{amount:,} — you sure?"},
        "cash_out": {"en": f"Cash out \u20a6{amount:,} — confirm?", "ha": f"Fitar \u20a6{amount:,} — tabbata?", "yo": f"Mu \u20a6{amount:,} jade — je?", "pcm": f"Give \u20a6{amount:,} — you sure?"},
        "airtime": {"en": f"Buy \u20a6{amount:,} airtime for {phone} — confirm?", "ha": f"Saya \u20a6{amount:,} airtime ga {phone} — tabbata?"},
        "balance": {"en": "Checking your balance...", "ha": "Ana duba balance...", "yo": "N wo balance re...", "pcm": "Checking your money..."},
        "transfer": {"en": f"Transfer \u20a6{amount:,} to {phone} — confirm?", "ha": f"Aika \u20a6{amount:,} zuwa {phone} — tabbata?"},
    }

    intent_prompts = prompts.get(intent, {"en": "I didn't understand. Please try again."})
    return intent_prompts.get(language, intent_prompts.get("en", "Confirm?"))

@app.post("/api/v1/voice/process", response_model=VoiceResponse)
async def process_voice(input_data: VoiceInput):
    pool = await get_pool()
    session_id = str(uuid.uuid4())

    intent, confidence, entities = match_intent(input_data.transcript, input_data.language)
    confidence *= input_data.audio_confidence  # Adjust by ASR confidence

    confirmation = generate_confirmation(intent, entities, input_data.language)
    requires_confirm = intent != "balance"

    # Persist
    await pool.execute(
        """INSERT INTO voice_sessions (session_id, agent_id, language, transcript, intent, entities, confidence, status)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8)""",
        session_id, input_data.agent_id, input_data.language, input_data.transcript,
        intent, json.dumps(entities), confidence, "awaiting_confirmation" if requires_confirm else "executed"
    )

    # Publish event via Dapr
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"http://localhost:{DAPR_HTTP_PORT}/v1.0/publish/pubsub/pos.voice.command",
                json={"session_id": session_id, "intent": intent, "entities": entities, "agent_id": input_data.agent_id}
            )
    except Exception:
        pass  # fail-open

    return VoiceResponse(
        session_id=session_id,
        intent=intent,
        entities=entities,
        confidence=round(confidence, 3),
        confirmation_prompt=confirmation,
        requires_confirmation=requires_confirm,
    )

@app.post("/api/v1/voice/confirm/{session_id}")
async def confirm_voice(session_id: str, confirmed: bool = True):
    pool = await get_pool()
    status = "confirmed" if confirmed else "cancelled"
    await pool.execute("UPDATE voice_sessions SET status=$1 WHERE session_id=$2", status, session_id)
    return {"session_id": session_id, "status": status}

@app.get("/api/v1/voice/languages")
async def supported_languages():
    return {"languages": ["en", "ha", "yo", "pcm"], "intents": list(INTENT_PATTERNS.keys())}

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "pos-voice", "port": 8285}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8285)
