"""
Lakehouse + Mojaloop Sidecar — Python FastAPI service providing:
1. Lakehouse: Delta Lake snapshots for commission, settlement, and dispute data
2. Mojaloop: ILP (Interledger Protocol) adapter for cross-border transfers

Connects to PostgreSQL for source data, writes Parquet/Delta to local storage,
and provides Mojaloop-compatible transfer endpoints.

Audit: All snapshot jobs are logged to the lakehouse_sync_log PostgreSQL table
(migration 0047) for lineage tracking and replay capability.
"""
import os
import json
import uuid
import hashlib
import base64
import logging
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, date as date_type
from typing import Optional, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# ── Configuration ─────────────────────────────────────────────────────────

POSTGRES_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/pos_shell")
LAKEHOUSE_PATH = os.getenv("LAKEHOUSE_PATH", "/var/lib/54agent/lakehouse")
MOJALOOP_HUB_URL = os.getenv("MOJALOOP_HUB_URL", "")
MOJALOOP_FSP_ID = os.getenv("MOJALOOP_FSP_ID", "54agent-fsp")
PORT = int(os.getenv("LAKEHOUSE_MOJALOOP_PORT", "8050"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("lakehouse-mojaloop")

app = FastAPI(
    title="Lakehouse + Mojaloop Sidecar",
    version="1.0.0",
    description="Delta Lake snapshots & Mojaloop ILP adapter for 54agent POS Shell",
)

# ── Lakehouse Sync Log Helper ─────────────────────────────────────────────

def _log_sync_to_db(
    job_id: str,
    bucket: str,
    object_key: str,
    table_source: str,
    record_count: int,
    size_bytes: int,
    fmt: str,
    status: str,
    partition_date: Optional[str],
    started_at: datetime,
    duration_ms: int,
    error_message: Optional[str] = None,
    checksum: Optional[str] = None,
) -> None:
    """
    Persist a lakehouse sync job record to the lakehouse_sync_log table.
    Called after each snapshot completes (success or failure).
    """
    try:
        import psycopg2
        conn = psycopg2.connect(POSTGRES_URL)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO lakehouse_sync_log
              (job_id, bucket, object_key, format, table_source, record_count,
               size_bytes, status, error_message, checksum, partition_date,
               started_at, completed_at, duration_ms, triggered_by, created_at)
            VALUES
              (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s, 'lakehouse-sidecar', NOW())
            ON CONFLICT (job_id) DO NOTHING
            """,
            (
                job_id, bucket, object_key, fmt, table_source,
                record_count, size_bytes, status, error_message, checksum,
                partition_date, started_at, duration_ms,
            ),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.warning(f"[Lakehouse] Failed to persist sync log: {e}")


# ── Health ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "lakehouse-mojaloop-sidecar",
        "version": "1.0.0",
        "lakehouse_path": LAKEHOUSE_PATH,
        "mojaloop_hub": MOJALOOP_HUB_URL or None,
        "mojaloop_hub_configured": bool(MOJALOOP_HUB_URL),
        "fsp_id": MOJALOOP_FSP_ID,
    }


# ── Lakehouse: Delta Lake Snapshot Models ─────────────────────────────────

class SnapshotRequest(BaseModel):
    date: str = Field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    format: str = "parquet"  # parquet or delta


class SnapshotResponse(BaseModel):
    snapshot_id: str
    table: str
    date: str
    row_count: int
    file_path: str
    format: str
    created_at: str


# ── Lakehouse: Commission Snapshot ────────────────────────────────────────

@app.post("/snapshot/commission", response_model=SnapshotResponse)
async def snapshot_commission(req: SnapshotRequest):
    """
    Export commission_ledger + commission_splits to Delta Lake / Parquet.
    Queries PostgreSQL, converts to Arrow, writes to lakehouse path.
    """
    snapshot_id = f"comm-{req.date}-{uuid.uuid4().hex[:8]}"
    table_path = os.path.join(LAKEHOUSE_PATH, "commission", req.date)
    os.makedirs(table_path, exist_ok=True)
    file_path = os.path.join(table_path, f"commission_ledger.{req.format}")
    started_at = datetime.now(timezone.utc)
    t0 = time.monotonic()

    try:
        row_count = await _export_table_snapshot(
            query=f"""
                SELECT cl.id, cl.transaction_id, cl.agent_id, cl.agent_code,
                       cl.amount, cl.rate, cl.tier_name, cl.hierarchy_level,
                       cl.entry_type, cl.parent_agent_id, cl.created_at
                FROM commission_ledger cl
                WHERE cl.created_at::date = '{req.date}'
                ORDER BY cl.id
            """,
            table_name="commission_ledger",
            output_path=table_path,
            fmt=req.format,
        )
        size_bytes = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        checksum = _file_checksum(file_path)
        duration_ms = int((time.monotonic() - t0) * 1000)
        _log_sync_to_db(
            job_id=snapshot_id, bucket="54link-lakehouse",
            object_key=f"commission/{req.date}/commission_ledger.{req.format}",
            table_source="commission_ledger", record_count=row_count,
            size_bytes=size_bytes, fmt=req.format, status="completed",
            partition_date=req.date, started_at=started_at,
            duration_ms=duration_ms, checksum=checksum,
        )
    except Exception as e:
        # Fail loud: never substitute sample data for a failed snapshot.
        logger.error(f"Commission snapshot failed: {e}")
        duration_ms = int((time.monotonic() - t0) * 1000)
        _log_sync_to_db(
            job_id=snapshot_id, bucket="54link-lakehouse",
            object_key=f"commission/{req.date}/commission_ledger.{req.format}",
            table_source="commission_ledger", record_count=0,
            size_bytes=0, fmt=req.format, status="failed",
            partition_date=req.date, started_at=started_at,
            duration_ms=duration_ms, error_message=str(e),
        )
        raise HTTPException(status_code=503, detail=f"Commission snapshot failed: {e}")

    logger.info(f"Commission snapshot: {snapshot_id} ({row_count} rows)")

    return SnapshotResponse(
        snapshot_id=snapshot_id,
        table="commission_ledger",
        date=req.date,
        row_count=row_count,
        file_path=file_path,
        format=req.format,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


# ── Lakehouse: Settlement Snapshot ────────────────────────────────────────

@app.post("/snapshot/settlement", response_model=SnapshotResponse)
async def snapshot_settlement(req: SnapshotRequest):
    """Export settlement audit_log entries to Delta Lake / Parquet."""
    snapshot_id = f"settle-{req.date}-{uuid.uuid4().hex[:8]}"
    table_path = os.path.join(LAKEHOUSE_PATH, "settlement", req.date)
    os.makedirs(table_path, exist_ok=True)
    file_path = os.path.join(table_path, f"settlement_audit.{req.format}")
    started_at = datetime.now(timezone.utc)
    t0 = time.monotonic()

    try:
        row_count = await _export_table_snapshot(
            query=f"""
                SELECT id, action, performed_by, ip_address, details, created_at
                FROM audit_log
                WHERE action LIKE 'settlement%%'
                  AND created_at::date = '{req.date}'
                ORDER BY id
            """,
            table_name="settlement_audit",
            output_path=table_path,
            fmt=req.format,
        )
        size_bytes = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        checksum = _file_checksum(file_path)
        duration_ms = int((time.monotonic() - t0) * 1000)
        _log_sync_to_db(
            job_id=snapshot_id, bucket="54link-lakehouse",
            object_key=f"settlement/{req.date}/settlement_audit.{req.format}",
            table_source="audit_log", record_count=row_count,
            size_bytes=size_bytes, fmt=req.format, status="completed",
            partition_date=req.date, started_at=started_at,
            duration_ms=duration_ms, checksum=checksum,
        )
    except Exception as e:
        # Fail loud: never substitute sample data for a failed snapshot.
        logger.error(f"Settlement snapshot failed: {e}")
        duration_ms = int((time.monotonic() - t0) * 1000)
        _log_sync_to_db(
            job_id=snapshot_id, bucket="54link-lakehouse",
            object_key=f"settlement/{req.date}/settlement_audit.{req.format}",
            table_source="audit_log", record_count=0,
            size_bytes=0, fmt=req.format, status="failed",
            partition_date=req.date, started_at=started_at,
            duration_ms=duration_ms, error_message=str(e),
        )
        raise HTTPException(status_code=503, detail=f"Settlement snapshot failed: {e}")

    return SnapshotResponse(
        snapshot_id=snapshot_id,
        table="settlement_audit",
        date=req.date,
        row_count=row_count,
        file_path=file_path,
        format=req.format,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


# ── Lakehouse: Dispute Snapshot ───────────────────────────────────────────

@app.post("/snapshot/dispute", response_model=SnapshotResponse)
async def snapshot_dispute(req: SnapshotRequest):
    """Export disputes + refunds to Delta Lake / Parquet."""
    snapshot_id = f"dispute-{req.date}-{uuid.uuid4().hex[:8]}"
    table_path = os.path.join(LAKEHOUSE_PATH, "dispute", req.date)
    os.makedirs(table_path, exist_ok=True)
    file_path = os.path.join(table_path, f"disputes.{req.format}")
    started_at = datetime.now(timezone.utc)
    t0 = time.monotonic()

    try:
        row_count = await _export_table_snapshot(
            query=f"""
                SELECT d.id, d.dispute_ref, d.transaction_id, d.raised_by_agent_id,
                       d.status, d.reason, d.amount, d.resolution_notes,
                       d.created_at, d.resolved_at
                FROM disputes d
                WHERE d.created_at::date = '{req.date}'
                ORDER BY d.id
            """,
            table_name="disputes",
            output_path=table_path,
            fmt=req.format,
        )
        size_bytes = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        checksum = _file_checksum(file_path)
        duration_ms = int((time.monotonic() - t0) * 1000)
        _log_sync_to_db(
            job_id=snapshot_id, bucket="54link-lakehouse",
            object_key=f"dispute/{req.date}/disputes.{req.format}",
            table_source="disputes", record_count=row_count,
            size_bytes=size_bytes, fmt=req.format, status="completed",
            partition_date=req.date, started_at=started_at,
            duration_ms=duration_ms, checksum=checksum,
        )
    except Exception as e:
        # Fail loud: never substitute sample data for a failed snapshot.
        logger.error(f"Dispute snapshot failed: {e}")
        duration_ms = int((time.monotonic() - t0) * 1000)
        _log_sync_to_db(
            job_id=snapshot_id, bucket="54link-lakehouse",
            object_key=f"dispute/{req.date}/disputes.{req.format}",
            table_source="disputes", record_count=0,
            size_bytes=0, fmt=req.format, status="failed",
            partition_date=req.date, started_at=started_at,
            duration_ms=duration_ms, error_message=str(e),
        )
        raise HTTPException(status_code=503, detail=f"Dispute snapshot failed: {e}")

    return SnapshotResponse(
        snapshot_id=snapshot_id,
        table="disputes",
        date=req.date,
        row_count=row_count,
        file_path=file_path,
        format=req.format,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


# ── Lakehouse: Internal Helpers ───────────────────────────────────────────

async def _export_table_snapshot(
    query: str, table_name: str, output_path: str, fmt: str
) -> int:
    """Execute SQL query, convert to Arrow table, write to Parquet/Delta."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    try:
        import psycopg2
        conn = psycopg2.connect(POSTGRES_URL)
        cur = conn.cursor()
        cur.execute(query)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()
        cur.close()
        conn.close()
    except Exception:
        raise

    if not rows:
        return 0

    # Convert to Arrow
    arrays = []
    for i, col in enumerate(columns):
        col_data = [row[i] for row in rows]
        # Convert datetime objects to strings for Arrow compatibility
        converted = []
        for v in col_data:
            if isinstance(v, datetime):
                converted.append(v.isoformat())
            elif v is None:
                converted.append(None)
            else:
                converted.append(str(v))
        arrays.append(pa.array(converted, type=pa.string()))

    table = pa.table({col: arr for col, arr in zip(columns, arrays)})

    file_path = os.path.join(output_path, f"{table_name}.{fmt}")

    if fmt == "delta":
        try:
            from deltalake import write_deltalake
            delta_path = os.path.join(output_path, f"{table_name}_delta")
            write_deltalake(delta_path, table, mode="overwrite")
        except ImportError:
            pq.write_table(table, file_path)
    else:
        pq.write_table(table, file_path)

    return len(rows)


def _file_checksum(file_path: str) -> Optional[str]:
    """Compute SHA-256 checksum of a file."""
    try:
        if not os.path.exists(file_path):
            return None
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return None


# ── Mojaloop: ILP Transfer Models ────────────────────────────────────────

class IlpTransferRequest(BaseModel):
    payer_fsp: str = Field(alias="payerFsp", default=MOJALOOP_FSP_ID)
    payee_fsp: str = Field(alias="payeeFsp", default="external-fsp")
    amount: float
    currency: str = "NGN"
    agent_code: Optional[str] = Field(alias="agentCode", default=None)
    transaction_ref: Optional[str] = Field(alias="transactionRef", default=None)

    class Config:
        populate_by_name = True


class IlpTransferResponse(BaseModel):
    transfer_id: str = Field(alias="transferId")
    ilp_packet: str = Field(alias="ilpPacket")
    condition: str
    fulfilment: Optional[str] = None
    state: str = "RECEIVED"

    class Config:
        populate_by_name = True


# ── Mojaloop: Hub Submission ─────────────────────────────────────────────

def _submit_transfer_to_hub(transfer_id: str, req: IlpTransferRequest, ilp_data: dict) -> str:
    """
    Submit a prepared ILP transfer to the Mojaloop hub (FSPIOP POST /transfers).

    Returns the transfer state reported by the hub (defaults to RECEIVED for
    the asynchronous FSPIOP flow). Fails loud (502/503) on any hub failure —
    never returns a fabricated COMMITTED state.
    """
    if not MOJALOOP_HUB_URL:
        raise HTTPException(
            status_code=503,
            detail="Mojaloop hub is not configured (MOJALOOP_HUB_URL unset); transfer refused.",
        )

    payload = {
        "transferId": transfer_id,
        "payerFsp": req.payer_fsp,
        "payeeFsp": req.payee_fsp,
        "amount": {"amount": str(req.amount), "currency": req.currency},
        "ilpPacket": ilp_data["packet"],
        "condition": ilp_data["condition"],
        "expiration": datetime.fromtimestamp(time.time() + 900, tz=timezone.utc).isoformat(),
    }
    http_req = urllib.request.Request(
        url=f"{MOJALOOP_HUB_URL.rstrip('/')}/transfers",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/vnd.interoperability.transfers+json;version=1.0",
            "Accept": "application/vnd.interoperability.transfers+json;version=1.0",
            "FSPIOP-Source": MOJALOOP_FSP_ID,
            "FSPIOP-Destination": req.payee_fsp,
        },
    )
    try:
        with urllib.request.urlopen(http_req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Mojaloop hub rejected transfer {transfer_id}: HTTP {e.code}",
        )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Mojaloop hub unreachable for transfer {transfer_id}: {e}",
        )

    try:
        data = json.loads(raw) if raw.strip() else {}
    except ValueError:
        data = {}

    # FSPIOP transfers complete asynchronously; only report a terminal state
    # if the hub explicitly returned one.
    return data.get("transferState", "RECEIVED")


def _initiate_ilp_transfer(req: IlpTransferRequest, purpose: str, reference: str) -> IlpTransferResponse:
    """Shared flow for commission/settlement/refund ILP transfers."""
    transfer_id = str(uuid.uuid4())
    ilp_data = _generate_ilp_packet(
        amount=req.amount,
        currency=req.currency,
        destination=f"g.{req.payee_fsp}.{purpose}.{reference}",
    )

    logger.info(
        f"[Mojaloop] {purpose} transfer {transfer_id}: "
        f"{req.payer_fsp} -> {req.payee_fsp} ({req.amount} {req.currency})"
    )

    state = _submit_transfer_to_hub(transfer_id, req, ilp_data)

    # Note: fulfilment is delivered asynchronously by the hub callback;
    # it is intentionally None here and never fabricated.
    return IlpTransferResponse(
        transferId=transfer_id,
        ilpPacket=ilp_data["packet"],
        condition=ilp_data["condition"],
        fulfilment=None,
        state=state,
    )


# ── Mojaloop: Commission Transfer ────────────────────────────────────────

@app.post("/mojaloop/commission-transfer", response_model=IlpTransferResponse)
async def mojaloop_commission_transfer(req: IlpTransferRequest):
    """
    Initiate an ILP transfer for cross-border commission settlement.
    Submits to the Mojaloop hub; state reflects the hub response.
    """
    return _initiate_ilp_transfer(req, "commission", req.agent_code or "unknown")


# ── Mojaloop: Settlement Transfer ────────────────────────────────────────

@app.post("/mojaloop/settlement-transfer", response_model=IlpTransferResponse)
async def mojaloop_settlement_transfer(req: IlpTransferRequest):
    """Initiate an ILP transfer for settlement disbursement."""
    return _initiate_ilp_transfer(req, "settlement", req.transaction_ref or "batch")


# ── Mojaloop: Refund Transfer ────────────────────────────────────────────

@app.post("/mojaloop/refund-transfer", response_model=IlpTransferResponse)
async def mojaloop_refund_transfer(req: IlpTransferRequest):
    """Initiate an ILP transfer for refund reversal."""
    return _initiate_ilp_transfer(req, "refund", req.transaction_ref or "unknown")


# ── Mojaloop: ILP Packet Generation ──────────────────────────────────────

def _generate_ilp_packet(amount: float, currency: str, destination: str) -> dict:
    """
    Generate ILP packet, condition, and fulfilment per Interledger Protocol spec.
    Uses SHA-256 for condition/fulfilment pair.
    """
    # Generate fulfilment (32 random bytes, base64url encoded)
    fulfilment_bytes = os.urandom(32)
    fulfilment = base64.urlsafe_b64encode(fulfilment_bytes).rstrip(b"=").decode()

    # Condition = SHA-256(fulfilment), base64url encoded
    condition_bytes = hashlib.sha256(fulfilment_bytes).digest()
    condition = base64.urlsafe_b64encode(condition_bytes).rstrip(b"=").decode()

    # ILP packet (simplified — real implementation uses ASN.1 OER encoding)
    packet_data = {
        "amount": str(int(amount * 100)),
        "account": destination,
        "data": base64.b64encode(json.dumps({
            "currency": currency,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }).encode()).decode(),
    }
    packet = base64.urlsafe_b64encode(json.dumps(packet_data).encode()).rstrip(b"=").decode()

    return {
        "packet": packet,
        "condition": condition,
        "fulfilment": fulfilment,
    }


# ── Mojaloop: Participant Lookup ──────────────────────────────────────────

class ParticipantLookupRequest(BaseModel):
    identifier_type: str = "MSISDN"
    identifier: str


@app.post("/mojaloop/participants/lookup")
async def lookup_participant(req: ParticipantLookupRequest):
    """
    Look up a participant FSP by identifier (MSISDN, account, etc.) via the
    Mojaloop Account Lookup Service. Fails loud when the hub is not configured
    or the participant is unknown — never fabricates a participant name.
    """
    if not MOJALOOP_HUB_URL:
        raise HTTPException(
            status_code=503,
            detail="Mojaloop hub is not configured (MOJALOOP_HUB_URL unset); lookup refused.",
        )

    url = f"{MOJALOOP_HUB_URL.rstrip('/')}/participants/{req.identifier_type}/{req.identifier}"
    http_req = urllib.request.Request(
        url=url,
        method="GET",
        headers={
            "Accept": "application/vnd.interoperability.participants+json;version=1.0",
            "FSPIOP-Source": MOJALOOP_FSP_ID,
        },
    )
    try:
        with urllib.request.urlopen(http_req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise HTTPException(status_code=404, detail="Participant not found.")
        raise HTTPException(status_code=502, detail=f"Mojaloop hub lookup failed: HTTP {e.code}")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Mojaloop hub unreachable: {e}")

    try:
        data = json.loads(raw) if raw.strip() else {}
    except ValueError:
        raise HTTPException(status_code=502, detail="Mojaloop hub returned a malformed lookup response.")

    # Async ALS flow: hub may answer 202 with the party delivered via callback.
    if not data:
        return {
            "status": "lookup_accepted",
            "identifier_type": req.identifier_type,
            "identifier": req.identifier,
            "note": "FSPIOP participant lookup is asynchronous; party info is delivered via callback.",
        }
    return data


# ── Entry Point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting Lakehouse + Mojaloop Sidecar on :{PORT}")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
