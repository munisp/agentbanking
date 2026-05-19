"""
Shared Lakehouse (MinIO + Delta Lake / Parquet) data pipeline
for all 8 competitor-gap services.

Each service writes analytics events to its own Delta table in MinIO,
enabling BI reporting, ML training, and CBN regulatory audit trails.
"""
import asyncio
import io
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

import boto3
from botocore.client import Config

logger = logging.getLogger(__name__)

# ─── MinIO / S3-compatible Config ────────────────────────────────────────────
MINIO_ENDPOINT    = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS_KEY  = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY  = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET      = os.getenv("LAKEHOUSE_BUCKET", "54link-lakehouse")
MINIO_REGION      = os.getenv("MINIO_REGION", "us-east-1")

# ─── Delta table paths per service ───────────────────────────────────────────
TABLE_PATHS = {
    "multi_sim_failover":        "silver/competitor_gap/multi_sim_failover/",
    "instant_reversal":          "silver/competitor_gap/instant_reversal/",
    "agent_wallet":              "silver/competitor_gap/agent_wallet/",
    "cbn_reports":               "gold/competitor_gap/cbn_reports/",
    "nfc_qr_payments":           "silver/competitor_gap/nfc_qr_payments/",
    "receipts":                  "silver/competitor_gap/receipts/",
    "training_academy":          "silver/competitor_gap/training_academy/",
    "liquidity_network":         "silver/competitor_gap/liquidity_network/",
    # Aggregated gold layer
    "agent_activity_gold":       "gold/competitor_gap/agent_activity/",
    "compliance_audit_gold":     "gold/competitor_gap/compliance_audit/",
}


def _get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
        region_name=MINIO_REGION,
    )


def _ensure_bucket(s3_client) -> None:
    try:
        s3_client.head_bucket(Bucket=MINIO_BUCKET)
    except Exception:
        try:
            s3_client.create_bucket(Bucket=MINIO_BUCKET)
            logger.info("[lakehouse] Created bucket: %s", MINIO_BUCKET)
        except Exception as exc:
            logger.warning("[lakehouse] Could not create bucket: %s", exc)


def _write_parquet_record(s3_client, table_key: str, record: Dict[str, Any]) -> str:
    """Write a single record as a Parquet-like JSON line to MinIO (JSONL format for Delta compatibility)."""
    record["_ingested_at"] = datetime.now(timezone.utc).isoformat()
    record["_record_id"] = str(uuid4())

    now = datetime.now(timezone.utc)
    partition = f"year={now.year}/month={now.month:02d}/day={now.day:02d}"
    file_key = f"{table_key}{partition}/{now.strftime('%H%M%S')}_{record['_record_id'][:8]}.jsonl"

    content = json.dumps(record) + "\n"
    s3_client.put_object(
        Bucket=MINIO_BUCKET,
        Key=file_key,
        Body=content.encode("utf-8"),
        ContentType="application/x-ndjson",
    )
    return file_key


def _write_parquet_batch(s3_client, table_key: str, records: List[Dict[str, Any]]) -> str:
    """Write a batch of records as JSONL to MinIO."""
    if not records:
        return ""
    now = datetime.now(timezone.utc)
    batch_id = str(uuid4())[:8]
    partition = f"year={now.year}/month={now.month:02d}/day={now.day:02d}"
    file_key = f"{table_key}{partition}/{now.strftime('%H%M%S')}_{batch_id}_batch.jsonl"

    lines = []
    for record in records:
        record["_ingested_at"] = now.isoformat()
        record["_record_id"] = str(uuid4())
        lines.append(json.dumps(record))

    content = "\n".join(lines) + "\n"
    s3_client.put_object(
        Bucket=MINIO_BUCKET,
        Key=file_key,
        Body=content.encode("utf-8"),
        ContentType="application/x-ndjson",
    )
    return file_key


async def _async_write(table_name: str, record: Dict[str, Any]) -> Optional[str]:
    """Async wrapper for writing to MinIO."""
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(None, _sync_write, table_name, record)
    except Exception as exc:
        logger.error("[lakehouse] async_write error table=%s: %s", table_name, exc)
        return None


def _sync_write(table_name: str, record: Dict[str, Any]) -> Optional[str]:
    table_key = TABLE_PATHS.get(table_name)
    if not table_key:
        logger.warning("[lakehouse] Unknown table: %s", table_name)
        return None
    try:
        s3 = _get_s3_client()
        _ensure_bucket(s3)
        return _write_parquet_record(s3, table_key, record)
    except Exception as exc:
        logger.error("[lakehouse] sync_write error table=%s: %s", table_name, exc)
        return None


# ─── Service-specific write helpers ──────────────────────────────────────────

class MultiSimLakehouse:
    @staticmethod
    async def write_failover_event(terminal_id: str, from_sim: str, to_sim: str,
                                    reason: str, tenant_id: str) -> None:
        await _async_write("multi_sim_failover", {
            "terminal_id": terminal_id,
            "from_sim_slot": from_sim,
            "to_sim_slot": to_sim,
            "failover_reason": reason,
            "tenant_id": tenant_id,
            "event_type": "failover",
        })

    @staticmethod
    async def write_signal_update(terminal_id: str, slot: str, signal_strength: int,
                                   network_type: str, tenant_id: str) -> None:
        await _async_write("multi_sim_failover", {
            "terminal_id": terminal_id,
            "sim_slot": slot,
            "signal_strength": signal_strength,
            "network_type": network_type,
            "tenant_id": tenant_id,
            "event_type": "signal_update",
        })


class ReversalLakehouse:
    @staticmethod
    async def write_reversal_initiated(reversal_id: str, transaction_id: str,
                                        amount: float, currency: str,
                                        agent_id: str, tenant_id: str) -> None:
        await _async_write("instant_reversal", {
            "reversal_id": reversal_id,
            "transaction_id": transaction_id,
            "amount": amount,
            "currency": currency,
            "agent_id": agent_id,
            "tenant_id": tenant_id,
            "event_type": "reversal_initiated",
        })

    @staticmethod
    async def write_reversal_completed(reversal_id: str, duration_seconds: float,
                                        status: str, tenant_id: str) -> None:
        await _async_write("instant_reversal", {
            "reversal_id": reversal_id,
            "duration_seconds": duration_seconds,
            "status": status,
            "tenant_id": tenant_id,
            "event_type": "reversal_completed",
            "sla_met": duration_seconds <= 60.0,
        })


class WalletLakehouse:
    @staticmethod
    async def write_balance_snapshot(agent_id: str, balance: float,
                                      currency: str, tenant_id: str) -> None:
        await _async_write("agent_wallet", {
            "agent_id": agent_id,
            "balance": balance,
            "currency": currency,
            "tenant_id": tenant_id,
            "event_type": "balance_snapshot",
        })

    @staticmethod
    async def write_transaction_entry(agent_id: str, txn_type: str,
                                       amount: float, running_balance: float,
                                       tenant_id: str) -> None:
        await _async_write("agent_wallet", {
            "agent_id": agent_id,
            "transaction_type": txn_type,
            "amount": amount,
            "running_balance": running_balance,
            "tenant_id": tenant_id,
            "event_type": "ledger_entry",
        })


class CBNLakehouse:
    @staticmethod
    async def write_report_generated(report_id: str, report_type: str,
                                      period: str, tenant_id: str,
                                      record_count: int) -> None:
        await _async_write("cbn_reports", {
            "report_id": report_id,
            "report_type": report_type,
            "period": period,
            "tenant_id": tenant_id,
            "record_count": record_count,
            "event_type": "report_generated",
        })

    @staticmethod
    async def write_sar_filed(sar_id: str, agent_id: str,
                               amount: float, tenant_id: str) -> None:
        await _async_write("cbn_reports", {
            "sar_id": sar_id,
            "agent_id": agent_id,
            "amount": amount,
            "tenant_id": tenant_id,
            "event_type": "sar_filed",
        })
        # Also write to compliance audit gold layer
        await _async_write("compliance_audit_gold", {
            "event_id": sar_id,
            "event_type": "sar_filed",
            "agent_id": agent_id,
            "amount": amount,
            "tenant_id": tenant_id,
            "source_service": "cbn-reporting-engine",
        })


class NFCQRLakehouse:
    @staticmethod
    async def write_qr_generated(qr_id: str, agent_id: str,
                                   amount: float, currency: str,
                                   tenant_id: str) -> None:
        await _async_write("nfc_qr_payments", {
            "qr_id": qr_id,
            "agent_id": agent_id,
            "amount": amount,
            "currency": currency,
            "tenant_id": tenant_id,
            "event_type": "qr_generated",
        })

    @staticmethod
    async def write_payment_completed(payment_id: str, qr_id: str,
                                       amount: float, method: str,
                                       agent_id: str, tenant_id: str) -> None:
        await _async_write("nfc_qr_payments", {
            "payment_id": payment_id,
            "qr_id": qr_id,
            "amount": amount,
            "payment_method": method,
            "agent_id": agent_id,
            "tenant_id": tenant_id,
            "event_type": "payment_completed",
        })
        # Write to agent activity gold layer
        await _async_write("agent_activity_gold", {
            "event_id": payment_id,
            "event_type": "qr_payment",
            "agent_id": agent_id,
            "amount": amount,
            "tenant_id": tenant_id,
            "source_service": "nfc-qr-payments",
        })


class ReceiptLakehouse:
    @staticmethod
    async def write_receipt_generated(receipt_id: str, transaction_id: str,
                                       channel: str, agent_id: str,
                                       tenant_id: str) -> None:
        await _async_write("receipts", {
            "receipt_id": receipt_id,
            "transaction_id": transaction_id,
            "delivery_channel": channel,
            "agent_id": agent_id,
            "tenant_id": tenant_id,
            "event_type": "receipt_generated",
        })

    @staticmethod
    async def write_delivery_status(receipt_id: str, channel: str,
                                     status: str, attempts: int,
                                     tenant_id: str) -> None:
        await _async_write("receipts", {
            "receipt_id": receipt_id,
            "delivery_channel": channel,
            "delivery_status": status,
            "delivery_attempts": attempts,
            "tenant_id": tenant_id,
            "event_type": "delivery_status",
        })


class TrainingLakehouse:
    @staticmethod
    async def write_enrollment(agent_id: str, course_id: str,
                                course_title: str, tenant_id: str) -> None:
        await _async_write("training_academy", {
            "agent_id": agent_id,
            "course_id": course_id,
            "course_title": course_title,
            "tenant_id": tenant_id,
            "event_type": "enrollment",
        })

    @staticmethod
    async def write_completion(agent_id: str, course_id: str,
                                score: float, is_cbn_required: bool,
                                tenant_id: str) -> None:
        await _async_write("training_academy", {
            "agent_id": agent_id,
            "course_id": course_id,
            "score": score,
            "is_cbn_required": is_cbn_required,
            "tenant_id": tenant_id,
            "event_type": "completion",
        })
        if is_cbn_required:
            await _async_write("compliance_audit_gold", {
                "event_id": f"{agent_id}:{course_id}",
                "event_type": "cbn_training_completed",
                "agent_id": agent_id,
                "score": score,
                "tenant_id": tenant_id,
                "source_service": "agent-training-academy",
            })

    @staticmethod
    async def write_quiz_attempt(agent_id: str, course_id: str,
                                  score: float, passed: bool,
                                  tenant_id: str) -> None:
        await _async_write("training_academy", {
            "agent_id": agent_id,
            "course_id": course_id,
            "quiz_score": score,
            "passed": passed,
            "tenant_id": tenant_id,
            "event_type": "quiz_attempt",
        })


class LiquidityLakehouse:
    @staticmethod
    async def write_request(request_id: str, agent_id: str,
                             amount: float, currency: str,
                             tenant_id: str) -> None:
        await _async_write("liquidity_network", {
            "request_id": request_id,
            "agent_id": agent_id,
            "amount": amount,
            "currency": currency,
            "tenant_id": tenant_id,
            "event_type": "liquidity_requested",
        })

    @staticmethod
    async def write_match_completed(match_id: str, requester_id: str,
                                     provider_id: str, amount: float,
                                     fee: float, tenant_id: str) -> None:
        await _async_write("liquidity_network", {
            "match_id": match_id,
            "requester_id": requester_id,
            "provider_id": provider_id,
            "amount": amount,
            "fee": fee,
            "tenant_id": tenant_id,
            "event_type": "match_completed",
        })
        # Write to agent activity gold layer for both agents
        for agent_id, role in [(requester_id, "requester"), (provider_id, "provider")]:
            await _async_write("agent_activity_gold", {
                "event_id": match_id,
                "event_type": f"liquidity_{role}",
                "agent_id": agent_id,
                "amount": amount,
                "tenant_id": tenant_id,
                "source_service": "agent-liquidity-network",
            })

    @staticmethod
    async def write_repayment(repayment_id: str, match_id: str,
                               agent_id: str, amount: float,
                               tenant_id: str) -> None:
        await _async_write("liquidity_network", {
            "repayment_id": repayment_id,
            "match_id": match_id,
            "agent_id": agent_id,
            "amount": amount,
            "tenant_id": tenant_id,
            "event_type": "repayment",
        })
