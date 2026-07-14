// @ts-nocheck — Sprint 69: production build compatibility
export const COOKIE_NAME = "kc_session";
export const ONE_YEAR_MS = 1000 * 60 * 60 * 24 * 365;
export const AXIOS_TIMEOUT_MS = 30_000;
export const UNAUTHED_ERR_MSG = "Please login (10001)";
export const NOT_ADMIN_ERR_MSG = "You do not have required permission (10002)";

// ── Session ──────────────────────────────────────────────────────────────────
export const SESSION_TTL_MS = 1000 * 60 * 60 * 8; // 8 hours
export const REFRESH_WINDOW_MS = 1000 * 60 * 15; // refresh 15 min before expiry

// ── Pagination ───────────────────────────────────────────────────────────────
export const DEFAULT_PAGE_SIZE = 20;
export const MAX_PAGE_SIZE = 100;

// ── Transaction limits (NGN) ─────────────────────────────────────────────────
export const CASH_IN_DAILY_LIMIT_NGN = 5_000_000;
export const CASH_OUT_DAILY_LIMIT_NGN = 2_000_000;
export const TRANSFER_DAILY_LIMIT_NGN = 10_000_000;
export const SINGLE_TXN_LIMIT_NGN = 1_000_000;
export const NANO_LOAN_MAX_NGN = 50_000;
export const MICRO_INSURANCE_MIN_NGN = 500;

// ── Float thresholds (NGN) ───────────────────────────────────────────────────
export const FLOAT_LOW_THRESHOLD_NGN = 10_000;
export const FLOAT_CRITICAL_NGN = 5_000;
export const FLOAT_MAX_BALANCE_NGN = 10_000_000;

// ── Commission rates ─────────────────────────────────────────────────────────
export const COMMISSION_CASH_IN_PCT = 0.003; // 0.3%
export const COMMISSION_CASH_OUT_PCT = 0.005; // 0.5%
export const COMMISSION_TRANSFER_PCT = 0.002; // 0.2%
export const COMMISSION_AIRTIME_PCT = 0.02; // 2%
export const COMMISSION_BILLS_PCT = 0.015; // 1.5%

// ── KYC tiers ────────────────────────────────────────────────────────────────
export const KYC_TIER1_DAILY_LIMIT_NGN = 50_000;
export const KYC_TIER2_DAILY_LIMIT_NGN = 200_000;
export const KYC_TIER3_DAILY_LIMIT_NGN = 1_000_000;

// ── Retry / resilience ───────────────────────────────────────────────────────
export const MAX_RETRY_ATTEMPTS = 5;
export const RETRY_BACKOFF_BASE_MS = 1_000;
export const RETRY_BACKOFF_MAX_MS = 60_000;
export const OFFLINE_QUEUE_MAX_SIZE = 500;
export const OFFLINE_SYNC_INTERVAL_MS = 30_000;

// ── Rate locking ─────────────────────────────────────────────────────────────
export const RATE_LOCK_DURATION_MINUTES = 15;
export const RATE_LOCK_MAX_AMOUNT_USD = 50_000;
export const RATE_SPREAD_PCT = 0.005; // 0.5% spread

// ── OTA / MDM ────────────────────────────────────────────────────────────────
export const OTA_CHECK_INTERVAL_HOURS = 6;
export const OTA_DOWNLOAD_TIMEOUT_MS = 300_000; // 5 minutes
export const MDM_HEARTBEAT_INTERVAL_MS = 60_000; // 1 minute

// ── Fraud detection ──────────────────────────────────────────────────────────
export const FRAUD_VELOCITY_WINDOW_MS = 300_000; // 5 minutes
export const FRAUD_MAX_TXN_PER_WINDOW = 10;
export const FRAUD_AMOUNT_SPIKE_FACTOR = 5; // 5x average = alert
export const FRAUD_RISK_SCORE_THRESHOLD = 75; // 0-100 scale

// ── Push notifications ───────────────────────────────────────────────────────
export const PUSH_ALERT_THROTTLE_MINUTES = 30;
export const PUSH_MAX_SUBSCRIPTIONS_PER_AGENT = 5;

// ── Loyalty / rewards ────────────────────────────────────────────────────────
export const LOYALTY_POINTS_PER_NGN = 0.01; // 1 point per ₦100
export const LOYALTY_BRONZE_THRESHOLD = 0;
export const LOYALTY_SILVER_THRESHOLD = 1_000;
export const LOYALTY_GOLD_THRESHOLD = 10_000;
export const LOYALTY_PLATINUM_THRESHOLD = 50_000;

// ── Branding ─────────────────────────────────────────────────────────────────
export const BRAND_NAME = "54agent";
export const BRAND_TAGLINE = "Agency Banking for Africa";
export const BRAND_COLOR_PRIMARY = "#1A56DB";
export const BRAND_COLOR_SECONDARY = "#10B981";
export const SUPPORT_EMAIL = "support@54agent.io";
export const SUPPORT_PHONE = "+234-800-54agent";
export const SUPPORT_WHATSAPP = "+2348005454650";

// ── API versioning ───────────────────────────────────────────────────────────
export const API_VERSION = "v1";
export const APP_VERSION = "2.0.0";
export const MIN_FLUTTER_APP_VERSION = "1.5.0";

// ── Currencies ───────────────────────────────────────────────────────────────
export const BASE_CURRENCY = "NGN";
export const SUPPORTED_CURRENCIES = [
  "NGN",
  "USD",
  "GBP",
  "EUR",
  "GHS",
  "KES",
  "ZAR",
  "XOF",
] as const;
export type SupportedCurrency = (typeof SUPPORTED_CURRENCIES)[number];

// ── Nigerian banks (NIP sort codes) ─────────────────────────────────────────
export const NIGERIAN_BANKS = [
  { code: "044", name: "Access Bank" },
  { code: "023", name: "Citibank" },
  { code: "050", name: "EcoBank" },
  { code: "011", name: "First Bank" },
  { code: "214", name: "First City Monument Bank (FCMB)" },
  { code: "070", name: "Fidelity Bank" },
  { code: "058", name: "Guaranty Trust Bank (GTB)" },
  { code: "030", name: "Heritage Bank" },
  { code: "301", name: "Jaiz Bank" },
  { code: "082", name: "Keystone Bank" },
  { code: "526", name: "Moniepoint MFB" },
  { code: "076", name: "Polaris Bank" },
  { code: "101", name: "ProvidusBank" },
  { code: "221", name: "Stanbic IBTC" },
  { code: "068", name: "Standard Chartered" },
  { code: "232", name: "Sterling Bank" },
  { code: "032", name: "Union Bank" },
  { code: "033", name: "United Bank for Africa (UBA)" },
  { code: "215", name: "Unity Bank" },
  { code: "035", name: "Wema Bank" },
  { code: "057", name: "Zenith Bank" },
  { code: "000026", name: "Opay" },
  { code: "000025", name: "Kuda Bank" },
  { code: "000023", name: "PalmPay" },
] as const;

// ── Bill payment billers ─────────────────────────────────────────────────────
export const BILL_CATEGORIES = [
  "electricity",
  "water",
  "cable_tv",
  "internet",
  "insurance",
  "government",
] as const;
export type BillCategory = (typeof BILL_CATEGORIES)[number];

export const ELECTRICITY_DISCOS = [
  "AEDC",
  "BEDC",
  "EEDC",
  "EKEDC",
  "IBEDC",
  "IKEDC",
  "JED",
  "KAEDCO",
  "PHED",
] as const;

// ── Airtime networks ─────────────────────────────────────────────────────────
export const AIRTIME_NETWORKS = ["MTN", "Airtel", "Glo", "9mobile"] as const;
export type AirtimeNetwork = (typeof AIRTIME_NETWORKS)[number];

// ── Terminal hardware ─────────────────────────────────────────────────────────
export const SUPPORTED_TERMINAL_MODELS = [
  "PAX A920",
  "PAX A920 Pro",
  "Aisino A75",
  "Verifone P400",
  "Ingenico Move 5000",
] as const;
export const PRINTER_PAPER_WIDTH_MM = 58;
export const RECEIPT_HEADER_LINES = 5;
export const RECEIPT_FOOTER_LINES = 3;

// ── Timeouts ─────────────────────────────────────────────────────────────────
export const PIN_ENTRY_TIMEOUT_MS = 30_000;
export const TRANSACTION_TIMEOUT_MS = 120_000;
export const IDLE_LOGOUT_MS = 300_000; // 5 minutes
export const BIOMETRIC_TIMEOUT_MS = 15_000;
export const QR_SCAN_TIMEOUT_MS = 60_000;

// ── Regex patterns ───────────────────────────────────────────────────────────
export const REGEX_PHONE_NG = /^(\+234|0)[789][01]\d{8}$/;
export const REGEX_BVN = /^\d{11}$/;
export const REGEX_NIN = /^\d{11}$/;
export const REGEX_ACCOUNT_NUMBER = /^\d{10}$/;
export const REGEX_AGENT_CODE = /^AGT-\d{6}$/;

// ── Extended Nigerian validation helpers ─────────────────────────────────────
/** Nigerian mobile number prefixes by network (NCC allocation as of 2024) */
export const NG_PHONE_PREFIXES: Record<string, string[]> = {
  MTN: [
    "0703",
    "0706",
    "0803",
    "0806",
    "0810",
    "0813",
    "0814",
    "0816",
    "0903",
    "0906",
    "0913",
    "0916",
  ],
  Airtel: [
    "0701",
    "0708",
    "0802",
    "0808",
    "0812",
    "0902",
    "0907",
    "0901",
    "0904",
    "0912",
  ],
  Glo: ["0705", "0805", "0807", "0811", "0815", "0905", "0915"],
  "9mobile": ["0809", "0817", "0818", "0909", "0908"],
};

/** Detect carrier from Nigerian phone number */
export function detectNgCarrier(phone: string): string | null {
  const normalised = phone.replace(/^\+234/, "0").replace(/\s/g, "");
  for (const [carrier, prefixes] of Object.entries(NG_PHONE_PREFIXES)) {
    if (prefixes.some(p => normalised.startsWith(p))) return carrier;
  }
  return null;
}

/** Normalise Nigerian phone number to international format (+234XXXXXXXXXX) */
export function normaliseNgPhone(phone: string): string {
  const cleaned = phone.replace(/\D/g, "");
  if (cleaned.startsWith("234") && cleaned.length === 13) return `+${cleaned}`;
  if (cleaned.startsWith("0") && cleaned.length === 11)
    return `+234${cleaned.slice(1)}`;
  return phone;
}

/** Validate Nigerian BVN — 11 digits, starts with 2 */
export function validateBvn(bvn: string): { valid: boolean; reason?: string } {
  if (!/^\d{11}$/.test(bvn))
    return { valid: false, reason: "BVN must be exactly 11 digits" };
  if (!bvn.startsWith("2"))
    return { valid: false, reason: "BVN must start with digit 2" };
  return { valid: true };
}

/** Validate Nigerian NIN — 11 digits */
export function validateNin(nin: string): { valid: boolean; reason?: string } {
  if (!/^\d{11}$/.test(nin))
    return { valid: false, reason: "NIN must be exactly 11 digits" };
  return { valid: true };
}

/** Validate Nigerian mobile phone number */
export function validateNgPhone(phone: string): {
  valid: boolean;
  reason?: string;
  carrier?: string;
} {
  const normalised = phone.replace(/^\+234/, "0").replace(/\s/g, "");
  if (!/^0[789][01]\d{8}$/.test(normalised)) {
    return {
      valid: false,
      reason: "Invalid Nigerian phone number (e.g. 08012345678)",
    };
  }
  const carrier = detectNgCarrier(normalised);
  return { valid: true, carrier: carrier ?? undefined };
}

/** Validate NUBAN bank account number — 10 digits */
export function validateNuban(account: string): {
  valid: boolean;
  reason?: string;
} {
  if (!/^\d{10}$/.test(account))
    return {
      valid: false,
      reason: "Account number must be exactly 10 digits (NUBAN)",
    };
  return { valid: true };
}

/** CAC registration number patterns */
export const REGEX_CAC_RC = /^RC\d{6,7}$/i;
export const REGEX_CAC_BN = /^BN\d{7}$/i;
export const REGEX_CAC_IT = /^IT\/\d{5,6}$/i;
export function validateCacNumber(cac: string): {
  valid: boolean;
  type?: string;
  reason?: string;
} {
  if (REGEX_CAC_RC.test(cac))
    return { valid: true, type: "Registered Company" };
  if (REGEX_CAC_BN.test(cac)) return { valid: true, type: "Business Name" };
  if (REGEX_CAC_IT.test(cac))
    return { valid: true, type: "Incorporated Trustee" };
  return {
    valid: false,
    reason: "Invalid CAC number (e.g. RC123456, BN1234567, IT/12345)",
  };
}

/** Nigerian TIN — 8 or 10 digits */
export const REGEX_TIN = /^\d{8}(\d{2})?$/;
export function validateTin(tin: string): { valid: boolean; reason?: string } {
  if (!REGEX_TIN.test(tin))
    return { valid: false, reason: "TIN must be 8 or 10 digits" };
  return { valid: true };
}

/** Nigerian Postal Code — 6 digits */
export const REGEX_POSTAL_CODE_NG = /^\d{6}$/;

/** 37 Nigerian states + FCT */
export const NIGERIAN_STATES = [
  "Abia",
  "Adamawa",
  "Akwa Ibom",
  "Anambra",
  "Bauchi",
  "Bayelsa",
  "Benue",
  "Borno",
  "Cross River",
  "Delta",
  "Ebonyi",
  "Edo",
  "Ekiti",
  "Enugu",
  "FCT",
  "Gombe",
  "Imo",
  "Jigawa",
  "Kaduna",
  "Kano",
  "Katsina",
  "Kebbi",
  "Kogi",
  "Kwara",
  "Lagos",
  "Nasarawa",
  "Niger",
  "Ogun",
  "Ondo",
  "Osun",
  "Oyo",
  "Plateau",
  "Rivers",
  "Sokoto",
  "Taraba",
  "Yobe",
  "Zamfara",
] as const;
export type NigerianState = (typeof NIGERIAN_STATES)[number];

/** Geopolitical zones */
export const NG_GEOPOLITICAL_ZONES: Record<string, string[]> = {
  "North Central": [
    "Benue",
    "FCT",
    "Kogi",
    "Kwara",
    "Nasarawa",
    "Niger",
    "Plateau",
  ],
  "North East": ["Adamawa", "Bauchi", "Borno", "Gombe", "Taraba", "Yobe"],
  "North West": [
    "Jigawa",
    "Kaduna",
    "Kano",
    "Katsina",
    "Kebbi",
    "Sokoto",
    "Zamfara",
  ],
  "South East": ["Abia", "Anambra", "Ebonyi", "Enugu", "Imo"],
  "South South": [
    "Akwa Ibom",
    "Bayelsa",
    "Cross River",
    "Delta",
    "Edo",
    "Rivers",
  ],
  "South West": ["Ekiti", "Lagos", "Ogun", "Ondo", "Osun", "Oyo"],
};

/** Format Nigerian Naira amount */
export function formatNaira(amount: number, showDecimals = true): string {
  return `\u20a6${amount.toLocaleString("en-NG", {
    minimumFractionDigits: showDecimals ? 2 : 0,
    maximumFractionDigits: showDecimals ? 2 : 0,
  })}`;
}

/** Parse Naira string to number */
export function parseNaira(value: string): number {
  return parseFloat(value.replace(/[\u20a6,\s]/g, "")) || 0;
}
