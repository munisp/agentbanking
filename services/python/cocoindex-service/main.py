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
CocoIndex Service
Contextual Code Indexing and Retrieval for Remittance Platform
Provides semantic code search and intelligent code recommendations
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app, enable_auth=True)
setup_logging("cocoindex-service")
app.include_router(metrics_router)

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import os
import uuid
import json
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss
from pathlib import Path
import ast
import hashlib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ── OpenTelemetry Tracing ────────────────────────────────────────────────────
_otel_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
if _otel_endpoint:
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        _resource = Resource.create({
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "cocoindex-service"),
            "service.version": os.environ.get("OTEL_SERVICE_VERSION", "1.0.0"),
            "deployment.environment": os.environ.get("ENVIRONMENT", "production"),
        })
        _provider = TracerProvider(resource=_resource)
        _exporter = OTLPSpanExporter(endpoint=f"{_otel_endpoint}/v1/traces")
        _provider.add_span_processor(BatchSpanProcessor(_exporter))
        trace.set_tracer_provider(_provider)
        logging.getLogger(__name__).info(f"[OTel] Tracing enabled → {_otel_endpoint}")
    except ImportError:
        logging.getLogger(__name__).warning("[OTel] opentelemetry packages not installed — tracing disabled")

app = FastAPI(
# Instrument FastAPI with OpenTelemetry
if _otel_endpoint:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor.instrument_app(app)
    except (ImportError, Exception):
        pass


import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/cocoindex_service")

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
    title="CocoIndex Service",
    description="Contextual Code Indexing and Retrieval Service",
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
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    INDEX_PATH = os.getenv("INDEX_PATH", "/data/cocoindex")
    VECTOR_DIM = 384  # Dimension for all-MiniLM-L6-v2
    DATABASE_URL = os.getenv("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/cocoindex_service")

config = Config()

# Models
class CodeSnippet(BaseModel):
    id: Optional[str] = None
    code: str
    language: str
    description: Optional[str] = None
    file_path: Optional[str] = None
    function_name: Optional[str] = None
    class_name: Optional[str] = None
    tags: List[str] = []
    metadata: Dict[str, Any] = {}
    created_at: Optional[datetime] = None

class SearchQuery(BaseModel):
    query: str
    language: Optional[str] = None
    top_k: int = Field(default=10, ge=1, le=100)
    filters: Dict[str, Any] = {}

class SearchResult(BaseModel):
    snippet: CodeSnippet
    score: float
    relevance: str

class IndexStats(BaseModel):
    total_snippets: int
    languages: Dict[str, int]
    total_size_bytes: int
    last_updated: datetime

# CocoIndex Engine
class CocoIndexEngine:
    def __init__(self):
        self.model = None
        self.index = None
        self.snippets = {}
        self.metadata = {}
        self.initialize()
    
    def initialize(self):
        """Initialize the embedding model and FAISS index"""
        try:
            logger.info("Initializing CocoIndex engine...")
            
            # Load sentence transformer model
            self.model = SentenceTransformer(config.EMBEDDING_MODEL)
            
            # Create or load FAISS index
            index_file = Path(config.INDEX_PATH) / "cocoindex.faiss"
            if index_file.exists():
                self.index = faiss.read_index(str(index_file))
                logger.info(f"Loaded existing index with {self.index.ntotal} vectors")
            else:
                # Create new index
                self.index = faiss.IndexFlatL2(config.VECTOR_DIM)
                logger.info("Created new FAISS index")
            
            # Load metadata
            self._load_metadata()
            
            logger.info("CocoIndex engine initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing CocoIndex engine: {str(e)}")
            raise
    
    def _load_metadata(self):
        """Load snippet metadata from disk"""
        metadata_file = Path(config.INDEX_PATH) / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                data = json.load(f)
                self.snippets = data.get('snippets', {})
                self.metadata = data.get('metadata', {})
    
    def _save_metadata(self):
        """Save snippet metadata to disk"""
        Path(config.INDEX_PATH).mkdir(parents=True, exist_ok=True)
        metadata_file = Path(config.INDEX_PATH) / "metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump({
                'snippets': self.snippets,
                'metadata': self.metadata
            }, f, default=str)
    
    def _save_index(self):
        """Save FAISS index to disk"""
        Path(config.INDEX_PATH).mkdir(parents=True, exist_ok=True)
        index_file = Path(config.INDEX_PATH) / "cocoindex.faiss"
        faiss.write_index(self.index, str(index_file))
    
    def add_snippet(self, snippet: CodeSnippet) -> str:
        """Add a code snippet to the index"""
        try:
            # Generate ID if not provided
            if not snippet.id:
                snippet.id = str(uuid.uuid4())
            
            # Create embedding text
            embedding_text = self._create_embedding_text(snippet)
            
            # Generate embedding
            embedding = self.model.encode([embedding_text])[0]
            
            # Add to FAISS index
            self.index.add(np.array([embedding], dtype=np.float32))
            
            # Store snippet metadata
            self.snippets[snippet.id] = snippet.dict()
            
            # Update metadata
            self.metadata[snippet.id] = {
                'index_position': self.index.ntotal - 1,
                'created_at': datetime.utcnow().isoformat()
            }
            
            # Save to disk
            self._save_metadata()
            self._save_index()
            
            logger.info(f"Added snippet {snippet.id} to index")
            return snippet.id
        except Exception as e:
            logger.error(f"Error adding snippet: {str(e)}")
            raise
    
    def _create_embedding_text(self, snippet: CodeSnippet) -> str:
        """Create text for embedding generation"""
        parts = []
        
        if snippet.description:
            parts.append(snippet.description)
        
        if snippet.function_name:
            parts.append(f"Function: {snippet.function_name}")
        
        if snippet.class_name:
            parts.append(f"Class: {snippet.class_name}")
        
        parts.append(f"Language: {snippet.language}")
        parts.append(snippet.code)
        
        if snippet.tags:
            parts.append(f"Tags: {', '.join(snippet.tags)}")
        
        return " | ".join(parts)
    
    def search(self, query: SearchQuery) -> List[SearchResult]:
        """Search for code snippets"""
        try:
            # Generate query embedding
            query_embedding = self.model.encode([query.query])[0]
            
            # Search in FAISS index
            k = min(query.top_k, self.index.ntotal)
            distances, indices = self.index.search(
                np.array([query_embedding], dtype=np.float32),
                k
            )
            
            # Prepare results
            results = []
            for i, (distance, idx) in enumerate(zip(distances[0], indices[0])):
                # Find snippet by index position
                snippet_id = None
                for sid, meta in self.metadata.items():
                    if meta['index_position'] == idx:
                        snippet_id = sid
                        break
                
                if snippet_id and snippet_id in self.snippets:
                    snippet_data = self.snippets[snippet_id]
                    
                    # Apply filters
                    if query.language and snippet_data['language'] != query.language:
                        continue
                    
                    # Calculate relevance score (convert distance to similarity)
                    score = 1.0 / (1.0 + distance)
                    
                    # Determine relevance level
                    if score > 0.8:
                        relevance = "high"
                    elif score > 0.6:
                        relevance = "medium"
                    else:
                        relevance = "low"
                    
                    results.append(SearchResult(
                        snippet=CodeSnippet(**snippet_data),
                        score=float(score),
                        relevance=relevance
                    ))
            
            logger.info(f"Search returned {len(results)} results")
            return results
        except Exception as e:
            logger.error(f"Error searching: {str(e)}")
            raise
    
    def get_stats(self) -> IndexStats:
        """Get index statistics"""
        languages = {}
        total_size = 0
        
        for snippet_data in self.snippets.values():
            lang = snippet_data.get('language', 'unknown')
            languages[lang] = languages.get(lang, 0) + 1
            total_size += len(snippet_data.get('code', ''))
        
        return IndexStats(
            total_snippets=len(self.snippets),
            languages=languages,
            total_size_bytes=total_size,
            last_updated=datetime.utcnow()
        )
    
    def analyze_code(self, code: str, language: str) -> Dict[str, Any]:
        """Analyze code structure"""
        analysis = {
            'language': language,
            'lines': len(code.split('\n')),
            'characters': len(code),
            'functions': [],
            'classes': [],
            'imports': []
        }
        
        if language == 'python':
            try:
                tree = ast.parse(code)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        analysis['functions'].append(node.name)
                    elif isinstance(node, ast.ClassDef):
                        analysis['classes'].append(node.name)
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            analysis['imports'].append(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            analysis['imports'].append(node.module)
            except:
                pass
        
        return analysis

# Initialize engine
engine = CocoIndexEngine()

# API Endpoints

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "cocoindex-service",
        "timestamp": datetime.utcnow().isoformat(),
        "index_size": engine.index.ntotal if engine.index else 0
    }

@app.post("/snippets", response_model=Dict[str, str])
async def add_snippet(snippet: CodeSnippet):
    """Add a code snippet to the index"""
    try:
        snippet_id = engine.add_snippet(snippet)
        return {
            "id": snippet_id,
            "message": "Snippet added successfully"
        }
    except Exception as e:
        logger.error(f"Error adding snippet: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search", response_model=List[SearchResult])
async def search_snippets(query: SearchQuery):
    """Search for code snippets"""
    try:
        results = engine.search(query)
        return results
    except Exception as e:
        logger.error(f"Error searching: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats", response_model=IndexStats)
async def get_stats():
    """Get index statistics"""
    try:
        return engine.get_stats()
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze")
async def analyze_code(code: str, language: str):
    """Analyze code structure"""
    try:
        analysis = engine.analyze_code(code, language)
        return analysis
    except Exception as e:
        logger.error(f"Error analyzing code: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/snippets/{snippet_id}")
async def get_snippet(snippet_id: str):
    """Get a specific code snippet"""
    if snippet_id not in engine.snippets:
        raise HTTPException(status_code=404, detail="Snippet not found")
    
    return engine.snippets[snippet_id]

@app.delete("/snippets/{snippet_id}")
async def delete_snippet(snippet_id: str):
    """Delete a code snippet"""
    if snippet_id not in engine.snippets:
        raise HTTPException(status_code=404, detail="Snippet not found")
    
    # Remove from snippets
    del engine.snippets[snippet_id]
    del engine.metadata[snippet_id]
    
    # Save metadata
    engine._save_metadata()
    
    # Note: FAISS doesn't support deletion, so we'd need to rebuild the index
    # For now, we just mark it as deleted in metadata
    
    return {"message": "Snippet deleted successfully"}

@app.post("/index/rebuild")
async def rebuild_index(background_tasks: BackgroundTasks):
    """Rebuild the entire index"""
    def rebuild():
        try:
            logger.info("Starting index rebuild...")
            
            # Create new index
            new_index = faiss.IndexFlatL2(config.VECTOR_DIM)
            new_metadata = {}
            
            # Re-add all snippets
            for snippet_id, snippet_data in engine.snippets.items():
                snippet = CodeSnippet(**snippet_data)
                embedding_text = engine._create_embedding_text(snippet)
                embedding = engine.model.encode([embedding_text])[0]
                
                new_index.add(np.array([embedding], dtype=np.float32))
                new_metadata[snippet_id] = {
                    'index_position': new_index.ntotal - 1,
                    'created_at': datetime.utcnow().isoformat()
                }
            
            # Replace old index
            engine.index = new_index
            engine.metadata = new_metadata
            
            # Save
            engine._save_index()
            engine._save_metadata()
            
            logger.info("Index rebuild completed")
        except Exception as e:
            logger.error(f"Error rebuilding index: {str(e)}")
    
    background_tasks.add_task(rebuild)
    return {"message": "Index rebuild started in background"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8090)

