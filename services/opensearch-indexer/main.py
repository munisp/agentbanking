"""
OpenSearch Indexer — 54agent POS Shell (Sprint 89)

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


_shutdown_handlers = _PgListStore("opensearch_indexer__shutdown_handlers", "OPENSEARCH_INDEXER_DATABASE_URL")  # round-11 wave-7 persistence

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

app = FastAPI(title="54agent OpenSearch Indexer", version="1.0.0")

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
    logger.info("  54agent OpenSearch Indexer v1.0.0")
    logger.info(f"  OpenSearch: {OPENSEARCH_URL}")
    logger.info(f"  Port: {PORT}")
    logger.info("=" * 60)

    uvicorn.run(app, host="0.0.0.0", port=PORT)
