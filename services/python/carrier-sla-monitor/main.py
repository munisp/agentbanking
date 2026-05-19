"""Carrier SLA Monitor — Sprint 76
Track uptime/availability per carrier per region, SLA compliance scoring
"""
import json, time, os
from http.server import HTTPServer, BaseHTTPRequestHandler
from collections import defaultdict
from threading import Lock

SERVICE_NAME = "carrier-sla-monitor"
SERVICE_VERSION = "1.0.0"
DEFAULT_PORT = 9107

SLA_TARGETS = {
    "MTN": {"uptime": 99.5, "latency_ms": 200, "packet_loss": 2.0},
    "Airtel": {"uptime": 99.0, "latency_ms": 250, "packet_loss": 3.0},
    "Safaricom": {"uptime": 99.5, "latency_ms": 150, "packet_loss": 1.5},
    "Glo": {"uptime": 98.0, "latency_ms": 300, "packet_loss": 5.0},
    "9mobile": {"uptime": 97.5, "latency_ms": 350, "packet_loss": 5.0},
    "MTN_GH": {"uptime": 99.0, "latency_ms": 200, "packet_loss": 2.5},
    "Vodafone_GH": {"uptime": 99.0, "latency_ms": 220, "packet_loss": 3.0},
    "Orange_SN": {"uptime": 98.5, "latency_ms": 250, "packet_loss": 3.0},
    "MTN_ZA": {"uptime": 99.5, "latency_ms": 180, "packet_loss": 2.0},
    "Vodacom_ZA": {"uptime": 99.5, "latency_ms": 180, "packet_loss": 2.0},
}

class SLAMonitor:
    def __init__(self):
        self.lock = Lock()
        self.checks = defaultdict(list)  # carrier -> [{timestamp, up, latency, loss}]
        self.violations = []

    def record_check(self, carrier, region, up, latency_ms, packet_loss):
        with self.lock:
            key = f"{carrier}:{region}"
            self.checks[key].append({
                "timestamp": int(time.time() * 1000), "up": up,
                "latencyMs": latency_ms, "packetLossPct": packet_loss,
            })
            # Check SLA violations
            target = SLA_TARGETS.get(carrier, {"uptime": 99.0, "latency_ms": 300, "packet_loss": 5.0})
            violations = []
            if not up:
                violations.append(f"Downtime detected")
            if latency_ms > target["latency_ms"]:
                violations.append(f"Latency {latency_ms}ms exceeds SLA target {target['latency_ms']}ms")
            if packet_loss > target["packet_loss"]:
                violations.append(f"Packet loss {packet_loss}% exceeds SLA target {target['packet_loss']}%")
            for v in violations:
                self.violations.append({
                    "timestamp": int(time.time() * 1000), "carrier": carrier,
                    "region": region, "violation": v, "severity": "critical" if not up else "warning",
                })

    def get_summary(self):
        with self.lock:
            summary = {}
            for key, checks in self.checks.items():
                carrier, region = key.split(":", 1)
                total = len(checks)
                up_count = sum(1 for c in checks if c["up"])
                avg_latency = sum(c["latencyMs"] for c in checks) / total if total else 0
                avg_loss = sum(c["packetLossPct"] for c in checks) / total if total else 0
                uptime_pct = (up_count / total * 100) if total else 100
                target = SLA_TARGETS.get(carrier, {"uptime": 99.0, "latency_ms": 300, "packet_loss": 5.0})
                compliant = uptime_pct >= target["uptime"] and avg_latency <= target["latency_ms"] and avg_loss <= target["packet_loss"]
                summary[key] = {
                    "carrier": carrier, "region": region, "totalChecks": total,
                    "uptimePct": round(uptime_pct, 2), "avgLatencyMs": round(avg_latency, 1),
                    "avgPacketLossPct": round(avg_loss, 2), "slaCompliant": compliant,
                    "slaTarget": target,
                }
            return summary

monitor = SLAMonitor()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self._json({"service": SERVICE_NAME, "version": SERVICE_VERSION, "status": "healthy"})
        elif self.path.startswith("/api/sla/summary"):
            self._json(monitor.get_summary())
        elif self.path.startswith("/api/sla/violations"):
            with monitor.lock:
                self._json(monitor.violations[-100:])
        elif self.path.startswith("/api/sla/targets"):
            self._json(SLA_TARGETS)
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == "/api/sla/check":
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            monitor.record_check(body["carrier"], body["region"], body.get("up", True), body.get("latencyMs", 0), body.get("packetLossPct", 0))
            self._json({"status": "recorded"})
        else:
            self.send_error(404)

    def _json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, format, *args): pass

if __name__ == "__main__":
    port = int(os.environ.get("PORT", DEFAULT_PORT))
    print(f"[{SERVICE_NAME}] v{SERVICE_VERSION} listening on :{port}")
    HTTPServer(("", port), Handler).serve_forever()
