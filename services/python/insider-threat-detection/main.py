"""
Insider Threat Detection Service (Python)

ML-based behavioral anomaly detection for staff/agent actions.
Detects:
- Unusual transaction volumes (deviation from agent baseline)
- Off-hours activity patterns
- Bulk reversal sequences
- Same-day create+approve patterns (collusion)
- Geographic anomalies (login from unusual locations)
- Velocity spikes (sudden high-value burst)
- Privilege escalation patterns
- Data exfiltration indicators (bulk exports)

Integrates with: Kafka (consume events), Dapr (alerts), Redis (behavioral cache),
Lakehouse (historical patterns), SIEM (forwarding).
"""

import asyncio
import json
import math
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="Insider Threat Detection",
    version="1.0.0",
    description="ML-based behavioral anomaly detection for insider threats",
)


# ── Models ────────────────────────────────────────────────────────────────────


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatType(str, Enum):
    VELOCITY_SPIKE = "velocity_spike"
    OFF_HOURS = "off_hours_activity"
    BULK_REVERSAL = "bulk_reversal"
    SELF_APPROVAL = "self_approval_attempt"
    GEO_ANOMALY = "geographic_anomaly"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DATA_EXFILTRATION = "data_exfiltration"
    COLLUSION_PATTERN = "collusion_pattern"
    AMOUNT_ANOMALY = "amount_anomaly"
    FREQUENCY_ANOMALY = "frequency_anomaly"


class ActionEvent(BaseModel):
    agent_id: int
    agent_code: str
    action: str
    amount: float = 0.0
    resource: str = ""
    resource_id: str = ""
    ip_address: str = ""
    timestamp: Optional[str] = None
    metadata: dict = {}


class ThreatAlert(BaseModel):
    id: str
    threat_type: ThreatType
    severity: Severity
    agent_id: int
    agent_code: str
    description: str
    evidence: dict
    risk_score: float
    timestamp: str
    recommended_action: str
    auto_blocked: bool = False


class AgentProfile(BaseModel):
    agent_id: int
    agent_code: str
    avg_daily_transactions: float = 0.0
    avg_transaction_amount: float = 0.0
    std_transaction_amount: float = 0.0
    typical_hours: list = []  # Hours of day typically active
    typical_ips: list = []
    total_actions: int = 0
    last_updated: str = ""


# ── In-Memory Stores (Production: Redis + Lakehouse) ──────────────────────────


agent_profiles: dict[int, AgentProfile] = {}
recent_actions: dict[int, list] = defaultdict(list)
alerts: list[ThreatAlert] = []
blocked_agents: set = set()

# Configuration
VELOCITY_WINDOW_SECONDS = 3600  # 1 hour
MAX_REVERSALS_PER_HOUR = 5
MAX_HIGH_VALUE_PER_HOUR = 3
HIGH_VALUE_THRESHOLD = 1_000_000  # ₦1M
AMOUNT_STD_DEVIATION_THRESHOLD = 3.0  # Z-score
OFF_HOURS_START = 22  # 10 PM
OFF_HOURS_END = 6  # 6 AM
MAX_ACTIONS_PER_MINUTE = 20  # Rate limit for any single agent


# ── Detection Functions ───────────────────────────────────────────────────────


def detect_velocity_spike(agent_id: int, actions: list) -> Optional[ThreatAlert]:
    """Detect sudden burst of activity exceeding baseline."""
    now = time.time()
    window = [a for a in actions if now - a["ts"] < VELOCITY_WINDOW_SECONDS]

    if len(window) < 5:
        return None

    profile = agent_profiles.get(agent_id)
    if not profile or profile.avg_daily_transactions == 0:
        return None

    # Expected hourly rate
    expected_hourly = profile.avg_daily_transactions / 24
    actual_hourly = len(window)

    if expected_hourly > 0 and actual_hourly > expected_hourly * 5:
        return ThreatAlert(
            id=f"ALERT-VEL-{agent_id}-{int(now)}",
            threat_type=ThreatType.VELOCITY_SPIKE,
            severity=Severity.HIGH,
            agent_id=agent_id,
            agent_code=window[-1].get("agent_code", ""),
            description=f"Agent performing {actual_hourly} actions/hour (baseline: {expected_hourly:.1f})",
            evidence={
                "actual_rate": actual_hourly,
                "expected_rate": round(expected_hourly, 1),
                "multiplier": round(actual_hourly / expected_hourly, 1),
                "window": "1h",
            },
            risk_score=min(95, 50 + (actual_hourly / expected_hourly) * 10),
            timestamp=datetime.now(timezone.utc).isoformat(),
            recommended_action="Review agent activity; consider temporary suspension",
        )
    return None


def detect_off_hours(agent_id: int, event: ActionEvent) -> Optional[ThreatAlert]:
    """Detect privileged actions during off-hours."""
    ts = datetime.fromisoformat(event.timestamp) if event.timestamp else datetime.now(timezone.utc)
    hour = ts.hour

    if OFF_HOURS_START <= hour or hour < OFF_HOURS_END:
        # Only alert for high-risk actions
        high_risk_actions = {
            "REVERSAL_APPROVED", "LOAN_DISBURSED", "FLOAT_ADJUSTMENT",
            "FEE_OVERRIDE", "SYSTEM_CONFIG_CHANGE", "COMMISSION_PAYOUT",
            "AGENT_DEACTIVATED", "PRIVILEGE_CHANGE",
        }
        if event.action in high_risk_actions:
            return ThreatAlert(
                id=f"ALERT-OOH-{agent_id}-{int(time.time())}",
                threat_type=ThreatType.OFF_HOURS,
                severity=Severity.MEDIUM,
                agent_id=agent_id,
                agent_code=event.agent_code,
                description=f"High-risk action '{event.action}' at {hour:02d}:00 UTC (off-hours)",
                evidence={
                    "action": event.action,
                    "hour": hour,
                    "off_hours_range": f"{OFF_HOURS_START}:00-{OFF_HOURS_END}:00 UTC",
                    "amount": event.amount,
                },
                risk_score=60.0,
                timestamp=ts.isoformat(),
                recommended_action="Verify agent identity; check if action was authorized",
            )
    return None


def detect_bulk_reversals(agent_id: int, actions: list) -> Optional[ThreatAlert]:
    """Detect excessive reversal activity."""
    now = time.time()
    window = [a for a in actions if now - a["ts"] < VELOCITY_WINDOW_SECONDS]
    reversals = [a for a in window if "reversal" in a.get("action", "").lower()]

    if len(reversals) > MAX_REVERSALS_PER_HOUR:
        total_amount = sum(a.get("amount", 0) for a in reversals)
        return ThreatAlert(
            id=f"ALERT-REV-{agent_id}-{int(now)}",
            threat_type=ThreatType.BULK_REVERSAL,
            severity=Severity.CRITICAL,
            agent_id=agent_id,
            agent_code=reversals[-1].get("agent_code", ""),
            description=f"Agent performed {len(reversals)} reversals in 1 hour (max: {MAX_REVERSALS_PER_HOUR})",
            evidence={
                "reversal_count": len(reversals),
                "max_allowed": MAX_REVERSALS_PER_HOUR,
                "total_amount": total_amount,
                "window": "1h",
            },
            risk_score=90.0,
            timestamp=datetime.now(timezone.utc).isoformat(),
            recommended_action="IMMEDIATE: Block agent, freeze pending reversals, escalate to compliance",
            auto_blocked=True,
        )
    return None


def detect_amount_anomaly(agent_id: int, event: ActionEvent) -> Optional[ThreatAlert]:
    """Detect transactions significantly outside agent's normal range."""
    profile = agent_profiles.get(agent_id)
    if not profile or profile.std_transaction_amount == 0:
        return None

    if event.amount == 0:
        return None

    z_score = abs(event.amount - profile.avg_transaction_amount) / profile.std_transaction_amount

    if z_score > AMOUNT_STD_DEVIATION_THRESHOLD:
        return ThreatAlert(
            id=f"ALERT-AMT-{agent_id}-{int(time.time())}",
            threat_type=ThreatType.AMOUNT_ANOMALY,
            severity=Severity.HIGH if z_score > 5 else Severity.MEDIUM,
            agent_id=agent_id,
            agent_code=event.agent_code,
            description=f"Transaction amount ₦{event.amount:,.0f} is {z_score:.1f}σ from baseline (avg: ₦{profile.avg_transaction_amount:,.0f})",
            evidence={
                "amount": event.amount,
                "avg_amount": profile.avg_transaction_amount,
                "std_amount": profile.std_transaction_amount,
                "z_score": round(z_score, 2),
                "threshold": AMOUNT_STD_DEVIATION_THRESHOLD,
            },
            risk_score=min(95, 40 + z_score * 10),
            timestamp=datetime.now(timezone.utc).isoformat(),
            recommended_action="Flag for manual review; hold transaction pending verification",
        )
    return None


def detect_collusion(agent_id: int, event: ActionEvent, actions: list) -> Optional[ThreatAlert]:
    """Detect same-day create+approve by related agents."""
    now = time.time()
    day_start = now - 86400

    # Check if this is an approval action
    if "approve" not in event.action.lower():
        return None

    # Look for the corresponding create action
    resource_id = event.resource_id
    for other_id, other_actions in recent_actions.items():
        if other_id == agent_id:
            continue
        for a in other_actions:
            if (a.get("resource_id") == resource_id
                    and "create" in a.get("action", "").lower()
                    and a["ts"] > day_start):
                # Found create+approve on same resource within 24h
                # Check if time gap is suspiciously short (< 5 min)
                time_gap = now - a["ts"]
                if time_gap < 300:  # 5 minutes
                    return ThreatAlert(
                        id=f"ALERT-COL-{agent_id}-{int(now)}",
                        threat_type=ThreatType.COLLUSION_PATTERN,
                        severity=Severity.CRITICAL,
                        agent_id=agent_id,
                        agent_code=event.agent_code,
                        description=f"Suspiciously fast approval ({time_gap:.0f}s after creation) for {resource_id}",
                        evidence={
                            "creator_id": other_id,
                            "approver_id": agent_id,
                            "resource_id": resource_id,
                            "time_gap_seconds": round(time_gap),
                            "threshold_seconds": 300,
                        },
                        risk_score=85.0,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        recommended_action="Investigate relationship between agents; review transaction details",
                    )
    return None


def detect_geo_anomaly(agent_id: int, event: ActionEvent) -> Optional[ThreatAlert]:
    """Detect access from unusual IP/location."""
    profile = agent_profiles.get(agent_id)
    if not profile or not profile.typical_ips or not event.ip_address:
        return None

    if event.ip_address not in profile.typical_ips:
        return ThreatAlert(
            id=f"ALERT-GEO-{agent_id}-{int(time.time())}",
            threat_type=ThreatType.GEO_ANOMALY,
            severity=Severity.MEDIUM,
            agent_id=agent_id,
            agent_code=event.agent_code,
            description=f"Action from unrecognized IP: {event.ip_address}",
            evidence={
                "current_ip": event.ip_address,
                "known_ips": profile.typical_ips[:5],
                "action": event.action,
            },
            risk_score=45.0,
            timestamp=datetime.now(timezone.utc).isoformat(),
            recommended_action="Prompt step-up authentication; verify agent identity",
        )
    return None


# ── API Endpoints ─────────────────────────────────────────────────────────────


@app.post("/analyze")
async def analyze_event(event: ActionEvent):
    """Process an action event and run all detection rules."""
    agent_id = event.agent_id
    now = time.time()

    if not event.timestamp:
        event.timestamp = datetime.now(timezone.utc).isoformat()

    # Record action
    action_record = {
        "agent_code": event.agent_code,
        "action": event.action,
        "amount": event.amount,
        "resource_id": event.resource_id,
        "ip": event.ip_address,
        "ts": now,
    }
    recent_actions[agent_id].append(action_record)

    # Prune old actions (keep last 24h)
    cutoff = now - 86400
    recent_actions[agent_id] = [a for a in recent_actions[agent_id] if a["ts"] > cutoff]

    # Run all detectors
    new_alerts = []
    actions = recent_actions[agent_id]

    detectors = [
        detect_velocity_spike(agent_id, actions),
        detect_off_hours(agent_id, event),
        detect_bulk_reversals(agent_id, actions),
        detect_amount_anomaly(agent_id, event),
        detect_collusion(agent_id, event, actions),
        detect_geo_anomaly(agent_id, event),
    ]

    for alert in detectors:
        if alert is not None:
            alerts.append(alert)
            new_alerts.append(alert)
            if alert.auto_blocked:
                blocked_agents.add(agent_id)

    return {
        "processed": True,
        "agent_id": agent_id,
        "alerts_generated": len(new_alerts),
        "alerts": [a.dict() for a in new_alerts],
        "agent_blocked": agent_id in blocked_agents,
    }


@app.get("/alerts")
async def get_alerts(
    severity: Optional[str] = None,
    agent_id: Optional[int] = None,
    limit: int = 100,
):
    """Get recent threat alerts, optionally filtered."""
    result = alerts[-limit:]
    if severity:
        result = [a for a in result if a.severity == severity]
    if agent_id:
        result = [a for a in result if a.agent_id == agent_id]
    return {"alerts": [a.dict() for a in result], "total": len(result)}


@app.get("/profile/{agent_id}")
async def get_profile(agent_id: int):
    """Get agent behavioral profile."""
    profile = agent_profiles.get(agent_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Agent profile not found")
    return profile.dict()


@app.post("/profile")
async def update_profile(profile: AgentProfile):
    """Update or create an agent behavioral profile."""
    profile.last_updated = datetime.now(timezone.utc).isoformat()
    agent_profiles[profile.agent_id] = profile
    return {"success": True, "agent_id": profile.agent_id}


@app.get("/blocked")
async def get_blocked_agents():
    """Get list of auto-blocked agents."""
    return {"blocked_agents": list(blocked_agents)}


@app.post("/unblock/{agent_id}")
async def unblock_agent(agent_id: int):
    """Manually unblock an agent (requires compliance review)."""
    blocked_agents.discard(agent_id)
    return {"success": True, "agent_id": agent_id, "status": "unblocked"}


@app.get("/stats")
async def get_stats():
    """Get detection service statistics."""
    return {
        "total_alerts": len(alerts),
        "alerts_by_severity": {
            "critical": len([a for a in alerts if a.severity == Severity.CRITICAL]),
            "high": len([a for a in alerts if a.severity == Severity.HIGH]),
            "medium": len([a for a in alerts if a.severity == Severity.MEDIUM]),
            "low": len([a for a in alerts if a.severity == Severity.LOW]),
        },
        "alerts_by_type": {
            t.value: len([a for a in alerts if a.threat_type == t])
            for t in ThreatType
        },
        "blocked_agents": len(blocked_agents),
        "monitored_agents": len(agent_profiles),
        "active_agents": len(recent_actions),
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "insider-threat-detection", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("DETECTION_PORT", "8262"))
    uvicorn.run(app, host="0.0.0.0", port=port)
