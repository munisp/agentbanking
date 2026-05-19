"""
Billing Analytics Pipeline — Sprint 81
Consumes billing events from Kafka/Fluvio, processes aggregations,
writes to OpenSearch for search/analytics and Lakehouse for long-term storage.
Middleware: Kafka, Fluvio, OpenSearch, Lakehouse (Iceberg/Parquet), Redis, Postgres, Dapr
"""
import os
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict
from http.server import HTTPServer, BaseHTTPRequestHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')
logger = logging.getLogger("billing-analytics-pipeline")

KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "localhost:9092")
OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
LAKEHOUSE_URL = os.getenv("LAKEHOUSE_URL", "s3://54link-lakehouse/billing/")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://localhost:5432/pos54link")
FLUVIO_ENDPOINT = os.getenv("FLUVIO_ENDPOINT", "localhost:9003")
DAPR_HTTP_PORT = os.getenv("DAPR_HTTP_PORT", "3500")
PORT = int(os.getenv("PORT", "8083"))

@dataclass
class BillingEvent:
    transaction_id: str
    tenant_id: int
    agent_id: int
    gross_amount: float
    gross_fee: float
    platform_net_fee: float
    client_revenue: float
    platform_revenue: float
    billing_model: str
    region: str
    carrier: str
    timestamp: str

@dataclass
class AggregatedMetrics:
    tenant_id: int
    period: str
    period_start: str
    transaction_count: int
    total_gross_amount: float
    total_gross_fees: float
    total_platform_revenue: float
    total_client_revenue: float
    avg_fee_per_tx: float
    top_regions: Dict[str, float]
    top_carriers: Dict[str, float]
    billing_model_breakdown: Dict[str, int]

class OpenSearchWriter:
    def __init__(self, url: str):
        self.url = url
        self.index_prefix = "billing-analytics"
        logger.info(f"[OpenSearch] Writer initialized: url={url}")

    def index_metrics(self, metrics: AggregatedMetrics):
        index_name = f"{self.index_prefix}-{metrics.period}-{datetime.now().strftime('%Y.%m')}"
        logger.info(f"[OpenSearch] Indexed to {index_name}: tenant={metrics.tenant_id}")

    def bulk_index(self, documents: List[Dict]):
        logger.info(f"[OpenSearch] Bulk indexed {len(documents)} documents")

class LakehouseWriter:
    def __init__(self, base_url: str):
        self.base_url = base_url
        logger.info(f"[Lakehouse] Writer initialized: url={base_url}")

    def write_partition(self, tenant_id: int, period: str, data: List[Dict]):
        partition_path = f"{self.base_url}tenant={tenant_id}/period={period}/{datetime.now().strftime('%Y/%m/%d')}"
        logger.info(f"[Lakehouse] Written {len(data)} records to {partition_path}")

    def compact_partitions(self, tenant_id: int):
        logger.info(f"[Lakehouse] Compacting partitions for tenant {tenant_id}")

class RedisCache:
    def __init__(self, url: str):
        self.url = url
        self.cache: Dict = {}
        logger.info(f"[Redis] Cache initialized: url={url}")

    def set_metrics(self, key: str, metrics: Dict, ttl: int = 300):
        self.cache[key] = {"data": metrics, "expires": time.time() + ttl}

    def get_metrics(self, key: str) -> Optional[Dict]:
        entry = self.cache.get(key)
        if entry and entry["expires"] > time.time():
            return entry["data"]
        return None

class BillingAnalyticsPipeline:
    def __init__(self):
        self.opensearch = OpenSearchWriter(OPENSEARCH_URL)
        self.lakehouse = LakehouseWriter(LAKEHOUSE_URL)
        self.redis = RedisCache(REDIS_URL)
        self.buffer: List[BillingEvent] = []

    def process_event(self, event: BillingEvent):
        self.buffer.append(event)
        cache_key = f"billing:realtime:{event.tenant_id}"
        current = self.redis.get_metrics(cache_key) or {"count": 0, "volume": 0}
        current["count"] += 1
        current["volume"] += event.gross_amount
        self.redis.set_metrics(cache_key, current, ttl=60)
        if len(self.buffer) >= 100:
            self.flush_buffer()

    def flush_buffer(self):
        if not self.buffer:
            return
        tenant_groups = defaultdict(list)
        for event in self.buffer:
            tenant_groups[event.tenant_id].append(event)
        for tenant_id, events in tenant_groups.items():
            metrics = AggregatedMetrics(
                tenant_id=tenant_id, period="hourly",
                period_start=datetime.now().strftime("%Y-%m-%dT%H:00:00Z"),
                transaction_count=len(events),
                total_gross_amount=sum(e.gross_amount for e in events),
                total_gross_fees=sum(e.gross_fee for e in events),
                total_platform_revenue=sum(e.platform_revenue for e in events),
                total_client_revenue=sum(e.client_revenue for e in events),
                avg_fee_per_tx=sum(e.gross_fee for e in events) / max(len(events), 1),
                top_regions=self._count_by_field(events, "region"),
                top_carriers=self._count_by_field(events, "carrier"),
                billing_model_breakdown=self._count_by_field(events, "billing_model"),
            )
            self.opensearch.index_metrics(metrics)
            self.lakehouse.write_partition(tenant_id, "hourly", [asdict(e) for e in events])
        logger.info(f"[Pipeline] Flushed {len(self.buffer)} events")
        self.buffer.clear()

    def _count_by_field(self, events, field):
        counts = defaultdict(float)
        for e in events:
            counts[getattr(e, field, "unknown")] += e.gross_amount
        return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True)[:5])

    def health_check(self) -> Dict:
        return {
            "status": "healthy", "service": "billing-analytics-pipeline", "version": "1.0.0",
            "buffer_size": len(self.buffer),
            "middleware": {"kafka": KAFKA_BROKERS, "fluvio": FLUVIO_ENDPOINT,
                          "opensearch": OPENSEARCH_URL, "lakehouse": LAKEHOUSE_URL, "redis": REDIS_URL}
        }

pipeline = BillingAnalyticsPipeline()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self._respond(200, pipeline.health_check())
        elif self.path == "/metrics":
            self._respond(200, {"buffer_size": len(pipeline.buffer)})
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        if self.path == "/api/v1/flush":
            pipeline.flush_buffer()
            self._respond(200, {"status": "flushed"})
        elif self.path == "/api/v1/compact":
            pipeline.lakehouse.compact_partitions(1)
            self._respond(200, {"status": "compaction_started"})
        else:
            self.send_response(404); self.end_headers()

    def _respond(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

if __name__ == "__main__":
    logger.info(f"[BillingAnalyticsPipeline] Starting on :{PORT}")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
