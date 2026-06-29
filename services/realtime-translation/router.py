"""
Real-time Translation Service — FastAPI Router
54agent Agency Banking Platform

Exposes:
  1. Native 54agent API  (/api/translate/*)
  2. LibreTranslate-compatible API  (/api/translate/libretranslate/*)
     Drop-in replacement for Google Translate or hosted LibreTranslate.

All translation uses open-source models only (NLLB-200 + Helsinki-NLP Opus-MT).
No Google Translate. No OpenAI translation calls.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from service import (
    BatchTranslateRequest,
    LanguagePreferenceRequest,
    MessageTranslationRequest,
    MessageTranslationResponse,
    OpenSourceTranslationEngine,
    RealtimeTranslationService,
    SUPPORTED_LANGUAGES,
    FINANCIAL_GLOSSARY,
    TranslateRequest,
    TranslateResponse,
    get_translation_engine,
)
from config import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/translate", tags=["Translation"])


# ---------------------------------------------------------------------------
# Dependency injection
# ---------------------------------------------------------------------------

async def get_service(
    engine: OpenSourceTranslationEngine = Depends(get_translation_engine),
    db: Session = Depends(get_db),
) -> RealtimeTranslationService:
    return RealtimeTranslationService(db=db, engine=engine)


# ---------------------------------------------------------------------------
# 1. Native 54agent translation endpoints
# ---------------------------------------------------------------------------

@router.post("/", response_model=TranslateResponse, summary="Translate text")
async def translate_text(
    req: TranslateRequest,
    svc: RealtimeTranslationService = Depends(get_service),
):
    """
    Translate text between any two supported languages.
    Engine: NLLB-200 (primary) + Helsinki-NLP Opus-MT (fallback).
    Fully self-hosted — no external API dependency.
    """
    try:
        return await svc.translate(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(f"Translation error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Translation failed")


@router.post("/message", response_model=MessageTranslationResponse,
             summary="Translate a chat message")
async def translate_message(
    req: MessageTranslationRequest,
    svc: RealtimeTranslationService = Depends(get_service),
):
    """
    Translate a message in a conversation context.
    Auto-detects sender/receiver language preferences and translates accordingly.
    """
    try:
        return await svc.translate_message_for_conversation(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(f"Message translation error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Message translation failed")


@router.post("/batch", summary="Batch translate multiple messages")
async def batch_translate(
    req: BatchTranslateRequest,
    svc: RealtimeTranslationService = Depends(get_service),
):
    """Translate a list of messages to the target language concurrently."""
    try:
        return await svc.batch_translate(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/detect", summary="Detect language of text")
async def detect_language(
    text: str = Query(..., min_length=1, max_length=2000),
    svc: RealtimeTranslationService = Depends(get_service),
):
    """Detect the language of input text (fully offline, no API)."""
    detected = svc.detect_language(text)
    return {
        "text": text[:100],
        "detected_language": detected,
        "language_name": SUPPORTED_LANGUAGES.get(detected, {}).get("name", "Unknown"),
        "supported": detected in SUPPORTED_LANGUAGES,
    }


@router.get("/languages", summary="List supported languages")
async def list_languages(
    svc: RealtimeTranslationService = Depends(get_service),
):
    """Return all supported languages with NLLB-200 and Opus-MT model info."""
    return svc.get_supported_languages()


@router.get("/glossary/{language}", summary="Get financial glossary for a language")
def get_glossary(language: str):
    """Return the banking/financial term glossary for a given language."""
    if language not in FINANCIAL_GLOSSARY:
        raise HTTPException(
            status_code=404,
            detail=f"No glossary for language '{language}'. "
                   f"Available: {', '.join(FINANCIAL_GLOSSARY)}",
        )
    return {
        "language": language,
        "language_name": SUPPORTED_LANGUAGES.get(language, {}).get("name", language),
        "terms": FINANCIAL_GLOSSARY[language],
    }


@router.get("/stats", summary="Translation engine statistics")
async def get_stats(
    svc: RealtimeTranslationService = Depends(get_service),
):
    """Return translation statistics and engine health."""
    return svc.get_translation_stats()


@router.get("/health")
def health():
    return {
        "status": "ok",
        "service": "realtime-translation",
        "engine": "open-source (NLLB-200 + Helsinki-NLP Opus-MT)",
        "external_api": "none",
    }


# ---------------------------------------------------------------------------
# 2. User language preference endpoints
# ---------------------------------------------------------------------------

@router.post("/preferences", summary="Set user language preference")
async def set_preference(
    req: LanguagePreferenceRequest,
    svc: RealtimeTranslationService = Depends(get_service),
):
    if req.preferred_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported language: {req.preferred_language}. "
                   f"Supported: {', '.join(SUPPORTED_LANGUAGES)}",
        )
    pref = svc.set_user_preference(req)
    return {
        "user_id": pref.user_id,
        "preferred_language": pref.preferred_language,
        "language_name": SUPPORTED_LANGUAGES.get(pref.preferred_language, {}).get("name"),
        "auto_translate": pref.auto_translate,
        "updated_at": pref.updated_at.isoformat() if pref.updated_at else None,
    }


@router.get("/preferences/{user_id}", summary="Get user language preference")
async def get_preference(
    user_id: str,
    svc: RealtimeTranslationService = Depends(get_service),
):
    pref = svc.get_user_preference(user_id)
    if not pref:
        return {
            "user_id": user_id,
            "preferred_language": "en",
            "auto_translate": True,
            "is_default": True,
        }
    return {
        "user_id": pref.user_id,
        "preferred_language": pref.preferred_language,
        "language_name": SUPPORTED_LANGUAGES.get(pref.preferred_language, {}).get("name"),
        "auto_translate": pref.auto_translate,
        "is_default": False,
    }


# ---------------------------------------------------------------------------
# 3. LibreTranslate-compatible API
#    Drop-in replacement — any client that was calling Google Translate or
#    a hosted LibreTranslate instance can point here with zero code changes.
# ---------------------------------------------------------------------------

lt_router = APIRouter(
    prefix="/api/translate/libretranslate",
    tags=["LibreTranslate-compatible API"],
)


@lt_router.post("/translate", summary="LibreTranslate-compatible translate")
async def lt_translate(
    body: dict,
    svc: RealtimeTranslationService = Depends(get_service),
):
    """
    LibreTranslate-compatible endpoint.
    Accepts: { "q": "...", "source": "en", "target": "yo" }
    Returns: { "translatedText": "..." }
    """
    q = body.get("q", "")
    source = body.get("source", "auto")
    target = body.get("target", "en")

    if not q:
        raise HTTPException(status_code=400, detail="Field 'q' is required")

    if source == "auto":
        source = svc.detect_language(q)

    try:
        result = await svc.translate(
            TranslateRequest(
                text=q,
                source_language=source,
                target_language=target,
            )
        )
        response = {"translatedText": result.translated_text}
        if body.get("source") == "auto":
            response["detectedLanguage"] = {
                "confidence": 90,
                "language": result.source_language,
            }
        return response
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@lt_router.post("/detect", summary="LibreTranslate-compatible detect")
async def lt_detect(
    body: dict,
    svc: RealtimeTranslationService = Depends(get_service),
):
    """
    LibreTranslate-compatible detect endpoint.
    Accepts: { "q": "..." }
    Returns: [{ "language": "en", "confidence": 0.90 }]
    """
    q = body.get("q", "")
    if not q:
        raise HTTPException(status_code=400, detail="Field 'q' is required")
    detected = svc.detect_language(q)
    return [{"language": detected, "confidence": 0.90}]


@lt_router.get("/languages", summary="LibreTranslate-compatible languages list")
async def lt_languages():
    """LibreTranslate-compatible languages endpoint."""
    return [
        {
            "code": code,
            "name": info["name"],
            "targets": [t for t in SUPPORTED_LANGUAGES if t != code],
        }
        for code, info in SUPPORTED_LANGUAGES.items()
    ]


@lt_router.get("/frontend/settings", summary="LibreTranslate frontend settings")
async def lt_settings():
    """LibreTranslate-compatible frontend settings (for UI compatibility)."""
    return {
        "charLimit": 5000,
        "frontendTimeout": 500,
        "apiKeys": False,
        "keyRequired": False,
        "suggestions": False,
        "supportedFilesFormat": [],
    }


# Attach LibreTranslate-compatible sub-router
router.include_router(lt_router)
