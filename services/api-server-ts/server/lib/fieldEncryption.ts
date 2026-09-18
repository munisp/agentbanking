/**
 * Field-level encryption for PII at rest (BVN, NIN, …).
 *
 * AES-256-GCM with a random IV per value. Ciphertext is stored as a single
 * self-describing string:
 *
 *   v1:<iv_b64>:<authTag_b64>:<ciphertext_b64>
 *
 * Key management:
 *  - FIELD_ENCRYPTION_KEY (env) — scrypt-derived to 32 bytes.
 *  - FAIL CLOSED in production: module init throws if the key is unset.
 *
 * Blind index:
 *  GCM ciphertext is non-deterministic (random IV), so equality lookups
 *  (duplicate pre-checks, verify-by-hash) use blindIndex(): a keyed SHA-256
 *  over the normalized value. Salt/key: FIELD_ENCRYPTION_SALT, falling back
 *  to FIELD_ENCRYPTION_KEY; fail-closed in production when neither is set.
 *
 * Pattern follows server/routers/encryptedFieldsCrud.ts (NF-SEC-4).
 */
import crypto from "crypto";

const ALGORITHM = "aes-256-gcm";
const FORMAT_PREFIX = "v1";
const KEY_SALT = "field-encryption-v1";

function resolveKey(): Buffer {
  const secret = process.env.FIELD_ENCRYPTION_KEY;
  if (secret) {
    return crypto.scryptSync(secret, KEY_SALT, 32);
  }
  if (process.env.NODE_ENV === "production") {
    throw new Error(
      "FATAL: FIELD_ENCRYPTION_KEY must be set in production; refusing to store PII with the insecure development fallback key"
    );
  }
  console.warn(
    "[fieldEncryption] WARNING: FIELD_ENCRYPTION_KEY is not set; using the insecure development fallback key. Never run this configuration in production."
  );
  return crypto.scryptSync("default-key-for-dev", KEY_SALT, 32);
}

const KEY = resolveKey();

function resolveBlindIndexSecret(): string {
  const secret =
    process.env.FIELD_ENCRYPTION_SALT || process.env.FIELD_ENCRYPTION_KEY;
  if (secret) return secret;
  if (process.env.NODE_ENV === "production") {
    throw new Error(
      "FATAL: FIELD_ENCRYPTION_SALT (or FIELD_ENCRYPTION_KEY) must be set in production for PII blind indexes"
    );
  }
  return "default-salt-for-dev";
}

const BLIND_INDEX_SECRET = resolveBlindIndexSecret();

/** Encrypt a single PII field. Returns the self-describing v1 payload. */
export function encryptField(plaintext: string): string {
  const iv = crypto.randomBytes(12); // 96-bit IV recommended for GCM
  const cipher = crypto.createCipheriv(ALGORITHM, KEY, iv);
  const encrypted = Buffer.concat([
    cipher.update(plaintext, "utf8"),
    cipher.final(),
  ]);
  const tag = cipher.getAuthTag();
  return [
    FORMAT_PREFIX,
    iv.toString("base64"),
    tag.toString("base64"),
    encrypted.toString("base64"),
  ].join(":");
}

/** Decrypt a payload produced by encryptField. Throws on tamper/bad format. */
export function decryptField(payload: string): string {
  const parts = payload.split(":");
  if (parts.length !== 4 || parts[0] !== FORMAT_PREFIX) {
    throw new Error("[fieldEncryption] Unrecognized ciphertext format");
  }
  const [, ivB64, tagB64, dataB64] = parts;
  const decipher = crypto.createDecipheriv(
    ALGORITHM,
    KEY,
    Buffer.from(ivB64, "base64")
  );
  decipher.setAuthTag(Buffer.from(tagB64, "base64"));
  return Buffer.concat([
    decipher.update(Buffer.from(dataB64, "base64")),
    decipher.final(),
  ]).toString("utf8");
}

/** True when the stored value is an encryptField payload (vs legacy plaintext). */
export function isEncryptedField(value: string | null | undefined): boolean {
  return typeof value === "string" && value.startsWith(`${FORMAT_PREFIX}:`);
}

/**
 * Deterministic blind index for equality lookups on encrypted PII.
 * Normalizes by trimming and stripping whitespace (BVN/NIN are numeric).
 */
export function blindIndex(plaintext: string): string {
  const normalized = plaintext.replace(/\s+/g, "").trim();
  return crypto
    .createHash("sha256")
    .update(normalized + BLIND_INDEX_SECRET)
    .digest("hex");
}
