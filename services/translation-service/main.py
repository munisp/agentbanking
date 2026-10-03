import sys as _sys, os as _os

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

# ── Round-11 persistence fix (wave-6: asyncpg) ────────────────────────────
# Process-memory containers replaced by Postgres-backed stores so business
# data survives restarts. Wave-6 upgrade: all DB I/O now runs on asyncpg via
# a dedicated background event loop, so async FastAPI handlers no longer
# block the main loop on sync SQLAlchemy calls. Same dict/list-compatible
# public API; {ENV}_DATABASE_URL convention unchanged.
import os as _r11_os
import json as _r11_json
import asyncio as _r11_asyncio
import threading as _r11_threading
import asyncpg as _r11_apg

_r11_loop = _r11_asyncio.new_event_loop()


def _r11_loop_main(loop):
    _r11_asyncio.set_event_loop(loop)
    loop.run_forever()


_r11_threading.Thread(
    target=_r11_loop_main, args=(_r11_loop,), daemon=True, name="r11-pg-io"
).start()


def _r11_sync(coro):
    """Run an asyncpg coroutine on the dedicated loop and wait for it."""
    return _r11_asyncio.run_coroutine_threadsafe(coro, _r11_loop).result()


class _PgDictStore:
    """Dict-compatible store persisted to Postgres (replaces in-memory dict)."""

    def __init__(self, table, env, model_name=None):
        if not table.replace("_", "").isalnum():
            raise ValueError("unsafe table name: %r" % table)
        self._model_name = model_name
        self._table = table
        url = _r11_os.getenv(
            env, "postgresql://postgres:postgres@localhost:5432/platform"
        )
        self._pool = _r11_sync(_r11_apg.create_pool(url, min_size=1, max_size=10))
        _r11_sync(self._ensure())

    async def _ensure(self):
        async with self._pool.acquire() as c:
            await c.execute(
                'CREATE TABLE IF NOT EXISTS "%s" ('
                "key VARCHAR(128) PRIMARY KEY, "
                "data TEXT NOT NULL, "
                "updated_at TIMESTAMPTZ NOT NULL DEFAULT now()"
                ")" % self._table
            )

    @staticmethod
    def _ser(v):
        def _cv(x):
            if hasattr(x, "model_dump"):
                return x.model_dump()
            if hasattr(x, "dict") and callable(x.dict):
                return x.dict()
            return x
        if isinstance(v, list):
            v = [_cv(x) for x in v]
        else:
            v = _cv(v)
        return _r11_json.dumps(v, default=str)

    def _deser(self, raw):
        d = _r11_json.loads(raw)
        if self._model_name:
            cls = globals().get(self._model_name)
            if cls is not None:
                if isinstance(d, list):
                    return [cls(**x) if isinstance(x, dict) else x for x in d]
                return cls(**d)
        return d

    async def _aset(self, k, payload):
        async with self._pool.acquire() as c:
            await c.execute(
                'INSERT INTO "%s" (key, data) VALUES ($1, $2) '
                "ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data, "
                "updated_at = now()" % self._table,
                str(k), payload,
            )

    def __setitem__(self, k, v):
        _r11_sync(self._aset(k, self._ser(v)))

    async def _aget(self, k):
        async with self._pool.acquire() as c:
            return await c.fetchval(
                'SELECT data FROM "%s" WHERE key = $1' % self._table, str(k)
            )

    def __getitem__(self, k):
        raw = _r11_sync(self._aget(k))
        if raw is None:
            raise KeyError(k)
        return self._deser(raw)

    def get(self, k, default=None):
        try:
            return self[k]
        except KeyError:
            return default

    async def _adel(self, k):
        async with self._pool.acquire() as c:
            return await c.execute(
                'DELETE FROM "%s" WHERE key = $1' % self._table, str(k)
            )

    def __delitem__(self, k):
        res = _r11_sync(self._adel(k))
        if res == "DELETE 0":
            raise KeyError(k)

    def __contains__(self, k):
        return _r11_sync(self._aget(k)) is not None

    def setdefault(self, k, default=None):
        try:
            return self[k]
        except KeyError:
            self[k] = default
            return default

    async def _aall(self):
        async with self._pool.acquire() as c:
            return await c.fetch('SELECT key, data FROM "%s"' % self._table)

    def _all(self):
        return _r11_sync(self._aall())

    def values(self):
        return [self._deser(r["data"]) for r in self._all()]

    def keys(self):
        return [r["key"] for r in self._all()]

    def items(self):
        return [(r["key"], self._deser(r["data"])) for r in self._all()]

    def __len__(self):
        async def _n():
            async with self._pool.acquire() as c:
                return await c.fetchval('SELECT COUNT(*) FROM "%s"' % self._table)
        return _r11_sync(_n())

    def pop(self, k, default=None):
        try:
            v = self[k]
            del self[k]
            return v
        except KeyError:
            return default

    def clear(self):
        async def _c():
            async with self._pool.acquire() as c:
                await c.execute('DELETE FROM "%s"' % self._table)
        _r11_sync(_c())


class _PgListStore:
    """List-compatible store persisted to Postgres (replaces in-memory list)."""

    def __init__(self, table, env):
        if not table.replace("_", "").isalnum():
            raise ValueError("unsafe table name: %r" % table)
        self._table = table
        url = _r11_os.getenv(
            env, "postgresql://postgres:postgres@localhost:5432/platform"
        )
        self._pool = _r11_sync(_r11_apg.create_pool(url, min_size=1, max_size=10))
        _r11_sync(self._ensure())

    async def _ensure(self):
        async with self._pool.acquire() as c:
            await c.execute(
                'CREATE TABLE IF NOT EXISTS "%s" ('
                "id SERIAL PRIMARY KEY, "
                "data TEXT NOT NULL, "
                "created_at TIMESTAMPTZ NOT NULL DEFAULT now()"
                ")" % self._table
            )

    @staticmethod
    def _ser(v):
        def _cv(x):
            if hasattr(x, "model_dump"):
                return x.model_dump()
            if hasattr(x, "dict") and callable(x.dict):
                return x.dict()
            return x
        return _r11_json.dumps(_cv(v), default=str)

    @staticmethod
    def _deser(raw):
        return _r11_json.loads(raw)

    def append(self, v):
        async def _a():
            async with self._pool.acquire() as c:
                await c.execute(
                    'INSERT INTO "%s" (data) VALUES ($1)' % self._table,
                    self._ser(v),
                )
        _r11_sync(_a())

    async def _arows(self):
        async with self._pool.acquire() as c:
            return await c.fetch(
                'SELECT id, data FROM "%s" ORDER BY id' % self._table
            )

    def _rows(self):
        return _r11_sync(self._arows())

    def __iter__(self):
        return iter([self._deser(r["data"]) for r in self._rows()])

    def __len__(self):
        async def _n():
            async with self._pool.acquire() as c:
                return await c.fetchval('SELECT COUNT(*) FROM "%s"' % self._table)
        return _r11_sync(_n())

    def __getitem__(self, idx):
        vals = [self._deser(r["data"]) for r in self._rows()]
        return vals[idx]

    def __delitem__(self, idx):
        rows = self._rows()
        targets = rows[idx] if isinstance(idx, slice) else [rows[idx]]
        ids = [r["id"] for r in targets]
        if not ids:
            return
        async def _d():
            async with self._pool.acquire() as c:
                await c.execute(
                    'DELETE FROM "%s" WHERE id = ANY($1::int[])' % self._table, ids
                )
        _r11_sync(_d())

    def clear(self):
        async def _c():
            async with self._pool.acquire() as c:
                await c.execute('DELETE FROM "%s"' % self._table)
        _r11_sync(_c())

_shutdown_handlers = []  # function registry — must stay in-process (wave-8 revert of wave-7 overreach)  # round-11 wave-7 persistence

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


from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import uvicorn
import httpx
import os

app = FastAPI(
    title="Translation Service",
    description="Multi-lingual translation for Nigerian languages",
    version="1.0.0"
)

apply_middleware(app)
setup_logging("translation-service")
app.include_router(metrics_router)

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

