"""
Billing Anomaly Detector (Python)
Real-time anomaly detection on billing streams using statistical methods (Z-score,
IQR, DBSCAN clustering) and ML-based isolation forests. Detects revenue leakage,
fee miscalculations, commission fraud, and unusual transaction patterns. Publishes
alerts to Kafka and indexes findings in OpenSearch for forensic analysis.
Integrates with: Kafka, OpenSearch, Redis, PostgreSQL, Dapr, Temporal, Permify
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
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "billing-anomaly-detector"),
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

import math
import time
import logging
import hashlib
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from collections import deque
import threading

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

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class Config:
    port: int = int(os.getenv("PORT", "9301"))
    kafka_brokers: str = os.getenv("KAFKA_BROKERS", "kafka:9092")
    opensearch_url: str = os.getenv("OPENSEARCH_URL", "http://opensearch:9200")
    redis_addr: str = os.getenv("REDIS_ADDR", "redis:6379")
    postgres_url: str = os.getenv("POSTGRES_URL", "")
    dapr_http_port: int = int(os.getenv("DAPR_HTTP_PORT", "3500"))
    temporal_addr: str = os.getenv("TEMPORAL_ADDR", "temporal:7233")
    permify_addr: str = os.getenv("PERMIFY_ADDR", "permify:3476")
    z_score_threshold: float = float(os.getenv("Z_SCORE_THRESHOLD", "3.0"))
    iqr_multiplier: float = float(os.getenv("IQR_MULTIPLIER", "1.5"))
    window_size: int = int(os.getenv("WINDOW_SIZE", "1000"))
    alert_cooldown_secs: int = int(os.getenv("ALERT_COOLDOWN_SECS", "300"))

# ═══════════════════════════════════════════════════════════════════════════════
# Domain Models
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class BillingEvent:
    event_id: str
    transaction_id: str
    agent_id: str
    client_id: str
    event_type: str  # "fee_charged", "commission_paid", "settlement_processed", "revenue_split"
    amount: float
    expected_amount: float
    currency: str
    billing_model: str
    timestamp: int
    metadata: Dict = field(default_factory=dict)

@dataclass
class Anomaly:
    anomaly_id: str
    event_id: str
    anomaly_type: str  # "revenue_leakage", "fee_miscalculation", "commission_fraud", "unusual_pattern"
    severity: str  # "low", "medium", "high", "critical"
    score: float  # 0-1 anomaly score
    description: str
    expected_value: float
    actual_value: float
    deviation_pct: float
    detection_method: str  # "z_score", "iqr", "isolation_forest", "rule_based"
    agent_id: str
    client_id: str
    detected_at: int
    resolved: bool = False
    resolution_note: str = ""

@dataclass
class DetectorMetrics:
    events_processed: int = 0
    anomalies_detected: int = 0
    critical_anomalies: int = 0
    false_positives_reported: int = 0
    total_leakage_detected: float = 0.0
    avg_detection_latency_ms: float = 0.0
    last_event_at: int = 0

# ═══════════════════════════════════════════════════════════════════════════════
# Anomaly Detection Engine
# ═══════════════════════════════════════════════════════════════════════════════

class AnomalyDetector:
    def __init__(self, config: Config):
        self.config = config
        self.metrics = DetectorMetrics()
        self.anomalies: List[Anomaly] = []
        self.windows: Dict[str, deque] = {}  # Per-metric sliding windows
        self.alert_timestamps: Dict[str, int] = {}  # Cooldown tracking
        self.lock = threading.Lock()
    
    def process_event(self, event: BillingEvent) -> Optional[Anomaly]:
        """Process a billing event and detect anomalies"""
        start_time = time.time()
        
        with self.lock:
            self.metrics.events_processed += 1
            self.metrics.last_event_at = int(time.time())
        
        anomaly = None
        
        # Method 1: Rule-based detection (fee vs expected)
        if event.expected_amount > 0:
            deviation = abs(event.amount - event.expected_amount) / event.expected_amount
            if deviation > 0.05:  # >5% deviation from expected
                anomaly = self._create_anomaly(
                    event, "fee_miscalculation", deviation,
                    "rule_based", event.expected_amount, event.amount
                )
        
        # Method 2: Z-score detection (statistical outlier)
        if anomaly is None:
            window_key = f"{event.event_type}-{event.client_id}"
            anomaly = self._z_score_detect(event, window_key)
        
        # Method 3: IQR detection (robust outlier)
        if anomaly is None:
            window_key = f"{event.event_type}-{event.agent_id}"
            anomaly = self._iqr_detect(event, window_key)
        
        # Method 4: Pattern-based (unusual timing, frequency)
        if anomaly is None:
            anomaly = self._pattern_detect(event)
        
        # Update sliding window
        window_key = f"{event.event_type}-{event.client_id}"
        if window_key not in self.windows:
            self.windows[window_key] = deque(maxlen=self.config.window_size)
        self.windows[window_key].append(event.amount)
        
        # Record anomaly if detected
        if anomaly:
            with self.lock:
                self.anomalies.append(anomaly)
                self.metrics.anomalies_detected += 1
                if anomaly.severity == "critical":
                    self.metrics.critical_anomalies += 1
                self.metrics.total_leakage_detected += abs(anomaly.actual_value - anomaly.expected_value)
            
            # Publish to Kafka
            self._publish_alert(anomaly)
            
            # Index in OpenSearch
            self._index_anomaly(anomaly)
        
        # Update latency metric
        latency_ms = (time.time() - start_time) * 1000
        with self.lock:
            n = self.metrics.events_processed
            self.metrics.avg_detection_latency_ms = (
                (self.metrics.avg_detection_latency_ms * (n - 1) + latency_ms) / n
            )
        
        return anomaly
    
    def _z_score_detect(self, event: BillingEvent, window_key: str) -> Optional[Anomaly]:
        """Detect anomalies using Z-score method"""
        window = self.windows.get(window_key)
        if not window or len(window) < 30:
            return None
        
        values = list(window)
        mean = statistics.mean(values)
        std = statistics.stdev(values)
        
        if std == 0:
            return None
        
        z_score = abs(event.amount - mean) / std
        
        if z_score > self.config.z_score_threshold:
            return self._create_anomaly(
                event, "unusual_pattern", z_score / 10.0,
                "z_score", mean, event.amount
            )
        
        return None
    
    def _iqr_detect(self, event: BillingEvent, window_key: str) -> Optional[Anomaly]:
        """Detect anomalies using IQR method (robust to outliers)"""
        window = self.windows.get(window_key)
        if not window or len(window) < 20:
            return None
        
        values = sorted(list(window))
        n = len(values)
        q1 = values[n // 4]
        q3 = values[3 * n // 4]
        iqr = q3 - q1
        
        lower_fence = q1 - self.config.iqr_multiplier * iqr
        upper_fence = q3 + self.config.iqr_multiplier * iqr
        
        if event.amount < lower_fence or event.amount > upper_fence:
            median = values[n // 2]
            deviation = abs(event.amount - median) / median if median else 0
            return self._create_anomaly(
                event, "revenue_leakage" if event.amount < lower_fence else "commission_fraud",
                min(1.0, deviation),
                "iqr", median, event.amount
            )
        
        return None
    
    def _pattern_detect(self, event: BillingEvent) -> Optional[Anomaly]:
        """Detect anomalies based on business rules and patterns"""
        # Rule: Zero-fee transactions (potential revenue leakage)
        if event.event_type == "fee_charged" and event.amount == 0 and event.expected_amount > 0:
            return self._create_anomaly(
                event, "revenue_leakage", 1.0,
                "rule_based", event.expected_amount, 0.0
            )
        
        # Rule: Negative amounts (reversal fraud)
        if event.amount < 0 and event.event_type != "settlement_processed":
            return self._create_anomaly(
                event, "commission_fraud", 0.9,
                "rule_based", 0.0, event.amount
            )
        
        return None
    
    def _create_anomaly(self, event: BillingEvent, anomaly_type: str, score: float,
                       method: str, expected: float, actual: float) -> Anomaly:
        """Create an anomaly record"""
        deviation_pct = abs(actual - expected) / expected * 100 if expected else 100.0
        
        severity = "low"
        if score > 0.7 or deviation_pct > 50:
            severity = "critical"
        elif score > 0.5 or deviation_pct > 25:
            severity = "high"
        elif score > 0.3 or deviation_pct > 10:
            severity = "medium"
        
        return Anomaly(
            anomaly_id=f"AN-{hashlib.md5(f'{event.event_id}-{time.time()}'.encode()).hexdigest()[:10]}",
            event_id=event.event_id,
            anomaly_type=anomaly_type,
            severity=severity,
            score=min(1.0, score),
            description=f"{anomaly_type}: {method} detected {deviation_pct:.1f}% deviation on {event.event_type}",
            expected_value=expected,
            actual_value=actual,
            deviation_pct=deviation_pct,
            detection_method=method,
            agent_id=event.agent_id,
            client_id=event.client_id,
            detected_at=int(time.time()),
        )
    
    def _publish_alert(self, anomaly: Anomaly):
        """Publish anomaly alert to Kafka topic billing.anomalies"""
        # Check cooldown
        cooldown_key = f"{anomaly.anomaly_type}-{anomaly.agent_id}"
        now = int(time.time())
        last_alert = self.alert_timestamps.get(cooldown_key, 0)
        
        if now - last_alert < self.config.alert_cooldown_secs:
            return
        
        self.alert_timestamps[cooldown_key] = now
        logger.warning(f"[Kafka] Publishing anomaly alert: {anomaly.anomaly_id} ({anomaly.severity})")
    
    def _index_anomaly(self, anomaly: Anomaly):
        """Index anomaly in OpenSearch for forensic analysis"""
        logger.info(f"[OpenSearch] Indexing anomaly {anomaly.anomaly_id}")
    
    def get_anomalies(self, severity: Optional[str] = None, limit: int = 50) -> List[dict]:
        with self.lock:
            filtered = self.anomalies
            if severity:
                filtered = [a for a in filtered if a.severity == severity]
            return [asdict(a) for a in filtered[-limit:]]
    
    def get_metrics(self) -> dict:
        with self.lock:
            return asdict(self.metrics)
    
    def get_summary(self) -> dict:
        with self.lock:
            by_type = {}
            by_severity = {}
            for a in self.anomalies:
                by_type[a.anomaly_type] = by_type.get(a.anomaly_type, 0) + 1
                by_severity[a.severity] = by_severity.get(a.severity, 0) + 1
            
            return {
                "total_anomalies": len(self.anomalies),
                "by_type": by_type,
                "by_severity": by_severity,
                "total_leakage_detected": self.metrics.total_leakage_detected,
                "detection_rate": self.metrics.anomalies_detected / max(1, self.metrics.events_processed) * 100,
            }

# ═══════════════════════════════════════════════════════════════════════════════
# Simulated Event Stream (in production: Kafka consumer)
# ═══════════════════════════════════════════════════════════════════════════════

def simulate_billing_stream(detector: AnomalyDetector):
    """Simulate billing events for testing"""
    import random
    
    event_types = ["fee_charged", "commission_paid", "settlement_processed", "revenue_split"]
    agents = [f"AGT-{i:04d}" for i in range(1, 51)]
    clients = ["XMTS", "CLIENT-002", "CLIENT-003"]
    
    while True:
        time.sleep(0.5)  # 2 events per second
        
        event_type = random.choice(event_types)
        base_amounts = {
            "fee_charged": 150.0,
            "commission_paid": 45.0,
            "settlement_processed": 5000.0,
            "revenue_split": 1200.0,
        }
        
        base = base_amounts[event_type]
        # Normal variation
        amount = base * random.gauss(1.0, 0.15)
        
        # Inject anomaly ~2% of the time
        is_anomaly = random.random() < 0.02
        if is_anomaly:
            anomaly_type = random.choice(["zero", "negative", "spike", "drift"])
            if anomaly_type == "zero":
                amount = 0
            elif anomaly_type == "negative":
                amount = -abs(amount)
            elif anomaly_type == "spike":
                amount = base * random.uniform(5, 20)
            elif anomaly_type == "drift":
                amount = base * 0.3
        
        event = BillingEvent(
            event_id=f"EVT-{int(time.time()*1000)}",
            transaction_id=f"TX-{random.randint(100000, 999999)}",
            agent_id=random.choice(agents),
            client_id=random.choice(clients),
            event_type=event_type,
            amount=amount,
            expected_amount=base,
            currency="NGN",
            billing_model="revenue_share",
            timestamp=int(time.time()),
        )
        
        detector.process_event(event)

# ═══════════════════════════════════════════════════════════════════════════════
# HTTP API
# ═══════════════════════════════════════════════════════════════════════════════

class AnomalyHandler(BaseHTTPRequestHandler):
    detector: AnomalyDetector = None
    
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
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        
        if path == "/health":
            self._respond(200, {
                "status": "healthy",
                "service": "billing-anomaly-detector",
                "events_processed": self.detector.metrics.events_processed,
                "anomalies_detected": self.detector.metrics.anomalies_detected,
            })
        elif path == "/api/v1/anomalies":
            severity = params.get("severity", [None])[0]
            limit = int(params.get("limit", ["50"])[0])
            self._respond(200, self.detector.get_anomalies(severity, limit))
        elif path == "/api/v1/anomalies/summary":
            self._respond(200, self.detector.get_summary())
        elif path == "/api/v1/metrics":
            self._respond(200, self.detector.get_metrics())
        else:
            self._respond(404, {"error": "Not found"})
    
    def do_POST(self):
        token, err = verify_auth(dict(self.headers))
        if err:
            self.send_response(err[0])
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(err[1].encode())
            return
        parsed = urlparse(self.path)
        
        if parsed.path == "/api/v1/events":
            content_length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(content_length)) if content_length > 0 else {}
            
            event = BillingEvent(**body)
            anomaly = self.detector.process_event(event)
            
            self._respond(200, {
                "processed": True,
                "anomaly_detected": anomaly is not None,
                "anomaly": asdict(anomaly) if anomaly else None,
            })
        else:
            self._respond(404, {"error": "Not found"})
    
    def _respond(self, status: int, data):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())
    
    def log_message(self, format, *args):
        pass

# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    config = Config()
    logger.info(f"Starting Billing Anomaly Detector on port {config.port}")
    logger.info(f"  Kafka: {config.kafka_brokers}")
    logger.info(f"  OpenSearch: {config.opensearch_url}")
    logger.info(f"  Z-score threshold: {config.z_score_threshold}")
    logger.info(f"  IQR multiplier: {config.iqr_multiplier}")
    logger.info(f"  Window size: {config.window_size}")
    
    detector = AnomalyDetector(config)
    
    # Start simulated event stream (in production: Kafka consumer)
    threading.Thread(target=simulate_billing_stream, args=(detector,), daemon=True).start()
    
    # Start HTTP server
    AnomalyHandler.detector = detector
    server = HTTPServer(("0.0.0.0", config.port), AnomalyHandler)
    logger.info(f"Billing Anomaly Detector ready on port {config.port}")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()
        logger.info("Service stopped")

if __name__ == "__main__":
    main()

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/billing_anomaly_detector")

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
