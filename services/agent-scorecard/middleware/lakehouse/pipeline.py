"""
Agent Scorecard — Lakehouse Data Pipeline
Writes scorecard events and snapshots to the 54agent Lakehouse (MinIO + Delta Lake).
Data is organized in a medallion architecture:
  Bronze: raw events (Kafka → Parquet)
  Silver: cleaned and enriched scorecard snapshots
  Gold:   aggregated analytics for BI and ML training

Uses PyArrow + MinIO (S3-compatible) for cloud-agnostic storage.
"""
import io
import json
import logging
import os
from datetime import datetime, date
from typing import Any, Dict, List, Optional

import boto3
import pyarrow as pa
import pyarrow.parquet as pq
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────
MINIO_ENDPOINT    = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS_KEY  = os.getenv("MINIO_ACCESS_KEY", "")
MINIO_SECRET_KEY  = os.getenv("MINIO_SECRET_KEY", "")
MINIO_REGION      = os.getenv("MINIO_REGION", "us-east-1")
LAKEHOUSE_BUCKET  = os.getenv("LAKEHOUSE_BUCKET", "54agent-lakehouse")

# Lakehouse paths
BRONZE_PATH = "bronze/agent_scorecard"
SILVER_PATH = "silver/agent_scorecard"
GOLD_PATH   = "gold/agent_scorecard"


# ── PyArrow Schemas ────────────────────────────────────────────────────────────

BRONZE_SCORECARD_SCHEMA = pa.schema([
    pa.field("event_id",          pa.string()),
    pa.field("event_type",        pa.string()),
    pa.field("agent_id",          pa.string()),
    pa.field("tenant_id",         pa.string()),
    pa.field("raw_payload",       pa.string()),  # JSON string
    pa.field("ingested_at",       pa.timestamp("us", tz="UTC")),
    pa.field("partition_date",    pa.string()),  # YYYY-MM-DD for partitioning
])

SILVER_SCORECARD_SCHEMA = pa.schema([
    pa.field("scorecard_id",                pa.string()),
    pa.field("agent_id",                    pa.string()),
    pa.field("tenant_id",                   pa.string()),
    pa.field("composite_score",             pa.float64()),
    pa.field("tier",                        pa.string()),
    pa.field("trend",                       pa.string()),
    pa.field("score_change",                pa.float64()),
    pa.field("percentile_rank",             pa.float64()),
    pa.field("transaction_score",           pa.float64()),
    pa.field("compliance_score",            pa.float64()),
    pa.field("customer_experience_score",   pa.float64()),
    pa.field("training_score",              pa.float64()),
    pa.field("network_score",               pa.float64()),
    pa.field("transaction_count_30d",       pa.int64()),
    pa.field("transaction_success_rate",    pa.float64()),
    pa.field("fraud_incidents_90d",         pa.int64()),
    pa.field("kyc_status",                  pa.string()),
    pa.field("training_completion_rate",    pa.float64()),
    pa.field("computed_at",                 pa.timestamp("us", tz="UTC")),
    pa.field("partition_date",              pa.string()),
    pa.field("partition_month",             pa.string()),
])

GOLD_TIER_DISTRIBUTION_SCHEMA = pa.schema([
    pa.field("tenant_id",          pa.string()),
    pa.field("report_date",        pa.string()),
    pa.field("tier",               pa.string()),
    pa.field("agent_count",        pa.int64()),
    pa.field("avg_composite_score",pa.float64()),
    pa.field("avg_txn_count",      pa.float64()),
    pa.field("avg_success_rate",   pa.float64()),
    pa.field("generated_at",       pa.timestamp("us", tz="UTC")),
])


# ── MinIO / S3 Client ──────────────────────────────────────────────────────────

class LakehouseClient:
    """
    S3-compatible client for writing Parquet files to MinIO Lakehouse.
    Implements the medallion architecture write pattern.
    """

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
        """Create the lakehouse bucket if it does not exist."""
        try:
            self._s3.head_bucket(Bucket=LAKEHOUSE_BUCKET)
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                self._s3.create_bucket(Bucket=LAKEHOUSE_BUCKET)
                logger.info("Created Lakehouse bucket: %s", LAKEHOUSE_BUCKET)
            else:
                logger.warning("Could not verify Lakehouse bucket: %s", e)

    def _write_parquet(self, table: pa.Table, s3_key: str) -> bool:
        """Write a PyArrow table as Parquet to MinIO."""
        buf = io.BytesIO()
        pq.write_table(
            table, buf,
            compression="snappy",
            use_dictionary=True,
            write_statistics=True,
        )
        buf.seek(0)
        try:
            self._s3.put_object(
                Bucket=LAKEHOUSE_BUCKET,
                Key=s3_key,
                Body=buf.getvalue(),
                ContentType="application/octet-stream",
            )
            logger.debug("Written Parquet to s3://%s/%s", LAKEHOUSE_BUCKET, s3_key)
            return True
        except ClientError as e:
            logger.error("Failed to write Parquet to %s: %s", s3_key, e)
            return False

    # ── Bronze Layer ───────────────────────────────────────────────────────────

    def write_bronze_event(self, event_id: str, event_type: str,
                            agent_id: str, tenant_id: str,
                            payload: Dict[str, Any]) -> bool:
        """Write a raw scorecard event to the Bronze layer."""
        now = datetime.utcnow()
        partition_date = now.strftime("%Y-%m-%d")

        table = pa.table(
            {
                "event_id":       [event_id],
                "event_type":     [event_type],
                "agent_id":       [agent_id],
                "tenant_id":      [tenant_id],
                "raw_payload":    [json.dumps(payload)],
                "ingested_at":    [pa.scalar(now, type=pa.timestamp("us", tz="UTC"))],
                "partition_date": [partition_date],
            },
            schema=BRONZE_SCORECARD_SCHEMA,
        )

        s3_key = (
            f"{BRONZE_PATH}/tenant={tenant_id}/date={partition_date}/"
            f"{event_type}_{event_id}.parquet"
        )
        return self._write_parquet(table, s3_key)

    # ── Silver Layer ───────────────────────────────────────────────────────────

    def write_silver_scorecard(self, scorecard: Dict[str, Any]) -> bool:
        """Write a computed scorecard snapshot to the Silver layer."""
        now = datetime.utcnow()
        partition_date = now.strftime("%Y-%m-%d")
        partition_month = now.strftime("%Y-%m")

        computed_at = scorecard.get("computed_at", now.isoformat())
        if isinstance(computed_at, str):
            try:
                computed_at = datetime.fromisoformat(computed_at.replace("Z", "+00:00"))
            except Exception:
                computed_at = now

        table = pa.table(
            {
                "scorecard_id":              [str(scorecard.get("scorecard_id", ""))],
                "agent_id":                  [str(scorecard.get("agent_id", ""))],
                "tenant_id":                 [str(scorecard.get("tenant_id", "default"))],
                "composite_score":           [float(scorecard.get("composite_score", 0.0))],
                "tier":                      [str(scorecard.get("tier", "Unrated"))],
                "trend":                     [str(scorecard.get("trend", "stable"))],
                "score_change":              [float(scorecard.get("score_change", 0.0))],
                "percentile_rank":           [float(scorecard.get("percentile_rank", 0.0))],
                "transaction_score":         [float(scorecard.get("transaction_score", 0.0))],
                "compliance_score":          [float(scorecard.get("compliance_score", 0.0))],
                "customer_experience_score": [float(scorecard.get("customer_experience_score", 0.0))],
                "training_score":            [float(scorecard.get("training_score", 0.0))],
                "network_score":             [float(scorecard.get("network_score", 0.0))],
                "transaction_count_30d":     [int(scorecard.get("transaction_count_30d", 0))],
                "transaction_success_rate":  [float(scorecard.get("transaction_success_rate", 0.0))],
                "fraud_incidents_90d":       [int(scorecard.get("fraud_incidents_90d", 0))],
                "kyc_status":                [str(scorecard.get("kyc_status", "pending"))],
                "training_completion_rate":  [float(scorecard.get("training_completion_rate", 0.0))],
                "computed_at":               [pa.scalar(computed_at, type=pa.timestamp("us", tz="UTC"))],
                "partition_date":            [partition_date],
                "partition_month":           [partition_month],
            },
            schema=SILVER_SCORECARD_SCHEMA,
        )

        tenant_id = scorecard.get("tenant_id", "default")
        scorecard_id = scorecard.get("scorecard_id", "unknown")
        s3_key = (
            f"{SILVER_PATH}/tenant={tenant_id}/month={partition_month}/"
            f"date={partition_date}/{scorecard_id}.parquet"
        )
        return self._write_parquet(table, s3_key)

    # ── Gold Layer ─────────────────────────────────────────────────────────────

    def write_gold_tier_distribution(self, tenant_id: str,
                                      tier_stats: List[Dict[str, Any]]) -> bool:
        """Write daily tier distribution aggregate to the Gold layer."""
        now = datetime.utcnow()
        report_date = now.strftime("%Y-%m-%d")

        if not tier_stats:
            return True

        table = pa.table(
            {
                "tenant_id":           [tenant_id] * len(tier_stats),
                "report_date":         [report_date] * len(tier_stats),
                "tier":                [str(s.get("tier", "")) for s in tier_stats],
                "agent_count":         [int(s.get("agent_count", 0)) for s in tier_stats],
                "avg_composite_score": [float(s.get("avg_composite_score", 0.0)) for s in tier_stats],
                "avg_txn_count":       [float(s.get("avg_txn_count", 0.0)) for s in tier_stats],
                "avg_success_rate":    [float(s.get("avg_success_rate", 0.0)) for s in tier_stats],
                "generated_at":        [pa.scalar(now, type=pa.timestamp("us", tz="UTC"))] * len(tier_stats),
            },
            schema=GOLD_TIER_DISTRIBUTION_SCHEMA,
        )

        s3_key = (
            f"{GOLD_PATH}/tier_distribution/tenant={tenant_id}/"
            f"date={report_date}/tier_distribution.parquet"
        )
        return self._write_parquet(table, s3_key)

    def ping(self) -> bool:
        """Check MinIO connectivity."""
        try:
            self._s3.head_bucket(Bucket=LAKEHOUSE_BUCKET)
            return True
        except Exception:
            return False


# ── Singleton ──────────────────────────────────────────────────────────────────

_lakehouse_client: Optional[LakehouseClient] = None


def get_lakehouse_client() -> LakehouseClient:
    global _lakehouse_client
    if _lakehouse_client is None:
        _lakehouse_client = LakehouseClient()
    return _lakehouse_client
