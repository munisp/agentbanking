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

apply_middleware(app)
setup_logging("epr-kgqa-service")
app.include_router(metrics_router)

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
