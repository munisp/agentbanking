// TypeScript enabled — Sprint 96 security audit
/**
 * 54agent Lakehouse Client
 * Uses MinIO (S3-compatible) as the object store for Parquet-format data exports.
 * Provides analytics data pipeline: PostgreSQL → JSON → Parquet → MinIO.
 *
 * Buckets:
 *   54agent-transactions   — daily transaction snapshots (Parquet)
 *   54agent-settlements    — settlement summaries (JSON)
 *   54agent-fraud-events   — fraud alert history (JSON)
 *   54agent-agent-metrics  — agent performance metrics (Parquet)
 */
import {
  S3Client,
  PutObjectCommand,
  GetObjectCommand,
  ListObjectsV2Command,
} from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";
import logger from "./_core/logger";

const MINIO_ENDPOINT = process.env.MINIO_ENDPOINT ?? "http://localhost:9000";
const MINIO_ACCESS_KEY = process.env.MINIO_ACCESS_KEY ?? "minioadmin";
const MINIO_SECRET_KEY = process.env.MINIO_SECRET_KEY ?? "minioadmin";
const MINIO_REGION = process.env.MINIO_REGION ?? "us-east-1";

let _s3: S3Client | null = null;

function getS3Client(): S3Client {
  if (_s3) return _s3;
  _s3 = new S3Client({
    endpoint: MINIO_ENDPOINT,
    region: MINIO_REGION,
    credentials: {
      accessKeyId: MINIO_ACCESS_KEY,
      secretAccessKey: MINIO_SECRET_KEY,
    },
    forcePathStyle: true, // Required for MinIO
  });
  return _s3;
}

// ── Bucket names ───────────────────────────────────────────────────────────────
export const BUCKETS = {
  TRANSACTIONS: "54agent-transactions",
  SETTLEMENTS: "54agent-settlements",
  FRAUD_EVENTS: "54agent-fraud-events",
  AGENT_METRICS: "54agent-agent-metrics",
} as const;

// ── Upload helpers ─────────────────────────────────────────────────────────────

/**
 * Upload a JSON snapshot to MinIO.
 * Key format: {bucket}/{YYYY}/{MM}/{DD}/{filename}.json
 */
export async function uploadJsonSnapshot(
  bucket: string,
  filename: string,
  data: object[]
): Promise<string | null> {
  const now = new Date();
  const key = `${now.getFullYear()}/${String(now.getMonth() + 1).padStart(2, "0")}/${String(now.getDate()).padStart(2, "0")}/${filename}.json`;

  try {
    const s3 = getS3Client();
    await s3.send(
      new PutObjectCommand({
        Bucket: bucket,
        Key: key,
        Body: JSON.stringify(data, null, 2),
        ContentType: "application/json",
        Metadata: {
          "record-count": String(data.length),
          "uploaded-at": now.toISOString(),
        },
      })
    );
    logger.info(
      `[Lakehouse] Uploaded ${data.length} records → s3://${bucket}/${key}`
    );
    return key;
  } catch (err) {
    logger.warn({ err }, `[Lakehouse] Upload to s3://${bucket}/${key} failed`);
    return null;
  }
}

/**
 * Upload a daily transaction snapshot.
 */
export async function uploadTransactionSnapshot(
  date: string,
  transactions: object[]
): Promise<string | null> {
  return uploadJsonSnapshot(
    BUCKETS.TRANSACTIONS,
    `transactions-${date}`,
    transactions
  );
}

/**
 * Upload a settlement summary.
 */
export async function uploadSettlementSummary(
  date: string,
  summary: object
): Promise<string | null> {
  const key = `${date.replace(/-/g, "/")}/settlement-summary-${date}.json`;
  try {
    const s3 = getS3Client();
    await s3.send(
      new PutObjectCommand({
        Bucket: BUCKETS.SETTLEMENTS,
        Key: key,
        Body: JSON.stringify(summary, null, 2),
        ContentType: "application/json",
      })
    );
    logger.info(
      `[Lakehouse] Settlement summary uploaded → s3://${BUCKETS.SETTLEMENTS}/${key}`
    );
    return key;
  } catch (err) {
    logger.warn({ err }, "[Lakehouse] Settlement summary upload failed");
    return null;
  }
}

/**
 * Upload a fraud events snapshot.
 */
export async function uploadFraudEvents(
  date: string,
  events: object[]
): Promise<string | null> {
  return uploadJsonSnapshot(
    BUCKETS.FRAUD_EVENTS,
    `fraud-events-${date}`,
    events
  );
}

/**
 * List available snapshots in a bucket for a given date prefix.
 */
export async function listSnapshots(
  bucket: string,
  datePrefix: string
): Promise<string[]> {
  try {
    const s3 = getS3Client();
    const res = await s3.send(
      new ListObjectsV2Command({
        Bucket: bucket,
        Prefix: datePrefix.replace(/-/g, "/"),
        MaxKeys: 100,
      })
    );
    return (res.Contents ?? []).map(obj => obj.Key ?? "").filter(Boolean);
  } catch (err) {
    logger.warn({ err }, `[Lakehouse] List snapshots in ${bucket} failed`);
    return [];
  }
}

/**
 * Get a presigned download URL for a snapshot file.
 */
export async function getSnapshotDownloadUrl(
  bucket: string,
  key: string,
  expiresInSeconds = 3600
): Promise<string | null> {
  try {
    const s3 = getS3Client();
    const url = await getSignedUrl(
      s3,
      new GetObjectCommand({ Bucket: bucket, Key: key }),
      { expiresIn: expiresInSeconds }
    );
    return url;
  } catch (err) {
    logger.warn({ err }, "[Lakehouse] Presigned URL generation failed");
    return null;
  }
}

// ── Unified Lakehouse Service Integration ─────────────────────────────────────
// Forward data to the Python Lakehouse service for Bronze/Silver/Gold processing

const LAKEHOUSE_API_URL =
  process.env.LAKEHOUSE_SERVICE_URL ?? "http://localhost:8156";

/**
 * Forward data to the unified Lakehouse API for Bronze layer ingestion.
 * Called after MinIO upload to maintain dual-write consistency.
 */
export async function ingestToLakehouse(
  table: string,
  data: Record<string, unknown> | Record<string, unknown>[],
  source: string = "typescript-minio"
): Promise<boolean> {
  try {
    const res = await fetch(`${LAKEHOUSE_API_URL}/v1/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ table, data, source }),
      signal: AbortSignal.timeout(5_000),
    });
    if (res.ok) {
      logger.info(`[Lakehouse] Ingested to ${table} via unified API`);
      return true;
    }
    logger.warn(`[Lakehouse] Ingest to ${table} returned ${res.status}`);
    return false;
  } catch (err) {
    logger.warn({ err }, `[Lakehouse] Ingest to ${table} failed`);
    return false;
  }
}

/**
 * Query the unified Lakehouse via SQL (DuckDB/DataFusion backend).
 */
export async function queryLakehouse(
  sql: string,
  layer: string = "gold"
): Promise<Record<string, unknown>[]> {
  try {
    const res = await fetch(`${LAKEHOUSE_API_URL}/v1/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sql, layer }),
      signal: AbortSignal.timeout(10_000),
    });
    if (!res.ok) return [];
    const result = (await res.json()) as {
      results?: Record<string, unknown>[];
    };
    return result.results ?? [];
  } catch {
    return [];
  }
}

/**
 * Get the Lakehouse catalog (all registered tables and schemas).
 */
export async function getLakehouseCatalog(
  layer?: string
): Promise<Record<string, unknown>> {
  try {
    const url = layer
      ? `${LAKEHOUSE_API_URL}/v1/catalog?layer=${layer}`
      : `${LAKEHOUSE_API_URL}/v1/catalog`;
    const res = await fetch(url, { signal: AbortSignal.timeout(5_000) });
    if (!res.ok) return { tables: [], total: 0 };
    return (await res.json()) as Record<string, unknown>;
  } catch {
    return { tables: [], total: 0 };
  }
}

/**
 * Trigger ETL promotion (Bronze→Silver or Silver→Gold).
 */
export async function promoteLakehouseTable(
  table: string,
  sourceLayer: string = "bronze",
  targetLayer: string = "silver"
): Promise<Record<string, unknown> | null> {
  try {
    const res = await fetch(`${LAKEHOUSE_API_URL}/v1/etl/promote`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        table,
        source_layer: sourceLayer,
        target_layer: targetLayer,
      }),
      signal: AbortSignal.timeout(30_000),
    });
    if (!res.ok) return null;
    return (await res.json()) as Record<string, unknown>;
  } catch {
    return null;
  }
}

export default {
  uploadTransactionSnapshot,
  uploadSettlementSummary,
  uploadFraudEvents,
  listSnapshots,
  getSnapshotDownloadUrl,
  ingestToLakehouse,
  queryLakehouse,
  getLakehouseCatalog,
  promoteLakehouseTable,
  BUCKETS,
};
