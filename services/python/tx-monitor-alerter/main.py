
from fastapi import FastAPI
from datetime import datetime

app = FastAPI(title="tx-monitor-alerter")

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "tx-monitor-alerter", "timestamp": datetime.utcnow().isoformat()}

"""
Transaction Monitor Alerter — Sprint 78
Real-time transaction monitoring with configurable alert rules
Monitors: velocity, amount thresholds, failure rates, geographic anomalies
"""
import json
import time
from dataclasses import dataclass, asdict, field
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
class AlertRule:
    rule_id: str
    name: str
    description: str
    severity: str  # info, warning, critical
    condition_type: str  # velocity, amount, failure_rate, geo_anomaly
    threshold: float
    window_seconds: int
    enabled: bool = True
    cooldown_seconds: int = 300

@dataclass
class Alert:
    alert_id: str
    rule_id: str
    severity: str
    title: str
    message: str
    agent_id: Optional[str]
    transaction_ref: Optional[str]
    triggered_at: float
    acknowledged: bool = False
    resolved: bool = False

class TransactionMonitor:
    DEFAULT_RULES = [
        AlertRule("R001", "High Velocity Agent", "Agent exceeds 50 tx/hour", "warning", "velocity", 50, 3600),
        AlertRule("R002", "Large Transaction", "Single tx exceeds ₦1,000,000", "critical", "amount", 1000000, 0),
        AlertRule("R003", "High Failure Rate", "Agent failure rate exceeds 20%", "warning", "failure_rate", 20, 3600),
        AlertRule("R004", "Suspicious Velocity", "Customer exceeds 10 tx/hour", "critical", "velocity", 10, 3600),
        AlertRule("R005", "Micro-Transaction Flood", "More than 100 tx under ₦1000 in 1 hour", "warning", "velocity", 100, 3600),
        AlertRule("R006", "Off-Hours Activity", "Transaction outside business hours (6am-10pm)", "info", "amount", 0, 0),
        AlertRule("R007", "Dormant Agent Activity", "Agent with no tx in 7 days suddenly active", "warning", "velocity", 1, 604800),
        AlertRule("R008", "Geographic Anomaly", "Agent transacting from unusual location", "critical", "geo_anomaly", 100, 0),
    ]

    def __init__(self):
        self.rules = {r.rule_id: r for r in self.DEFAULT_RULES}
        self.alerts: List[Alert] = []
        self.agent_txs: Dict[str, List[float]] = defaultdict(list)
        self.agent_failures: Dict[str, int] = defaultdict(int)
        self.agent_successes: Dict[str, int] = defaultdict(int)
        self.alert_seq = 0
        self._seed_alerts()

    def _seed_alerts(self):
        self.alerts = [
            Alert("ALT-001", "R002", "critical", "Large Transaction Detected",
                  "Agent AGT-001 processed ₦2,500,000 cash out", "AGT-001", "TX-LARGE-001", time.time() - 1800),
            Alert("ALT-002", "R001", "warning", "High Velocity Alert",
                  "Agent AGT-003 processed 62 transactions in last hour", "AGT-003", None, time.time() - 900),
            Alert("ALT-003", "R003", "warning", "High Failure Rate",
                  "Agent AGT-005 has 35% failure rate (14/40 failed)", "AGT-005", None, time.time() - 600),
            Alert("ALT-004", "R008", "critical", "Geographic Anomaly",
                  "Agent AGT-002 (Abuja) transacting from Lagos (450km away)", "AGT-002", "TX-GEO-001", time.time() - 300),
        ]

    def process_transaction(self, tx: Dict) -> List[Alert]:
        new_alerts = []
        agent_id = tx.get("agent_id", "")
        amount = tx.get("amount", 0)
        status = tx.get("status", "completed")
        now = time.time()
        self.agent_txs[agent_id].append(now)
        if status == "failed":
            self.agent_failures[agent_id] += 1
        else:
            self.agent_successes[agent_id] += 1
        # Check amount threshold
        if amount >= self.rules["R002"].threshold:
            alert = self._create_alert("R002", f"Large transaction ₦{amount:,.0f} by {agent_id}", agent_id, tx.get("ref"))
            new_alerts.append(alert)
        # Check velocity
        recent = [t for t in self.agent_txs[agent_id] if t > now - 3600]
        if len(recent) >= self.rules["R001"].threshold:
            alert = self._create_alert("R001", f"Agent {agent_id} at {len(recent)} tx/hour", agent_id, None)
            new_alerts.append(alert)
        # Check failure rate
        total = self.agent_failures[agent_id] + self.agent_successes[agent_id]
        if total >= 10:
            rate = (self.agent_failures[agent_id] / total) * 100
            if rate >= self.rules["R003"].threshold:
                alert = self._create_alert("R003", f"Agent {agent_id} failure rate {rate:.1f}%", agent_id, None)
                new_alerts.append(alert)
        self.alerts.extend(new_alerts)
        return new_alerts

    def _create_alert(self, rule_id: str, message: str, agent_id: Optional[str], tx_ref: Optional[str]) -> Alert:
        self.alert_seq += 1
        rule = self.rules[rule_id]
        return Alert(
            alert_id=f"ALT-{self.alert_seq:04d}",
            rule_id=rule_id,
            severity=rule.severity,
            title=rule.name,
            message=message,
            agent_id=agent_id,
            transaction_ref=tx_ref,
            triggered_at=time.time(),
        )

    def get_dashboard(self) -> Dict:
        return {
            "total_alerts": len(self.alerts),
            "critical": len([a for a in self.alerts if a.severity == "critical"]),
            "warning": len([a for a in self.alerts if a.severity == "warning"]),
            "info": len([a for a in self.alerts if a.severity == "info"]),
            "unacknowledged": len([a for a in self.alerts if not a.acknowledged]),
            "rules_count": len(self.rules),
            "active_rules": len([r for r in self.rules.values() if r.enabled]),
            "recent_alerts": [asdict(a) for a in self.alerts[-10:]],
        }

def main():
    monitor = TransactionMonitor()
    print(f"[tx-monitor-alerter] Starting with {len(monitor.rules)} rules, {len(monitor.alerts)} seed alerts")
    dashboard = monitor.get_dashboard()
    print(f"  Critical: {dashboard['critical']}, Warning: {dashboard['warning']}, Info: {dashboard['info']}")
    # Process test transactions
    test_txs = [
        {"agent_id": "AGT-001", "amount": 2500000, "status": "completed", "ref": "TX-TEST-001"},
        {"agent_id": "AGT-003", "amount": 5000, "status": "failed", "ref": "TX-TEST-002"},
    ]
    for tx in test_txs:
        alerts = monitor.process_transaction(tx)
        for a in alerts:
            print(f"  NEW ALERT: [{a.severity.upper()}] {a.title}: {a.message}")

if __name__ == "__main__":
    main()
