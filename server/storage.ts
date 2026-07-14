/**
 * storage.ts — Self-hosted S3/MinIO file storage. No external platform dependency.
 *
 * Env vars:
 *   S3_ENDPOINT   — e.g. http://minio:9000  (omit for AWS S3)
 *   S3_BUCKET     — bucket name (default: "54link-storage")
 *   S3_REGION     — AWS region (default: "us-east-1")
 *   S3_ACCESS_KEY — access key ID
 *   S3_SECRET_KEY — secret access key
 *   S3_PUBLIC_URL — public base URL for download links (optional)
 */
import {
  S3Client,
  PutObjectCommand,
  GetObjectCommand,
} from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";

function getS3Client(): S3Client {
  const endpoint = process.env.S3_ENDPOINT;
  const region = process.env.S3_REGION ?? "us-east-1";
  const accessKeyId = process.env.S3_ACCESS_KEY ?? "";
  const secretAccessKey = process.env.S3_SECRET_KEY ?? "";
  return new S3Client({
    region,
    ...(endpoint ? { endpoint, forcePathStyle: true } : {}),
    credentials:
      accessKeyId && secretAccessKey
        ? { accessKeyId, secretAccessKey }
        : undefined,
  });
}

function getBucket(): string {
  return process.env.S3_BUCKET ?? "54link-storage";
}

function normalizeKey(relKey: string): string {
  return relKey.replace(/^\/+/, "");
}

async function buildDownloadUrl(
  client: S3Client,
  bucket: string,
  key: string
): Promise<string> {
  const publicBase = process.env.S3_PUBLIC_URL;
  if (publicBase) return `${publicBase.replace(/\/+$/, "")}/${key}`;
  const command = new GetObjectCommand({ Bucket: bucket, Key: key });
  return getSignedUrl(client, command, { expiresIn: 604_800 });
}

export async function storagePut(
  relKey: string,
  data: Buffer | Uint8Array | string,
  contentType = "application/octet-stream"
): Promise<{ key: string; url: string }> {
  const client = getS3Client();
  const bucket = getBucket();
  const key = normalizeKey(relKey);
  const body =
    typeof data === "string" ? Buffer.from(data, "utf-8") : Buffer.from(data as any);
  await client.send(
    new PutObjectCommand({ Bucket: bucket, Key: key, Body: body, ContentType: contentType })
  );
  const url = await buildDownloadUrl(client, bucket, key);
  return { key, url };
}

export async function storageGet(
  relKey: string
): Promise<{ key: string; url: string }> {
  const client = getS3Client();
  const bucket = getBucket();
  const key = normalizeKey(relKey);
  return { key, url: await buildDownloadUrl(client, bucket, key) };
}
