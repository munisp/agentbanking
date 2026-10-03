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

_shutdown_handlers = _PgListStore("falkordb_service__shutdown_handlers", "FALKORDB_SERVICE_DATABASE_URL")  # round-11 wave-7 persistence

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
FalkorDB Service
Graph Database Service for Remittance Platform
Provides graph-based data storage and querying using FalkorDB
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware


from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
import logging
import os
import uuid
import json
from falkordb import FalkorDB

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="FalkorDB Service",
    description="Graph Database Service using FalkorDB",
    version="1.0.0"
)

apply_middleware(app)
setup_logging("falkordb-service")
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
    FALKORDB_HOST = os.getenv("FALKORDB_HOST", "localhost")
    FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", "6379"))
    FALKORDB_PASSWORD = os.getenv("FALKORDB_PASSWORD", None)
    DEFAULT_GRAPH = os.getenv("DEFAULT_GRAPH", "remittance")

config = Config()

# Models
class Node(BaseModel):
    id: Optional[str] = None
    label: str
    properties: Dict[str, Any] = {}

class Edge(BaseModel):
    id: Optional[str] = None
    source: str
    target: str
    type: str
    properties: Dict[str, Any] = {}

class CypherQuery(BaseModel):
    query: str
    parameters: Dict[str, Any] = {}
    graph: Optional[str] = None

class GraphStats(BaseModel):
    graph_name: str
    node_count: int
    edge_count: int
    labels: List[str]
    relationship_types: List[str]

class TransactionNode(BaseModel):
    transaction_id: str
    amount: float
    timestamp: datetime
    status: str
    metadata: Dict[str, Any] = {}

class AgentNode(BaseModel):
    agent_id: str
    name: str
    email: str
    phone: str
    status: str
    metadata: Dict[str, Any] = {}

# FalkorDB Engine
class FalkorDBEngine:
    def __init__(self):
        self.client = None
        self.graphs = {}
        self.initialize()
    
    def initialize(self):
        """Initialize FalkorDB connection"""
        try:
            logger.info("Initializing FalkorDB connection...")
            
            # Connect to FalkorDB
            self.client = FalkorDB(
                host=config.FALKORDB_HOST,
                port=config.FALKORDB_PORT,
                password=config.FALKORDB_PASSWORD
            )
            
            # Get or create default graph
            self.graphs[config.DEFAULT_GRAPH] = self.client.select_graph(config.DEFAULT_GRAPH)
            
            logger.info("FalkorDB connection established successfully")
        except Exception as e:
            logger.error(f"Error initializing FalkorDB: {str(e)}")
            raise
    
    def get_graph(self, graph_name: str = None):
        """Get or create a graph"""
        if graph_name is None:
            graph_name = config.DEFAULT_GRAPH
        
        if graph_name not in self.graphs:
            self.graphs[graph_name] = self.client.select_graph(graph_name)
        
        return self.graphs[graph_name]
    
    def execute_query(self, query: str, parameters: Dict[str, Any] = None, graph_name: str = None):
        """Execute a Cypher query"""
        try:
            graph = self.get_graph(graph_name)
            
            if parameters:
                result = graph.query(query, parameters)
            else:
                result = graph.query(query)
            
            return result
        except Exception as e:
            logger.error(f"Error executing query: {str(e)}")
            raise
    
    def create_node(self, node: Node, graph_name: str = None) -> str:
        """Create a node in the graph"""
        try:
            if not node.id:
                node.id = str(uuid.uuid4())
            
            # Build properties string
            props = {**node.properties, "id": node.id}
            props_str = ", ".join([f"{k}: ${k}" for k in props.keys()])
            
            query = f"CREATE (n:{node.label} {{{props_str}}}) RETURN n.id"
            
            result = self.execute_query(query, props, graph_name)
            
            logger.info(f"Created node with ID: {node.id}")
            return node.id
        except Exception as e:
            logger.error(f"Error creating node: {str(e)}")
            raise
    
    def create_edge(self, edge: Edge, graph_name: str = None) -> str:
        """Create an edge in the graph"""
        try:
            if not edge.id:
                edge.id = str(uuid.uuid4())
            
            # Build properties string
            props = {**edge.properties, "id": edge.id}
            props_str = ", ".join([f"{k}: ${k}" for k in props.keys()])
            
            query = f"""
            MATCH (a {{id: $source}}), (b {{id: $target}})
            CREATE (a)-[r:{edge.type} {{{props_str}}}]->(b)
            RETURN r.id
            """
            
            params = {**props, "source": edge.source, "target": edge.target}
            result = self.execute_query(query, params, graph_name)
            
            logger.info(f"Created edge with ID: {edge.id}")
            return edge.id
        except Exception as e:
            logger.error(f"Error creating edge: {str(e)}")
            raise
    
    def get_node(self, node_id: str, graph_name: str = None) -> Optional[Dict[str, Any]]:
        """Get a node by ID"""
        try:
            query = "MATCH (n {id: $node_id}) RETURN n"
            result = self.execute_query(query, {"node_id": node_id}, graph_name)
            
            if result.result_set:
                return result.result_set[0][0]
            return None
        except Exception as e:
            logger.error(f"Error getting node: {str(e)}")
            raise
    
    def find_path(self, source_id: str, target_id: str, max_depth: int = 5, graph_name: str = None):
        """Find shortest path between two nodes"""
        try:
            query = f"""
            MATCH path = shortestPath((a {{id: $source}})-[*..{max_depth}]-(b {{id: $target}}))
            RETURN path
            """
            
            result = self.execute_query(
                query,
                {"source": source_id, "target": target_id},
                graph_name
            )
            
            return result.result_set if result.result_set else []
        except Exception as e:
            logger.error(f"Error finding path: {str(e)}")
            raise
    
    def get_neighbors(self, node_id: str, depth: int = 1, graph_name: str = None):
        """Get neighbors of a node"""
        try:
            query = f"""
            MATCH (n {{id: $node_id}})-[*1..{depth}]-(neighbor)
            RETURN DISTINCT neighbor
            """
            
            result = self.execute_query(query, {"node_id": node_id}, graph_name)
            
            return result.result_set if result.result_set else []
        except Exception as e:
            logger.error(f"Error getting neighbors: {str(e)}")
            raise
    
    def get_stats(self, graph_name: str = None) -> GraphStats:
        """Get graph statistics"""
        try:
            graph = self.get_graph(graph_name)
            
            # Get node count
            node_result = graph.query("MATCH (n) RETURN count(n) as count")
            node_count = node_result.result_set[0][0] if node_result.result_set else 0
            
            # Get edge count
            edge_result = graph.query("MATCH ()-[r]->() RETURN count(r) as count")
            edge_count = edge_result.result_set[0][0] if edge_result.result_set else 0
            
            # Get labels
            label_result = graph.query("CALL db.labels()")
            labels = [row[0] for row in label_result.result_set] if label_result.result_set else []
            
            # Get relationship types
            rel_result = graph.query("CALL db.relationshipTypes()")
            rel_types = [row[0] for row in rel_result.result_set] if rel_result.result_set else []
            
            return GraphStats(
                graph_name=graph_name or config.DEFAULT_GRAPH,
                node_count=node_count,
                edge_count=edge_count,
                labels=labels,
                relationship_types=rel_types
            )
        except Exception as e:
            logger.error(f"Error getting stats: {str(e)}")
            raise
    
    def create_transaction_graph(self, transaction: TransactionNode, agent_id: str, graph_name: str = None):
        """Create a transaction node and link to agent"""
        try:
            # Create transaction node
            tx_node = Node(
                id=transaction.transaction_id,
                label="Transaction",
                properties={
                    "amount": transaction.amount,
                    "timestamp": transaction.timestamp.isoformat(),
                    "status": transaction.status,
                    **transaction.metadata
                }
            )
            self.create_node(tx_node, graph_name)
            
            # Create edge from agent to transaction
            edge = Edge(
                source=agent_id,
                target=transaction.transaction_id,
                type="PERFORMED",
                properties={"timestamp": transaction.timestamp.isoformat()}
            )
            self.create_edge(edge, graph_name)
            
            logger.info(f"Created transaction graph for {transaction.transaction_id}")
            return transaction.transaction_id
        except Exception as e:
            logger.error(f"Error creating transaction graph: {str(e)}")
            raise
    
    def detect_fraud_patterns(self, agent_id: str, graph_name: str = None):
        """Detect fraud patterns using graph queries"""
        try:
            patterns = []
            
            # Pattern 1: Rapid transactions
            query1 = """
            MATCH (a:Agent {id: $agent_id})-[:PERFORMED]->(t:Transaction)
            WHERE t.timestamp > datetime() - duration('PT1H')
            RETURN count(t) as count
            """
            result1 = self.execute_query(query1, {"agent_id": agent_id}, graph_name)
            if result1.result_set and result1.result_set[0][0] > 10:
                patterns.append({
                    "type": "rapid_transactions",
                    "severity": "high",
                    "description": f"More than 10 transactions in the last hour"
                })
            
            # Pattern 2: Unusual amount
            query2 = """
            MATCH (a:Agent {id: $agent_id})-[:PERFORMED]->(t:Transaction)
            RETURN avg(t.amount) as avg_amount, max(t.amount) as max_amount
            """
            result2 = self.execute_query(query2, {"agent_id": agent_id}, graph_name)
            if result2.result_set:
                avg_amount = result2.result_set[0][0]
                max_amount = result2.result_set[0][1]
                if max_amount > avg_amount * 5:
                    patterns.append({
                        "type": "unusual_amount",
                        "severity": "medium",
                        "description": f"Transaction amount significantly higher than average"
                    })
            
            # Pattern 3: Connected to suspicious agents
            query3 = """
            MATCH (a:Agent {id: $agent_id})-[:TRANSFERRED_TO]->(b:Agent)
            WHERE b.status = 'suspended'
            RETURN count(b) as count
            """
            result3 = self.execute_query(query3, {"agent_id": agent_id}, graph_name)
            if result3.result_set and result3.result_set[0][0] > 0:
                patterns.append({
                    "type": "suspicious_connections",
                    "severity": "high",
                    "description": "Connected to suspended agents"
                })
            
            return patterns
        except Exception as e:
            logger.error(f"Error detecting fraud patterns: {str(e)}")
            raise

# Initialize engine
engine = FalkorDBEngine()

# API Endpoints

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "falkordb-service",
        "timestamp": datetime.utcnow().isoformat(),
        "connected": engine.client is not None
    }

@app.post("/nodes", response_model=Dict[str, str])
async def create_node(node: Node, graph: Optional[str] = None):
    """Create a node in the graph"""
    try:
        node_id = engine.create_node(node, graph)
        return {"id": node_id, "message": "Node created successfully"}
    except Exception as e:
        logger.error(f"Error creating node: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/edges", response_model=Dict[str, str])
async def create_edge(edge: Edge, graph: Optional[str] = None):
    """Create an edge in the graph"""
    try:
        edge_id = engine.create_edge(edge, graph)
        return {"id": edge_id, "message": "Edge created successfully"}
    except Exception as e:
        logger.error(f"Error creating edge: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/nodes/{node_id}")
async def get_node(node_id: str, graph: Optional[str] = None):
    """Get a node by ID"""
    try:
        node = engine.get_node(node_id, graph)
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")
        return node
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting node: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/query")
async def execute_query(query: CypherQuery):
    """Execute a Cypher query"""
    try:
        result = engine.execute_query(query.query, query.parameters, query.graph)
        return {
            "result_set": result.result_set if hasattr(result, 'result_set') else [],
            "statistics": result.statistics if hasattr(result, 'statistics') else {}
        }
    except Exception as e:
        logger.error(f"Error executing query: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats", response_model=GraphStats)
async def get_stats(graph: Optional[str] = None):
    """Get graph statistics"""
    try:
        return engine.get_stats(graph)
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/path/{source_id}/{target_id}")
async def find_path(source_id: str, target_id: str, max_depth: int = 5, graph: Optional[str] = None):
    """Find shortest path between two nodes"""
    try:
        path = engine.find_path(source_id, target_id, max_depth, graph)
        return {"path": path}
    except Exception as e:
        logger.error(f"Error finding path: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/neighbors/{node_id}")
async def get_neighbors(node_id: str, depth: int = 1, graph: Optional[str] = None):
    """Get neighbors of a node"""
    try:
        neighbors = engine.get_neighbors(node_id, depth, graph)
        return {"neighbors": neighbors}
    except Exception as e:
        logger.error(f"Error getting neighbors: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/transactions")
async def create_transaction(transaction: TransactionNode, agent_id: str, graph: Optional[str] = None):
    """Create a transaction node and link to agent"""
    try:
        tx_id = engine.create_transaction_graph(transaction, agent_id, graph)
        return {"transaction_id": tx_id, "message": "Transaction created successfully"}
    except Exception as e:
        logger.error(f"Error creating transaction: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/fraud/detect/{agent_id}")
async def detect_fraud(agent_id: str, graph: Optional[str] = None):
    """Detect fraud patterns for an agent"""
    try:
        patterns = engine.detect_fraud_patterns(agent_id, graph)
        return {"agent_id": agent_id, "patterns": patterns, "risk_level": "high" if patterns else "low"}
    except Exception as e:
        logger.error(f"Error detecting fraud: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8091)

