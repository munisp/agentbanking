"""
MinIO / S3-Compatible Storage for 54Link Lakehouse
Handles Bronze/Silver/Gold/Platinum Parquet layer uploads.
"""
import os
import io
import logging
from datetime import datetime
from typing import Optional, BinaryIO
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# ── Configuration ─────────────────────────────────────────────────────────────
MINIO_ENDPOINT  = os.getenv("MINIO_ENDPOINT",   "http://minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "54link-lakehouse")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "54link-lakehouse-secret-2026")
MINIO_REGION    = os.getenv("MINIO_REGION",      "us-east-1")

# Bucket per data layer
BUCKETS = {
    "bronze":   "54link-bronze",
    "silver":   "54link-silver",
    "gold":     "54link-gold",
    "platinum": "54link-platinum",
}


class MinIOStorage:
    """Thin wrapper around boto3 for MinIO-compatible S3 operations."""

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=MINIO_ENDPOINT,
                aws_access_key_id=MINIO_ACCESS_KEY,
                aws_secret_access_key=MINIO_SECRET_KEY,
                region_name=MINIO_REGION,
                config=Config(signature_version="s3v4"),
            )
        return self._client

    def ensure_buckets(self) -> None:
        """Create all layer buckets if they don't exist."""
        for layer, bucket in BUCKETS.items():
            try:
                self.client.head_bucket(Bucket=bucket)
                logger.debug(f"Bucket {bucket} already exists")
            except ClientError as e:
                if e.response["Error"]["Code"] in ("404", "NoSuchBucket"):
                    self.client.create_bucket(Bucket=bucket)
                    logger.info(f"Created bucket: {bucket} (layer={layer})")
                else:
                    raise

    def upload_parquet(
        self,
        layer: str,
        partition_path: str,
        data: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        Upload a Parquet file to the appropriate layer bucket.

        Args:
            layer: One of bronze | silver | gold | platinum
            partition_path: e.g. "transactions/year=2026/month=04/day=09/batch_001.parquet"
            data: Raw Parquet bytes
            content_type: MIME type

        Returns:
            S3 URI of the uploaded object
        """
        bucket = BUCKETS.get(layer)
        if not bucket:
            raise ValueError(f"Unknown layer: {layer}. Must be one of {list(BUCKETS)}")

        self.client.put_object(
            Bucket=bucket,
            Key=partition_path,
            Body=data,
            ContentType=content_type,
            Metadata={
                "layer": layer,
                "uploaded-at": datetime.utcnow().isoformat(),
                "platform": "54link-agency-banking",
            },
        )
        uri = f"s3://{bucket}/{partition_path}"
        logger.info(f"Uploaded {len(data):,} bytes → {uri}")
        return uri

    def download_parquet(self, layer: str, partition_path: str) -> bytes:
        """Download a Parquet file from a layer bucket."""
        bucket = BUCKETS.get(layer)
        if not bucket:
            raise ValueError(f"Unknown layer: {layer}")
        response = self.client.get_object(Bucket=bucket, Key=partition_path)
        return response["Body"].read()

    def list_objects(self, layer: str, prefix: str = "") -> list[dict]:
        """List objects in a layer bucket under the given prefix."""
        bucket = BUCKETS.get(layer)
        if not bucket:
            raise ValueError(f"Unknown layer: {layer}")
        paginator = self.client.get_paginator("list_objects_v2")
        results = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                results.append({
                    "key": obj["Key"],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                    "etag": obj["ETag"].strip('"'),
                })
        return results

    def presigned_url(self, layer: str, partition_path: str, expiry: int = 3600) -> str:
        """Generate a presigned GET URL for a Parquet file."""
        bucket = BUCKETS.get(layer)
        if not bucket:
            raise ValueError(f"Unknown layer: {layer}")
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": partition_path},
            ExpiresIn=expiry,
        )


# Singleton instance
minio_storage = MinIOStorage()


def get_partition_path(layer: str, event_type: str, timestamp: datetime, batch_id: str) -> str:
    """
    Generate a Hive-style partition path for a Parquet batch.

    Example:
        bronze/transactions/year=2026/month=04/day=09/batch_abc123.parquet
    """
    return (
        f"{event_type}/"
        f"year={timestamp.year}/"
        f"month={timestamp.month:02d}/"
        f"day={timestamp.day:02d}/"
        f"batch_{batch_id}.parquet"
    )
