"""
OpenSearch Indexer — 54Link POS Shell (Sprint 89)

FastAPI service that receives batched transaction events from the Fluvio consumer
and indexes them into OpenSearch for real-time analytics queries.

Endpoints:
  POST /index         — Bulk index documents
  GET  /health        — Health check
  GET  /metrics       — Indexing metrics
  POST /search        — Proxy search to OpenSearch
  POST /create-index  — Create index with mapping
"""

import os
import json
import time
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from pydantic import BaseModel

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

# --- PostgreSQL Persistence ---
import asyncpg
from typing import Optional

_pg_pool: Optional[asyncpg.Pool] = None

async def get_pg_pool() -> Optional[asyncpg.Pool]:
    global _pg_pool
    if _pg_pool is None:
        try:
            _pg_pool = await asyncpg.create_pool(
                dsn=os.environ.get("DATABASE_URL", "postgresql://localhost:5432/agentbanking"),
                min_size=2, max_size=10, command_timeout=10
            )
            await _pg_pool.execute("""
                CREATE TABLE IF NOT EXISTS service_state (
                    key TEXT PRIMARY KEY,
                    value JSONB NOT NULL DEFAULT '{}',
                    service TEXT NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        except Exception:
            _pg_pool = None
    return _pg_pool

async def pg_get(key: str, service: str):
    pool = await get_pg_pool()
    if pool:
        row = await pool.fetchrow(
            "SELECT value FROM service_state WHERE key = $1 AND service = $2", key, service
        )
        return row["value"] if row else None
    return None

async def pg_set(key: str, value, service: str):
    pool = await get_pg_pool()
    if pool:
        import json
        await pool.execute(
            "INSERT INTO service_state (key, value, service, updated_at) VALUES ($1, $2::jsonb, $3, NOW()) "
            "ON CONFLICT (key) DO UPDATE SET value = $2::jsonb, updated_at = NOW()",
            key, json.dumps(value) if not isinstance(value, str) else value, service
        )
# --- End PostgreSQL Persistence ---


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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("opensearch-indexer")

OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
OPENSEARCH_USER = os.getenv("OPENSEARCH_USER", "admin")
OPENSEARCH_PASS = os.getenv("OPENSEARCH_PASS", "admin")
PORT = int(os.getenv("PORT", "8092"))

app = FastAPI(title="54Link OpenSearch Indexer", version="1.0.0")

@app.on_event("startup")
async def _init_pg_pool():
    await get_pg_pool()

apply_middleware(app, enable_auth=True)

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/opensearch_indexer")

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

# Metrics
metrics = {
    "total_indexed": 0,
    "total_errors": 0,
    "total_batches": 0,
    "last_index_time": None,
    "started_at": datetime.now(timezone.utc).isoformat(),
}

# ── Models ───────────────────────────────────────────────────────────────────

class IndexRequest(BaseModel):
    index: str = "transactions"
    documents: list[dict[str, Any]]
    batch_size: int | None = None

class SearchRequest(BaseModel):
    index: str = "transactions"
    query: dict[str, Any]
    size: int = 20
    from_: int = 0

class CreateIndexRequest(BaseModel):
    index: str
    mappings: dict[str, Any] | None = None
    settings: dict[str, Any] | None = None

# ── OpenSearch Client ────────────────────────────────────────────────────────

async def os_request(method: str, path: str, body: dict | None = None) -> dict:
    """Make HTTP request to OpenSearch."""
    import httpx

    url = f"{OPENSEARCH_URL}/{path}"
    auth = (OPENSEARCH_USER, OPENSEARCH_PASS)

    try:
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            if method == "GET":
                resp = await client.get(url, auth=auth)
            elif method == "POST":
                resp = await client.post(url, json=body, auth=auth)
            elif method == "PUT":
                resp = await client.put(url, json=body, auth=auth)
            else:
                raise ValueError(f"Unsupported method: {method}")

            return resp.json()
    except Exception as e:
        logger.error(f"OpenSearch request failed: {e}")
        raise HTTPException(status_code=502, detail=f"OpenSearch unavailable: {str(e)}")

async def bulk_index(index: str, documents: list[dict]) -> dict:
    """Bulk index documents using OpenSearch _bulk API."""
    import httpx

    lines = []
    for doc in documents:
        # Add indexing metadata
        doc["indexed_at"] = datetime.now(timezone.utc).isoformat()
        action = {"index": {"_index": index}}
        lines.append(json.dumps(action))
        lines.append(json.dumps(doc))

    bulk_body = "\n".join(lines) + "\n"

    try:
        async with httpx.AsyncClient(verify=False, timeout=60.0) as client:
            resp = await client.post(
                f"{OPENSEARCH_URL}/_bulk",
                content=bulk_body,
                headers={"Content-Type": "application/x-ndjson"},
                auth=(OPENSEARCH_USER, OPENSEARCH_PASS),
            )
            return resp.json()
    except Exception as e:
        logger.error(f"Bulk index failed: {e}")
        raise HTTPException(status_code=502, detail=f"Bulk index failed: {str(e)}")

# ── Transaction Index Mapping ────────────────────────────────────────────────

TRANSACTION_MAPPING = {
    "mappings": {
        "properties": {
            "transactionId": {"type": "keyword"},
            "tenantId": {"type": "keyword"},
            "userId": {"type": "keyword"},
            "amount": {"type": "float"},
            "currency": {"type": "keyword"},
            "status": {"type": "keyword"},
            "type": {"type": "keyword"},
            "invoiceId": {"type": "keyword"},
            "stripePaymentIntentId": {"type": "keyword"},
            "stripeSubscriptionId": {"type": "keyword"},
            "timestamp": {"type": "date"},
            "createdAt": {"type": "date"},
            "_topic": {"type": "keyword"},
            "_offset": {"type": "long"},
            "_ingested_at": {"type": "date"},
            "indexed_at": {"type": "date"},
            "metadata": {"type": "object", "enabled": True},
        }
    },
    "settings": {
        "number_of_shards": 2,
        "number_of_replicas": 1,
        "refresh_interval": "5s",
    },
}

# ── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/index")
async def index_documents(req: IndexRequest):
    """Bulk index documents from Fluvio consumer."""
    # Persist operation result to PostgreSQL
    import json as _json, time as _time
    await pg_set("index_documents_" + str(int(_time.time() * 1000)), _json.dumps({"action": "index_documents", "timestamp": _time.time()}), "opensearch-indexer")

    if not req.documents:
        return {"indexed": 0, "errors": 0}

    start = time.monotonic()

    try:
        result = await bulk_index(req.index, req.documents)
        elapsed = time.monotonic() - start

        errors = result.get("errors", False)
        indexed = len(req.documents)

        metrics["total_indexed"] += indexed
        metrics["total_batches"] += 1
        metrics["last_index_time"] = datetime.now(timezone.utc).isoformat()

        if errors:
            error_items = [
                item for item in result.get("items", [])
                if "error" in item.get("index", {})
            ]
            metrics["total_errors"] += len(error_items)
            logger.warning(f"Indexed {indexed} docs with {len(error_items)} errors in {elapsed:.2f}s")
        else:
            logger.info(f"Indexed {indexed} docs in {elapsed:.2f}s")

        return {
            "indexed": indexed,
            "errors": len(error_items) if errors else 0,
            "elapsed_ms": round(elapsed * 1000),
        }
    except HTTPException:
        raise
    except Exception as e:
        metrics["total_errors"] += len(req.documents)
        logger.error(f"Index batch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/search")
async def search_documents(req: SearchRequest):
    """Proxy search request to OpenSearch."""
    # Persist operation result to PostgreSQL
    import json as _json, time as _time
    await pg_set("search_documents_" + str(int(_time.time() * 1000)), _json.dumps({"action": "search_documents", "timestamp": _time.time()}), "opensearch-indexer")

    body = {
        "query": req.query,
        "size": req.size,
        "from": req.from_,
    }
    result = await os_request("POST", f"{req.index}/_search", body)
    return result

@app.post("/create-index")
async def create_index(req: CreateIndexRequest):
    """Create an OpenSearch index with optional mappings."""
    # Persist operation result to PostgreSQL
    import json as _json, time as _time
    await pg_set("create_index_" + str(int(_time.time() * 1000)), _json.dumps({"action": "create_index", "timestamp": _time.time()}), "opensearch-indexer")

    body = req.mappings or TRANSACTION_MAPPING
    if req.settings:
        body["settings"] = req.settings

    result = await os_request("PUT", req.index, body)
    logger.info(f"Created index '{req.index}': {result}")
    return result

@app.get("/health")
async def health():
    """Health check."""
    os_healthy = False
    try:
        import httpx
        async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
            resp = await client.get(
                f"{OPENSEARCH_URL}/_cluster/health",
                auth=(OPENSEARCH_USER, OPENSEARCH_PASS),
            )
            os_healthy = resp.status_code == 200
    except Exception:
        pass

    return {
        "status": "healthy",
        "service": "opensearch-indexer",
        "version": "1.0.0",
        "opensearch": "connected" if os_healthy else "unavailable",
        "opensearch_url": OPENSEARCH_URL,
    }

@app.get("/metrics")
async def get_metrics():
    """Indexing metrics."""
    return {
        **metrics,
        "uptime_seconds": round(
            (datetime.now(timezone.utc) - datetime.fromisoformat(metrics["started_at"])).total_seconds()
        ),
    }

# ── Settlement & Reconciliation Indexing Pipeline ────────────────────────────

SETTLEMENT_MAPPING = {
    "mappings": {
        "properties": {
            "batch_id": {"type": "keyword"},
            "batch_ref": {"type": "keyword"},
            "terminal_id": {"type": "keyword"},
            "agent_id": {"type": "keyword"},
            "status": {"type": "keyword"},
            "total_amount": {"type": "float"},
            "net_amount": {"type": "float"},
            "total_fees": {"type": "float"},
            "transaction_count": {"type": "integer"},
            "settlement_ref": {"type": "keyword"},
            "settled_at": {"type": "date"},
            "created_at": {"type": "date"},
            "indexed_at": {"type": "date"},
        }
    },
    "settings": {"number_of_shards": 2, "number_of_replicas": 1, "refresh_interval": "5s"},
}

RECONCILIATION_MAPPING = {
    "mappings": {
        "properties": {
            "reconciliation_id": {"type": "keyword"},
            "period": {"type": "keyword"},
            "status": {"type": "keyword"},
            "revenue_variance_pct": {"type": "float"},
            "volume_variance_pct": {"type": "float"},
            "agent_variance_pct": {"type": "float"},
            "projected_revenue": {"type": "float"},
            "actual_revenue": {"type": "float"},
            "generated_at": {"type": "date"},
            "indexed_at": {"type": "date"},
        }
    },
    "settings": {"number_of_shards": 1, "number_of_replicas": 1, "refresh_interval": "10s"},
}

class SettlementIndexRequest(BaseModel):
    documents: list[dict[str, Any]]

class ReconciliationIndexRequest(BaseModel):
    documents: list[dict[str, Any]]

@app.post("/index/settlements")
async def index_settlements(req: SettlementIndexRequest):
    """Index settlement batch documents into OpenSearch."""
    if not req.documents:
        return {"indexed": 0, "errors": 0}

    start = time.monotonic()
    try:
        result = await bulk_index("settlement-batches", req.documents)
        elapsed = time.monotonic() - start
        indexed = len(req.documents)
        metrics["total_indexed"] += indexed
        metrics["total_batches"] += 1
        logger.info(f"Indexed {indexed} settlement docs in {elapsed:.2f}s")
        log_audit("INDEX_SETTLEMENTS", f"batch_{indexed}", json.dumps({"count": indexed}))
        return {"indexed": indexed, "errors": 0, "elapsed_ms": round(elapsed * 1000)}
    except HTTPException:
        raise
    except Exception as e:
        metrics["total_errors"] += len(req.documents)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/index/reconciliations")
async def index_reconciliations(req: ReconciliationIndexRequest):
    """Index reconciliation report documents into OpenSearch."""
    if not req.documents:
        return {"indexed": 0, "errors": 0}

    start = time.monotonic()
    try:
        result = await bulk_index("reconciliation-reports", req.documents)
        elapsed = time.monotonic() - start
        indexed = len(req.documents)
        metrics["total_indexed"] += indexed
        metrics["total_batches"] += 1
        logger.info(f"Indexed {indexed} reconciliation docs in {elapsed:.2f}s")
        log_audit("INDEX_RECONCILIATIONS", f"recon_{indexed}", json.dumps({"count": indexed}))
        return {"indexed": indexed, "errors": 0, "elapsed_ms": round(elapsed * 1000)}
    except HTTPException:
        raise
    except Exception as e:
        metrics["total_errors"] += len(req.documents)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/create-settlement-index")
async def create_settlement_index():
    """Create the settlement-batches index with proper mappings."""
    result = await os_request("PUT", "settlement-batches", SETTLEMENT_MAPPING)
    logger.info(f"Created settlement-batches index: {result}")
    return result

@app.post("/create-reconciliation-index")
async def create_reconciliation_index():
    """Create the reconciliation-reports index with proper mappings."""
    result = await os_request("PUT", "reconciliation-reports", RECONCILIATION_MAPPING)
    logger.info(f"Created reconciliation-reports index: {result}")
    return result

if __name__ == "__main__":
    import uvicorn

    logger.info("=" * 60)
    logger.info("  54Link OpenSearch Indexer v2.0.0")
    logger.info(f"  OpenSearch: {OPENSEARCH_URL}")
    logger.info(f"  Port: {PORT}")
    logger.info(f"  Settlement & Reconciliation pipeline: enabled")
    logger.info("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=PORT)
