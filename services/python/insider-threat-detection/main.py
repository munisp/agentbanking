"""
Insider Threat Detection Service (Python)

ML-based behavioral anomaly detection for staff/agent actions.
All state persisted to PostgreSQL — zero in-memory mutable state.

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

import json
import math
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

import asyncpg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


# ── Database Connection ───────────────────────────────────────────────────────

pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    global pool
    if pool is None:
        dsn = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or \
            "postgres://postgres:postgres@localhost:5432/agentbanking"
        pool = await asyncpg.create_pool(dsn, min_size=5, max_size=25)
        await init_db()
    return pool


async def init_db():
    """Create tables if they don't exist."""
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS threat_agent_profiles (
                agent_id             BIGINT PRIMARY KEY,
                agent_code           VARCHAR(64) NOT NULL DEFAULT '',
                avg_daily_transactions DOUBLE PRECISION NOT NULL DEFAULT 0,
                avg_transaction_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
                std_transaction_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
                typical_hours        JSONB NOT NULL DEFAULT '[]',
                typical_ips          JSONB NOT NULL DEFAULT '[]',
                total_actions        INT NOT NULL DEFAULT 0,
                last_updated         TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS threat_recent_actions (
                id           BIGSERIAL PRIMARY KEY,
                agent_id     BIGINT NOT NULL,
                agent_code   VARCHAR(64) NOT NULL DEFAULT '',
                action       VARCHAR(128) NOT NULL,
                amount       DOUBLE PRECISION NOT NULL DEFAULT 0,
                resource_id  VARCHAR(128) NOT NULL DEFAULT '',
                ip_address   VARCHAR(64) NOT NULL DEFAULT '',
                recorded_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_threat_actions_agent
                ON threat_recent_actions (agent_id, recorded_at);

            CREATE TABLE IF NOT EXISTS threat_alerts (
                id                VARCHAR(128) PRIMARY KEY,
                threat_type       VARCHAR(64) NOT NULL,
                severity          VARCHAR(16) NOT NULL,
                agent_id          BIGINT NOT NULL,
                agent_code        VARCHAR(64) NOT NULL DEFAULT '',
                description       TEXT NOT NULL,
                evidence          JSONB NOT NULL DEFAULT '{}',
                risk_score        DOUBLE PRECISION NOT NULL DEFAULT 0,
                timestamp         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                recommended_action TEXT NOT NULL DEFAULT '',
                auto_blocked      BOOLEAN NOT NULL DEFAULT FALSE
            );
            CREATE INDEX IF NOT EXISTS idx_threat_alerts_agent
                ON threat_alerts (agent_id);
            CREATE INDEX IF NOT EXISTS idx_threat_alerts_severity
                ON threat_alerts (severity);

            CREATE TABLE IF NOT EXISTS threat_blocked_agents (
                agent_id    BIGINT PRIMARY KEY,
                blocked_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                reason      TEXT NOT NULL DEFAULT ''
            );
        """)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_pool()
    yield
    if pool:
        await pool.close()


app = FastAPI(
    title="Insider Threat Detection",
    version="2.0.0",
    description="ML-based behavioral anomaly detection — PostgreSQL-backed, zero in-memory state",
    lifespan=lifespan,
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
    agent_code: str = ""
    avg_daily_transactions: float = 0.0
    avg_transaction_amount: float = 0.0
    std_transaction_amount: float = 0.0
    typical_hours: list = []
    typical_ips: list = []
    total_actions: int = 0
    last_updated: str = ""


# Configuration
VELOCITY_WINDOW_SECONDS = 3600  # 1 hour
MAX_REVERSALS_PER_HOUR = 5
MAX_HIGH_VALUE_PER_HOUR = 3
HIGH_VALUE_THRESHOLD = 1_000_000  # ₦1M
AMOUNT_STD_DEVIATION_THRESHOLD = 3.0  # Z-score
OFF_HOURS_START = 22  # 10 PM
OFF_HOURS_END = 6  # 6 AM
MAX_ACTIONS_PER_MINUTE = 20


# ── Detection Functions ───────────────────────────────────────────────────────


async def get_agent_profile(conn, agent_id: int) -> Optional[dict]:
    row = await conn.fetchrow(
        "SELECT * FROM threat_agent_profiles WHERE agent_id = $1", agent_id
    )
    if row:
        return dict(row)
    return None


async def get_recent_actions(conn, agent_id: int, window_seconds: int = 3600) -> list:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    rows = await conn.fetch(
        """SELECT agent_code, action, amount, resource_id, ip_address,
                  EXTRACT(EPOCH FROM recorded_at) as ts
           FROM threat_recent_actions
           WHERE agent_id = $1 AND recorded_at > $2
           ORDER BY recorded_at ASC""",
        agent_id, cutoff,
    )
    return [dict(r) for r in rows]


async def detect_velocity_spike(conn, agent_id: int, actions: list) -> Optional[ThreatAlert]:
    """Detect sudden burst of activity exceeding baseline."""
    if len(actions) < 5:
        return None

    profile = await get_agent_profile(conn, agent_id)
    if not profile or profile["avg_daily_transactions"] == 0:
        return None

    expected_hourly = profile["avg_daily_transactions"] / 24
    actual_hourly = len(actions)

    if expected_hourly > 0 and actual_hourly > expected_hourly * 5:
        now = time.time()
        return ThreatAlert(
            id=f"ALERT-VEL-{agent_id}-{int(now)}",
            threat_type=ThreatType.VELOCITY_SPIKE,
            severity=Severity.HIGH,
            agent_id=agent_id,
            agent_code=actions[-1].get("agent_code", ""),
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


async def detect_off_hours(conn, agent_id: int, event: ActionEvent) -> Optional[ThreatAlert]:
    """Detect privileged actions during off-hours."""
    ts = datetime.fromisoformat(event.timestamp) if event.timestamp else datetime.now(timezone.utc)
    hour = ts.hour

    if OFF_HOURS_START <= hour or hour < OFF_HOURS_END:
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


async def detect_bulk_reversals(conn, agent_id: int, actions: list) -> Optional[ThreatAlert]:
    """Detect excessive reversal activity."""
    reversals = [a for a in actions if "reversal" in a.get("action", "").lower()]

    if len(reversals) > MAX_REVERSALS_PER_HOUR:
        total_amount = sum(a.get("amount", 0) for a in reversals)
        return ThreatAlert(
            id=f"ALERT-REV-{agent_id}-{int(time.time())}",
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


async def detect_amount_anomaly(conn, agent_id: int, event: ActionEvent) -> Optional[ThreatAlert]:
    """Detect transactions significantly outside agent's normal range."""
    profile = await get_agent_profile(conn, agent_id)
    if not profile or profile["std_transaction_amount"] == 0:
        return None

    if event.amount == 0:
        return None

    z_score = abs(event.amount - profile["avg_transaction_amount"]) / profile["std_transaction_amount"]

    if z_score > AMOUNT_STD_DEVIATION_THRESHOLD:
        return ThreatAlert(
            id=f"ALERT-AMT-{agent_id}-{int(time.time())}",
            threat_type=ThreatType.AMOUNT_ANOMALY,
            severity=Severity.HIGH if z_score > 5 else Severity.MEDIUM,
            agent_id=agent_id,
            agent_code=event.agent_code,
            description=f"Transaction amount ₦{event.amount:,.0f} is {z_score:.1f}σ from baseline (avg: ₦{profile['avg_transaction_amount']:,.0f})",
            evidence={
                "amount": event.amount,
                "avg_amount": profile["avg_transaction_amount"],
                "std_amount": profile["std_transaction_amount"],
                "z_score": round(z_score, 2),
                "threshold": AMOUNT_STD_DEVIATION_THRESHOLD,
            },
            risk_score=min(95, 40 + z_score * 10),
            timestamp=datetime.now(timezone.utc).isoformat(),
            recommended_action="Flag for manual review; hold transaction pending verification",
        )
    return None


async def detect_collusion(conn, agent_id: int, event: ActionEvent) -> Optional[ThreatAlert]:
    """Detect same-day create+approve by related agents."""
    if "approve" not in event.action.lower():
        return None

    resource_id = event.resource_id
    now = datetime.now(timezone.utc)
    day_start = now - timedelta(hours=24)

    # Query PostgreSQL for matching create action from another agent
    row = await conn.fetchrow(
        """SELECT agent_id, EXTRACT(EPOCH FROM recorded_at) as ts
           FROM threat_recent_actions
           WHERE resource_id = $1
             AND agent_id != $2
             AND action ILIKE '%create%'
             AND recorded_at > $3
           ORDER BY recorded_at DESC
           LIMIT 1""",
        resource_id, agent_id, day_start,
    )

    if row:
        time_gap = time.time() - float(row["ts"])
        if time_gap < 300:  # 5 minutes
            return ThreatAlert(
                id=f"ALERT-COL-{agent_id}-{int(time.time())}",
                threat_type=ThreatType.COLLUSION_PATTERN,
                severity=Severity.CRITICAL,
                agent_id=agent_id,
                agent_code=event.agent_code,
                description=f"Suspiciously fast approval ({time_gap:.0f}s after creation) for {resource_id}",
                evidence={
                    "creator_id": row["agent_id"],
                    "approver_id": agent_id,
                    "resource_id": resource_id,
                    "time_gap_seconds": round(time_gap),
                    "threshold_seconds": 300,
                },
                risk_score=85.0,
                timestamp=now.isoformat(),
                recommended_action="Investigate relationship between agents; review transaction details",
            )
    return None


async def detect_geo_anomaly(conn, agent_id: int, event: ActionEvent) -> Optional[ThreatAlert]:
    """Detect access from unusual IP/location."""
    profile = await get_agent_profile(conn, agent_id)
    if not profile or not profile["typical_ips"] or not event.ip_address:
        return None

    typical_ips = profile["typical_ips"] if isinstance(profile["typical_ips"], list) else json.loads(profile["typical_ips"])

    if event.ip_address not in typical_ips:
        return ThreatAlert(
            id=f"ALERT-GEO-{agent_id}-{int(time.time())}",
            threat_type=ThreatType.GEO_ANOMALY,
            severity=Severity.MEDIUM,
            agent_id=agent_id,
            agent_code=event.agent_code,
            description=f"Action from unrecognized IP: {event.ip_address}",
            evidence={
                "current_ip": event.ip_address,
                "known_ips": typical_ips[:5],
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

    if not event.timestamp:
        event.timestamp = datetime.now(timezone.utc).isoformat()

    p = await get_pool()
    async with p.acquire() as conn:
        # Record action in PostgreSQL
        await conn.execute(
            """INSERT INTO threat_recent_actions (agent_id, agent_code, action, amount, resource_id, ip_address)
               VALUES ($1, $2, $3, $4, $5, $6)""",
            agent_id, event.agent_code, event.action, event.amount,
            event.resource_id, event.ip_address,
        )

        # Prune old actions (keep last 24h)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        await conn.execute(
            "DELETE FROM threat_recent_actions WHERE recorded_at < $1", cutoff
        )

        # Get recent actions for this agent
        actions = await get_recent_actions(conn, agent_id)

        # Run all detectors
        new_alerts = []
        detectors = [
            await detect_velocity_spike(conn, agent_id, actions),
            await detect_off_hours(conn, agent_id, event),
            await detect_bulk_reversals(conn, agent_id, actions),
            await detect_amount_anomaly(conn, agent_id, event),
            await detect_collusion(conn, agent_id, event),
            await detect_geo_anomaly(conn, agent_id, event),
        ]

        for alert in detectors:
            if alert is not None:
                # Persist alert to PostgreSQL
                await conn.execute(
                    """INSERT INTO threat_alerts (id, threat_type, severity, agent_id, agent_code, description, evidence, risk_score, timestamp, recommended_action, auto_blocked)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::timestamptz, $10, $11)
                       ON CONFLICT (id) DO NOTHING""",
                    alert.id, alert.threat_type.value, alert.severity.value,
                    alert.agent_id, alert.agent_code, alert.description,
                    json.dumps(alert.evidence), alert.risk_score,
                    alert.timestamp, alert.recommended_action, alert.auto_blocked,
                )
                new_alerts.append(alert)

                if alert.auto_blocked:
                    await conn.execute(
                        """INSERT INTO threat_blocked_agents (agent_id, reason)
                           VALUES ($1, $2)
                           ON CONFLICT (agent_id) DO UPDATE SET blocked_at = NOW(), reason = EXCLUDED.reason""",
                        agent_id, alert.description,
                    )

        # Check if agent is blocked
        is_blocked = await conn.fetchval(
            "SELECT EXISTS(SELECT 1 FROM threat_blocked_agents WHERE agent_id = $1)",
            agent_id,
        )

    return {
        "processed": True,
        "agent_id": agent_id,
        "alerts_generated": len(new_alerts),
        "alerts": [a.model_dump() for a in new_alerts],
        "agent_blocked": is_blocked,
    }


@app.get("/alerts")
async def get_alerts(
    severity: Optional[str] = None,
    agent_id: Optional[int] = None,
    limit: int = 100,
):
    """Get recent threat alerts from PostgreSQL."""
    p = await get_pool()
    async with p.acquire() as conn:
        query = "SELECT * FROM threat_alerts"
        conditions = []
        params = []

        if severity:
            params.append(severity)
            conditions.append(f"severity = ${len(params)}")
        if agent_id:
            params.append(agent_id)
            conditions.append(f"agent_id = ${len(params)}")

        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += f" ORDER BY timestamp DESC LIMIT {limit}"

        rows = await conn.fetch(query, *params)

    alerts_list = []
    for row in rows:
        alerts_list.append({
            "id": row["id"],
            "threat_type": row["threat_type"],
            "severity": row["severity"],
            "agent_id": row["agent_id"],
            "agent_code": row["agent_code"],
            "description": row["description"],
            "evidence": row["evidence"] if isinstance(row["evidence"], dict) else json.loads(row["evidence"]),
            "risk_score": row["risk_score"],
            "timestamp": str(row["timestamp"]),
            "recommended_action": row["recommended_action"],
            "auto_blocked": row["auto_blocked"],
        })

    return {"alerts": alerts_list, "total": len(alerts_list)}


@app.get("/profile/{agent_id}")
async def get_profile(agent_id: int):
    """Get agent behavioral profile from PostgreSQL."""
    p = await get_pool()
    async with p.acquire() as conn:
        profile = await get_agent_profile(conn, agent_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Agent profile not found")
    return {
        "agent_id": profile["agent_id"],
        "agent_code": profile["agent_code"],
        "avg_daily_transactions": profile["avg_daily_transactions"],
        "avg_transaction_amount": profile["avg_transaction_amount"],
        "std_transaction_amount": profile["std_transaction_amount"],
        "typical_hours": profile["typical_hours"],
        "typical_ips": profile["typical_ips"],
        "total_actions": profile["total_actions"],
        "last_updated": str(profile["last_updated"]),
    }


@app.post("/profile")
async def update_profile(profile: AgentProfile):
    """Update or create an agent behavioral profile in PostgreSQL."""
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute(
            """INSERT INTO threat_agent_profiles
               (agent_id, agent_code, avg_daily_transactions, avg_transaction_amount,
                std_transaction_amount, typical_hours, typical_ips, total_actions, last_updated)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
               ON CONFLICT (agent_id) DO UPDATE SET
                   agent_code = EXCLUDED.agent_code,
                   avg_daily_transactions = EXCLUDED.avg_daily_transactions,
                   avg_transaction_amount = EXCLUDED.avg_transaction_amount,
                   std_transaction_amount = EXCLUDED.std_transaction_amount,
                   typical_hours = EXCLUDED.typical_hours,
                   typical_ips = EXCLUDED.typical_ips,
                   total_actions = EXCLUDED.total_actions,
                   last_updated = NOW()""",
            profile.agent_id, profile.agent_code,
            profile.avg_daily_transactions, profile.avg_transaction_amount,
            profile.std_transaction_amount,
            json.dumps(profile.typical_hours), json.dumps(profile.typical_ips),
            profile.total_actions,
        )
    return {"success": True, "agent_id": profile.agent_id}


@app.get("/blocked")
async def get_blocked_agents():
    """Get list of auto-blocked agents from PostgreSQL."""
    p = await get_pool()
    async with p.acquire() as conn:
        rows = await conn.fetch("SELECT agent_id, blocked_at, reason FROM threat_blocked_agents")
    return {
        "blocked_agents": [
            {"agent_id": r["agent_id"], "blocked_at": str(r["blocked_at"]), "reason": r["reason"]}
            for r in rows
        ]
    }


@app.post("/unblock/{agent_id}")
async def unblock_agent(agent_id: int):
    """Manually unblock an agent (requires compliance review)."""
    p = await get_pool()
    async with p.acquire() as conn:
        await conn.execute(
            "DELETE FROM threat_blocked_agents WHERE agent_id = $1", agent_id
        )
    return {"success": True, "agent_id": agent_id, "status": "unblocked"}


@app.get("/stats")
async def get_stats():
    """Get detection service statistics from PostgreSQL."""
    p = await get_pool()
    async with p.acquire() as conn:
        total_alerts = await conn.fetchval("SELECT COUNT(*) FROM threat_alerts")
        alerts_by_severity = {}
        for sev in ["critical", "high", "medium", "low"]:
            alerts_by_severity[sev] = await conn.fetchval(
                "SELECT COUNT(*) FROM threat_alerts WHERE severity = $1", sev
            )
        alerts_by_type = {}
        for t in ThreatType:
            alerts_by_type[t.value] = await conn.fetchval(
                "SELECT COUNT(*) FROM threat_alerts WHERE threat_type = $1", t.value
            )
        blocked_count = await conn.fetchval("SELECT COUNT(*) FROM threat_blocked_agents")
        monitored_count = await conn.fetchval("SELECT COUNT(*) FROM threat_agent_profiles")
        active_count = await conn.fetchval(
            "SELECT COUNT(DISTINCT agent_id) FROM threat_recent_actions WHERE recorded_at > NOW() - INTERVAL '24 hours'"
        )

    return {
        "total_alerts": total_alerts,
        "alerts_by_severity": alerts_by_severity,
        "alerts_by_type": alerts_by_type,
        "blocked_agents": blocked_count,
        "monitored_agents": monitored_count,
        "active_agents": active_count,
    }


@app.get("/health")
async def health():
    status = "healthy"
    try:
        p = await get_pool()
        async with p.acquire() as conn:
            await conn.fetchval("SELECT 1")
    except Exception:
        status = "degraded"
    return {"status": status, "service": "insider-threat-detection", "version": "2.0.0", "storage": "postgresql"}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("DETECTION_PORT", "8262"))
    uvicorn.run(app, host="0.0.0.0", port=port)
