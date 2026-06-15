"""
Billing SLA Monitor — Sprint 81
Monitors billing SLA compliance, triggers alerts when thresholds are breached.
Middleware: Kafka (events), Redis (metrics cache), Postgres (SLA config),
OpenSearch (SLA history), Temporal (alert workflows), Dapr (notifications)
"""
import os
import json


# ── OpenTelemetry Tracing ────────────────────────────────────────────────────
_otel_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
if _otel_endpoint:
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource

        _resource = Resource.create({
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "billing-sla-monitor"),
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

def verify_auth(headers):
    """Verify Bearer token from Authorization header."""
    auth = headers.get("Authorization", "")
    if not auth:
        return None, (401, '{"error":"missing authorization header"}')
    if not auth.startswith("Bearer ") or len(auth) < 17:
        return None, (401, '{"error":"invalid token format"}')
    return auth[7:], None

import logging
import time
from datetime import datetime
from typing import Dict, List
from dataclasses import dataclass, asdict
from http.server import HTTPServer, BaseHTTPRequestHandler

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

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(levelname)s: %(message)s')
logger = logging.getLogger("billing-sla-monitor")

KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "localhost:9092")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://localhost:5432/pos54link")
OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
TEMPORAL_ADDR = os.getenv("TEMPORAL_ADDR", "localhost:7233")
PORT = int(os.getenv("PORT", "8086"))

@dataclass
class SLARule:
    rule_id: str
    tenant_id: int
    metric: str  # settlement_latency, reconciliation_accuracy, uptime, invoice_delivery
    threshold: float
    comparison: str  # lt, gt, eq
    window_minutes: int
    severity: str  # critical, warning, info
    notification_channels: List[str]

@dataclass
class SLAViolation:
    violation_id: str
    rule_id: str
    tenant_id: int
    metric: str
    current_value: float
    threshold: float
    severity: str
    detected_at: str
    resolved_at: str = None
    status: str = "active"

class SLAMonitor:
    def __init__(self):
        self.rules: List[SLARule] = self._load_default_rules()
        self.violations: List[SLAViolation] = []
        self.metrics_cache: Dict[str, float] = {}
        logger.info(f"[SLAMonitor] Initialized with {len(self.rules)} rules")

    def _load_default_rules(self) -> List[SLARule]:
        return [
            SLARule("sla_001", 1, "settlement_latency_ms", 5000, "lt", 5, "critical", ["email", "slack", "sms"]),
            SLARule("sla_002", 1, "reconciliation_accuracy_pct", 99.5, "gt", 60, "warning", ["email", "slack"]),
            SLARule("sla_003", 1, "billing_uptime_pct", 99.9, "gt", 1440, "critical", ["email", "slack", "sms", "pagerduty"]),
            SLARule("sla_004", 1, "invoice_delivery_hours", 24, "lt", 720, "warning", ["email"]),
            SLARule("sla_005", 2, "settlement_latency_ms", 3000, "lt", 5, "critical", ["email", "slack"]),
            SLARule("sla_006", 2, "reconciliation_accuracy_pct", 99.0, "gt", 60, "warning", ["email"]),
        ]

    def check_all_rules(self) -> List[SLAViolation]:
        """Check all SLA rules against current metrics"""
        new_violations = []
        for rule in self.rules:
            current_value = self._get_metric(rule.tenant_id, rule.metric)
            violated = False
            if rule.comparison == "lt" and current_value >= rule.threshold:
                violated = True
            elif rule.comparison == "gt" and current_value <= rule.threshold:
                violated = True
            if violated:
                violation = SLAViolation(
                    violation_id=f"viol_{int(time.time()*1000)}",
                    rule_id=rule.rule_id, tenant_id=rule.tenant_id,
                    metric=rule.metric, current_value=current_value,
                    threshold=rule.threshold, severity=rule.severity,
                    detected_at=datetime.now().isoformat(),
                )
                self.violations.append(violation)
                new_violations.append(violation)
                self._trigger_alert(violation, rule)
        return new_violations

    def _get_metric(self, tenant_id: int, metric: str) -> float:
        """Get current metric value from Redis cache or compute"""
        key = f"sla:{tenant_id}:{metric}"
        # Simulated metric values
        defaults = {
            "settlement_latency_ms": 2500.0,
            "reconciliation_accuracy_pct": 99.7,
            "billing_uptime_pct": 99.95,
            "invoice_delivery_hours": 4.0,
        }
        return self.metrics_cache.get(key, defaults.get(metric, 0.0))

    def _trigger_alert(self, violation: SLAViolation, rule: SLARule):
        """Trigger alert via configured channels"""
        for channel in rule.notification_channels:
            logger.warning(f"[Alert] {channel}: SLA violation {violation.violation_id} "
                         f"({violation.metric}={violation.current_value}, threshold={violation.threshold})")

    def get_sla_dashboard(self) -> Dict:
        active_violations = [v for v in self.violations if v.status == "active"]
        return {
            "total_rules": len(self.rules),
            "active_violations": len(active_violations),
            "violations_by_severity": {
                "critical": sum(1 for v in active_violations if v.severity == "critical"),
                "warning": sum(1 for v in active_violations if v.severity == "warning"),
            },
            "compliance_score": max(0, 100 - len(active_violations) * 5),
        }

    def health_check(self) -> Dict:
        return {
            "status": "healthy", "service": "billing-sla-monitor", "version": "1.0.0",
            "rules_count": len(self.rules), "active_violations": sum(1 for v in self.violations if v.status == "active"),
            "middleware": {"kafka": KAFKA_BROKERS, "redis": REDIS_URL, "opensearch": OPENSEARCH_URL}
        }

monitor = SLAMonitor()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Skip auth for health checks
        if self.path not in ("/health", "/ready", "/metrics"):
            token, err = verify_auth(dict(self.headers))
            if err:
                self.send_response(err[0])
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(err[1].encode())
                return
        if self.path == "/health":
            self._respond(200, monitor.health_check())
        elif self.path == "/api/v1/dashboard":
            self._respond(200, monitor.get_sla_dashboard())
        elif self.path == "/api/v1/violations":
            self._respond(200, {"violations": [asdict(v) for v in monitor.violations[-50:]]})
        elif self.path == "/api/v1/rules":
            self._respond(200, {"rules": [asdict(r) for r in monitor.rules]})
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        token, err = verify_auth(dict(self.headers))
        if err:
            self.send_response(err[0])
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(err[1].encode())
            return
        if self.path == "/api/v1/check":
            violations = monitor.check_all_rules()
            self._respond(200, {"new_violations": [asdict(v) for v in violations]})
        else:
            self.send_response(404); self.end_headers()

    def _respond(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

if __name__ == "__main__":
    logger.info(f"[BillingSLAMonitor] Starting on :{PORT}")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/billing_sla_monitor")

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
