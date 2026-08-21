/**
 * PII Encryption Utilities — Data at Rest Protection
 *
 * Column-level AES-256-GCM encryption for Personally Identifiable Information.
 * Encrypts: BVN, NIN, phone, SSN, account numbers, passport numbers.
 *
 * Usage:
 *   const encrypted = encryptPII(plaintext);   // → base64 ciphertext
 *   const decrypted = decryptPII(encrypted);   // → original plaintext
 *
 * Key management:
 *   PII_ENCRYPTION_KEY env var — 32-byte hex key (64 hex chars).
 *   In production, rotate via Keycloak/Vault key management.
 */

import crypto from "crypto";

const ALGORITHM = "aes-256-gcm";
const IV_LENGTH = 16;
const TAG_LENGTH = 16;

// NF-SEC-4: fail fast at module init when the dedicated PII key is absent in
// production — never silently fall back to a hardcoded development secret.
if (process.env.NODE_ENV === "production") {
  const k = process.env.PII_ENCRYPTION_KEY;
  if (!k || k.length < 64) {
    throw new Error(
      "FATAL: PII_ENCRYPTION_KEY must be set (64+ hex chars) in production; refusing to start with the insecure development fallback key"
    );
  }
}

function getEncryptionKey(): Buffer {
  const keyHex = process.env.PII_ENCRYPTION_KEY;
  if (keyHex && keyHex.length >= 64) {
    return Buffer.from(keyHex, "hex");
  }
  // Dev-only fallback (production is guarded at module init above).
  // NOTE (salt limitation): this scrypt derivation uses a static salt
  // ("54link-pii-salt"); migrating to random per-record salts would change the
  // ciphertext format and is intentionally out of scope for this fix.
  console.warn(
    "[piiEncryption] WARNING: PII_ENCRYPTION_KEY is not set or too short; using the insecure development fallback key. Never run this configuration in production."
  );
  const secret =
    process.env.JWT_SECRET ?? "54link-dev-key-not-for-production";
  return crypto.scryptSync(secret, "54link-pii-salt", 32);
}

/**
 * Encrypt a PII value using AES-256-GCM.
 * Returns base64-encoded string: IV + ciphertext + auth tag.
 */
export function encryptPII(plaintext: string): string {
  if (!plaintext) return plaintext;

  const key = getEncryptionKey();
  const iv = crypto.randomBytes(IV_LENGTH);
  const cipher = crypto.createCipheriv(ALGORITHM, key, iv);

  const encrypted = Buffer.concat([
    cipher.update(plaintext, "utf8"),
    cipher.final(),
  ]);
  const tag = cipher.getAuthTag();

  // Format: IV (16) + ciphertext (variable) + tag (16)
  return Buffer.concat([iv, encrypted, tag]).toString("base64");
}

/**
 * Decrypt a PII value encrypted with encryptPII.
 */
export function decryptPII(ciphertext: string): string {
  if (!ciphertext) return ciphertext;

  try {
    const key = getEncryptionKey();
    const data = Buffer.from(ciphertext, "base64");

    const iv = data.subarray(0, IV_LENGTH);
    const tag = data.subarray(data.length - TAG_LENGTH);
    const encrypted = data.subarray(IV_LENGTH, data.length - TAG_LENGTH);

    const decipher = crypto.createDecipheriv(ALGORITHM, key, iv);
    decipher.setAuthTag(tag);

    return decipher.update(encrypted) + decipher.final("utf8");
  } catch {
    // If decryption fails, return as-is (migration path for pre-encryption data)
    return ciphertext;
  }
}

/**
 * Mask a PII value for display (e.g., BVN: 22*****789).
 */
export function maskPII(value: string, visibleChars = 3): string {
  if (!value || value.length <= visibleChars * 2) return "****";
  const start = value.slice(0, visibleChars);
  const end = value.slice(-visibleChars);
  return `${start}${"*".repeat(value.length - visibleChars * 2)}${end}`;
}

/** PII field names that should be encrypted at rest */
export const PII_FIELDS = [
  "bvn",
  "nin",
  "phone",
  "ssn",
  "accountNumber",
  "passportNumber",
  "driversLicense",
  "dateOfBirth",
  "motherMaidenName",
  "taxId",
] as const;
