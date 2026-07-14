"""
Fraud ML Scoring Pipeline — Sprint 78
Real-time fraud detection using ensemble ML models
Features: velocity checks, amount anomaly, geo-fencing, device fingerprint, behavioral analysis
"""
import json
import math
import time
import hashlib
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from collections import defaultdict

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


@dataclass
class FraudFeatures:
    tx_amount: float
    tx_type: str
    agent_id: str
    customer_phone: str
    device_id: str
    latitude: float
    longitude: float
    timestamp: float
    channel: str  # pos, ussd, mobile, web

@dataclass
class FraudScore:
    transaction_ref: str
    overall_score: float  # 0-100, higher = more suspicious
    risk_level: str  # low, medium, high, critical
    velocity_score: float
    amount_anomaly_score: float
    geo_score: float
    device_score: float
    behavioral_score: float
    rules_triggered: List[str]
    recommendation: str  # approve, review, block
    processing_time_ms: float

class VelocityTracker:
    def __init__(self):
        self.agent_txs: Dict[str, List[float]] = defaultdict(list)
        self.customer_txs: Dict[str, List[float]] = defaultdict(list)
        self.device_txs: Dict[str, List[float]] = defaultdict(list)

    def record(self, features: FraudFeatures):
        now = features.timestamp
        self.agent_txs[features.agent_id].append(now)
        self.customer_txs[features.customer_phone].append(now)
        self.device_txs[features.device_id].append(now)

    def get_velocity(self, key: str, category: str, window_seconds: int = 3600) -> int:
        store = {"agent": self.agent_txs, "customer": self.customer_txs, "device": self.device_txs}
        txs = store.get(category, {}).get(key, [])
        cutoff = time.time() - window_seconds
        return len([t for t in txs if t > cutoff])

class AmountAnalyzer:
    def __init__(self):
        self.agent_amounts: Dict[str, List[float]] = defaultdict(list)

    def record(self, agent_id: str, amount: float):
        self.agent_amounts[agent_id].append(amount)

    def get_anomaly_score(self, agent_id: str, amount: float) -> float:
        history = self.agent_amounts.get(agent_id, [])
        if len(history) < 5:
            return 10.0  # Not enough data
        mean = sum(history) / len(history)
        variance = sum((x - mean) ** 2 for x in history) / len(history)
        std_dev = math.sqrt(variance) if variance > 0 else 1.0
        z_score = abs(amount - mean) / std_dev
        return min(100.0, z_score * 20)

class GeoFenceChecker:
    AGENT_ZONES = {
        "AGT-001": {"lat": 6.5244, "lng": 3.3792, "radius_km": 50},  # Lagos
        "AGT-002": {"lat": 9.0579, "lng": 7.4951, "radius_km": 30},  # Abuja
        "AGT-003": {"lat": -1.2921, "lng": 36.8219, "radius_km": 40},  # Nairobi
    }

    @staticmethod
    def haversine(lat1, lon1, lat2, lon2):
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
        return R * 2 * math.asin(math.sqrt(a))

    def check(self, agent_id: str, lat: float, lng: float) -> float:
        zone = self.AGENT_ZONES.get(agent_id)
        if not zone:
            return 5.0
        distance = self.haversine(zone["lat"], zone["lng"], lat, lng)
        if distance <= zone["radius_km"]:
            return 0.0
        excess = distance - zone["radius_km"]
        return min(100.0, excess * 2)

class DeviceFingerprinter:
    def __init__(self):
        self.known_devices: Dict[str, set] = defaultdict(set)

    def record(self, agent_id: str, device_id: str):
        self.known_devices[agent_id].add(device_id)

    def score(self, agent_id: str, device_id: str) -> float:
        known = self.known_devices.get(agent_id, set())
        if device_id in known:
            return 0.0
        if len(known) == 0:
            return 5.0
        return 60.0  # Unknown device for known agent

class FraudScoringEngine:
    def __init__(self):
        self.velocity = VelocityTracker()
        self.amounts = AmountAnalyzer()
        self.geo = GeoFenceChecker()
        self.device = DeviceFingerprinter()
        self.scored_count = 0

    def score(self, features: FraudFeatures) -> FraudScore:
        start = time.time()
        rules = []

        # Velocity scoring
        agent_vel = self.velocity.get_velocity(features.agent_id, "agent")
        customer_vel = self.velocity.get_velocity(features.customer_phone, "customer")
        velocity_score = min(100, agent_vel * 5 + customer_vel * 10)
        if agent_vel > 20:
            rules.append(f"HIGH_AGENT_VELOCITY:{agent_vel}/hr")
        if customer_vel > 5:
            rules.append(f"HIGH_CUSTOMER_VELOCITY:{customer_vel}/hr")

        # Amount anomaly
        amount_score = self.amounts.get_anomaly_score(features.agent_id, features.tx_amount)
        if features.tx_amount > 500000:
            rules.append(f"LARGE_AMOUNT:{features.tx_amount}")
            amount_score = max(amount_score, 70)

        # Geo-fence
        geo_score = self.geo.check(features.agent_id, features.latitude, features.longitude)
        if geo_score > 50:
            rules.append("OUTSIDE_GEOFENCE")

        # Device fingerprint
        device_score = self.device.score(features.agent_id, features.device_id)
        if device_score > 50:
            rules.append("UNKNOWN_DEVICE")

        # Behavioral (time-based)
        hour = time.localtime(features.timestamp).tm_hour
        behavioral_score = 0.0
        if hour < 6 or hour > 22:
            behavioral_score = 40.0
            rules.append("OFF_HOURS_TX")

        # Ensemble scoring (weighted average)
        overall = (
            velocity_score * 0.25 +
            amount_score * 0.25 +
            geo_score * 0.20 +
            device_score * 0.15 +
            behavioral_score * 0.15
        )

        if overall >= 75:
            risk_level = "critical"
            recommendation = "block"
        elif overall >= 50:
            risk_level = "high"
            recommendation = "review"
        elif overall >= 25:
            risk_level = "medium"
            recommendation = "review"
        else:
            risk_level = "low"
            recommendation = "approve"

        # Record for future scoring
        self.velocity.record(features)
        self.amounts.record(features.agent_id, features.tx_amount)
        self.device.record(features.agent_id, features.device_id)
        self.scored_count += 1

        tx_ref = hashlib.sha256(f"{features.agent_id}{features.timestamp}{features.tx_amount}".encode()).hexdigest()[:16]

        return FraudScore(
            transaction_ref=f"TX-{tx_ref.upper()}",
            overall_score=round(overall, 2),
            risk_level=risk_level,
            velocity_score=round(velocity_score, 2),
            amount_anomaly_score=round(amount_score, 2),
            geo_score=round(geo_score, 2),
            device_score=round(device_score, 2),
            behavioral_score=round(behavioral_score, 2),
            rules_triggered=rules,
            recommendation=recommendation,
            processing_time_ms=round((time.time() - start) * 1000, 2),
        )

def main():
    engine = FraudScoringEngine()
    test_cases = [
        FraudFeatures(50000, "cash_in", "AGT-001", "+2348012345678", "DEV-001", 6.52, 3.38, time.time(), "pos"),
        FraudFeatures(750000, "cash_out", "AGT-001", "+2348012345678", "DEV-001", 6.52, 3.38, time.time(), "pos"),
        FraudFeatures(100000, "transfer", "AGT-002", "+2348099999999", "DEV-UNKNOWN", 9.06, 7.50, time.time(), "ussd"),
        FraudFeatures(25000, "airtime", "AGT-003", "+254712345678", "DEV-003", -1.29, 36.82, time.time(), "mobile"),
        FraudFeatures(2000000, "cash_out", "AGT-001", "+2348055555555", "DEV-STOLEN", 9.06, 7.50, time.time(), "pos"),
    ]
    print(f"[fraud-ml-pipeline] Starting with {len(test_cases)} test transactions")
    for features in test_cases:
        score = engine.score(features)
        print(f"  {score.transaction_ref}: {score.risk_level.upper()} ({score.overall_score}) -> {score.recommendation} | rules: {score.rules_triggered} | {score.processing_time_ms}ms")
    print(f"[fraud-ml-pipeline] Scored {engine.scored_count} transactions")

if __name__ == "__main__":
    main()
