# connectivity-analytics: real-time metrics and analytics for network quality
"""
connectivity-analytics — 54Link Connectivity Analytics Service

Aggregates network telemetry from all terminals, generates heatmaps,
detects outage patterns, and provides carrier SLA compliance reports.

HTTP API (port 8082):
  POST /api/telemetry         — ingest terminal telemetry
  GET  /api/heatmap           — network quality heatmap by region
  GET  /api/outages           — detected outage events
  GET  /api/carrier-sla       — carrier SLA compliance
  POST /api/alert/configure   — configure alerting thresholds
  GET  /api/alerts            — list active alerts
  GET  /api/dashboard         — aggregated dashboard data
  GET  /api/stats             — service statistics
  GET  /api/health            — liveness check
"""

import json
import time
import uuid
import os
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

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


# ── Telemetry Data ────────────────────────────────────────────────────────────

@dataclass
class TerminalTelemetry:
    id: str
    terminal_id: str
    timestamp: float
    region: str
    carrier: str
    network_type: str
    latency_ms: float
    bandwidth_kbps: float
    packet_loss_pct: float
    jitter_ms: float
    signal_strength_dbm: int
    connection_state: str  # connected, degraded, offline
    uptime_pct: float
    transactions_queued: int
    last_sync_age_sec: int

@dataclass
class OutageEvent:
    id: str
    region: str
    carrier: str
    started_at: float
    ended_at: Optional[float]
    duration_sec: Optional[float]
    affected_terminals: int
    severity: str  # minor, major, critical
    root_cause: str
    status: str  # active, resolved

@dataclass
class Alert:
    id: str
    type: str  # latency_spike, bandwidth_drop, outage, packet_loss
    severity: str
    region: str
    carrier: str
    message: str
    threshold: float
    actual_value: float
    created_at: float
    acknowledged: bool

# ── Analytics Engine ──────────────────────────────────────────────────────────

class ConnectivityAnalytics:
    def __init__(self):
        self.telemetry: deque = deque(maxlen=50000)
        self.by_region: dict = defaultdict(lambda: deque(maxlen=5000))
        self.by_carrier: dict = defaultdict(lambda: deque(maxlen=5000))
        self.by_terminal: dict = defaultdict(lambda: deque(maxlen=500))
        self.outages: list = []
        self.alerts: list = []
        self.alert_thresholds = {
            "latency_spike_ms": 500,
            "bandwidth_drop_kbps": 50,
            "packet_loss_pct": 5,
            "offline_terminals_pct": 20,
        }
        self.stats = {
            "total_telemetry": 0,
            "total_outages": 0,
            "total_alerts": 0,
        }

    def ingest(self, t: TerminalTelemetry):
        self.telemetry.append(t)
        self.by_region[t.region].append(t)
        self.by_carrier[t.carrier].append(t)
        self.by_terminal[t.terminal_id].append(t)
        self.stats["total_telemetry"] += 1
        self._check_alerts(t)

    def _check_alerts(self, t: TerminalTelemetry):
        if t.latency_ms > self.alert_thresholds["latency_spike_ms"]:
            self._create_alert("latency_spike", "warning", t.region, t.carrier,
                f"Latency spike: {t.latency_ms}ms on {t.carrier} in {t.region}",
                self.alert_thresholds["latency_spike_ms"], t.latency_ms)

        if t.bandwidth_kbps < self.alert_thresholds["bandwidth_drop_kbps"]:
            self._create_alert("bandwidth_drop", "critical", t.region, t.carrier,
                f"Bandwidth drop: {t.bandwidth_kbps}kbps on {t.carrier} in {t.region}",
                self.alert_thresholds["bandwidth_drop_kbps"], t.bandwidth_kbps)

        if t.packet_loss_pct > self.alert_thresholds["packet_loss_pct"]:
            self._create_alert("packet_loss", "warning", t.region, t.carrier,
                f"High packet loss: {t.packet_loss_pct}% on {t.carrier} in {t.region}",
                self.alert_thresholds["packet_loss_pct"], t.packet_loss_pct)

        if t.connection_state == "offline":
            self._detect_outage(t)

    def _create_alert(self, alert_type: str, severity: str, region: str,
                      carrier: str, message: str, threshold: float, actual: float):
        # Deduplicate: don't create same alert within 5 minutes
        recent = [a for a in self.alerts[-50:]
                  if a.type == alert_type and a.region == region
                  and a.carrier == carrier
                  and time.time() - a.created_at < 300]
        if recent:
            return

        alert = Alert(
            id=str(uuid.uuid4())[:8],
            type=alert_type,
            severity=severity,
            region=region,
            carrier=carrier,
            message=message,
            threshold=threshold,
            actual_value=actual,
            created_at=time.time(),
            acknowledged=False,
        )
        self.alerts.append(alert)
        self.stats["total_alerts"] += 1

    def _detect_outage(self, t: TerminalTelemetry):
        # Check if there's an active outage for this region+carrier
        active = [o for o in self.outages
                  if o.status == "active" and o.region == t.region
                  and o.carrier == t.carrier]
        if active:
            active[0].affected_terminals += 1
            return

        # Check how many terminals in this region+carrier are offline
        region_terminals = list(self.by_region[t.region])[-100:]
        offline_count = sum(1 for tt in region_terminals if tt.connection_state == "offline")
        total = len(region_terminals)

        if total > 0 and (offline_count / total) > 0.3:
            severity = "critical" if offline_count / total > 0.5 else "major"
            outage = OutageEvent(
                id=str(uuid.uuid4())[:8],
                region=t.region,
                carrier=t.carrier,
                started_at=time.time(),
                ended_at=None,
                duration_sec=None,
                affected_terminals=offline_count,
                severity=severity,
                root_cause="Under investigation",
                status="active",
            )
            self.outages.append(outage)
            self.stats["total_outages"] += 1

    def get_heatmap(self) -> dict:
        result = {}
        for region, probes in self.by_region.items():
            recent = list(probes)[-100:]
            if not recent:
                continue
            online = sum(1 for t in recent if t.connection_state == "connected")
            degraded = sum(1 for t in recent if t.connection_state == "degraded")
            offline = sum(1 for t in recent if t.connection_state == "offline")
            total = len(recent)

            result[region] = {
                "region": region,
                "avg_latency_ms": round(statistics.mean(t.latency_ms for t in recent), 1),
                "avg_bandwidth_kbps": round(statistics.mean(t.bandwidth_kbps for t in recent), 1),
                "avg_packet_loss_pct": round(statistics.mean(t.packet_loss_pct for t in recent), 2),
                "online_pct": round(online / total * 100, 1) if total else 0,
                "degraded_pct": round(degraded / total * 100, 1) if total else 0,
                "offline_pct": round(offline / total * 100, 1) if total else 0,
                "terminal_count": total,
                "quality_score": self._quality_score(recent),
            }
        return result

    def get_carrier_sla(self) -> dict:
        result = {}
        for carrier, probes in self.by_carrier.items():
            recent = list(probes)[-200:]
            if not recent:
                continue
            uptime_values = [t.uptime_pct for t in recent]
            latency_values = [t.latency_ms for t in recent]

            sla_uptime = statistics.mean(uptime_values) if uptime_values else 0
            sla_latency = statistics.mean(latency_values) if latency_values else 0
            sla_met = sla_uptime >= 99.0 and sla_latency <= 200

            result[carrier] = {
                "carrier": carrier,
                "uptime_pct": round(sla_uptime, 2),
                "avg_latency_ms": round(sla_latency, 1),
                "p95_latency_ms": round(sorted(latency_values)[int(len(latency_values) * 0.95)] if latency_values else 0, 1),
                "avg_bandwidth_kbps": round(statistics.mean(t.bandwidth_kbps for t in recent), 1),
                "packet_loss_pct": round(statistics.mean(t.packet_loss_pct for t in recent), 2),
                "sla_met": sla_met,
                "outage_count": sum(1 for o in self.outages if o.carrier == carrier),
                "regions_covered": list(set(t.region for t in recent)),
                "sample_count": len(recent),
            }
        return result

    def get_dashboard(self) -> dict:
        all_recent = list(self.telemetry)[-500:]
        if not all_recent:
            return {"message": "No telemetry data yet"}

        online = sum(1 for t in all_recent if t.connection_state == "connected")
        degraded = sum(1 for t in all_recent if t.connection_state == "degraded")
        offline = sum(1 for t in all_recent if t.connection_state == "offline")
        total = len(all_recent)

        return {
            "total_terminals": total,
            "online": online,
            "degraded": degraded,
            "offline": offline,
            "online_pct": round(online / total * 100, 1),
            "avg_latency_ms": round(statistics.mean(t.latency_ms for t in all_recent), 1),
            "avg_bandwidth_kbps": round(statistics.mean(t.bandwidth_kbps for t in all_recent), 1),
            "avg_packet_loss_pct": round(statistics.mean(t.packet_loss_pct for t in all_recent), 2),
            "active_outages": sum(1 for o in self.outages if o.status == "active"),
            "active_alerts": sum(1 for a in self.alerts if not a.acknowledged),
            "queued_transactions": sum(t.transactions_queued for t in all_recent),
            "regions_count": len(self.by_region),
            "carriers_count": len(self.by_carrier),
        }

    def _quality_score(self, probes: list) -> float:
        if not probes:
            return 50
        avg_lat = statistics.mean(t.latency_ms for t in probes)
        avg_bw = statistics.mean(t.bandwidth_kbps for t in probes)
        avg_loss = statistics.mean(t.packet_loss_pct for t in probes)
        lat_score = max(0, 100 - avg_lat / 10)
        bw_score = min(100, avg_bw / 100)
        loss_score = max(0, 100 - avg_loss * 10)
        return round(lat_score * 0.4 + bw_score * 0.4 + loss_score * 0.2, 1)


# ── HTTP Server ───────────────────────────────────────────────────────────────

analytics = ConnectivityAnalytics()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def _send_json(self, data, status=200):
        body = json.dumps(data, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/health":
            self._send_json({"status": "healthy", "service": "connectivity-analytics", "version": "1.0.0"})
        elif self.path == "/api/stats":
            self._send_json(analytics.stats)
        elif self.path == "/api/heatmap":
            self._send_json(analytics.get_heatmap())
        elif self.path == "/api/outages":
            self._send_json([asdict(o) for o in analytics.outages[-50:]])
        elif self.path == "/api/carrier-sla":
            self._send_json(analytics.get_carrier_sla())
        elif self.path == "/api/alerts":
            self._send_json([asdict(a) for a in analytics.alerts[-100:]])
        elif self.path == "/api/dashboard":
            self._send_json(analytics.get_dashboard())
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        try:
            body = self._read_body()
        except Exception as e:
            self._send_json({"error": str(e)}, 400)
            return

        if self.path == "/api/telemetry":
            t = TerminalTelemetry(
                id=str(uuid.uuid4())[:8],
                terminal_id=body.get("terminal_id", "unknown"),
                timestamp=time.time(),
                region=body.get("region", "unknown"),
                carrier=body.get("carrier", "unknown"),
                network_type=body.get("network_type", "3g"),
                latency_ms=body.get("latency_ms", 100),
                bandwidth_kbps=body.get("bandwidth_kbps", 500),
                packet_loss_pct=body.get("packet_loss_pct", 0),
                jitter_ms=body.get("jitter_ms", 10),
                signal_strength_dbm=body.get("signal_strength_dbm", -70),
                connection_state=body.get("connection_state", "connected"),
                uptime_pct=body.get("uptime_pct", 99.9),
                transactions_queued=body.get("transactions_queued", 0),
                last_sync_age_sec=body.get("last_sync_age_sec", 0),
            )
            analytics.ingest(t)
            self._send_json(asdict(t), 201)

        elif self.path == "/api/alert/configure":
            for key, value in body.items():
                if key in analytics.alert_thresholds:
                    analytics.alert_thresholds[key] = value
            self._send_json({"thresholds": analytics.alert_thresholds})

        else:
            self._send_json({"error": "Not found"}, 404)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8082"))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"[connectivity-analytics] Starting on :{port}")
    server.serve_forever()


# Connectivity trend analysis
# Tracks network quality history and computes trend direction
def compute_trend(history: list) -> dict:
    """Compute connectivity trend from historical latency measurements."""
    if len(history) < 2:
        return {'trend': 'stable', 'direction': 0}
    recent = sum(history[-5:]) / min(len(history), 5)
    older = sum(history[:5]) / min(len(history), 5)
    if recent < older * 0.9:
        return {'trend': 'improving', 'direction': 1}
    elif recent > older * 1.1:
        return {'trend': 'degrading', 'direction': -1}
    return {'trend': 'stable', 'direction': 0}


import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/connectivity_analytics")

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
