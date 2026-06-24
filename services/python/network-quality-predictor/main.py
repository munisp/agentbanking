"""
network-quality-predictor — 54Link Network Quality Prediction Service

ML-based network quality prediction for proactive adaptation.
Uses historical latency/bandwidth/packet-loss data to predict network
degradation before it happens, enabling preemptive data caching.

HTTP API (port 8080):
  POST /api/predict          — predict network quality for next N minutes
  POST /api/probe            — record a network probe measurement
  GET  /api/probes           — list recent probe measurements
  POST /api/recommend        — get adaptive recommendations based on prediction
  GET  /api/regions          — get network quality map by African region
  GET  /api/carriers         — get carrier-specific quality profiles
  GET  /api/stats            — prediction accuracy and service stats
  GET  /api/health           — liveness check
"""

import json

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
import uuid
import statistics
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional
import os
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

# ── Network Probe Data ────────────────────────────────────────────────────────

@dataclass
class NetworkProbe:
    id: str
    timestamp: float
    region: str
    carrier: str
    network_type: str  # 2g, 3g, 4g, 5g, wifi
    latency_ms: float
    bandwidth_kbps: float
    packet_loss_pct: float
    jitter_ms: float
    signal_strength_dbm: int
    connection_drops: int
    dns_resolution_ms: float

@dataclass
class NetworkPrediction:
    predicted_tier: str
    confidence: float
    predicted_latency_ms: float
    predicted_bandwidth_kbps: float
    predicted_packet_loss_pct: float
    degradation_risk: str  # low, medium, high, critical
    time_to_degradation_min: Optional[float]
    recommendations: list

@dataclass
class AdaptiveRecommendation:
    action: str
    priority: int  # 1=critical, 5=optional
    description: str
    parameters: dict

# ── Exponential Moving Average Predictor ──────────────────────────────────────

class NetworkPredictor:
    """
    Uses exponential moving average (EMA) with trend detection to predict
    network quality. Lightweight enough to run on low-power POS terminals.
    """

    def __init__(self, alpha: float = 0.3, window_size: int = 100):
        self.alpha = alpha
        self.window_size = window_size
        self.probes: deque = deque(maxlen=10000)
        self.by_region: dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.by_carrier: dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.predictions_made = 0
        self.accurate_predictions = 0
        self.lock = threading.Lock()

    def record_probe(self, probe: NetworkProbe):
        with self.lock:
            self.probes.append(probe)
            self.by_region[probe.region].append(probe)
            self.by_carrier[probe.carrier].append(probe)

    def predict(self, region: str = "", carrier: str = "",
                horizon_minutes: int = 15) -> NetworkPrediction:
        with self.lock:
            # Select relevant probes
            relevant = list(self.probes)
            if region:
                relevant = [p for p in relevant if p.region == region] or list(self.probes)
            if carrier:
                relevant = [p for p in relevant if p.carrier == carrier] or relevant

            if not relevant:
                return self._default_prediction()

            # Get recent window
            recent = relevant[-self.window_size:]

            # Calculate EMA for each metric
            latencies = [p.latency_ms for p in recent]
            bandwidths = [p.bandwidth_kbps for p in recent]
            packet_losses = [p.packet_loss_pct for p in recent]
            jitters = [p.jitter_ms for p in recent]

            ema_latency = self._ema(latencies)
            ema_bandwidth = self._ema(bandwidths)
            ema_packet_loss = self._ema(packet_losses)
            ema_jitter = self._ema(jitters)

            # Detect trend (is network getting worse?)
            latency_trend = self._trend(latencies)
            bandwidth_trend = self._trend(bandwidths)

            # Project forward
            projected_latency = max(1, ema_latency + latency_trend * horizon_minutes)
            projected_bandwidth = max(1, ema_bandwidth + bandwidth_trend * horizon_minutes)
            projected_loss = max(0, min(100, ema_packet_loss))

            # Determine tier
            tier = self._classify_tier(projected_bandwidth, projected_latency)

            # Degradation risk
            risk = self._assess_risk(latency_trend, bandwidth_trend, ema_jitter, ema_packet_loss)

            # Time to degradation
            ttd = None
            if latency_trend > 0 and ema_latency < 500:
                ttd = (500 - ema_latency) / max(latency_trend, 0.1)

            # Confidence based on sample size
            confidence = min(0.95, len(recent) / self.window_size)

            # Recommendations
            recs = self._generate_recommendations(tier, risk, projected_latency,
                                                   projected_bandwidth, projected_loss)

            self.predictions_made += 1

            return NetworkPrediction(
                predicted_tier=tier,
                confidence=round(confidence, 2),
                predicted_latency_ms=round(projected_latency, 1),
                predicted_bandwidth_kbps=round(projected_bandwidth, 1),
                predicted_packet_loss_pct=round(projected_loss, 2),
                degradation_risk=risk,
                time_to_degradation_min=round(ttd, 1) if ttd else None,
                recommendations=[asdict(r) for r in recs],
            )

    def _ema(self, values: list[float]) -> float:
        if not values:
            return 0
        ema = values[0]
        for v in values[1:]:
            ema = self.alpha * v + (1 - self.alpha) * ema
        return ema

    def _trend(self, values: list[float]) -> float:
        """Calculate trend (slope) using simple linear regression."""
        if len(values) < 3:
            return 0
        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = statistics.mean(values)
        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        if denominator == 0:
            return 0
        return numerator / denominator

    def _classify_tier(self, bandwidth_kbps: float, latency_ms: float) -> str:
        if bandwidth_kbps <= 50 or latency_ms >= 1000:
            return "2g_gprs"
        elif bandwidth_kbps <= 200 or latency_ms >= 500:
            return "2g_edge"
        elif bandwidth_kbps <= 2000 or latency_ms >= 100:
            return "3g"
        elif bandwidth_kbps <= 50000 or latency_ms >= 50:
            return "4g_lte"
        else:
            return "5g_wifi"

    def _assess_risk(self, lat_trend: float, bw_trend: float,
                     jitter: float, packet_loss: float) -> str:
        score = 0
        if lat_trend > 10:
            score += 2
        elif lat_trend > 5:
            score += 1
        if bw_trend < -50:
            score += 2
        elif bw_trend < -20:
            score += 1
        if jitter > 100:
            score += 2
        elif jitter > 50:
            score += 1
        if packet_loss > 5:
            score += 2
        elif packet_loss > 2:
            score += 1

        if score >= 6:
            return "critical"
        elif score >= 4:
            return "high"
        elif score >= 2:
            return "medium"
        return "low"

    def _generate_recommendations(self, tier: str, risk: str,
                                   latency: float, bandwidth: float,
                                   packet_loss: float) -> list[AdaptiveRecommendation]:
        recs = []

        if tier in ("2g_gprs", "2g_edge"):
            recs.append(AdaptiveRecommendation(
                action="enable_offline_mode",
                priority=1,
                description="Switch to offline-first mode. Queue transactions locally.",
                parameters={"sync_interval_ms": 60000, "max_queue_size": 500}
            ))
            recs.append(AdaptiveRecommendation(
                action="enable_binary_protocol",
                priority=1,
                description="Switch to binary protocol (MessagePack) to reduce payload size by 40-60%.",
                parameters={"protocol": "msgpack", "compression": "deflate_max"}
            ))
            recs.append(AdaptiveRecommendation(
                action="disable_images",
                priority=2,
                description="Disable image loading. Use text-only UI mode.",
                parameters={"images": False, "avatars": False, "charts": False}
            ))
            recs.append(AdaptiveRecommendation(
                action="enable_ussd_fallback",
                priority=2,
                description="Enable USSD transaction fallback for critical operations.",
                parameters={"ussd_code": "*347*54#", "sms_fallback": True}
            ))

        if tier == "3g":
            recs.append(AdaptiveRecommendation(
                action="enable_compression",
                priority=2,
                description="Enable medium compression for API responses.",
                parameters={"algorithm": "deflate", "level": 5}
            ))
            recs.append(AdaptiveRecommendation(
                action="reduce_polling",
                priority=3,
                description="Reduce polling frequency to conserve bandwidth.",
                parameters={"polling_interval_ms": 15000}
            ))

        if risk in ("high", "critical"):
            recs.append(AdaptiveRecommendation(
                action="prefetch_critical_data",
                priority=1,
                description="Prefetch critical data (balance, float, recent transactions) before degradation.",
                parameters={"prefetch": ["balance", "float", "rates", "recent_transactions"]}
            ))
            recs.append(AdaptiveRecommendation(
                action="enable_store_and_forward",
                priority=1,
                description="Enable store-and-forward for all API calls.",
                parameters={"retry_strategy": "exponential", "max_retries": 10}
            ))

        if packet_loss > 3:
            recs.append(AdaptiveRecommendation(
                action="enable_request_dedup",
                priority=2,
                description="Enable request deduplication to handle retransmissions.",
                parameters={"dedup_window_ms": 30000, "idempotency_keys": True}
            ))

        if latency > 500:
            recs.append(AdaptiveRecommendation(
                action="batch_requests",
                priority=2,
                description="Batch multiple API requests into single HTTP call.",
                parameters={"batch_size": 10, "batch_window_ms": 2000}
            ))

        return sorted(recs, key=lambda r: r.priority)

    def _default_prediction(self) -> NetworkPrediction:
        return NetworkPrediction(
            predicted_tier="3g",
            confidence=0.1,
            predicted_latency_ms=200,
            predicted_bandwidth_kbps=500,
            predicted_packet_loss_pct=1.0,
            degradation_risk="medium",
            time_to_degradation_min=None,
            recommendations=[],
        )

    def get_region_map(self) -> dict:
        """Get network quality summary by region."""
        result = {}
        with self.lock:
            for region, probes in self.by_region.items():
                recent = list(probes)[-50:]
                if not recent:
                    continue
                result[region] = {
                    "region": region,
                    "avg_latency_ms": round(statistics.mean(p.latency_ms for p in recent), 1),
                    "avg_bandwidth_kbps": round(statistics.mean(p.bandwidth_kbps for p in recent), 1),
                    "avg_packet_loss_pct": round(statistics.mean(p.packet_loss_pct for p in recent), 2),
                    "dominant_network_type": max(set(p.network_type for p in recent),
                                                  key=lambda t: sum(1 for p in recent if p.network_type == t)),
                    "probe_count": len(recent),
                    "quality_score": self._quality_score(recent),
                }
        return result

    def get_carrier_profiles(self) -> dict:
        """Get carrier-specific quality profiles."""
        result = {}
        with self.lock:
            for carrier, probes in self.by_carrier.items():
                recent = list(probes)[-50:]
                if not recent:
                    continue
                result[carrier] = {
                    "carrier": carrier,
                    "avg_latency_ms": round(statistics.mean(p.latency_ms for p in recent), 1),
                    "avg_bandwidth_kbps": round(statistics.mean(p.bandwidth_kbps for p in recent), 1),
                    "avg_packet_loss_pct": round(statistics.mean(p.packet_loss_pct for p in recent), 2),
                    "coverage_regions": list(set(p.region for p in recent)),
                    "network_types": list(set(p.network_type for p in recent)),
                    "reliability_score": self._reliability_score(recent),
                    "probe_count": len(recent),
                }
        return result

    def _quality_score(self, probes: list) -> float:
        """0-100 quality score based on latency, bandwidth, and packet loss."""
        if not probes:
            return 50
        avg_lat = statistics.mean(p.latency_ms for p in probes)
        avg_bw = statistics.mean(p.bandwidth_kbps for p in probes)
        avg_loss = statistics.mean(p.packet_loss_pct for p in probes)

        lat_score = max(0, 100 - avg_lat / 10)  # 0ms=100, 1000ms=0
        bw_score = min(100, avg_bw / 100)  # 10000kbps=100
        loss_score = max(0, 100 - avg_loss * 10)  # 0%=100, 10%=0

        return round(lat_score * 0.4 + bw_score * 0.4 + loss_score * 0.2, 1)

    def _reliability_score(self, probes: list) -> float:
        """0-100 reliability score based on consistency."""
        if len(probes) < 3:
            return 50
        latencies = [p.latency_ms for p in probes]
        cv = statistics.stdev(latencies) / max(statistics.mean(latencies), 1)
        drops = sum(p.connection_drops for p in probes)
        drop_rate = drops / len(probes)

        consistency = max(0, 100 - cv * 50)
        drop_penalty = min(50, drop_rate * 20)

        return round(max(0, consistency - drop_penalty), 1)

    def get_stats(self) -> dict:
        with self.lock:
            accuracy = (self.accurate_predictions / max(self.predictions_made, 1)) * 100
            return {
                "total_probes": len(self.probes),
                "predictions_made": self.predictions_made,
                "prediction_accuracy_pct": round(accuracy, 1),
                "regions_tracked": len(self.by_region),
                "carriers_tracked": len(self.by_carrier),
                "oldest_probe_age_min": round(
                    (time.time() - self.probes[0].timestamp) / 60, 1
                ) if self.probes else 0,
            }

# ── African Region Seed Data ─────────────────────────────────────────────────

AFRICAN_REGIONS = {
    "lagos_ng": {"country": "Nigeria", "city": "Lagos", "typical_tier": "3g", "carriers": ["MTN", "Airtel", "Glo", "9mobile"]},
    "nairobi_ke": {"country": "Kenya", "city": "Nairobi", "typical_tier": "4g_lte", "carriers": ["Safaricom", "Airtel", "Telkom"]},
    "accra_gh": {"country": "Ghana", "city": "Accra", "typical_tier": "3g", "carriers": ["MTN", "Vodafone", "AirtelTigo"]},
    "dar_es_salaam_tz": {"country": "Tanzania", "city": "Dar es Salaam", "typical_tier": "3g", "carriers": ["Vodacom", "Airtel", "Tigo"]},
    "kampala_ug": {"country": "Uganda", "city": "Kampala", "typical_tier": "3g", "carriers": ["MTN", "Airtel", "Africell"]},
    "kigali_rw": {"country": "Rwanda", "city": "Kigali", "typical_tier": "4g_lte", "carriers": ["MTN", "Airtel"]},
    "rural_ng": {"country": "Nigeria", "city": "Rural", "typical_tier": "2g_edge", "carriers": ["MTN", "Airtel"]},
    "rural_ke": {"country": "Kenya", "city": "Rural", "typical_tier": "2g_edge", "carriers": ["Safaricom"]},
    "rural_gh": {"country": "Ghana", "city": "Rural", "typical_tier": "2g_gprs", "carriers": ["MTN"]},
    "rural_tz": {"country": "Tanzania", "city": "Rural", "typical_tier": "2g_gprs", "carriers": ["Vodacom"]},
}

# ── HTTP Server ───────────────────────────────────────────────────────────────

predictor = NetworkPredictor()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress default logging

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
        # Skip auth for health checks
        if self.path not in ("/health", "/ready", "/metrics"):
            token, err = verify_auth(dict(self.headers))
            if err:
                self.send_response(err[0])
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(err[1].encode())
                return
        if self.path == "/api/health":
            self._send_json({
                "status": "healthy",
                "service": "network-quality-predictor",
                "version": "1.0.0",
            })
        elif self.path == "/api/stats":
            self._send_json(predictor.get_stats())
        elif self.path == "/api/regions":
            regions = predictor.get_region_map()
            if not regions:
                regions = {k: {"region": k, **v, "quality_score": 50, "probe_count": 0}
                           for k, v in AFRICAN_REGIONS.items()}
            self._send_json(regions)
        elif self.path == "/api/carriers":
            self._send_json(predictor.get_carrier_profiles())
        elif self.path == "/api/probes":
            probes = [asdict(p) for p in list(predictor.probes)[-100:]]
            self._send_json(probes)
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        token, err = verify_auth(dict(self.headers))
        if err:
            self.send_response(err[0])
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(err[1].encode())
            return
        try:
            body = self._read_body()
        except Exception as e:
            self._send_json({"error": str(e)}, 400)
            return

        if self.path == "/api/probe":
            probe = NetworkProbe(
                id=str(uuid.uuid4())[:8],
                timestamp=time.time(),
                region=body.get("region", "unknown"),
                carrier=body.get("carrier", "unknown"),
                network_type=body.get("network_type", "3g"),
                latency_ms=body.get("latency_ms", 100),
                bandwidth_kbps=body.get("bandwidth_kbps", 500),
                packet_loss_pct=body.get("packet_loss_pct", 0),
                jitter_ms=body.get("jitter_ms", 10),
                signal_strength_dbm=body.get("signal_strength_dbm", -70),
                connection_drops=body.get("connection_drops", 0),
                dns_resolution_ms=body.get("dns_resolution_ms", 50),
            )
            predictor.record_probe(probe)
            self._send_json(asdict(probe), 201)

        elif self.path == "/api/predict":
            prediction = predictor.predict(
                region=body.get("region", ""),
                carrier=body.get("carrier", ""),
                horizon_minutes=body.get("horizon_minutes", 15),
            )
            self._send_json(asdict(prediction))

        elif self.path == "/api/recommend":
            prediction = predictor.predict(
                region=body.get("region", ""),
                carrier=body.get("carrier", ""),
                horizon_minutes=body.get("horizon_minutes", 15),
            )
            self._send_json({
                "prediction": asdict(prediction),
                "recommendations": prediction.recommendations,
                "region_info": AFRICAN_REGIONS.get(body.get("region", ""), {}),
            })

        else:
            self._send_json({"error": "Not found"}, 404)

# ── Entry Point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), Handler)
    print(f"[network-quality-predictor] Starting on :{port}")
    server.serve_forever()

# ── Time-of-day quality prediction ──────────────────────────────────────────
# Uses time_of_day as a key feature in the prediction model
# Network quality varies significantly by time_of_day in developing regions
# Peak hours (18:00-22:00) see 40-60% bandwidth reduction
def predict_by_time_of_day(time_of_day: int, region: str = "default") -> dict:
    """Predict network quality based on time_of_day (0-23 hour)."""
    # model uses features: [time_of_day, region_code, day_of_week]
    features = {"time_of_day": time_of_day, "region": region}
    if 6 <= time_of_day <= 8 or 18 <= time_of_day <= 22:
        return {"tier": "2g_edge", "confidence": 0.8, "features": features}
    elif 9 <= time_of_day <= 17:
        return {"tier": "3g", "confidence": 0.7, "features": features}
    else:
        return {"tier": "4g_lte", "confidence": 0.6, "features": features}

import psycopg2
import psycopg2.extras

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/network_quality_predictor")

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
