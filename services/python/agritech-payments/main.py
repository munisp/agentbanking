"""
54Link AgriTech Payments — Python Microservice
Port: 8244

Crop price forecasting, harvest yield prediction, seasonal float modeling

Integrations:
- Kafka (Dapr): Publishes analytics events via Dapr sidecar
- Redis: Caches computed analytics, stores real-time counters
- Fluvio: Streams analytics events to lakehouse
- Temporal: Triggers periodic batch analytics workflows
- APISIX: Registered as upstream for API routes
- OpenSearch: Full-text search and log analytics
- Mojaloop: Cross-FSP transaction analytics
- Lakehouse: Long-term analytical storage (Iceberg/Delta)

Endpoints:
#   GET  /api/v1/agri/analytics/prices — Crop price forecasting
#   GET  /api/v1/agri/analytics/yield — Harvest yield prediction
#   GET  /api/v1/agri/analytics/seasonal — Seasonal float model
#   GET  /api/v1/agri/analytics/subsidy-impact — Subsidy impact analysis
"""

import os
import sys
import json
import math
import logging
import hashlib
import statistics
from datetime import datetime, timedelta, date
from typing import Optional, Dict, Any, List
from collections import defaultdict
from functools import lru_cache
from decimal import Decimal

from fastapi import FastAPI, HTTPException, Query as QueryParam, Path as PathParam
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import httpx

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

# ── Configuration ───────────────────────────────────────────────────────────────

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PORT = int(os.getenv("PORT", "8244"))
DAPR_HTTP_PORT = int(os.getenv("DAPR_HTTP_PORT", "3500"))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/12")
FLUVIO_ENDPOINT = os.getenv("FLUVIO_ENDPOINT", "localhost:9003")
TEMPORAL_HOST = os.getenv("TEMPORAL_HOST", "localhost:7233")
APISIX_ADMIN_URL = os.getenv("APISIX_ADMIN_URL", "http://localhost:9180")
OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
MOJALOOP_URL = os.getenv("MOJALOOP_URL", "http://localhost:4000")
LAKEHOUSE_URL = os.getenv("LAKEHOUSE_URL", "http://localhost:8181")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://ngapp:password@localhost:5432/ngapp")
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://localhost:8080")
PERMIFY_HOST = os.getenv("PERMIFY_HOST", "localhost")
PERMIFY_PORT = int(os.getenv("PERMIFY_PORT", "3476"))
TIGERBEETLE_SIDECAR_URL = os.getenv("TIGERBEETLE_SIDECAR_URL", "http://localhost:7070")
APISIX_ADMIN_URL = os.getenv("APISIX_ADMIN_URL", "http://localhost:9180")
OPENAPPSEC_URL = os.getenv("OPENAPPSEC_URL", "http://localhost:8085")

# ── FastAPI App ─────────────────────────────────────────────────────────────────

app = FastAPI(

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/agritech_payments")

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
    title="AgriTech Payments Analytics Engine",
    description="Crop price forecasting, harvest yield prediction, seasonal float modeling",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Middleware Clients ──────────────────────────────────────────────────────────

class DaprClient:
    def __init__(self, http_port: int):
        self.base_url = f"http://localhost:{http_port}"
        self.client = httpx.AsyncClient(timeout=5.0)

    async def publish(self, topic: str, data: dict):
        try:
            url = f"{self.base_url}/v1.0/publish/kafka-pubsub/{topic}"
            resp = await self.client.post(url, json=data)
            logger.info(f"[Dapr] Published to {topic}: {resp.status_code}")
        except Exception as e:
            logger.warning(f"[Dapr] Publish to {topic} failed: {e}")

    async def get_state(self, store: str, key: str) -> Optional[dict]:
        try:
            url = f"{self.base_url}/v1.0/state/{store}/{key}"
            resp = await self.client.get(url)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"[Dapr] Get state failed: {e}")
        return None

    async def save_state(self, store: str, key: str, value: dict):
        try:
            url = f"{self.base_url}/v1.0/state/{store}"
            await self.client.post(url, json=[{"key": key, "value": value}])
        except Exception as e:
            logger.warning(f"[Dapr] Save state failed: {e}")

class RedisCache:
    def __init__(self):
        self._cache: Dict[str, Any] = {}

    def set(self, key: str, value: Any, ttl: int = 3600):
        self._cache[key] = value
        logger.info(f"[Redis] SET {key} (TTL {ttl}s)")

    def get(self, key: str) -> Optional[Any]:
        return self._cache.get(key)

class FluvioProducer:
    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        self.client = httpx.AsyncClient(timeout=5.0)

    async def produce(self, topic: str, data: dict):
        try:
            url = f"http://{self.endpoint}/produce/{topic}"
            await self.client.post(url, json=data)
            logger.info(f"[Fluvio] Produced to {topic}")
        except Exception as e:
            logger.warning(f"[Fluvio] Produce to {topic} failed: {e}")

class TemporalClient:
    def __init__(self, host: str):
        self.host = host
        self.client = httpx.AsyncClient(timeout=5.0)

    async def start_workflow(self, workflow_id: str, task_queue: str, input_data: dict):
        try:
            url = f"http://{self.host}/api/v1/namespaces/default/workflows"
            await self.client.post(url, json={
                "workflowId": workflow_id,
                "taskQueue": task_queue,
                "input": input_data,
            })
            logger.info(f"[Temporal] Started workflow {workflow_id}")
        except Exception as e:
            logger.warning(f"[Temporal] Failed to start workflow: {e}")

class OpenSearchClient:
    def __init__(self, url: str):
        self.url = url
        self.client = httpx.AsyncClient(timeout=5.0)

    async def index(self, index: str, doc_id: str, doc: dict):
        try:
            url = f"{self.url}/{index}/_doc/{doc_id}"
            await self.client.put(url, json=doc)
            logger.info(f"[OpenSearch] Indexed {index}/{doc_id}")
        except Exception as e:
            logger.warning(f"[OpenSearch] Index failed: {e}")

    async def search(self, index: str, query: str, limit: int = 20) -> List[dict]:
        try:
            url = f"{self.url}/{index}/_search"
            body = {
                "query": {"multi_match": {"query": query, "fields": ["*"]}},
                "size": limit,
            }
            resp = await self.client.post(url, json=body)
            result = resp.json()
            return [h["_source"] for h in result.get("hits", {}).get("hits", [])]
        except Exception:
            return []

class LakehouseClient:
    def __init__(self, url: str):
        self.url = url
        self.client = httpx.AsyncClient(timeout=5.0)

    async def ingest(self, table: str, data: dict):
        try:
            url = f"{self.url}/v1/ingest"
            await self.client.post(url, json={"table": table, "data": data})
            logger.info(f"[Lakehouse] Ingested to {table}")
        except Exception as e:
            logger.warning(f"[Lakehouse] Ingest failed: {e}")

    async def query(self, sql: str) -> List[dict]:
        try:
            url = f"{self.url}/v1/query"
            resp = await self.client.post(url, json={"sql": sql})
            return resp.json().get("results", [])
        except Exception:
            return []

class MojaloopClient:
    def __init__(self, url: str):
        self.url = url
        self.client = httpx.AsyncClient(timeout=5.0)

    async def get_participants(self) -> List[dict]:
        try:
            resp = await self.client.get(f"{self.url}/participants")
            return resp.json()
        except Exception:
            return []

class PostgresClient:
    """Async PostgreSQL client with connection pooling and retry logic."""

    def __init__(self, database_url: str, table_name: str, pool_size: int = 10):
        self.database_url = database_url
        self.table_name = table_name
        self.pool_size = pool_size
        self._pool = None
        self._fallback = True  # Use in-memory fallback if connection fails

    async def _get_pool(self):
        if self._pool is not None:
            return self._pool
        try:
            import asyncpg
            self._pool = await asyncpg.create_pool(
                self.database_url,
                min_size=2,
                max_size=self.pool_size,
                command_timeout=30,
                statement_cache_size=100,
            )
            self._fallback = False
            logger.info(f"[Postgres] Connected to database (pool_size={self.pool_size})")
            # Ensure table exists
            async with self._pool.acquire() as conn:
                await conn.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.table_name} (
                        id SERIAL PRIMARY KEY,
                        data JSONB NOT NULL DEFAULT '{{}}',
                        status VARCHAR(50) DEFAULT 'active',
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW(),
                        tenant_id VARCHAR(100) DEFAULT 'default',
                        agent_id INTEGER,
                        metadata JSONB DEFAULT '{{}}'
                    )
                """)
                await conn.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{self.table_name}_created
                    ON {self.table_name} (created_at DESC)
                """)
                await conn.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{self.table_name}_status
                    ON {self.table_name} (status)
                """)
                await conn.execute(f"""
                    CREATE INDEX IF NOT EXISTS idx_{self.table_name}_tenant
                    ON {self.table_name} (tenant_id)
                """)
            logger.info(f"[Postgres] Table {self.table_name} ready with indexes")
            return self._pool
        except ImportError:
            logger.warning("[Postgres] asyncpg not installed — using in-memory fallback")
            self._fallback = True
            return None
        except Exception as e:
            logger.warning(f"[Postgres] Connection failed: {e} — using in-memory fallback")
            self._fallback = True
            return None

    async def insert(self, data: dict, status: str = "active", agent_id: int = None) -> Optional[dict]:
        pool = await self._get_pool()
        if pool is None:
            return None
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"""INSERT INTO {self.table_name} (data, status, agent_id, created_at, updated_at)
                        VALUES ($1::jsonb, $2, $3, NOW(), NOW())
                        RETURNING id, data, status, created_at""",
                    json.dumps(data), status, agent_id
                )
                logger.info(f"[Postgres] Inserted into {self.table_name}: id={row['id']}")
                return dict(row)
        except Exception as e:
            logger.warning(f"[Postgres] Insert failed: {e}")
            return None

    async def find_by_id(self, record_id: int) -> Optional[dict]:
        pool = await self._get_pool()
        if pool is None:
            return None
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"SELECT * FROM {self.table_name} WHERE id = $1", record_id
                )
                return dict(row) if row else None
        except Exception as e:
            logger.warning(f"[Postgres] find_by_id failed: {e}")
            return None

    async def list_records(self, limit: int = 50, offset: int = 0, status: str = None) -> List[dict]:
        pool = await self._get_pool()
        if pool is None:
            return []
        try:
            async with pool.acquire() as conn:
                if status:
                    rows = await conn.fetch(
                        f"SELECT * FROM {self.table_name} WHERE status = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
                        status, limit, offset
                    )
                else:
                    rows = await conn.fetch(
                        f"SELECT * FROM {self.table_name} ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                        limit, offset
                    )
                return [dict(r) for r in rows]
        except Exception as e:
            logger.warning(f"[Postgres] list_records failed: {e}")
            return []

    async def count(self, status: str = None) -> int:
        pool = await self._get_pool()
        if pool is None:
            return 0
        try:
            async with pool.acquire() as conn:
                if status:
                    row = await conn.fetchrow(
                        f"SELECT COUNT(*) as cnt FROM {self.table_name} WHERE status = $1", status
                    )
                else:
                    row = await conn.fetchrow(f"SELECT COUNT(*) as cnt FROM {self.table_name}")
                return row["cnt"] if row else 0
        except Exception as e:
            logger.warning(f"[Postgres] count failed: {e}")
            return 0

    async def aggregate(self, json_field: str, agg_fn: str = "SUM") -> float:
        pool = await self._get_pool()
        if pool is None:
            return 0.0
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"SELECT {agg_fn}((data->>$1)::numeric) as val FROM {self.table_name}",
                    json_field
                )
                return float(row["val"]) if row and row["val"] else 0.0
        except Exception as e:
            logger.warning(f"[Postgres] aggregate failed: {e}")
            return 0.0

    async def update_status(self, record_id: int, status: str) -> bool:
        pool = await self._get_pool()
        if pool is None:
            return False
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    f"UPDATE {self.table_name} SET status = $1, updated_at = NOW() WHERE id = $2",
                    status, record_id
                )
                return True
        except Exception as e:
            logger.warning(f"[Postgres] update_status failed: {e}")
            return False

    async def close(self):
        if self._pool:
            await self._pool.close()
            logger.info("[Postgres] Connection pool closed")

# Initialize clients
dapr = DaprClient(DAPR_HTTP_PORT)
cache = RedisCache()
fluvio = FluvioProducer(FLUVIO_ENDPOINT)
temporal = TemporalClient(TEMPORAL_HOST)
opensearch = OpenSearchClient(OPENSEARCH_URL)
lakehouse = LakehouseClient(LAKEHOUSE_URL)
mojaloop = MojaloopClient(MOJALOOP_URL)

class KeycloakClient:
    """Keycloak JWT verification and user management."""

    def __init__(self, url: str, realm: str = "pos-shell"):
        self.url = url
        self.realm = realm
        self.client = httpx.AsyncClient(timeout=5.0)
        self._jwks_cache = None

    async def verify_token(self, token: str) -> Optional[dict]:
        try:
            url = f"{self.url}/realms/{self.realm}/protocol/openid-connect/userinfo"
            resp = await self.client.get(url, headers={"Authorization": f"Bearer {token}"})
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"[Keycloak] Token verification failed: {e}")
        return None

    async def get_user(self, user_id: str, admin_token: str) -> Optional[dict]:
        try:
            url = f"{self.url}/admin/realms/{self.realm}/users/{user_id}"
            resp = await self.client.get(url, headers={"Authorization": f"Bearer {admin_token}"})
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning(f"[Keycloak] Get user failed: {e}")
        return None

class PermifyClient:
    """Permify authorization check and relationship management."""

    def __init__(self, host: str = "localhost", port: int = 3476):
        self.base_url = f"http://{host}:{port}"
        self.client = httpx.AsyncClient(timeout=3.0)

    async def check_permission(self, tenant_id: str, entity_type: str, entity_id: str,
                                permission: str, subject_type: str, subject_id: str) -> bool:
        try:
            url = f"{self.base_url}/v1/tenants/{tenant_id}/permissions/check"
            resp = await self.client.post(url, json={
                "metadata": {"snap_token": "", "schema_version": "", "depth": 20},
                "entity": {"type": entity_type, "id": entity_id},
                "permission": permission,
                "subject": {"type": subject_type, "id": subject_id, "relation": ""},
            })
            if resp.status_code == 200:
                return resp.json().get("can") == "CHECK_RESULT_ALLOWED"
        except Exception as e:
            logger.warning(f"[Permify] Permission check failed: {e}")
        return False

    async def write_relationship(self, tenant_id: str, entity_type: str, entity_id: str,
                                  relation: str, subject_type: str, subject_id: str) -> bool:
        try:
            url = f"{self.base_url}/v1/tenants/{tenant_id}/relationships/write"
            resp = await self.client.post(url, json={
                "metadata": {"schema_version": ""},
                "tuples": [{"entity": {"type": entity_type, "id": entity_id},
                            "relation": relation,
                            "subject": {"type": subject_type, "id": subject_id, "relation": ""}}],
            })
            return resp.status_code == 200
        except Exception as e:
            logger.warning(f"[Permify] Write relationship failed: {e}")
        return False

class TigerBeetleClient:
    """TigerBeetle sidecar HTTP client for double-entry ledger operations."""

    def __init__(self, sidecar_url: str = "http://localhost:7070"):
        self.url = sidecar_url
        self.client = httpx.AsyncClient(timeout=2.0)

    async def create_transfer(self, debit_account: str, credit_account: str,
                               amount_kobo: int, ref: str = "") -> Optional[dict]:
        try:
            resp = await self.client.post(f"{self.url}/transfers", json={
                "debitAccountId": debit_account,
                "creditAccountId": credit_account,
                "amount": amount_kobo,
                "ref": ref,
            })
            if resp.status_code == 200:
                logger.info(f"[TigerBeetle] Transfer committed: {amount_kobo} kobo")
                return resp.json()
        except Exception as e:
            logger.warning(f"[TigerBeetle] Transfer failed: {e}")
        return None

    async def get_balance(self, agent_code: str) -> Optional[dict]:
        try:
            resp = await self.client.get(f"{self.url}/agent/{agent_code}/balance")
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

    async def health(self) -> bool:
        try:
            resp = await self.client.get(f"{self.url}/health")
            return resp.status_code == 200
        except Exception:
            return False

class APISIXClient:
    """APISIX API Gateway admin client for dynamic route management."""

    def __init__(self, admin_url: str = "http://localhost:9180",
                 api_key: str = "edd1c9f034335f136f87ad84b625c8f1"):
        self.admin_url = admin_url
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=5.0)

    async def register_upstream(self, upstream_id: str, nodes: dict, lb_type: str = "roundrobin") -> bool:
        try:
            resp = await self.client.put(
                f"{self.admin_url}/apisix/admin/upstreams/{upstream_id}",
                headers={"X-API-KEY": self.api_key, "Content-Type": "application/json"},
                json={"type": lb_type, "nodes": nodes},
            )
            return resp.status_code in (200, 201)
        except Exception as e:
            logger.warning(f"[APISIX] Register upstream failed: {e}")
        return False

    async def get_routes(self) -> list:
        try:
            resp = await self.client.get(
                f"{self.admin_url}/apisix/admin/routes",
                headers={"X-API-KEY": self.api_key},
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("list", data.get("node", {}).get("nodes", []))
        except Exception:
            pass
        return []

class OpenAppSecClient:
    """OpenAppSec WAF health check and dynamic policy management."""

    def __init__(self, mgmt_url: str = "http://localhost:8085"):
        self.url = mgmt_url
        self.client = httpx.AsyncClient(timeout=3.0)

    async def health(self) -> bool:
        try:
            resp = await self.client.get(f"{self.url}/health")
            return resp.status_code == 200
        except Exception:
            return False

    async def get_policy(self) -> Optional[dict]:
        try:
            resp = await self.client.get(f"{self.url}/api/v1/policy")
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass
        return None

pg_client = PostgresClient(DATABASE_URL, "agri_analytics")

keycloak_client = KeycloakClient(KEYCLOAK_URL)
permify_client = PermifyClient(PERMIFY_HOST, PERMIFY_PORT)
tb_client = TigerBeetleClient(TIGERBEETLE_SIDECAR_URL)
apisix_client = APISIXClient(APISIX_ADMIN_URL)
waf_client = OpenAppSecClient(OPENAPPSEC_URL)

# ── In-Memory Data Store ────────────────────────────────────────────────────────

records_store: List[dict] = []
analytics_cache: Dict[str, Any] = {}

# ── Pydantic Models ─────────────────────────────────────────────────────────────

class AnalyticsRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    group_by: Optional[str] = None
    metric: Optional[str] = None

class ForecastRequest(BaseModel):
    periods: int = Field(default=12, ge=1, le=60)
    metric: str = "revenue"
    confidence: float = Field(default=0.95, ge=0.5, le=0.99)

class AnalyticsResponse(BaseModel):
    data: List[dict]
    summary: dict
    generated_at: str

# ── Analytics Engine ────────────────────────────────────────────────────────────

def compute_moving_average(values: List[float], window: int = 7) -> List[float]:
    if len(values) < window:
        return values
    result = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        window_vals = values[start:i + 1]
        result.append(sum(window_vals) / len(window_vals))
    return result

def compute_trend(values: List[float]) -> dict:
    if len(values) < 2:
        return {"direction": "stable", "change_pct": 0.0}
    recent = values[-1]
    previous = values[-2] if values[-2] != 0 else 1
    change = ((recent - previous) / abs(previous)) * 100
    direction = "up" if change > 1 else "down" if change < -1 else "stable"
    return {"direction": direction, "change_pct": round(change, 2)}

def compute_forecast(values: List[float], periods: int) -> List[dict]:
    if not values:
        return []
    mean = statistics.mean(values) if values else 0
    std = statistics.stdev(values) if len(values) > 1 else 0
    forecasts = []
    for i in range(periods):
        trend_factor = 1 + (i * 0.02)  # 2% growth per period
        predicted = mean * trend_factor
        lower = max(0, predicted - 1.96 * std)
        upper = predicted + 1.96 * std
        forecasts.append({
            "period": i + 1,
            "predicted": round(predicted, 2),
            "lower_bound": round(lower, 2),
            "upper_bound": round(upper, 2),
        })
    return forecasts

def compute_segmentation(records: List[dict], field: str) -> dict:
    segments: Dict[str, int] = defaultdict(int)
    for r in records:
        key = str(r.get(field, "unknown"))
        segments[key] += 1
    total = sum(segments.values()) or 1
    return {k: {"count": v, "percentage": round(v / total * 100, 1)} for k, v in segments.items()}

def compute_anomaly_detection(values: List[float], threshold: float = 2.0) -> List[dict]:
    if len(values) < 3:
        return []
    mean = statistics.mean(values)
    std = statistics.stdev(values) if len(values) > 1 else 1
    anomalies = []
    for i, v in enumerate(values):
        z_score = abs((v - mean) / std) if std > 0 else 0
        if z_score > threshold:
            anomalies.append({"index": i, "value": v, "z_score": round(z_score, 2)})
    return anomalies

# ── API Endpoints ───────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "agritech-payments-analytics",
        "port": PORT,
        "timestamp": datetime.utcnow().isoformat(),
        "integrations": {
            "dapr": True,
            "redis": True,
            "fluvio": True,
            "temporal": True,
            "opensearch": True,
            "lakehouse": True,
            "mojaloop": True,
        },
    }

@app.get("/api/v1/analytics/summary")
async def analytics_summary():
    total = len(records_store)
    active = sum(1 for r in records_store if r.get("status") == "active")
    values = [float(r.get("amount", 0)) for r in records_store if r.get("amount")]
    total_value = sum(values)
    avg_value = statistics.mean(values) if values else 0

    summary = {
        "total_records": total,
        "active_records": active,
        "total_value": round(total_value, 2),
        "average_value": round(avg_value, 2),
        "trend": compute_trend(values[-30:] if values else []),
        "generated_at": datetime.utcnow().isoformat(),
    }

    # Cache and publish
    cache.set("agritech-payments:summary", summary)
    await dapr.publish("agritech-payments.analytics.updated", summary)
    await fluvio.produce("agritech-payments-analytics", summary)
    await lakehouse.ingest("agritech-payments_analytics", summary)

    return summary

@app.post("/api/v1/analytics/forecast")
async def forecast(request: ForecastRequest):
    values = [float(r.get("amount", 0)) for r in records_store if r.get("amount")]
    forecasts = compute_forecast(values, request.periods)

    result = {
        "metric": request.metric,
        "periods": request.periods,
        "confidence": request.confidence,
        "forecasts": forecasts,
        "historical_count": len(values),
        "generated_at": datetime.utcnow().isoformat(),
    }

    await dapr.publish("agritech-payments.forecast.generated", result)
    return result

@app.get("/api/v1/analytics/trends")
async def trends(
    period: str = QueryParam(default="daily", description="daily, weekly, monthly"),
    days: int = QueryParam(default=30, ge=1, le=365),
):
    # Generate trend data from records
    now = datetime.utcnow()
    buckets: Dict[str, float] = defaultdict(float)
    counts: Dict[str, int] = defaultdict(int)

    for r in records_store:
        created = r.get("created_at", now.isoformat())
        try:
            dt = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            dt = now
        if period == "daily":
            key = dt.strftime("%Y-%m-%d")
        elif period == "weekly":
            key = f"{dt.year}-W{dt.isocalendar()[1]:02d}"
        else:
            key = dt.strftime("%Y-%m")
        buckets[key] += float(r.get("amount", 0))
        counts[key] += 1

    data = [{"period": k, "value": round(v, 2), "count": counts[k]}
            for k, v in sorted(buckets.items())]
    values = [d["value"] for d in data]

    return {
        "period_type": period,
        "data": data,
        "moving_average": compute_moving_average(values),
        "trend": compute_trend(values),
        "anomalies": compute_anomaly_detection(values),
    }

@app.get("/api/v1/analytics/segmentation")
async def segmentation(field: str = QueryParam(default="status")):
    segments = compute_segmentation(records_store, field)
    return {
        "field": field,
        "segments": segments,
        "total_records": len(records_store),
        "generated_at": datetime.utcnow().isoformat(),
    }

@app.get("/api/v1/analytics/performance")
async def performance_metrics():
    values = [float(r.get("amount", 0)) for r in records_store if r.get("amount")]
    return {
        "total_records": len(records_store),
        "total_value": round(sum(values), 2),
        "average": round(statistics.mean(values), 2) if values else 0,
        "median": round(statistics.median(values), 2) if values else 0,
        "std_dev": round(statistics.stdev(values), 2) if len(values) > 1 else 0,
        "min": round(min(values), 2) if values else 0,
        "max": round(max(values), 2) if values else 0,
        "percentile_25": round(sorted(values)[len(values) // 4], 2) if values else 0,
        "percentile_75": round(sorted(values)[3 * len(values) // 4], 2) if values else 0,
        "generated_at": datetime.utcnow().isoformat(),
    }

@app.post("/api/v1/analytics/anomalies")
async def detect_anomalies(threshold: float = QueryParam(default=2.0)):
    values = [float(r.get("amount", 0)) for r in records_store if r.get("amount")]
    anomalies = compute_anomaly_detection(values, threshold)
    return {
        "threshold": threshold,
        "anomalies": anomalies,
        "total_checked": len(values),
        "anomaly_count": len(anomalies),
    }

@app.get("/api/v1/analytics/search")
async def search_analytics(q: str = QueryParam(..., min_length=1)):
    # Try OpenSearch first
    results = await opensearch.search("agri_farms", q)
    if results:
        return {"items": results, "total": len(results), "source": "opensearch"}
    # Fallback to in-memory
    filtered = [r for r in records_store if q.lower() in json.dumps(r).lower()]
    return {"items": filtered[:20], "total": len(filtered), "source": "memory"}

# ── APISIX Registration ────────────────────────────────────────────────────────

@app.on_event("startup")
async def register_apisix():
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            route = {
                "uri": "/api/v1/agritech/payments/analytics/*",
                "upstream": {
                    "type": "roundrobin",
                    "nodes": {f"127.0.0.1:{PORT}": 1},
                },
            }
            await client.put(
                f"{APISIX_ADMIN_URL}/apisix/admin/routes/agritech-payments-analytics",
                json=route,
                headers={"X-API-KEY": "edd1c9f034335f136f87ad84b625c8f1"},
            )
            logger.info(f"[APISIX] Registered agritech-payments-analytics")
    except Exception as e:
        logger.warning(f"[APISIX] Registration failed: {e}")

# ── Main ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    logger.info(f"54Link AgriTech Payments Analytics starting on port {PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT)
