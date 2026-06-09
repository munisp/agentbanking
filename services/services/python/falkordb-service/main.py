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
FalkorDB Service
Graph Database Service for Remittance Platform
Provides graph-based data storage and querying using FalkorDB
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

apply_middleware(app, enable_auth=True)
setup_logging("falkordb-service")
app.include_router(metrics_router)

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

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/falkordb_service")

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
        conn.execute("INSERT INTO audit_log (action, entity_id, data) VALUES (?, ?, ?)", (action, entity_id, data))
        conn.commit()
        conn.close()
    except Exception:
        pass
    title="FalkorDB Service",
    description="Graph Database Service using FalkorDB",
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

