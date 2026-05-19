"""
NLP Service - Natural Language Processing for Customer Support
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="NLP Service",
    description="Natural Language Processing for customer support and text analysis",
    version="1.0.0"
)

# Request/Response Models
class TextAnalysisRequest(BaseModel):
    text: str
    language: str = "en"
    
class SentimentResponse(BaseModel):
    sentiment: str  # positive, negative, neutral
    confidence: float
    score: float  # -1 to 1
    
class IntentRequest(BaseModel):
    text: str
    context: Optional[Dict[str, Any]] = None
    
class IntentResponse(BaseModel):
    intent: str
    confidence: float
    entities: Dict[str, Any]
    suggested_action: str
    
class EntityExtractionResponse(BaseModel):
    entities: List[Dict[str, Any]]
    
class LanguageDetectionResponse(BaseModel):
    language: str
    confidence: float

# Simple rule-based implementations (would use ML models in production)

def analyze_sentiment(text: str) -> SentimentResponse:
    """Analyze sentiment of text"""
    text_lower = text.lower()
    
    # Positive words
    positive_words = ["good", "great", "excellent", "happy", "satisfied", "love", "best", "wonderful", "amazing"]
    # Negative words
    negative_words = ["bad", "poor", "terrible", "unhappy", "disappointed", "hate", "worst", "awful", "horrible"]
    
    positive_count = sum(1 for word in positive_words if word in text_lower)
    negative_count = sum(1 for word in negative_words if word in text_lower)
    
    if positive_count > negative_count:
        sentiment = "positive"
        score = min(positive_count / 10, 1.0)
    elif negative_count > positive_count:
        sentiment = "negative"
        score = -min(negative_count / 10, 1.0)
    else:
        sentiment = "neutral"
        score = 0.0
    
    confidence = abs(score)
    
    return SentimentResponse(
        sentiment=sentiment,
        confidence=confidence,
        score=score
    )

def detect_intent(text: str, context: Optional[Dict] = None) -> IntentResponse:
    """Detect user intent from text"""
    text_lower = text.lower()
    
    # Intent patterns
    intents = {
        "transfer_money": ["send money", "transfer", "remit", "pay"],
        "check_balance": ["balance", "how much", "account"],
        "transaction_status": ["status", "where is", "track", "receipt"],
        "kyc_verification": ["verify", "kyc", "identity", "document"],
        "complaint": ["problem", "issue", "not working", "error", "help"],
        "greeting": ["hello", "hi", "hey", "good morning"],
    }
    
    detected_intent = "unknown"
    confidence = 0.0
    
    for intent, keywords in intents.items():
        matches = sum(1 for keyword in keywords if keyword in text_lower)
        if matches > 0:
            detected_intent = intent
            confidence = min(matches / len(keywords), 1.0)
            break
    
    # Extract entities
    entities = extract_entities(text)
    
    # Suggest action
    actions = {
        "transfer_money": "Navigate to transfer page",
        "check_balance": "Show wallet balance",
        "transaction_status": "Show transaction history",
        "kyc_verification": "Navigate to KYC page",
        "complaint": "Connect to customer support",
        "greeting": "Show welcome message",
        "unknown": "Ask for clarification"
    }
    
    return IntentResponse(
        intent=detected_intent,
        confidence=confidence,
        entities=entities,
        suggested_action=actions.get(detected_intent, "Ask for clarification")
    )

def extract_entities(text: str) -> Dict[str, Any]:
    """Extract named entities from text"""
    entities = {}
    
    # Extract amounts
    amount_pattern = r'₦?(\d+(?:,\d{3})*(?:\.\d{2})?)'
    amounts = re.findall(amount_pattern, text)
    if amounts:
        entities["amounts"] = [float(a.replace(',', '')) for a in amounts]
    
    # Extract phone numbers
    phone_pattern = r'\+?234\d{10}|\d{11}'
    phones = re.findall(phone_pattern, text)
    if phones:
        entities["phone_numbers"] = phones
    
    # Extract emails
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, text)
    if emails:
        entities["emails"] = emails
    
    # Extract dates
    date_pattern = r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}'
    dates = re.findall(date_pattern, text)
    if dates:
        entities["dates"] = dates
    
    return entities

def detect_language(text: str) -> LanguageDetectionResponse:
    """Detect language of text"""
    # Simple heuristic (would use proper language detection in production)
    text_lower = text.lower()
    
    # Check for common Nigerian languages
    yoruba_words = ["bawo", "daadaa", "ẹ", "ọ"]
    hausa_words = ["sannu", "yaya", "nagode"]
    igbo_words = ["kedu", "daalu", "ndewo"]
    
    if any(word in text_lower for word in yoruba_words):
        return LanguageDetectionResponse(language="yo", confidence=0.8)
    elif any(word in text_lower for word in hausa_words):
        return LanguageDetectionResponse(language="ha", confidence=0.8)
    elif any(word in text_lower for word in igbo_words):
        return LanguageDetectionResponse(language="ig", confidence=0.8)
    else:
        return LanguageDetectionResponse(language="en", confidence=0.9)

# API Endpoints

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "nlp-service",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/analyze/sentiment", response_model=SentimentResponse)
async def analyze_sentiment_endpoint(request: TextAnalysisRequest):
    """Analyze sentiment of text"""
    try:
        result = analyze_sentiment(request.text)
        logger.info(f"Sentiment analysis: {result.sentiment} ({result.confidence:.2f})")
        return result
    except Exception as e:
        logger.error(f"Sentiment analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze/intent", response_model=IntentResponse)
async def detect_intent_endpoint(request: IntentRequest):
    """Detect user intent from text"""
    try:
        result = detect_intent(request.text, request.context)
        logger.info(f"Intent detection: {result.intent} ({result.confidence:.2f})")
        return result
    except Exception as e:
        logger.error(f"Intent detection error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze/entities", response_model=EntityExtractionResponse)
async def extract_entities_endpoint(request: TextAnalysisRequest):
    """Extract named entities from text"""
    try:
        entities = extract_entities(request.text)
        logger.info(f"Entity extraction: {len(entities)} types found")
        return EntityExtractionResponse(entities=[{"type": k, "values": v} for k, v in entities.items()])
    except Exception as e:
        logger.error(f"Entity extraction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze/language", response_model=LanguageDetectionResponse)
async def detect_language_endpoint(request: TextAnalysisRequest):
    """Detect language of text"""
    try:
        result = detect_language(request.text)
        logger.info(f"Language detection: {result.language} ({result.confidence:.2f})")
        return result
    except Exception as e:
        logger.error(f"Language detection error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze/all")
async def analyze_all(request: TextAnalysisRequest):
    """Perform all NLP analyses on text"""
    try:
        return {
            "sentiment": analyze_sentiment(request.text),
            "intent": detect_intent(request.text),
            "entities": extract_entities(request.text),
            "language": detect_language(request.text)
        }
    except Exception as e:
        logger.error(f"Complete analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)
