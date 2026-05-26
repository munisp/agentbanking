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
from pydantic import BaseModel

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


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("opensearch-indexer")

OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
OPENSEARCH_USER = os.getenv("OPENSEARCH_USER", "admin")
OPENSEARCH_PASS = os.getenv("OPENSEARCH_PASS", "admin")
PORT = int(os.getenv("PORT", "8092"))

app = FastAPI(title="54Link OpenSearch Indexer", version="1.0.0")

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


if __name__ == "__main__":
    import uvicorn

    logger.info("=" * 60)
    logger.info("  54Link OpenSearch Indexer v1.0.0")
    logger.info(f"  OpenSearch: {OPENSEARCH_URL}")
    logger.info(f"  Port: {PORT}")
    logger.info("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=PORT)
