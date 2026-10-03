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

_shutdown_handlers = _PgListStore("ollama_service__shutdown_handlers", "OLLAMA_SERVICE_DATABASE_URL")  # round-11 wave-7 persistence

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

apply_middleware(app)
setup_logging("ollama-service")
app.include_router(metrics_router)

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

