"""
Agent Embedded Finance — Lakehouse Data Pipeline
Writes loan and BNPL events to the 54agent Lakehouse (MinIO + Delta Lake).
Medallion architecture:
  Bronze: raw loan/BNPL events
  Silver: cleaned loan lifecycle snapshots
  Gold:   portfolio analytics, default rates, BNPL performance
"""
import io
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import boto3
import pyarrow as pa
import pyarrow.parquet as pq
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

MINIO_ENDPOINT   = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "")
MINIO_REGION     = os.getenv("MINIO_REGION", "us-east-1")
LAKEHOUSE_BUCKET = os.getenv("LAKEHOUSE_BUCKET", "54agent-lakehouse")

BRONZE_PATH = "bronze/agent_finance"
SILVER_PATH = "silver/agent_finance"
GOLD_PATH   = "gold/agent_finance"

BRONZE_SCHEMA = pa.schema([
    pa.field("event_id",       pa.string()),
    pa.field("event_type",     pa.string()),
    pa.field("agent_id",       pa.string()),
    pa.field("tenant_id",      pa.string()),
    pa.field("raw_payload",    pa.string()),
    pa.field("ingested_at",    pa.timestamp("us", tz="UTC")),
    pa.field("partition_date", pa.string()),
])

SILVER_LOAN_SCHEMA = pa.schema([
    pa.field("loan_id",             pa.string()),
    pa.field("application_id",      pa.string()),
    pa.field("agent_id",            pa.string()),
    pa.field("tenant_id",           pa.string()),
    pa.field("product_type",        pa.string()),
    pa.field("principal_amount",    pa.float64()),
    pa.field("interest_rate",       pa.float64()),
    pa.field("tenor_days",          pa.int64()),
    pa.field("total_repayable",     pa.float64()),
    pa.field("amount_repaid",       pa.float64()),
    pa.field("outstanding_balance", pa.float64()),
    pa.field("status",              pa.string()),
    pa.field("disbursed_at",        pa.timestamp("us", tz="UTC")),
    pa.field("due_date",            pa.string()),
    pa.field("days_overdue",        pa.int64()),
    pa.field("partition_date",      pa.string()),
    pa.field("partition_month",     pa.string()),
])

GOLD_PORTFOLIO_SCHEMA = pa.schema([
    pa.field("tenant_id",           pa.string()),
    pa.field("report_date",         pa.string()),
    pa.field("total_loans",         pa.int64()),
    pa.field("active_loans",        pa.int64()),
    pa.field("total_disbursed",     pa.float64()),
    pa.field("total_outstanding",   pa.float64()),
    pa.field("total_repaid",        pa.float64()),
    pa.field("default_rate",        pa.float64()),
    pa.field("avg_loan_size",       pa.float64()),
    pa.field("bnpl_orders",         pa.int64()),
    pa.field("bnpl_outstanding",    pa.float64()),
    pa.field("generated_at",        pa.timestamp("us", tz="UTC")),
])


class FinanceLakehouseClient:
    def __init__(self):
        self._s3 = boto3.client(
            "s3",
            endpoint_url=MINIO_ENDPOINT,
            aws_access_key_id=MINIO_ACCESS_KEY,
            aws_secret_access_key=MINIO_SECRET_KEY,
            region_name=MINIO_REGION,
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "adaptive"},
                max_pool_connections=20,
            ),
        )
        self._ensure_bucket()

    def _ensure_bucket(self):
        try:
            self._s3.head_bucket(Bucket=LAKEHOUSE_BUCKET)
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                self._s3.create_bucket(Bucket=LAKEHOUSE_BUCKET)

    def _write_parquet(self, table: pa.Table, s3_key: str) -> bool:
        buf = io.BytesIO()
        pq.write_table(table, buf, compression="snappy", use_dictionary=True)
        buf.seek(0)
        try:
            self._s3.put_object(
                Bucket=LAKEHOUSE_BUCKET, Key=s3_key,
                Body=buf.getvalue(), ContentType="application/octet-stream",
            )
            return True
        except ClientError as e:
            logger.error("Lakehouse write failed for %s: %s", s3_key, e)
            return False

    def write_bronze_event(self, event_id: str, event_type: str,
                            agent_id: str, tenant_id: str,
                            payload: Dict[str, Any]) -> bool:
        now = datetime.utcnow()
        partition_date = now.strftime("%Y-%m-%d")
        table = pa.table({
            "event_id":       [event_id],
            "event_type":     [event_type],
            "agent_id":       [agent_id],
            "tenant_id":      [tenant_id],
            "raw_payload":    [json.dumps(payload)],
            "ingested_at":    [pa.scalar(now, type=pa.timestamp("us", tz="UTC"))],
            "partition_date": [partition_date],
        }, schema=BRONZE_SCHEMA)
        s3_key = (f"{BRONZE_PATH}/tenant={tenant_id}/date={partition_date}/"
                  f"{event_type}_{event_id}.parquet")
        return self._write_parquet(table, s3_key)

    def write_silver_loan(self, loan: Dict[str, Any]) -> bool:
        now = datetime.utcnow()
        partition_date = now.strftime("%Y-%m-%d")
        partition_month = now.strftime("%Y-%m")
        disbursed_at = loan.get("disbursed_at", now.isoformat())
        if isinstance(disbursed_at, str):
            try:
                disbursed_at = datetime.fromisoformat(disbursed_at.replace("Z", "+00:00"))
            except Exception:
                disbursed_at = now
        table = pa.table({
            "loan_id":             [str(loan.get("loan_id", ""))],
            "application_id":      [str(loan.get("application_id", ""))],
            "agent_id":            [str(loan.get("agent_id", ""))],
            "tenant_id":           [str(loan.get("tenant_id", "default"))],
            "product_type":        [str(loan.get("product_type", ""))],
            "principal_amount":    [float(loan.get("principal_amount", 0.0))],
            "interest_rate":       [float(loan.get("interest_rate", 0.0))],
            "tenor_days":          [int(loan.get("tenor_days", 0))],
            "total_repayable":     [float(loan.get("total_repayable", 0.0))],
            "amount_repaid":       [float(loan.get("amount_repaid", 0.0))],
            "outstanding_balance": [float(loan.get("outstanding_balance", 0.0))],
            "status":              [str(loan.get("status", ""))],
            "disbursed_at":        [pa.scalar(disbursed_at, type=pa.timestamp("us", tz="UTC"))],
            "due_date":            [str(loan.get("due_date", ""))],
            "days_overdue":        [int(loan.get("days_overdue", 0))],
            "partition_date":      [partition_date],
            "partition_month":     [partition_month],
        }, schema=SILVER_LOAN_SCHEMA)
        tenant_id = loan.get("tenant_id", "default")
        loan_id = loan.get("loan_id", "unknown")
        s3_key = (f"{SILVER_PATH}/loans/tenant={tenant_id}/month={partition_month}/"
                  f"date={partition_date}/{loan_id}.parquet")
        return self._write_parquet(table, s3_key)

    def write_gold_portfolio(self, tenant_id: str, stats: Dict[str, Any]) -> bool:
        now = datetime.utcnow()
        report_date = now.strftime("%Y-%m-%d")
        table = pa.table({
            "tenant_id":         [tenant_id],
            "report_date":       [report_date],
            "total_loans":       [int(stats.get("total_loans", 0))],
            "active_loans":      [int(stats.get("active_loans", 0))],
            "total_disbursed":   [float(stats.get("total_disbursed", 0.0))],
            "total_outstanding": [float(stats.get("total_outstanding", 0.0))],
            "total_repaid":      [float(stats.get("total_repaid", 0.0))],
            "default_rate":      [float(stats.get("default_rate", 0.0))],
            "avg_loan_size":     [float(stats.get("avg_loan_size", 0.0))],
            "bnpl_orders":       [int(stats.get("bnpl_orders", 0))],
            "bnpl_outstanding":  [float(stats.get("bnpl_outstanding", 0.0))],
            "generated_at":      [pa.scalar(now, type=pa.timestamp("us", tz="UTC"))],
        }, schema=GOLD_PORTFOLIO_SCHEMA)
        s3_key = (f"{GOLD_PATH}/portfolio/tenant={tenant_id}/"
                  f"date={report_date}/portfolio_summary.parquet")
        return self._write_parquet(table, s3_key)

    def ping(self) -> bool:
        try:
            self._s3.head_bucket(Bucket=LAKEHOUSE_BUCKET)
            return True
        except Exception:
            return False


_client: Optional[FinanceLakehouseClient] = None


def get_finance_lakehouse_client() -> FinanceLakehouseClient:
    global _client
    if _client is None:
        _client = FinanceLakehouseClient()
    return _client
