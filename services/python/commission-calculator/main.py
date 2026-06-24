
from fastapi import FastAPI
import sys as _sys2, os as _os2
_sys2.path.insert(0, _os2.path.join(_os2.path.dirname(_os2.path.abspath(__file__)), ".."))
from shared.middleware import apply_middleware, ErrorResponse
from datetime import datetime

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


app = FastAPI(title="commission-calculator")

@app.on_event("startup")
async def _init_pg_pool():
    await get_pg_pool()

apply_middleware(app, enable_auth=True)

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "commission-calculator", "timestamp": datetime.utcnow().isoformat()}

"""
Commission Calculator — Sprint 78
Tiered commission engine for POS agents
Supports: volume-based tiers, transaction-type multipliers, bonus thresholds, clawback rules
"""
import json
import time
from dataclasses import dataclass, asdict, field
from typing import List, Dict, Optional

# --- Production: Graceful Shutdown ---
import signal
import sys
import atexit
import logging

import psycopg2
import psycopg2.extras

def _init_persistence():
    """Initialize PostgreSQL persistence for commission-calculator."""
    import os
    try:
        conn = psycopg2.connect(os.environ.get('DATABASE_URL', 'postgres://postgres:postgres@localhost:5432/commission_calculator'))
        
        
        return conn
    except Exception as e:
        import logging
        logging.warning(f"Database unavailable ({e}) — running in-memory only")
        return None

_persistence_db = _init_persistence()

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
class CommissionTier:
    tier_name: str
    min_volume: float
    max_volume: float
    base_rate_pct: float
    bonus_rate_pct: float
    min_tx_count: int

TIERS = [
    CommissionTier("Bronze", 0, 500000, 0.5, 0.0, 0),
    CommissionTier("Silver", 500001, 2000000, 0.7, 0.1, 50),
    CommissionTier("Gold", 2000001, 10000000, 0.9, 0.2, 200),
    CommissionTier("Platinum", 10000001, 50000000, 1.1, 0.3, 500),
    CommissionTier("Diamond", 50000001, float('inf'), 1.3, 0.5, 1000),
]

TX_TYPE_MULTIPLIERS = {
    "cash_in": 1.0,
    "cash_out": 1.2,
    "transfer": 0.8,
    "bill_payment": 0.6,
    "airtime": 0.4,
    "card_payment": 0.9,
    "qr_payment": 0.7,
    "nfc_payment": 0.9,
    "ussd": 0.5,
}

@dataclass
class CommissionResult:
    agent_id: str
    period: str
    tier: str
    total_volume: float
    tx_count: int
    base_commission: float
    bonus_commission: float
    total_commission: float
    effective_rate_pct: float
    breakdown: List[Dict]
    clawback_amount: float = 0.0
    net_commission: float = 0.0

class CommissionEngine:
    def __init__(self):
        self.history: Dict[str, List[CommissionResult]] = {}

    def get_tier(self, volume: float) -> CommissionTier:
        for tier in TIERS:
            if tier.min_volume <= volume <= tier.max_volume:
                return tier
        return TIERS[0]

    def calculate(self, agent_id: str, transactions: List[Dict], period: str = "monthly") -> CommissionResult:
        total_volume = sum(tx.get("amount", 0) for tx in transactions)
        tx_count = len(transactions)
        tier = self.get_tier(total_volume)
        breakdown = []
        base_total = 0.0
        for tx in transactions:
            tx_type = tx.get("type", "cash_in")
            amount = tx.get("amount", 0)
            multiplier = TX_TYPE_MULTIPLIERS.get(tx_type, 1.0)
            commission = amount * (tier.base_rate_pct / 100) * multiplier
            base_total += commission
            breakdown.append({
                "tx_ref": tx.get("ref", ""),
                "type": tx_type,
                "amount": amount,
                "multiplier": multiplier,
                "commission": round(commission, 2),
            })
        bonus = 0.0
        if tx_count >= tier.min_tx_count and tier.bonus_rate_pct > 0:
            bonus = total_volume * (tier.bonus_rate_pct / 100)
        # Clawback for reversed transactions
        reversed_txs = [tx for tx in transactions if tx.get("status") == "reversed"]
        clawback = sum(
            tx.get("amount", 0) * (tier.base_rate_pct / 100) * TX_TYPE_MULTIPLIERS.get(tx.get("type", "cash_in"), 1.0)
            for tx in reversed_txs
        )
        total = base_total + bonus
        net = total - clawback
        effective_rate = (net / total_volume * 100) if total_volume > 0 else 0
        result = CommissionResult(
            agent_id=agent_id,
            period=period,
            tier=tier.tier_name,
            total_volume=round(total_volume, 2),
            tx_count=tx_count,
            base_commission=round(base_total, 2),
            bonus_commission=round(bonus, 2),
            total_commission=round(total, 2),
            effective_rate_pct=round(effective_rate, 4),
            breakdown=breakdown[:10],  # Top 10 for display
            clawback_amount=round(clawback, 2),
            net_commission=round(net, 2),
        )
        if agent_id not in self.history:
            self.history[agent_id] = []
        self.history[agent_id].append(result)
        return result

def main():
    engine = CommissionEngine()
    # Simulate agent with mixed transactions
    test_txs = [
        {"ref": f"TX-{i:04d}", "type": "cash_in", "amount": 50000 + i * 1000, "status": "completed"} for i in range(30)
    ] + [
        {"ref": f"TX-{i:04d}", "type": "cash_out", "amount": 30000 + i * 500, "status": "completed"} for i in range(30, 50)
    ] + [
        {"ref": "TX-0099", "type": "transfer", "amount": 100000, "status": "reversed"},
    ]
    result = engine.calculate("AGT-001", test_txs, "2026-04")
    print(f"[commission-calculator] Agent {result.agent_id}")
    print(f"  Tier: {result.tier} | Volume: ₦{result.total_volume:,.2f} | Txs: {result.tx_count}")
    print(f"  Base: ₦{result.base_commission:,.2f} | Bonus: ₦{result.bonus_commission:,.2f}")
    print(f"  Clawback: ₦{result.clawback_amount:,.2f} | Net: ₦{result.net_commission:,.2f}")
    print(f"  Effective Rate: {result.effective_rate_pct}%")

if __name__ == "__main__":
    main()
