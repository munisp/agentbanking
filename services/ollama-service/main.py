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
Ollama Service
Local LLM Service for Remittance Platform
Provides local LLM inference using Ollama
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app)
setup_logging("ollama-service")
app.include_router(metrics_router)

from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, AsyncIterator
from datetime import datetime
import logging
import os
import json
import asyncio
import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Ollama Service",
    description="Local LLM Service using Ollama",
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
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "llama2")
    TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "300"))

config = Config()

# Models
class ChatMessage(BaseModel):
    role: str = Field(..., description="Role: system, user, or assistant")
    content: str = Field(..., description="Message content")

class ChatRequest(BaseModel):
    model: Optional[str] = None
    messages: List[ChatMessage]
    stream: bool = False
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = None
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)

class CompletionRequest(BaseModel):
    model: Optional[str] = None
    prompt: str
    stream: bool = False
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = None
    top_p: float = Field(default=0.9, ge=0.0, le=1.0)

class EmbeddingRequest(BaseModel):
    model: Optional[str] = None
    input: str

class ModelInfo(BaseModel):
    name: str
    size: int
    modified_at: datetime
    details: Dict[str, Any] = {}

class BankingQuery(BaseModel):
    query: str
    context: Dict[str, Any] = {}
    model: Optional[str] = None

# Ollama Engine
class OllamaEngine:
    def __init__(self):
        self.base_url = config.OLLAMA_HOST
        self.default_model = config.DEFAULT_MODEL
        self.client = httpx.AsyncClient(timeout=config.TIMEOUT)
    
    async def chat(self, request: ChatRequest) -> Dict[str, Any]:
        """Send a chat request to Ollama"""
        try:
            model = request.model or self.default_model
            
            payload = {
                "model": model,
                "messages": [msg.dict() for msg in request.messages],
                "stream": request.stream,
                "options": {
                    "temperature": request.temperature,
                    "top_p": request.top_p
                }
            }
            
            if request.max_tokens:
                payload["options"]["num_predict"] = request.max_tokens
            
            response = await self.client.post(
                f"{self.base_url}/api/chat",
                json=payload
            )
            response.raise_for_status()
            
            return response.json()
        except Exception as e:
            logger.error(f"Error in chat: {str(e)}")
            raise
    
    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """Stream chat responses from Ollama"""
        try:
            model = request.model or self.default_model
            
            payload = {
                "model": model,
                "messages": [msg.dict() for msg in request.messages],
                "stream": True,
                "options": {
                    "temperature": request.temperature,
                    "top_p": request.top_p
                }
            }
            
            if request.max_tokens:
                payload["options"]["num_predict"] = request.max_tokens
            
            async with self.client.stream(
                "POST",
                f"{self.base_url}/api/chat",
                json=payload
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        yield f"data: {line}\n\n"
        except Exception as e:
            logger.error(f"Error in chat stream: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    async def generate(self, request: CompletionRequest) -> Dict[str, Any]:
        """Generate completion from Ollama"""
        try:
            model = request.model or self.default_model
            
            payload = {
                "model": model,
                "prompt": request.prompt,
                "stream": request.stream,
                "options": {
                    "temperature": request.temperature,
                    "top_p": request.top_p
                }
            }
            
            if request.max_tokens:
                payload["options"]["num_predict"] = request.max_tokens
            
            response = await self.client.post(
                f"{self.base_url}/api/generate",
                json=payload
            )
            response.raise_for_status()
            
            return response.json()
        except Exception as e:
            logger.error(f"Error in generate: {str(e)}")
            raise
    
    async def embeddings(self, request: EmbeddingRequest) -> Dict[str, Any]:
        """Generate embeddings from Ollama"""
        try:
            model = request.model or self.default_model
            
            payload = {
                "model": model,
                "prompt": request.input
            }
            
            response = await self.client.post(
                f"{self.base_url}/api/embeddings",
                json=payload
            )
            response.raise_for_status()
            
            return response.json()
        except Exception as e:
            logger.error(f"Error generating embeddings: {str(e)}")
            raise
    
    async def list_models(self) -> List[ModelInfo]:
        """List available models"""
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            
            data = response.json()
            models = []
            
            for model in data.get("models", []):
                models.append(ModelInfo(
                    name=model.get("name", ""),
                    size=model.get("size", 0),
                    modified_at=datetime.fromisoformat(model.get("modified_at", datetime.utcnow().isoformat())),
                    details=model.get("details", {})
                ))
            
            return models
        except Exception as e:
            logger.error(f"Error listing models: {str(e)}")
            raise
    
    async def pull_model(self, model_name: str):
        """Pull a model from Ollama registry"""
        try:
            payload = {"name": model_name}
            
            response = await self.client.post(
                f"{self.base_url}/api/pull",
                json=payload
            )
            response.raise_for_status()
            
            return {"status": "success", "model": model_name}
        except Exception as e:
            logger.error(f"Error pulling model: {str(e)}")
            raise
    
    async def banking_assistant(self, query: BankingQuery) -> Dict[str, Any]:
        """Banking-specific AI assistant"""
        try:
            # Create system prompt for banking
            system_prompt = """You are a helpful banking assistant for an remittance platform. 
            You help agents with:
            - Transaction processing
            - Account management
            - Fraud detection insights
            - Customer service
            - Compliance questions
            
            Provide clear, accurate, and professional responses. 
            If you're unsure, say so and suggest contacting support."""
            
            # Add context if provided
            context_str = ""
            if query.context:
                context_str = f"\n\nContext: {json.dumps(query.context, indent=2)}"
            
            messages = [
                ChatMessage(role="system", content=system_prompt + context_str),
                ChatMessage(role="user", content=query.query)
            ]
            
            request = ChatRequest(
                model=query.model,
                messages=messages,
                temperature=0.7
            )
            
            response = await self.chat(request)
            
            return {
                "query": query.query,
                "response": response.get("message", {}).get("content", ""),
                "model": query.model or self.default_model,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error in banking assistant: {str(e)}")
            raise
    
    async def fraud_analysis(self, transaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze transaction for fraud using LLM"""
        try:
            prompt = f"""Analyze the following transaction for potential fraud indicators:

Transaction Data:
{json.dumps(transaction_data, indent=2)}

Provide:
1. Risk assessment (Low/Medium/High)
2. Suspicious patterns identified
3. Recommended actions
4. Confidence level

Format your response as JSON."""
            
            request = CompletionRequest(
                prompt=prompt,
                temperature=0.3  # Lower temperature for more consistent analysis
            )
            
            response = await self.generate(request)
            
            return {
                "transaction_id": transaction_data.get("transaction_id"),
                "analysis": response.get("response", ""),
                "model": self.default_model,
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error in fraud analysis: {str(e)}")
            raise
    
    async def customer_query_classifier(self, query: str) -> Dict[str, Any]:
        """Classify customer queries for routing"""
        try:
            prompt = f"""Classify the following customer query into one of these categories:
- account_inquiry
- transaction_issue
- fraud_report
- technical_support
- general_inquiry

Query: "{query}"

Respond with only the category name."""
            
            request = CompletionRequest(
                prompt=prompt,
                temperature=0.2
            )
            
            response = await self.generate(request)
            
            category = response.get("response", "general_inquiry").strip().lower()
            
            return {
                "query": query,
                "category": category,
                "confidence": 0.85,  # Could be enhanced with actual confidence scoring
                "timestamp": datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.error(f"Error classifying query: {str(e)}")
            raise

# Initialize engine
engine = OllamaEngine()

# API Endpoints

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Try to connect to Ollama
        response = await engine.client.get(f"{config.OLLAMA_HOST}/api/tags")
        connected = response.status_code == 200
    except:
        connected = False
    
    return {
        "status": "healthy" if connected else "degraded",
        "service": "ollama-service",
        "timestamp": datetime.utcnow().isoformat(),
        "ollama_connected": connected,
        "ollama_host": config.OLLAMA_HOST
    }

@app.post("/chat")
async def chat(request: ChatRequest):
    """Chat with Ollama"""
    try:
        if request.stream:
            return StreamingResponse(
                engine.chat_stream(request),
                media_type="text/event-stream"
            )
        else:
            response = await engine.chat(request)
            return response
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/completions")
async def generate(request: CompletionRequest):
    """Generate completion"""
    try:
        response = await engine.generate(request)
        return response
    except Exception as e:
        logger.error(f"Error in generate endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/embeddings")
async def embeddings(request: EmbeddingRequest):
    """Generate embeddings"""
    try:
        response = await engine.embeddings(request)
        return response
    except Exception as e:
        logger.error(f"Error in embeddings endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/models", response_model=List[ModelInfo])
async def list_models():
    """List available models"""
    try:
        models = await engine.list_models()
        return models
    except Exception as e:
        logger.error(f"Error listing models: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/models/pull")
async def pull_model(model_name: str, background_tasks: BackgroundTasks):
    """Pull a model from Ollama registry"""
    try:
        background_tasks.add_task(engine.pull_model, model_name)
        return {"message": f"Pulling model {model_name} in background", "status": "started"}
    except Exception as e:
        logger.error(f"Error pulling model: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/banking/assistant")
async def banking_assistant(query: BankingQuery):
    """Banking-specific AI assistant"""
    try:
        response = await engine.banking_assistant(query)
        return response
    except Exception as e:
        logger.error(f"Error in banking assistant: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/banking/fraud-analysis")
async def fraud_analysis(transaction_data: Dict[str, Any]):
    """Analyze transaction for fraud"""
    try:
        response = await engine.fraud_analysis(transaction_data)
        return response
    except Exception as e:
        logger.error(f"Error in fraud analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/banking/classify-query")
async def classify_query(query: str):
    """Classify customer query"""
    try:
        response = await engine.customer_query_classifier(query)
        return response
    except Exception as e:
        logger.error(f"Error classifying query: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8092)

