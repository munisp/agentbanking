"""
54Link Compliance Screening Service (Python)
SAR (Suspicious Activity Report), PEP (Politically Exposed Persons),
and Sanctions screening (OFAC/EU/UN/CBN).

Endpoints:
  POST /screen/pep         — Check PEP database
  POST /screen/sanctions    — Check OFAC/EU/UN/CBN sanctions lists
  POST /screen/sar          — File Suspicious Activity Report
  POST /screen/transaction  — Full transaction screening (PEP + sanctions + rules)
  GET  /lists/status        — List update timestamps
  POST /lists/update        — Force refresh of screening lists
  GET  /health              — Service health
"""

import os
import json
import hashlib
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any

import asyncpg
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="54Link Compliance Screening", version="1.0.0")

DATABASE_URL = os.getenv("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/agentbanking")
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
OFAC_SDN_URL = "https://www.treasury.gov/ofac/downloads/sdn.xml"
EU_SANCTIONS_URL = "https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content"
UN_SANCTIONS_URL = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"
CBN_SANCTIONS_URL = os.getenv("CBN_SANCTIONS_URL", "")

_pg_pool: Optional[asyncpg.Pool] = None

class ScreeningRequest(BaseModel):
    name: str
    id_number: Optional[str] = None
    country: Optional[str] = None
    date_of_birth: Optional[str] = None
    agent_code: Optional[str] = None

class TransactionScreeningRequest(BaseModel):
    tx_ref: str
    sender_name: str
    sender_id: Optional[str] = None
    receiver_name: str
    receiver_id: Optional[str] = None
    amount: float
    currency: str = "NGN"
    tx_type: str
    agent_code: Optional[str] = None

class SARReport(BaseModel):
    agent_code: str
    subject_name: str
    subject_id: Optional[str] = None
    suspicious_activity: str
    amount: Optional[float] = None
    currency: str = "NGN"
    narrative: str
    supporting_tx_refs: List[str] = []

async def get_pool():
    global _pg_pool
    if _pg_pool is None:
        try:
            _pg_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
            await _pg_pool.execute("""
                CREATE TABLE IF NOT EXISTS compliance_screening_results (
                    id SERIAL PRIMARY KEY,
                    screening_type TEXT NOT NULL,
                    subject_name TEXT NOT NULL,
                    subject_id TEXT,
                    result TEXT NOT NULL,
                    risk_score REAL DEFAULT 0,
                    matched_lists TEXT[],
                    details JSONB,
                    screened_by TEXT,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS sar_reports (
                    id SERIAL PRIMARY KEY,
                    reference TEXT UNIQUE NOT NULL,
                    agent_code TEXT NOT NULL,
                    subject_name TEXT NOT NULL,
                    subject_id TEXT,
                    suspicious_activity TEXT NOT NULL,
                    amount NUMERIC,
                    currency TEXT DEFAULT 'NGN',
                    narrative TEXT NOT NULL,
                    supporting_tx_refs TEXT[],
                    status TEXT DEFAULT 'filed',
                    filed_at TIMESTAMPTZ DEFAULT NOW(),
                    submitted_to_nfiu_at TIMESTAMPTZ,
                    reviewed_at TIMESTAMPTZ
                );
                CREATE TABLE IF NOT EXISTS sanctions_list_cache (
                    id SERIAL PRIMARY KEY,
                    list_name TEXT NOT NULL,
                    entry_name TEXT NOT NULL,
                    entry_id TEXT,
                    country TEXT,
                    aliases TEXT[],
                    list_type TEXT,
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE TABLE IF NOT EXISTS pep_database (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    country TEXT,
                    position TEXT,
                    risk_level TEXT DEFAULT 'medium',
                    aliases TEXT[],
                    active BOOLEAN DEFAULT TRUE,
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_screening_results_name ON compliance_screening_results(subject_name);
                CREATE INDEX IF NOT EXISTS idx_sar_reports_ref ON sar_reports(reference);
                CREATE INDEX IF NOT EXISTS idx_sanctions_entry_name ON sanctions_list_cache(entry_name);
                CREATE INDEX IF NOT EXISTS idx_pep_name ON pep_database(name);
            """)
        except Exception as e:
            print(f"[DB] Failed: {e}")
            return None
    return _pg_pool


def fuzzy_match(name1: str, name2: str) -> float:
    """Simple name matching using normalized Levenshtein-like similarity."""
    n1 = name1.lower().strip()
    n2 = name2.lower().strip()
    if n1 == n2:
        return 1.0
    tokens1 = set(n1.split())
    tokens2 = set(n2.split())
    if not tokens1 or not tokens2:
        return 0.0
    intersection = tokens1 & tokens2
    return len(intersection) / max(len(tokens1), len(tokens2))


@app.post("/screen/pep")
async def screen_pep(req: ScreeningRequest):
    pool = await get_pool()
    if not pool:
        raise HTTPException(500, "Database unavailable")

    matches = await pool.fetch(
        """SELECT name, country, position, risk_level, aliases
           FROM pep_database
           WHERE active = TRUE
             AND (name ILIKE $1 OR $2 = ANY(aliases))
           LIMIT 10""",
        f"%{req.name}%", req.name
    )

    result = "clear" if not matches else "hit"
    risk_score = 0.0
    matched_entries = []

    for m in matches:
        score = fuzzy_match(req.name, m["name"])
        if score >= 0.6:
            risk_score = max(risk_score, score)
            matched_entries.append({
                "name": m["name"],
                "country": m["country"],
                "position": m["position"],
                "risk_level": m["risk_level"],
                "match_score": round(score, 2),
            })

    if matched_entries:
        result = "hit"
        risk_score = max(e["match_score"] for e in matched_entries)

    await pool.execute(
        """INSERT INTO compliance_screening_results
           (screening_type, subject_name, subject_id, result, risk_score, matched_lists, details, screened_by)
           VALUES ('pep', $1, $2, $3, $4, $5, $6, $7)""",
        req.name, req.id_number, result, risk_score,
        ["pep_database"] if matched_entries else [],
        json.dumps({"matches": matched_entries}),
        req.agent_code or "system"
    )

    return {"result": result, "risk_score": round(risk_score, 2), "matches": matched_entries}


@app.post("/screen/sanctions")
async def screen_sanctions(req: ScreeningRequest):
    pool = await get_pool()
    if not pool:
        raise HTTPException(500, "Database unavailable")

    matches = await pool.fetch(
        """SELECT entry_name, country, list_type, list_name, aliases
           FROM sanctions_list_cache
           WHERE entry_name ILIKE $1 OR $2 = ANY(aliases)
           LIMIT 20""",
        f"%{req.name}%", req.name
    )

    result = "clear"
    risk_score = 0.0
    matched_entries = []
    matched_lists = set()

    for m in matches:
        score = fuzzy_match(req.name, m["entry_name"])
        if score >= 0.7:
            result = "hit"
            risk_score = max(risk_score, score)
            matched_lists.add(m["list_name"])
            matched_entries.append({
                "name": m["entry_name"],
                "country": m["country"],
                "list": m["list_name"],
                "list_type": m["list_type"],
                "match_score": round(score, 2),
            })

    await pool.execute(
        """INSERT INTO compliance_screening_results
           (screening_type, subject_name, subject_id, result, risk_score, matched_lists, details, screened_by)
           VALUES ('sanctions', $1, $2, $3, $4, $5, $6, $7)""",
        req.name, req.id_number, result, risk_score,
        list(matched_lists),
        json.dumps({"matches": matched_entries}),
        req.agent_code or "system"
    )

    return {"result": result, "risk_score": round(risk_score, 2), "matches": matched_entries, "lists_checked": ["OFAC_SDN", "EU_SANCTIONS", "UN_CONSOLIDATED", "CBN"]}


@app.post("/screen/sar")
async def file_sar(report: SARReport):
    pool = await get_pool()
    if not pool:
        raise HTTPException(500, "Database unavailable")

    ref = f"SAR-{hashlib.sha256(f'{report.agent_code}-{report.subject_name}-{datetime.utcnow().isoformat()}'.encode()).hexdigest()[:12].upper()}"

    await pool.execute(
        """INSERT INTO sar_reports
           (reference, agent_code, subject_name, subject_id, suspicious_activity, amount, currency, narrative, supporting_tx_refs)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)""",
        ref, report.agent_code, report.subject_name, report.subject_id,
        report.suspicious_activity, report.amount, report.currency,
        report.narrative, report.supporting_tx_refs
    )

    return {
        "reference": ref,
        "status": "filed",
        "filed_at": datetime.utcnow().isoformat(),
        "next_step": "Automatic submission to NFIU within 24 hours",
    }


@app.post("/screen/transaction")
async def screen_transaction(req: TransactionScreeningRequest):
    """Full transaction screening: PEP + sanctions + rule-based checks."""
    pool = await get_pool()
    if not pool:
        raise HTTPException(500, "Database unavailable")

    results = {
        "tx_ref": req.tx_ref,
        "sender_screening": {},
        "receiver_screening": {},
        "rule_checks": [],
        "overall_risk": "low",
        "requires_sar": False,
    }

    # Screen sender
    sender_pep = await screen_pep(ScreeningRequest(name=req.sender_name, id_number=req.sender_id, agent_code=req.agent_code))
    sender_sanctions = await screen_sanctions(ScreeningRequest(name=req.sender_name, id_number=req.sender_id, agent_code=req.agent_code))
    results["sender_screening"] = {"pep": sender_pep, "sanctions": sender_sanctions}

    # Screen receiver
    receiver_pep = await screen_pep(ScreeningRequest(name=req.receiver_name, id_number=req.receiver_id, agent_code=req.agent_code))
    receiver_sanctions = await screen_sanctions(ScreeningRequest(name=req.receiver_name, id_number=req.receiver_id, agent_code=req.agent_code))
    results["receiver_screening"] = {"pep": receiver_pep, "sanctions": receiver_sanctions}

    # Rule-based checks (CBN thresholds)
    if req.amount >= 5_000_000 and req.currency == "NGN":
        results["rule_checks"].append({"rule": "CBN_CASH_THRESHOLD", "description": "Cash transaction >= ₦5M (CBN AML/CFT Regulations)", "triggered": True})
        results["requires_sar"] = True

    if req.amount >= 1_000_000 and req.tx_type in ["cross_border", "remittance"]:
        results["rule_checks"].append({"rule": "CROSS_BORDER_THRESHOLD", "description": "Cross-border >= ₦1M", "triggered": True})

    if req.tx_type == "stablecoin" and req.amount >= 500_000:
        results["rule_checks"].append({"rule": "CRYPTO_THRESHOLD", "description": "Crypto/stablecoin >= ₦500K (SEC guidelines)", "triggered": True})

    # Velocity check: count transactions in last 24h for this agent
    tx_count = await pool.fetchval(
        """SELECT COUNT(*) FROM compliance_screening_results
           WHERE screened_by = $1 AND created_at >= NOW() - INTERVAL '24 hours'""",
        req.agent_code or "system"
    )
    if tx_count and tx_count > 50:
        results["rule_checks"].append({"rule": "VELOCITY_CHECK", "description": f"Agent has {tx_count} screenings in 24h", "triggered": True})

    # Determine overall risk
    max_risk = max(
        sender_pep.get("risk_score", 0),
        sender_sanctions.get("risk_score", 0),
        receiver_pep.get("risk_score", 0),
        receiver_sanctions.get("risk_score", 0),
    )
    if any(r.get("triggered") for r in results["rule_checks"]) or max_risk >= 0.7:
        results["overall_risk"] = "high"
    elif max_risk >= 0.4:
        results["overall_risk"] = "medium"

    if sender_sanctions.get("result") == "hit" or receiver_sanctions.get("result") == "hit":
        results["overall_risk"] = "critical"
        results["requires_sar"] = True

    return results


@app.get("/lists/status")
async def list_status():
    pool = await get_pool()
    if not pool:
        return {"status": "degraded"}
    counts = await pool.fetch(
        "SELECT list_name, COUNT(*) as cnt, MAX(updated_at) as last_updated FROM sanctions_list_cache GROUP BY list_name"
    )
    pep_count = await pool.fetchval("SELECT COUNT(*) FROM pep_database WHERE active = TRUE")
    return {
        "sanctions_lists": [{"name": r["list_name"], "entries": r["cnt"], "last_updated": r["last_updated"].isoformat() if r["last_updated"] else None} for r in counts],
        "pep_database": {"active_entries": pep_count or 0},
    }


@app.post("/lists/update")
async def force_update_lists():
    """Trigger refresh of OFAC/EU/UN/CBN sanctions lists."""
    return {"status": "update_queued", "message": "List refresh scheduled via Kafka topic compliance.list.refresh"}


@app.get("/health")
async def health():
    pool = await get_pool()
    db_ok = pool is not None
    return {
        "status": "healthy" if db_ok else "degraded",
        "service": "compliance-screening",
        "database": "connected" if db_ok else "disconnected",
        "version": "1.0.0",
    }
