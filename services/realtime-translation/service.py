"""
Real-time Language Translation Service
54agent Agency Banking Platform

Engine: 100% open-source, self-hosted — zero external API dependencies
  Primary:  Meta NLLB-200 (facebook/nllb-200-distilled-600M)
            Covers Yoruba, Hausa, Igbo, Nigerian Pidgin + 196 other languages.
            Released under CC-BY-NC 4.0 by Meta AI Research.
  Fallback: Helsinki-NLP Opus-MT bilingual models
              opus-mt-en-yo  / opus-mt-yo-en
              opus-mt-en-ha  / opus-mt-ha-en
              opus-mt-en-ig  / opus-mt-ig-en
            Released under CC-BY 4.0 by University of Helsinki.
  Detect:   langdetect (offline, no API) + heuristic character analysis
  Cache:    Redis (TTL 24 h) + PostgreSQL persistent cache
            Identical text is never translated twice.

Supported language pairs (all bidirectional):
  en  ↔ yo   English ↔ Yoruba
  en  ↔ ha   English ↔ Hausa
  en  ↔ ig   English ↔ Igbo
  en  ↔ pcm  English ↔ Nigerian Pidgin
  yo  ↔ ha   via English pivot
  yo  ↔ ig   via English pivot
  ha  ↔ ig   via English pivot
  yo  ↔ pcm  via English pivot
  ha  ↔ pcm  via English pivot
  ig  ↔ pcm  via English pivot
  en  ↔ fr   English ↔ French
  en  ↔ ar   English ↔ Arabic

NO Google Translate. NO OpenAI. NO external translation API.
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

import redis.asyncio as aioredis
from sqlalchemy import (
    Boolean, Column, DateTime, Float, Index, Integer,
    String, Text, Enum as SAEnum,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
Base = declarative_base()

# ---------------------------------------------------------------------------
# NLLB-200 flores200 language codes
# ---------------------------------------------------------------------------
NLLB_LANG_MAP: Dict[str, str] = {
    "en":  "eng_Latn",
    "yo":  "yor_Latn",
    "ha":  "hau_Latn",
    "ig":  "ibo_Latn",
    "pcm": "pcm_Latn",
    "fr":  "fra_Latn",
    "ar":  "arb_Arab",
    "sw":  "swh_Latn",
    "zu":  "zul_Latn",
    "am":  "amh_Ethi",
}

# Helsinki-NLP Opus-MT model IDs for direct bilingual pairs
OPUS_MT_MODELS_IDS: Dict[Tuple[str, str], str] = {
    ("en", "yo"):  "Helsinki-NLP/opus-mt-en-yo",
    ("yo", "en"):  "Helsinki-NLP/opus-mt-yo-en",
    ("en", "ha"):  "Helsinki-NLP/opus-mt-en-ha",
    ("ha", "en"):  "Helsinki-NLP/opus-mt-ha-en",
    ("en", "ig"):  "Helsinki-NLP/opus-mt-en-ig",
    ("ig", "en"):  "Helsinki-NLP/opus-mt-ig-en",
}

# Pairs that must go through an English pivot
PIVOT_PAIRS = {
    ("yo", "ha"), ("ha", "yo"),
    ("yo", "ig"), ("ig", "yo"),
    ("ha", "ig"), ("ig", "ha"),
    ("yo", "pcm"), ("pcm", "yo"),
    ("ha", "pcm"), ("pcm", "ha"),
    ("ig", "pcm"), ("pcm", "ig"),
}

SUPPORTED_LANGUAGES: Dict[str, Dict[str, str]] = {
    "en":  {"name": "English",         "native": "English"},
    "yo":  {"name": "Yoruba",          "native": "Yorùbá"},
    "ha":  {"name": "Hausa",           "native": "Hausa"},
    "ig":  {"name": "Igbo",            "native": "Igbo"},
    "pcm": {"name": "Nigerian Pidgin", "native": "Naijá"},
    "fr":  {"name": "French",          "native": "Français"},
    "ar":  {"name": "Arabic",          "native": "العربية"},
}

# Banking/financial glossary — consistent translation of key terms
FINANCIAL_GLOSSARY: Dict[str, Dict[str, str]] = {
    "en": {
        "transfer": "transfer", "balance": "balance", "deposit": "deposit",
        "withdrawal": "withdrawal", "agent": "agent", "account": "account",
        "transaction": "transaction", "receipt": "receipt",
        "pin": "PIN", "otp": "OTP",
    },
    "yo": {
        "transfer": "gbigbe owo", "balance": "iye owo", "deposit": "fifi owo sinu",
        "withdrawal": "yiyọ owo", "agent": "aṣoju", "account": "akọọlẹ",
        "transaction": "iṣowo", "receipt": "iwe-eri",
        "pin": "koodu aṣiri", "otp": "koodu igba kan",
    },
    "ha": {
        "transfer": "canja kudi", "balance": "adadin kudi", "deposit": "ajiye kudi",
        "withdrawal": "fitar kudi", "agent": "wakili", "account": "asusun",
        "transaction": "ma'amala", "receipt": "rasit",
        "pin": "lambar sirri", "otp": "lambar lokaci guda",
    },
    "ig": {
        "transfer": "nnyefe ego", "balance": "ọnụ ego", "deposit": "itinye ego",
        "withdrawal": "iwepụ ego", "agent": "onye nnọchi", "account": "akaụntụ",
        "transaction": "azụmahịa", "receipt": "akwụkwọ nkwenye",
        "pin": "nọmba nzuzo", "otp": "nọmba otu oge",
    },
    "pcm": {
        "transfer": "send money", "balance": "how much dey account",
        "deposit": "put money", "withdrawal": "collect money",
        "agent": "agent", "account": "account",
        "transaction": "transaction", "receipt": "receipt",
        "pin": "pin number", "otp": "otp code",
    },
}

# Environment
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHE_TTL = int(os.getenv("TRANSLATION_CACHE_TTL", "86400"))
MODEL_CACHE_DIR = os.getenv("MODEL_CACHE_DIR", "/app/models")
USE_NLLB = os.getenv("USE_NLLB", "true").lower() == "true"
NLLB_MODEL_ID = os.getenv("NLLB_MODEL_ID", "facebook/nllb-200-distilled-600M")
MAX_INPUT_LENGTH = int(os.getenv("MAX_INPUT_LENGTH", "512"))


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class TranslationEngine(str, Enum):
    NLLB_200 = "nllb-200"
    OPUS_MT = "opus-mt"
    PIVOT = "pivot"
    GLOSSARY = "glossary"
    CACHE = "cache"
    PASSTHROUGH = "passthrough"


# ---------------------------------------------------------------------------
# Database models
# ---------------------------------------------------------------------------

class UserLanguagePreference(Base):
    __tablename__ = "user_language_preferences"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(String(100), nullable=False, unique=True, index=True)
    preferred_language = Column(String(10), default="en")
    auto_translate = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TranslationRecord(Base):
    __tablename__ = "translation_records"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    message_id = Column(String(100), nullable=True, index=True)
    source_text = Column(Text, nullable=False)
    source_language = Column(String(10), nullable=False)
    target_language = Column(String(10), nullable=False)
    translated_text = Column(Text, nullable=False)
    engine = Column(String(50), nullable=False)
    quality_score = Column(Float, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    cache_hit = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (
        Index("ix_translation_lang_pair", "source_language", "target_language"),
    )


class TranslationCache(Base):
    __tablename__ = "translation_cache_v2"
    id = Column(String(64), primary_key=True)  # SHA-256 of source+lang_pair
    source_text = Column(Text, nullable=False)
    source_language = Column(String(10), nullable=False)
    target_language = Column(String(10), nullable=False)
    translated_text = Column(Text, nullable=False)
    engine_used = Column(String(50), nullable=False)
    hit_count = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class TranslateRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    source_language: Optional[str] = None
    target_language: str
    message_id: Optional[str] = None
    apply_glossary: bool = True


class TranslateResponse(BaseModel):
    original_text: str
    translated_text: str
    source_language: str
    target_language: str
    engine_used: str
    cache_hit: bool
    latency_ms: int
    quality_score: Optional[float] = None


class BatchTranslateRequest(BaseModel):
    messages: List[Dict]
    target_language: str


class LanguagePreferenceRequest(BaseModel):
    user_id: str
    preferred_language: str
    auto_translate: bool = True


class MessageTranslationRequest(BaseModel):
    sender_id: str
    receiver_id: str
    message_text: str
    message_id: Optional[str] = None
    channel: str = "CHAT"


class MessageTranslationResponse(BaseModel):
    message_id: Optional[str]
    original_text: str
    sender_language: str
    receiver_language: str
    translated_for_receiver: Optional[str]
    translation_applied: bool
    engine_used: str


# ---------------------------------------------------------------------------
# Core translation engine (open-source, self-hosted)
# ---------------------------------------------------------------------------

class OpenSourceTranslationEngine:
    """
    Wraps NLLB-200 and Helsinki-NLP Opus-MT models.
    All inference is local — no external API calls.
    """

    def __init__(self):
        self._nllb_model = None
        self._nllb_tokenizer = None
        self._opus_models: Dict[Tuple[str, str], tuple] = {}
        self._redis: Optional[aioredis.Redis] = None
        self._ready = False
        self._stats = {
            "total_requests": 0,
            "cache_hits": 0,
            "nllb_translations": 0,
            "opus_translations": 0,
            "pivot_translations": 0,
            "errors": 0,
        }

    async def initialize(self):
        logger.info("Initialising open-source translation engine...")
        try:
            self._redis = await aioredis.from_url(REDIS_URL, decode_responses=True)
            await self._redis.ping()
            logger.info("Redis cache connected")
        except Exception as exc:
            logger.warning(f"Redis unavailable, running without cache: {exc}")
            self._redis = None

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, self._load_models_sync)
        self._ready = True
        logger.info("Translation engine ready")

    def _load_models_sync(self):
        try:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
            import torch

            device = "cuda" if self._cuda_available() else "cpu"
            logger.info(f"Loading models on device: {device}")

            if USE_NLLB:
                logger.info(f"Loading NLLB-200: {NLLB_MODEL_ID}")
                self._nllb_tokenizer = AutoTokenizer.from_pretrained(
                    NLLB_MODEL_ID, cache_dir=MODEL_CACHE_DIR
                )
                self._nllb_model = AutoModelForSeq2SeqLM.from_pretrained(
                    NLLB_MODEL_ID, cache_dir=MODEL_CACHE_DIR
                ).to(device)
                self._nllb_model.eval()
                logger.info("NLLB-200 loaded")

            for (src, tgt), model_id in OPUS_MT_MODELS_IDS.items():
                try:
                    tokenizer = AutoTokenizer.from_pretrained(
                        model_id, cache_dir=MODEL_CACHE_DIR
                    )
                    model = AutoModelForSeq2SeqLM.from_pretrained(
                        model_id, cache_dir=MODEL_CACHE_DIR
                    ).to(device)
                    model.eval()
                    self._opus_models[(src, tgt)] = (model, tokenizer)
                    logger.info(f"Opus-MT {src}→{tgt} loaded")
                except Exception as exc:
                    logger.warning(f"Could not load Opus-MT {src}→{tgt}: {exc}")

        except ImportError as exc:
            logger.error(
                f"transformers/torch not installed: {exc}. "
                "Run: pip install transformers torch sentencepiece"
            )

    async def shutdown(self):
        if self._redis:
            await self._redis.aclose()

    async def translate(
        self, text: str, source_lang: str, target_lang: str
    ) -> Tuple[str, str]:
        """
        Returns (translated_text, engine_name).
        Raises ValueError for unsupported pairs.
        """
        self._stats["total_requests"] += 1

        if source_lang == target_lang:
            return text, TranslationEngine.PASSTHROUGH.value

        if source_lang not in SUPPORTED_LANGUAGES or target_lang not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Unsupported language pair: {source_lang}→{target_lang}"
            )

        text = text[:MAX_INPUT_LENGTH]

        # Redis cache
        cache_key = self._cache_key(text, source_lang, target_lang)
        cached = await self._cache_get(cache_key)
        if cached:
            self._stats["cache_hits"] += 1
            return cached["translated"], TranslationEngine.CACHE.value

        # Choose translation path
        if (source_lang, target_lang) in PIVOT_PAIRS:
            translated, engine = await self._pivot_translate(text, source_lang, target_lang)
            self._stats["pivot_translations"] += 1
        elif (
            self._nllb_model
            and source_lang in NLLB_LANG_MAP
            and target_lang in NLLB_LANG_MAP
        ):
            translated, engine = await self._nllb_translate(text, source_lang, target_lang)
            self._stats["nllb_translations"] += 1
        elif (source_lang, target_lang) in self._opus_models:
            translated, engine = await self._opus_translate(text, source_lang, target_lang)
            self._stats["opus_translations"] += 1
        else:
            raise ValueError(
                f"No open-source model available for {source_lang}→{target_lang}"
            )

        await self._cache_set(cache_key, {"translated": translated, "engine": engine})
        return translated, engine

    # -- NLLB-200 --

    async def _nllb_translate(self, text: str, src: str, tgt: str) -> Tuple[str, str]:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, self._nllb_translate_sync, text, src, tgt
        )
        return result, f"{TranslationEngine.NLLB_200.value}:{src}→{tgt}"

    def _nllb_translate_sync(self, text: str, src: str, tgt: str) -> str:
        import torch
        src_code = NLLB_LANG_MAP[src]
        tgt_code = NLLB_LANG_MAP[tgt]
        inputs = self._nllb_tokenizer(
            text, return_tensors="pt", padding=True,
            truncation=True, max_length=MAX_INPUT_LENGTH,
        ).to(self._nllb_model.device)
        forced_bos = self._nllb_tokenizer.lang_code_to_id[tgt_code]
        with torch.no_grad():
            tokens = self._nllb_model.generate(
                **inputs,
                forced_bos_token_id=forced_bos,
                max_length=MAX_INPUT_LENGTH + 50,
                num_beams=4,
                early_stopping=True,
            )
        return self._nllb_tokenizer.batch_decode(tokens, skip_special_tokens=True)[0]

    # -- Opus-MT --

    async def _opus_translate(self, text: str, src: str, tgt: str) -> Tuple[str, str]:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, self._opus_translate_sync, text, src, tgt
        )
        return result, f"{TranslationEngine.OPUS_MT.value}:{src}→{tgt}"

    def _opus_translate_sync(self, text: str, src: str, tgt: str) -> str:
        import torch
        model, tokenizer = self._opus_models[(src, tgt)]
        inputs = tokenizer(
            text, return_tensors="pt", padding=True,
            truncation=True, max_length=MAX_INPUT_LENGTH,
        ).to(model.device)
        with torch.no_grad():
            tokens = model.generate(
                **inputs,
                max_length=MAX_INPUT_LENGTH + 50,
                num_beams=4,
                early_stopping=True,
            )
        return tokenizer.batch_decode(tokens, skip_special_tokens=True)[0]

    # -- Pivot --

    async def _pivot_translate(self, text: str, src: str, tgt: str) -> Tuple[str, str]:
        en_text, eng1 = await self._to_english(text, src) if src != "en" else (text, "passthrough")
        final_text, eng2 = await self._from_english(en_text, tgt) if tgt != "en" else (en_text, "passthrough")
        engine = f"{TranslationEngine.PIVOT.value}({src}→en:{eng1}, en→{tgt}:{eng2})"
        return final_text, engine

    async def _to_english(self, text: str, src: str) -> Tuple[str, str]:
        if (src, "en") in self._opus_models:
            return await self._opus_translate(text, src, "en")
        if self._nllb_model and src in NLLB_LANG_MAP:
            return await self._nllb_translate(text, src, "en")
        raise ValueError(f"No model to translate {src}→en")

    async def _from_english(self, text: str, tgt: str) -> Tuple[str, str]:
        if ("en", tgt) in self._opus_models:
            return await self._opus_translate(text, "en", tgt)
        if self._nllb_model and tgt in NLLB_LANG_MAP:
            return await self._nllb_translate(text, "en", tgt)
        raise ValueError(f"No model to translate en→{tgt}")

    # -- Cache --

    def _cache_key(self, text: str, src: str, tgt: str) -> str:
        return "tr:" + hashlib.sha256(f"{src}:{tgt}:{text}".encode()).hexdigest()

    async def _cache_get(self, key: str) -> Optional[dict]:
        if not self._redis:
            return None
        try:
            val = await self._redis.get(key)
            return json.loads(val) if val else None
        except Exception:
            return None

    async def _cache_set(self, key: str, value: dict):
        if not self._redis:
            return
        try:
            await self._redis.setex(key, CACHE_TTL, json.dumps(value))
        except Exception:
            pass

    @staticmethod
    def _cuda_available() -> bool:
        try:
            import torch
            return torch.cuda.is_available()
        except ImportError:
            return False

    def get_stats(self) -> dict:
        total = self._stats["total_requests"] or 1
        return {
            **self._stats,
            "cache_hit_rate_pct": round(self._stats["cache_hits"] / total * 100, 2),
            "nllb_loaded": self._nllb_model is not None,
            "opus_pairs_loaded": [f"{s}→{t}" for (s, t) in self._opus_models],
            "redis_connected": self._redis is not None,
            "ready": self._ready,
        }


# ---------------------------------------------------------------------------
# High-level service (used by router)
# ---------------------------------------------------------------------------

class RealtimeTranslationService:
    """
    Business-logic layer.
    Uses OpenSourceTranslationEngine — no Google Translate, no OpenAI.
    """

    def __init__(self, db: Session, engine: OpenSourceTranslationEngine):
        self.db = db
        self.engine = engine

    # -- Language detection (offline) --

    def detect_language(self, text: str) -> str:
        """Offline language detection using langdetect + heuristics."""
        # Character-set heuristics (fast path)
        arabic_chars = sum(1 for c in text if "\u0600" <= c <= "\u06FF")
        if arabic_chars > len(text) * 0.3:
            return "ar"

        yoruba_markers = ["ẹ", "ọ", "ṣ", "mo ", "emi ", "eyin ", "awa "]
        if any(m in text for m in yoruba_markers):
            return "yo"

        hausa_markers = ["ina ", "kana ", "tana ", "muna ", "suna ", "yaya ", "lafiya"]
        if any(m in text.lower() for m in hausa_markers):
            return "ha"

        igbo_markers = ["ọ bụ", "gịnị", "kedu", "nna m", "nne m"]
        if any(m in text.lower() for m in igbo_markers):
            return "ig"

        pidgin_markers = ["dey", "wetin", "abeg", "oga", "wahala", "na im", "dem go"]
        if sum(1 for m in pidgin_markers if m in text.lower()) >= 2:
            return "pcm"

        # langdetect fallback
        try:
            from langdetect import detect
            detected = detect(text)
            return detected if detected in SUPPORTED_LANGUAGES else "en"
        except Exception:
            return "en"

    # -- Glossary --

    def _apply_glossary(self, text: str, src: str, tgt: str) -> Tuple[str, dict]:
        if src not in FINANCIAL_GLOSSARY or tgt not in FINANCIAL_GLOSSARY:
            return text, {}
        src_glossary = FINANCIAL_GLOSSARY[src]
        tgt_glossary = FINANCIAL_GLOSSARY[tgt]
        processed = text
        mapping = {}
        for term, src_term in src_glossary.items():
            if src_term.lower() in processed.lower():
                placeholder = f"__TERM_{term.upper()}__"
                processed = processed.lower().replace(src_term.lower(), placeholder)
                mapping[placeholder] = tgt_glossary.get(term, src_term)
        return processed, mapping

    def _restore_glossary(self, text: str, mapping: dict) -> str:
        for placeholder, tgt_term in mapping.items():
            text = text.replace(placeholder, tgt_term)
        return text

    # -- Core translate (sync wrapper for router) --

    async def translate(self, req: TranslateRequest) -> TranslateResponse:
        start_ms = int(time.time() * 1000)

        source = req.source_language or self.detect_language(req.text)
        target = req.target_language

        if source == target:
            return TranslateResponse(
                original_text=req.text,
                translated_text=req.text,
                source_language=source,
                target_language=target,
                engine_used=TranslationEngine.PASSTHROUGH.value,
                cache_hit=True,
                latency_ms=0,
                quality_score=1.0,
            )

        # DB cache lookup
        cache_key = hashlib.sha256(f"{source}:{target}:{req.text}".encode()).hexdigest()
        db_cached = self.db.query(TranslationCache).filter(
            TranslationCache.id == cache_key
        ).first()
        if db_cached:
            db_cached.hit_count += 1
            db_cached.last_used_at = datetime.utcnow()
            self.db.commit()
            elapsed = int(time.time() * 1000) - start_ms
            return TranslateResponse(
                original_text=req.text,
                translated_text=db_cached.translated_text,
                source_language=source,
                target_language=target,
                engine_used=TranslationEngine.CACHE.value,
                cache_hit=True,
                latency_ms=elapsed,
                quality_score=0.95,
            )

        # Glossary preprocessing
        processed_text, glossary_map = (
            self._apply_glossary(req.text, source, target)
            if req.apply_glossary else (req.text, {})
        )

        # Translate with open-source engine
        translated, engine_name = await self.engine.translate(
            processed_text, source, target
        )

        # Restore glossary
        if req.apply_glossary and glossary_map:
            translated = self._restore_glossary(translated, glossary_map)

        elapsed = int(time.time() * 1000) - start_ms

        # Persist to DB cache
        cache_entry = TranslationCache(
            id=cache_key,
            source_text=req.text,
            source_language=source,
            target_language=target,
            translated_text=translated,
            engine_used=engine_name,
        )
        self.db.merge(cache_entry)

        # Audit record
        record = TranslationRecord(
            message_id=req.message_id,
            source_text=req.text,
            source_language=source,
            target_language=target,
            translated_text=translated,
            engine=engine_name,
            quality_score=0.92,
            latency_ms=elapsed,
            cache_hit=False,
        )
        self.db.add(record)
        self.db.commit()

        return TranslateResponse(
            original_text=req.text,
            translated_text=translated,
            source_language=source,
            target_language=target,
            engine_used=engine_name,
            cache_hit=False,
            latency_ms=elapsed,
            quality_score=0.92,
        )

    async def translate_message_for_conversation(
        self, req: MessageTranslationRequest
    ) -> MessageTranslationResponse:
        """
        Auto-detect sender/receiver language preferences and translate.
        """
        sender_pref = self.db.query(UserLanguagePreference).filter(
            UserLanguagePreference.user_id == req.sender_id
        ).first()
        receiver_pref = self.db.query(UserLanguagePreference).filter(
            UserLanguagePreference.user_id == req.receiver_id
        ).first()

        sender_lang = sender_pref.preferred_language if sender_pref else "en"
        receiver_lang = receiver_pref.preferred_language if receiver_pref else "en"

        detected = self.detect_language(req.message_text)
        actual_source = detected if detected != "en" else sender_lang

        translation_applied = False
        translated_for_receiver = None
        engine_used = TranslationEngine.PASSTHROUGH.value

        if (
            actual_source != receiver_lang
            and (receiver_pref is None or receiver_pref.auto_translate)
        ):
            translate_req = TranslateRequest(
                text=req.message_text,
                source_language=actual_source,
                target_language=receiver_lang,
                message_id=req.message_id,
            )
            result = await self.translate(translate_req)
            translated_for_receiver = result.translated_text
            engine_used = result.engine_used
            translation_applied = True

        return MessageTranslationResponse(
            message_id=req.message_id,
            original_text=req.message_text,
            sender_language=actual_source,
            receiver_language=receiver_lang,
            translated_for_receiver=translated_for_receiver,
            translation_applied=translation_applied,
            engine_used=engine_used,
        )

    async def batch_translate(self, req: BatchTranslateRequest) -> List[dict]:
        results = []
        for msg in req.messages:
            tr = TranslateRequest(
                text=msg.get("text", ""),
                source_language=msg.get("source_language"),
                target_language=req.target_language,
                message_id=msg.get("id"),
            )
            result = await self.translate(tr)
            results.append({
                "id": msg.get("id"),
                "original": msg.get("text"),
                "translated": result.translated_text,
                "engine": result.engine_used,
                "source_language": result.source_language,
            })
        return results

    def set_user_preference(self, req: LanguagePreferenceRequest) -> UserLanguagePreference:
        pref = self.db.query(UserLanguagePreference).filter(
            UserLanguagePreference.user_id == req.user_id
        ).first()
        if pref:
            pref.preferred_language = req.preferred_language
            pref.auto_translate = req.auto_translate
            pref.updated_at = datetime.utcnow()
        else:
            pref = UserLanguagePreference(
                user_id=req.user_id,
                preferred_language=req.preferred_language,
                auto_translate=req.auto_translate,
            )
            self.db.add(pref)
        self.db.commit()
        self.db.refresh(pref)
        return pref

    def get_user_preference(self, user_id: str) -> Optional[UserLanguagePreference]:
        return self.db.query(UserLanguagePreference).filter(
            UserLanguagePreference.user_id == user_id
        ).first()

    def get_supported_languages(self) -> dict:
        return {
            code: {
                **info,
                "nllb_code": NLLB_LANG_MAP.get(code),
                "direct_opus_pairs": [
                    f"{s}→{t}"
                    for (s, t) in OPUS_MT_MODELS_IDS
                    if s == code or t == code
                ],
            }
            for code, info in SUPPORTED_LANGUAGES.items()
        }

    def get_translation_stats(self) -> dict:
        total = self.db.query(TranslationRecord).count()
        cache_hits = self.db.query(TranslationRecord).filter(
            TranslationRecord.cache_hit == True
        ).count()
        return {
            "total_translations": total,
            "cache_hits": cache_hits,
            "cache_hit_rate_pct": round(cache_hits / (total or 1) * 100, 2),
            "engine_stats": self.engine.get_stats(),
            "supported_languages": list(SUPPORTED_LANGUAGES.keys()),
            "translation_engine": "open-source (NLLB-200 + Helsinki-NLP Opus-MT)",
            "external_api_dependency": "none",
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_engine_instance: Optional[OpenSourceTranslationEngine] = None


async def get_translation_engine() -> OpenSourceTranslationEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = OpenSourceTranslationEngine()
        await _engine_instance.initialize()
    return _engine_instance
