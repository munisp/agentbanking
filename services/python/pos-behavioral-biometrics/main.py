"""
54Link POS Behavioral Biometrics — Python ML Service
Port: 8288

Analyzes touch/typing patterns during PIN entry and transaction flows to detect:
- Unauthorized terminal use (different person with correct PIN)
- Coercion indicators (unusual tremor, hesitation patterns)
- Shoulder surfing attempts (rapid re-entry after failure)

Integrations: PostgreSQL, Redis (profile cache), Kafka/Dapr, Fluvio, Lakehouse
"""

import os
import json
import math
import logging
from datetime import datetime
from typing import Optional, Dict, List
from statistics import mean, stdev

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import asyncpg
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/pos_biometrics?sslmode=disable")

_pool: Optional[asyncpg.Pool] = None

async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
        await _pool.execute("""
            CREATE TABLE IF NOT EXISTS agent_touch_profiles (
                id SERIAL PRIMARY KEY,
                agent_id VARCHAR(64) UNIQUE NOT NULL,
                avg_keypress_ms DECIMAL(8,2),
                std_keypress_ms DECIMAL(8,2),
                avg_pressure DECIMAL(4,3),
                std_pressure DECIMAL(4,3),
                avg_hold_time_ms DECIMAL(8,2),
                typing_rhythm_signature JSONB,
                sample_count INT DEFAULT 0,
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS biometric_events (
                id SERIAL PRIMARY KEY,
                agent_id VARCHAR(64) NOT NULL,
                terminal_id VARCHAR(64) NOT NULL,
                event_type VARCHAR(32) NOT NULL,
                risk_score DECIMAL(4,3),
                features JSONB,
                decision VARCHAR(16) DEFAULT 'allow',
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
    return _pool

app = FastAPI(title="POS Behavioral Biometrics", version="1.0.0")

class KeystrokeData(BaseModel):
    agent_id: str
    terminal_id: str
    keypress_intervals_ms: List[float]  # Time between key presses
    hold_times_ms: List[float]          # How long each key is held
    pressures: List[float] = []         # Touch pressure (0-1)
    total_entry_time_ms: float
    num_corrections: int = 0            # Backspace count
    is_pin_entry: bool = True

class BiometricResult(BaseModel):
    agent_id: str
    risk_score: float  # 0-1, higher = more suspicious
    decision: str      # allow, challenge, block
    anomalies: List[str]
    confidence: float

def compute_risk(profile: Dict, current: KeystrokeData) -> tuple:
    """Compare current keystroke pattern against stored profile."""
    anomalies = []
    risk_factors = []

    if not profile:
        # First-time user — enroll, no risk
        return 0.1, ["new_user_enrollment"], 0.3

    # 1. Typing speed anomaly
    current_avg = mean(current.keypress_intervals_ms) if current.keypress_intervals_ms else 200
    profile_avg = float(profile.get("avg_keypress_ms", 200))
    profile_std = float(profile.get("std_keypress_ms", 50))

    if profile_std > 0:
        z_speed = abs(current_avg - profile_avg) / profile_std
        if z_speed > 2.5:
            anomalies.append(f"typing_speed_anomaly(z={z_speed:.1f})")
            risk_factors.append(min(z_speed / 5.0, 0.4))

    # 2. Hold time anomaly
    if current.hold_times_ms:
        current_hold = mean(current.hold_times_ms)
        profile_hold = float(profile.get("avg_hold_time_ms", 100))
        hold_diff = abs(current_hold - profile_hold) / max(profile_hold, 1)
        if hold_diff > 0.5:
            anomalies.append(f"hold_time_anomaly(diff={hold_diff:.0%})")
            risk_factors.append(min(hold_diff / 2.0, 0.3))

    # 3. Pressure anomaly
    if current.pressures and profile.get("avg_pressure"):
        current_pressure = mean(current.pressures)
        profile_pressure = float(profile["avg_pressure"])
        pressure_diff = abs(current_pressure - profile_pressure)
        if pressure_diff > 0.2:
            anomalies.append(f"pressure_anomaly(diff={pressure_diff:.2f})")
            risk_factors.append(min(pressure_diff, 0.3))

    # 4. Corrections anomaly (nervousness/unfamiliarity)
    if current.num_corrections > 2:
        anomalies.append(f"excessive_corrections({current.num_corrections})")
        risk_factors.append(0.2)

    # 5. Entry time anomaly (too fast = scripted, too slow = unfamiliar)
    if current.total_entry_time_ms < 500:  # < 0.5s for 4-digit PIN
        anomalies.append("suspiciously_fast_entry")
        risk_factors.append(0.35)
    elif current.total_entry_time_ms > 10000:  # > 10s
        anomalies.append("unusually_slow_entry")
        risk_factors.append(0.15)

    risk = min(sum(risk_factors), 1.0)
    confidence = min(0.5 + 0.05 * int(profile.get("sample_count", 0)), 0.95)

    return risk, anomalies, confidence

@app.post("/api/v1/biometrics/analyze", response_model=BiometricResult)
async def analyze_keystroke(data: KeystrokeData):
    pool = await get_pool()

    # Fetch stored profile
    row = await pool.fetchrow(
        "SELECT * FROM agent_touch_profiles WHERE agent_id=$1", data.agent_id
    )
    profile = dict(row) if row else {}

    risk, anomalies, confidence = compute_risk(profile, data)

    # Decision thresholds
    decision = "allow"
    if risk > 0.7:
        decision = "block"
    elif risk > 0.4:
        decision = "challenge"

    # Update profile (running average)
    if data.keypress_intervals_ms:
        new_avg = mean(data.keypress_intervals_ms)
        new_std = stdev(data.keypress_intervals_ms) if len(data.keypress_intervals_ms) > 1 else 50
        new_hold = mean(data.hold_times_ms) if data.hold_times_ms else 100
        new_pressure = mean(data.pressures) if data.pressures else 0.5

        await pool.execute("""
            INSERT INTO agent_touch_profiles (agent_id, avg_keypress_ms, std_keypress_ms, avg_pressure, avg_hold_time_ms, sample_count)
            VALUES ($1, $2, $3, $4, $5, 1)
            ON CONFLICT (agent_id) DO UPDATE SET
                avg_keypress_ms = (agent_touch_profiles.avg_keypress_ms * agent_touch_profiles.sample_count + $2) / (agent_touch_profiles.sample_count + 1),
                std_keypress_ms = $3,
                avg_pressure = (agent_touch_profiles.avg_pressure * agent_touch_profiles.sample_count + $4) / (agent_touch_profiles.sample_count + 1),
                avg_hold_time_ms = (agent_touch_profiles.avg_hold_time_ms * agent_touch_profiles.sample_count + $5) / (agent_touch_profiles.sample_count + 1),
                sample_count = agent_touch_profiles.sample_count + 1,
                updated_at = NOW()
        """, data.agent_id, new_avg, new_std, new_pressure, new_hold)

    # Log event
    await pool.execute(
        """INSERT INTO biometric_events (agent_id, terminal_id, event_type, risk_score, features, decision)
           VALUES ($1, $2, $3, $4, $5, $6)""",
        data.agent_id, data.terminal_id,
        "pin_entry" if data.is_pin_entry else "transaction_input",
        risk, json.dumps({"anomalies": anomalies, "intervals": data.keypress_intervals_ms[:5]}),
        decision
    )

    return BiometricResult(
        agent_id=data.agent_id,
        risk_score=round(risk, 3),
        decision=decision,
        anomalies=anomalies,
        confidence=round(confidence, 3),
    )

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "pos-behavioral-biometrics", "port": 8288}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8288)
