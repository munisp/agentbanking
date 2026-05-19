"""
Billing SLA Monitor — Sprint 81
Monitors billing SLA compliance, triggers alerts when thresholds are breached.
Middleware: Kafka (events), Redis (metrics cache), Postgres (SLA config),
OpenSearch (SLA history), Temporal (alert workflows), Dapr (notifications)
"""
import os
import json
import logging
import time
from datetime import datetime
from typing import Dict, List
from dataclasses import dataclass, asdict
from http.server import HTTPServer, BaseHTTPRequestHandler

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
