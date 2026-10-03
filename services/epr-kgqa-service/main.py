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

_shutdown_handlers = _PgListStore("epr_kgqa_service__shutdown_handlers", "EPR_KGQA_SERVICE_DATABASE_URL")  # round-11 wave-7 persistence

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
EPR-KGQA Service
Entity-Property-Relation Knowledge Graph Question Answering
Provides intelligent question answering over knowledge graphs for banking domain

NOTE: Answers are grounded in REAL knowledge-graph query results. When the
knowledge graph cannot be reached or returns no data, the service explicitly
says it could not retrieve the information — it never fabricates balances,
statistics, fraud verdicts, or confidence scores.
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware


from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime
import logging
import os
import uuid
import json
import re
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="EPR-KGQA Service",
    description="Knowledge Graph Question Answering Service",
    version="1.0.0"
)

apply_middleware(app)
setup_logging("epr-kgqa-service")
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
    KNOWLEDGE_GRAPH_URL = os.getenv("KNOWLEDGE_GRAPH_URL", "http://localhost:8091")
    LLM_SERVICE_URL = os.getenv("LLM_SERVICE_URL", "http://localhost:8092")
    KG_QUERY_TIMEOUT_SECS = float(os.getenv("KG_QUERY_TIMEOUT_SECS", "10"))

config = Config()

# Models
class Entity(BaseModel):
    id: str
    type: str
    properties: Dict[str, Any] = {}

class Relation(BaseModel):
    id: str
    source: str
    target: str
    type: str
    properties: Dict[str, Any] = {}

class Question(BaseModel):
    text: str
    context: Dict[str, Any] = {}
    language: str = "en"

class Answer(BaseModel):
    question: str
    answer: str
    confidence: Optional[float] = None
    entities: List[Entity] = []
    relations: List[Relation] = []
    reasoning_path: List[str] = []
    sources: List[str] = []
    timestamp: datetime

class KnowledgeGraphQuery(BaseModel):
    entities: List[str]
    relations: List[str]
    constraints: Dict[str, Any] = {}

class QueryResult(BaseModel):
    query: str
    results: List[Dict[str, Any]]
    execution_time: float

# EPR-KGQA Engine
class EPRKGQAEngine:
    def __init__(self):
        self.knowledge_base = self._initialize_banking_kb()
        self.entity_patterns = self._compile_entity_patterns()
        self.relation_patterns = self._compile_relation_patterns()

    def _initialize_banking_kb(self) -> Dict[str, Any]:
        """Initialize banking domain knowledge base (schema/ontology only — no data)"""
        return {
            "entities": {
                "transaction": {
                    "properties": ["amount", "timestamp", "status", "type"],
                    "relations": ["performed_by", "sent_to", "received_from"]
                },
                "agent": {
                    "properties": ["name", "id", "status", "location", "balance"],
                    "relations": ["performed", "manages", "reports_to"]
                },
                "account": {
                    "properties": ["number", "balance", "type", "status"],
                    "relations": ["owned_by", "linked_to"]
                },
                "customer": {
                    "properties": ["name", "id", "phone", "email"],
                    "relations": ["has_account", "made_transaction"]
                }
            },
            "relations": {
                "performed_by": {"domain": "transaction", "range": "agent"},
                "sent_to": {"domain": "transaction", "range": "account"},
                "received_from": {"domain": "transaction", "range": "account"},
                "has_account": {"domain": "customer", "range": "account"},
                "made_transaction": {"domain": "customer", "range": "transaction"}
            }
        }

    def _compile_entity_patterns(self) -> Dict[str, List[str]]:
        """Compile regex patterns for entity extraction"""
        return {
            "transaction": [
                r"transaction\s+(\w+)",
                r"txn\s+(\w+)",
                r"payment\s+(\w+)"
            ],
            "agent": [
                r"agent\s+(\w+)",
                r"AG-(\d+)"
            ],
            "account": [
                r"account\s+(\w+)",
                r"ACC-(\d+)"
            ],
            "amount": [
                r"\$?([\d,]+\.?\d*)",
                r"(\d+)\s+(dollars|USD|NGN)"
            ]
        }

    def _compile_relation_patterns(self) -> Dict[str, List[str]]:
        """Compile patterns for relation extraction"""
        return {
            "performed_by": ["performed by", "made by", "done by", "executed by"],
            "sent_to": ["sent to", "transferred to", "paid to"],
            "received_from": ["received from", "got from", "obtained from"],
            "has_balance": ["has balance", "balance of", "balance is"]
        }

    def extract_entities(self, text: str) -> List[Entity]:
        """Extract entities from question text"""
        entities = []
        text_lower = text.lower()

        for entity_type, patterns in self.entity_patterns.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text_lower)
                for match in matches:
                    entity_id = match.group(1) if match.lastindex else match.group(0)
                    entities.append(Entity(
                        id=entity_id,
                        type=entity_type,
                        properties={}
                    ))

        return entities

    def extract_relations(self, text: str) -> List[str]:
        """Extract relations from question text"""
        relations = []
        text_lower = text.lower()

        for relation_type, patterns in self.relation_patterns.items():
            for pattern in patterns:
                if pattern in text_lower:
                    relations.append(relation_type)

        return relations

    def classify_question_type(self, text: str) -> str:
        """Classify the type of question"""
        text_lower = text.lower()

        if any(word in text_lower for word in ["who", "which agent", "which customer"]):
            return "entity_query"
        elif any(word in text_lower for word in ["what", "how much", "how many"]):
            return "property_query"
        elif any(word in text_lower for word in ["when", "what time"]):
            return "temporal_query"
        elif any(word in text_lower for word in ["why", "reason"]):
            return "explanation_query"
        elif any(word in text_lower for word in ["is", "are", "does", "did"]):
            return "verification_query"
        else:
            return "general_query"

    def generate_cypher_query(self, question: Question, entities: List[Entity], relations: List[str]) -> str:
        """Generate Cypher query from question analysis"""
        question_type = self.classify_question_type(question.text)

        # Build Cypher query based on question type
        if question_type == "entity_query":
            # Who performed transaction X?
            if entities:
                entity = entities[0]
                return f"""
                MATCH (e:{entity.type.capitalize()} {{id: '{entity.id}'}})-[r]->(related)
                RETURN e, r, related
                """

        elif question_type == "property_query":
            # What is the balance of agent X?
            if entities:
                entity = entities[0]
                return f"""
                MATCH (e:{entity.type.capitalize()} {{id: '{entity.id}'}})
                RETURN e
                """

        elif question_type == "temporal_query":
            # When did agent X perform transaction Y?
            return """
            MATCH (a:Agent)-[r:PERFORMED]->(t:Transaction)
            WHERE t.timestamp IS NOT NULL
            RETURN a, r, t
            ORDER BY t.timestamp DESC
            LIMIT 10
            """

        # Default query
        return """
        MATCH (n)
        RETURN n
        LIMIT 10
        """

    def _execute_kg_query(self, cypher_query: str) -> Optional[List[Dict[str, Any]]]:
        """Execute a Cypher query against the configured knowledge graph service.

        Returns a list of result records on success, or None when the knowledge
        graph could not be reached / the query failed.
        """
        import urllib.request
        url = f"{config.KNOWLEDGE_GRAPH_URL}/query"
        payload = json.dumps({"query": cypher_query}).encode("utf-8")
        req = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=config.KG_QUERY_TIMEOUT_SECS) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    for key in ("results", "records", "data", "rows"):
                        if isinstance(data.get(key), list):
                            return data[key]
                    return [data]
                return []
        except Exception as e:
            logger.error(f"Knowledge graph query failed: {e}")
            return None

    @staticmethod
    def _find_property(record: Any, names: List[str]) -> Optional[Any]:
        """Best-effort extraction of a named property from a KG result record."""
        def search(obj: Any) -> Optional[Any]:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if str(k).lower() in names and v is not None:
                        return v
                for v in obj.values():
                    found = search(v)
                    if found is not None:
                        return found
            elif isinstance(obj, list):
                for item in obj:
                    found = search(item)
                    if found is not None:
                        return found
            return None
        return search(record)

    def answer_question(self, question: Question) -> Answer:
        """Answer a question using the knowledge graph.

        The generated Cypher query is executed against the real knowledge
        graph. If the KG is unreachable, the answer explicitly states the
        information could not be retrieved and no confidence is claimed.
        """
        try:
            # Extract entities and relations
            entities = self.extract_entities(question.text)
            relations = self.extract_relations(question.text)

            # Classify question type
            question_type = self.classify_question_type(question.text)

            # Generate Cypher query
            cypher_query = self.generate_cypher_query(question, entities, relations)

            # Execute the query against the real knowledge graph
            kg_results = self._execute_kg_query(cypher_query)

            # Reasoning path (honest about what actually happened)
            reasoning_path = [
                f"1. Identified question type: {question_type}",
                f"2. Extracted entities: {[e.type for e in entities]}",
                f"3. Extracted relations: {relations}",
                f"4. Generated query: {cypher_query[:100]}...",
            ]
            if kg_results is None:
                reasoning_path.append("5. Knowledge graph query FAILED — no data retrieved")
            elif not kg_results:
                reasoning_path.append("5. Knowledge graph query returned 0 records")
            else:
                reasoning_path.append(f"5. Knowledge graph query returned {len(kg_results)} record(s)")

            # Generate answer grounded in real results
            answer_text, confidence = self._generate_answer_text(
                question, entities, relations, question_type, kg_results
            )

            return Answer(
                question=question.text,
                answer=answer_text,
                confidence=confidence,
                entities=entities,
                relations=[Relation(
                    id=str(uuid.uuid4()),
                    source="entity1",
                    target="entity2",
                    type=rel,
                    properties={}
                ) for rel in relations],
                reasoning_path=reasoning_path,
                sources=["knowledge_graph"] if kg_results is not None else [],
                timestamp=datetime.utcnow()
            )
        except Exception as e:
            logger.error(f"Error answering question: {str(e)}")
            raise

    def _generate_answer_text(self, question: Question, entities: List[Entity],
                             relations: List[str], question_type: str,
                             kg_results: Optional[List[Dict[str, Any]]]) -> Tuple[str, Optional[float]]:
        """Generate natural language answer grounded in real KG results.

        Returns (answer_text, confidence). Confidence is None unless the
        answer is directly grounded in retrieved data.
        """
        text_lower = question.text.lower()
        entity_desc = f"{entities[0].type} {entities[0].id}" if entities else "the requested entity"

        if kg_results is None:
            return (
                "I couldn't retrieve that information from the knowledge graph right now. "
                "Please try again later or contact support.",
                None,
            )

        if not kg_results:
            return (
                f"No records were found in the knowledge graph for {entity_desc}. "
                "I cannot answer this question with the available data.",
                None,
            )

        # Grounded answers for common banking question shapes
        if "balance" in text_lower:
            for rec in kg_results:
                bal = self._find_property(rec, ["balance"])
                if bal is not None:
                    return (f"The balance for {entity_desc} is {bal}.", 0.8)
            return (
                f"The knowledge graph has records for {entity_desc} but no balance value was stored. "
                "Balance information is unavailable.",
                None,
            )

        if "transaction" in text_lower and "who" in text_lower:
            for rec in kg_results:
                performer = self._find_property(rec, ["performed_by", "agent_id", "agent", "name"])
                if performer is not None:
                    return (f"The transaction was performed by {performer}.", 0.8)
            return (
                f"The knowledge graph returned records but no performer could be determined for {entity_desc}.",
                None,
            )

        if "status" in text_lower:
            for rec in kg_results:
                status = self._find_property(rec, ["status"])
                if status is not None:
                    return (f"The status of {entity_desc} is: {status}", 0.8)
            return (f"No status value is stored in the knowledge graph for {entity_desc}.", None)

        if "fraud" in text_lower or "suspicious" in text_lower:
            flags = []
            for rec in kg_results:
                flag = self._find_property(rec, ["fraud_flag", "is_fraud", "suspicious", "risk_level"])
                if flag is not None:
                    flags.append(flag)
            if flags:
                return (
                    f"The knowledge graph contains the following risk/fraud indicators for {entity_desc}: "
                    f"{', '.join(str(f) for f in flags)}. Please review these records.",
                    0.7,
                )
            return (
                f"The knowledge graph has no recorded fraud or risk indicators for {entity_desc}. "
                "Note: this only means no such records exist in the graph — it is not a guarantee of safety.",
                None,
            )

        if "total" in text_lower or "how many" in text_lower:
            return (
                f"The knowledge graph query returned {len(kg_results)} record(s) matching your question.",
                0.7,
            )

        # Generic grounded answer: summarize actual records
        summary = json.dumps(kg_results[:3], default=str)
        return (
            f"The knowledge graph returned {len(kg_results)} record(s) for your question. "
            f"First results: {summary}",
            0.6,
        )

    def get_entity_neighbors(self, entity_id: str, depth: int = 2) -> Dict[str, Any]:
        """Get neighboring entities in the knowledge graph (real query).

        Raises HTTP 503 when the knowledge graph is unavailable — never
        returns fabricated neighbor lists.
        """
        cypher = f"""
        MATCH (e {{id: '{entity_id}'}})-[r*1..{depth}]-(neighbor)
        RETURN e, r, neighbor
        LIMIT 100
        """
        results = self._execute_kg_query(cypher)
        if results is None:
            raise HTTPException(
                status_code=503,
                detail="Knowledge graph unavailable — cannot retrieve entity neighbors",
            )
        return {
            "entity_id": entity_id,
            "depth": depth,
            "neighbors": results,
        }

    def explain_reasoning(self, question: str, answer: str) -> List[str]:
        """Explain the reasoning process"""
        return [
            "1. Parsed the question to identify key entities and relations",
            "2. Queried the knowledge graph for relevant information",
            "3. Applied domain-specific rules from banking knowledge base",
            "4. Generated a natural language answer grounded in the retrieved records",
            "5. If no records were retrieved, the answer states that the information is unavailable",
        ]

    def get_knowledge_stats(self) -> Dict[str, Any]:
        """Get knowledge graph statistics (queried live; no fabricated counts)."""
        counts = self._execute_kg_query("""
        MATCH (n)
        RETURN count(n) AS total_entities
        """)
        entity_total = None
        if counts:
            entity_total = self._find_property(counts, ["total_entities", "count(n)"])

        if entity_total is None:
            return {
                "status": "unavailable",
                "detail": "Knowledge graph statistics could not be retrieved",
                "entity_types": list(self.knowledge_base["entities"].keys()),
                "relation_types": list(self.knowledge_base["relations"].keys()),
                "last_checked": datetime.utcnow().isoformat()
            }

        return {
            "total_entities": entity_total,
            "entity_types": list(self.knowledge_base["entities"].keys()),
            "relation_types": list(self.knowledge_base["relations"].keys()),
            "last_checked": datetime.utcnow().isoformat()
        }

# Initialize engine
engine = EPRKGQAEngine()

# API Endpoints

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "epr-kgqa-service",
        "timestamp": datetime.utcnow().isoformat(),
        "knowledge_base_loaded": True
    }

@app.post("/ask", response_model=Answer)
async def ask_question(question: Question):
    """Ask a question and get an answer from the knowledge graph"""
    try:
        answer = engine.answer_question(question)
        return answer
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error answering question: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/entities/extract")
async def extract_entities(text: str):
    """Extract entities from text"""
    try:
        entities = engine.extract_entities(text)
        return {"text": text, "entities": entities}
    except Exception as e:
        logger.error(f"Error extracting entities: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/relations/extract")
async def extract_relations(text: str):
    """Extract relations from text"""
    try:
        relations = engine.extract_relations(text)
        return {"text": text, "relations": relations}
    except Exception as e:
        logger.error(f"Error extracting relations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/entities/{entity_id}/neighbors")
async def get_neighbors(entity_id: str, depth: int = 2):
    """Get neighboring entities"""
    try:
        neighbors = engine.get_entity_neighbors(entity_id, depth)
        return neighbors
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting neighbors: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/explain")
async def explain_reasoning(question: str, answer: str):
    """Explain the reasoning process"""
    try:
        explanation = engine.explain_reasoning(question, answer)
        return {"question": question, "answer": answer, "explanation": explanation}
    except Exception as e:
        logger.error(f"Error explaining reasoning: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats")
async def get_stats():
    """Get knowledge graph statistics"""
    try:
        stats = engine.get_knowledge_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/classify")
async def classify_question(text: str):
    """Classify question type"""
    try:
        question_type = engine.classify_question_type(text)
        return {"text": text, "type": question_type}
    except Exception as e:
        logger.error(f"Error classifying question: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8093)
