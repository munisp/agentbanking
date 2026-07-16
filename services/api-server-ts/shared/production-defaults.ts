// @ts-nocheck — Sprint 69: production build compatibility
/**
 * Sprint 52 — Production API Defaults
 * F05: All URLs, IDs, secrets with sensible defaults
 */

// ─── Nigerian Financial APIs ────────────────────────────────────
export const NIBSS_API_URL =
  process.env.NIBSS_API_URL || "https://api.nibss-plc.com.ng/v2";
export const NIBSS_API_KEY = process.env.NIBSS_API_KEY || "";
export const NIBSS_INSTITUTION_CODE =
  process.env.NIBSS_INSTITUTION_CODE || "999999";

export const CBN_REPORTING_URL =
  process.env.CBN_REPORTING_URL || "https://reporting.cbn.gov.ng/api/v1";
export const CBN_INSTITUTION_ID =
  process.env.CBN_INSTITUTION_ID || "FI-54agent-001";

export const NFIU_API_URL =
  process.env.NFIU_API_URL || "https://api.nfiu.gov.ng/v1";
export const NFIU_REPORTING_KEY = process.env.NFIU_REPORTING_KEY || "";

// ─── KYC/Identity Verification ──────────────────────────────────
export const YOUVERIFY_API_URL =
  process.env.YOUVERIFY_API_URL || "https://api.youverify.co/v2";
export const YOUVERIFY_API_KEY = process.env.YOUVERIFY_API_KEY || "";

export const SMILE_ID_API_URL =
  process.env.SMILE_ID_API_URL || "https://api.smileidentity.com/v1";
export const SMILE_ID_PARTNER_ID = process.env.SMILE_ID_PARTNER_ID || "";

export const NIN_VERIFICATION_URL =
  process.env.NIN_VERIFICATION_URL || "https://api.nimc.gov.ng/v1/verify";
export const BVN_VERIFICATION_URL =
  process.env.BVN_VERIFICATION_URL ||
  "https://api.nibss-plc.com.ng/bvn/v2/verify";

// ─── SMS/Notification Providers ─────────────────────────────────
export const TERMII_API_URL =
  process.env.TERMII_API_URL || "https://api.ng.termii.com/api";
export const TERMII_API_KEY = process.env.TERMII_API_KEY || "";
export const TERMII_SENDER_ID = process.env.TERMII_SENDER_ID || "54agent";

export const FIREBASE_PROJECT_ID =
  process.env.FIREBASE_PROJECT_ID || "pos-shell-demo";
export const FIREBASE_SERVER_KEY = process.env.FIREBASE_SERVER_KEY || "";

export const SENDGRID_API_KEY = process.env.SENDGRID_API_KEY || "";
export const SENDGRID_FROM_EMAIL =
  process.env.SENDGRID_FROM_EMAIL || "noreply@54agent.com";

// ─── Payment Processors ────────────────────────────────────────
export const PAYSTACK_SECRET_KEY = process.env.PAYSTACK_SECRET_KEY || "";
export const PAYSTACK_PUBLIC_KEY = process.env.PAYSTACK_PUBLIC_KEY || "";

export const FLUTTERWAVE_SECRET_KEY = process.env.FLUTTERWAVE_SECRET_KEY || "";
export const FLUTTERWAVE_PUBLIC_KEY = process.env.FLUTTERWAVE_PUBLIC_KEY || "";

// ─── TigerBeetle / Ledger ───────────────────────────────────────
export const TIGERBEETLE_CLUSTER_ID = process.env.TIGERBEETLE_CLUSTER_ID || "0";
export const TIGERBEETLE_ADDRESSES =
  process.env.TIGERBEETLE_ADDRESSES || "127.0.0.1:3000";
export const TB_SIDECAR_URL =
  process.env.TB_SIDECAR_URL || "http://localhost:9090";

// ─── Infrastructure ─────────────────────────────────────────────
export const REDIS_URL = process.env.REDIS_URL || "redis://localhost:6379";
export const KAFKA_BROKERS = (
  process.env.KAFKA_BROKERS || "localhost:9092"
).split(",");
export const ELASTICSEARCH_URL =
  process.env.ELASTICSEARCH_URL || "http://localhost:9200";
export const S3_BUCKET = process.env.S3_BUCKET || "pos-shell-demo-storage";
export const S3_REGION = process.env.S3_REGION || "us-east-1";

// ─── Monitoring ─────────────────────────────────────────────────
export const SENTRY_DSN = process.env.SENTRY_DSN || "";
export const GRAFANA_URL = process.env.GRAFANA_URL || "http://localhost:3001";
export const PROMETHEUS_URL =
  process.env.PROMETHEUS_URL || "http://localhost:9090";

// ─── Application ────────────────────────────────────────────────
export const APP_NAME = "54agent POS Shell";
export const APP_VERSION = "3.0.0";
export const APP_ENVIRONMENT = process.env.NODE_ENV || "development";
export const APP_BASE_URL =
  process.env.APP_BASE_URL || "https://pos.54agent.com";
export const SUPPORT_EMAIL = "support@54agent.com";
export const SUPPORT_PHONE = "+234-800-54agent";

// ─── Business Rules ─────────────────────────────────────────────
export const MAX_DAILY_TX_LIMIT_NGN = 5_000_000; // ₦5M CBN limit
export const MAX_SINGLE_TX_LIMIT_NGN = 1_000_000; // ₦1M per transaction
export const MIN_FLOAT_BALANCE_NGN = 10_000; // ₦10K minimum float
export const COMMISSION_PAYOUT_THRESHOLD_NGN = 500; // ₦500 minimum payout
export const KYC_EXPIRY_DAYS = 365; // Annual KYC renewal
export const SESSION_TIMEOUT_MS = 12 * 60 * 60 * 1000; // 12 hours
export const OTP_EXPIRY_MS = 10 * 60 * 1000; // 10 minutes
export const MAX_LOGIN_ATTEMPTS = 5;
export const LOCKOUT_DURATION_MS = 30 * 60 * 1000; // 30 minutes

// ─── Fee Schedule (Nigerian POS Standard) ───────────────────────
export const FEE_SCHEDULE = {
  CASH_IN: { flat: 0, percentage: 0 },
  CASH_OUT: { flat: 100, percentage: 0.5, cap: 1000 },
  TRANSFER: { flat: 50, percentage: 0.25, cap: 500 },
  AIRTIME: { flat: 0, percentage: 2.5, cap: 200 },
  BILLS: { flat: 100, percentage: 0 },
  CARD_PAYMENT: { flat: 0, percentage: 1.5, cap: 2000 },
  QR_PAYMENT: { flat: 0, percentage: 0.5, cap: 500 },
  NFC_PAYMENT: { flat: 0, percentage: 0.75, cap: 750 },
} as const;

// ─── Commission Tiers ───────────────────────────────────────────
export const COMMISSION_TIERS = [
  { name: "Bronze", minVolume: 0, rate: 0.002 },
  { name: "Silver", minVolume: 500_000, rate: 0.003 },
  { name: "Gold", minVolume: 2_000_000, rate: 0.005 },
  { name: "Platinum", minVolume: 10_000_000, rate: 0.008 },
  { name: "Diamond", minVolume: 50_000_000, rate: 0.01 },
] as const;

// ── Timeout Configuration ──────────────────────────────────────────────
export const TIMEOUT_DEFAULTS = {
  /** API request timeout in milliseconds */
  apiRequestTimeout: 30_000,
  /** Database query timeout in milliseconds */
  dbQueryTimeout: 15_000,
  /** External service call timeout in milliseconds */
  externalServiceTimeout: 45_000,
  /** WebSocket heartbeat interval in milliseconds */
  wsHeartbeatInterval: 30_000,
  /** Session idle timeout in milliseconds (30 minutes) */
  sessionIdleTimeout: 1_800_000,
  /** File upload timeout in milliseconds */
  fileUploadTimeout: 120_000,
  /** Batch processing timeout in milliseconds */
  batchProcessingTimeout: 300_000,
};
