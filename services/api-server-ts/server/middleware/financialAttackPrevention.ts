// TypeScript enabled — Sprint 96 security audit
/**
 * Financial Attack Prevention Middleware
 * Protects against: card testing, account takeover, replay attacks,
 * split-transaction fraud, phantom reversals, collusion detection,
 * credential stuffing, and enumeration attacks.
 */
import { Request, Response, NextFunction } from "express";
import crypto from "crypto";

// ── Replay Attack Prevention (Nonce + Idempotency) ───────────────────
// Round-11 wave-7 persistence fix: nonces and idempotency keys were held in
// process memory, so a restart wiped them and replayed financial mutations
// could execute twice. Both are now persisted in Postgres and checked
// atomically (INSERT ... ON CONFLICT DO NOTHING), which is correct across
// restarts AND across multiple replicas. Fails closed (503) when the DB is
// unavailable — a replay check that cannot run must not silently pass.
import { getPool } from "../db";

const NONCE_TTL = 300_000; // 5 min
const IDEMPOTENCY_TTL = 3_600_000; // 1 hour

let replayTablesReady: Promise<void> | null = null;
function ensureReplayTables(): Promise<void> {
  if (!replayTablesReady) {
    replayTablesReady = (async () => {
      const pool = await getPool();
      if (!pool) throw new Error("database pool unavailable");
      await pool.query(`
        CREATE TABLE IF NOT EXISTS replay_nonces (
          nonce VARCHAR(255) PRIMARY KEY,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE TABLE IF NOT EXISTS replay_idempotency_keys (
          key VARCHAR(255) PRIMARY KEY,
          status INTEGER,
          body JSONB,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
      `);
    })();
    replayTablesReady.catch(() => {
      replayTablesReady = null; // allow retry after a transient failure
    });
  }
  return replayTablesReady;
}

setInterval(() => {
  getPool()
    .then((pool) =>
      pool?.query(
        `DELETE FROM replay_nonces WHERE created_at < now() - interval '5 minutes';
         DELETE FROM replay_idempotency_keys WHERE created_at < now() - interval '1 hour';`
      )
    )
    .catch(() => {});
}, 60_000).unref();

export function replayAttackPrevention(
  req: Request,
  res: Response,
  next: NextFunction
) {
  // Only apply to mutation endpoints (POST, PUT, PATCH, DELETE)
  if (
    req.method === "GET" ||
    req.method === "HEAD" ||
    req.method === "OPTIONS"
  ) {
    return next();
  }

  const nonce = req.headers["x-request-nonce"] as string;
  const idempotencyKey = req.headers["idempotency-key"] as string;
  if (!nonce && !idempotencyKey) return next();

  (async () => {
    await ensureReplayTables();
    const pool = await getPool();
    if (!pool) throw new Error("database pool unavailable");

    if (nonce) {
      const r = await pool.query(
        "INSERT INTO replay_nonces (nonce) VALUES ($1) ON CONFLICT (nonce) DO NOTHING RETURNING nonce",
        [nonce]
      );
      if (r.rowCount === 0) {
        res
          .status(409)
          .json({ error: "Duplicate request detected (nonce reuse)" });
        return;
      }
    }

    if (idempotencyKey) {
      const r = await pool.query(
        "INSERT INTO replay_idempotency_keys (key) VALUES ($1) ON CONFLICT (key) DO NOTHING RETURNING key",
        [idempotencyKey]
      );
      if (r.rowCount === 0) {
        const cached = await pool.query(
          "SELECT status, body FROM replay_idempotency_keys WHERE key = $1",
          [idempotencyKey]
        );
        const row = cached.rows[0];
        if (row && row.status != null) {
          res.status(row.status).json(row.body);
        } else {
          // First request still in flight — reject the concurrent duplicate.
          res
            .status(409)
            .json({ error: "Duplicate request in flight (idempotency key)" });
        }
        return;
      }
      // First time we see this key: capture the response to complete the record.
      const originalJson = res.json.bind(res);
      res.json = function (body: any) {
        pool
          .query(
            "UPDATE replay_idempotency_keys SET status = $2, body = $3 WHERE key = $1",
            [idempotencyKey, res.statusCode, JSON.stringify(body ?? null)]
          )
          .catch(() => {});
        return originalJson(body);
      };
    }

    next();
  })().catch((err) => {
    res
      .status(503)
      .json({ error: "Replay protection unavailable", detail: String(err) });
  });
}

// ── Card Testing Detection ───────────────────────────────────────────
// Detects rapid small-amount card transactions (probing stolen cards)
interface CardTestWindow {
  attempts: number;
  smallAmounts: number; // < $5 transactions
  uniqueCards: Set<string>;
  windowStart: number;
}

const cardTestWindows = new Map<string, CardTestWindow>();

export function cardTestingDetection(
  req: Request,
  res: Response,
  next: NextFunction
) {
  if (!req.url.includes("/trpc/") || req.method !== "POST") return next();

  const ip =
    (req.headers["x-forwarded-for"] as string)?.split(",")[0]?.trim() ||
    req.socket.remoteAddress ||
    "unknown";
  const now = Date.now();
  const windowMs = 300_000; // 5 min window

  let window = cardTestWindows.get(ip);
  if (!window || now - window.windowStart > windowMs) {
    window = {
      attempts: 0,
      smallAmounts: 0,
      uniqueCards: new Set(),
      windowStart: now,
    };
    cardTestWindows.set(ip, window);
  }

  // Parse body for transaction indicators
  try {
    const body = typeof req.body === "string" ? JSON.parse(req.body) : req.body;
    if (body && typeof body === "object") {
      const amount = body.amount || body["0"]?.json?.amount;
      const cardLast4 = body.cardLast4 || body["0"]?.json?.cardLast4;

      if (amount !== undefined) {
        window.attempts++;
        if (amount < 500) window.smallAmounts++; // Less than ₦500
        if (cardLast4) window.uniqueCards.add(cardLast4);

        // Card testing indicators:
        // 1. Many small amounts from same IP
        // 2. Many unique cards from same IP
        // 3. High frequency of attempts
        if (
          window.smallAmounts > 10 ||
          window.uniqueCards.size > 5 ||
          window.attempts > 20
        ) {
          console.warn(
            `[CardTest] Suspected card testing from ${ip}: ${window.attempts} attempts, ${window.smallAmounts} small, ${window.uniqueCards.size} unique cards`
          );
          res.status(429).json({
            error: "Suspicious activity detected. Please try again later.",
            code: "CARD_TEST_DETECTED",
          });
          return;
        }
      }
    }
  } catch (e) {
    /* ignore parse errors */
  }

  next();
}

// ── Account Takeover Prevention ──────────────────────────────────────
interface LoginAttempt {
  attempts: number;
  failures: number;
  lastAttempt: number;
  lockedUntil: number;
  ips: Set<string>;
  userAgents: Set<string>;
}

const loginAttempts = new Map<string, LoginAttempt>();
const MAX_FAILED_LOGINS = 5;
const LOCKOUT_DURATION = 900_000; // 15 min
const PROGRESSIVE_LOCKOUT_MULTIPLIER = 2;

export function accountTakeoverPrevention(
  req: Request,
  res: Response,
  next: NextFunction
) {
  // Only apply to auth-related endpoints
  if (
    !req.url.includes("login") &&
    !req.url.includes("auth") &&
    !req.url.includes("pin")
  ) {
    return next();
  }
  if (req.method !== "POST") return next();

  const ip =
    (req.headers["x-forwarded-for"] as string)?.split(",")[0]?.trim() ||
    req.socket.remoteAddress ||
    "unknown";
  const userAgent = req.headers["user-agent"] || "unknown";
  const now = Date.now();

  // Extract identifier (agentCode, email, etc.)
  let identifier = "unknown";
  try {
    const body = typeof req.body === "string" ? JSON.parse(req.body) : req.body;
    identifier =
      body?.agentCode || body?.email || body?.["0"]?.json?.agentCode || ip;
  } catch (e) {
    identifier = ip;
  }

  let record = loginAttempts.get(identifier);
  if (!record) {
    record = {
      attempts: 0,
      failures: 0,
      lastAttempt: now,
      lockedUntil: 0,
      ips: new Set(),
      userAgents: new Set(),
    };
    loginAttempts.set(identifier, record);
  }

  // Check lockout
  if (record.lockedUntil > now) {
    const retryAfter = Math.ceil((record.lockedUntil - now) / 1000);
    res.status(429).json({
      error: "Account temporarily locked due to too many failed attempts",
      retryAfter,
      code: "ACCOUNT_LOCKED",
    });
    return;
  }

  record.attempts++;
  record.lastAttempt = now;
  record.ips.add(ip);
  record.userAgents.add(userAgent);

  // Detect suspicious patterns
  if (record.ips.size > 5) {
    console.warn(
      `[ATO] Account ${identifier} accessed from ${record.ips.size} different IPs`
    );
  }

  // Intercept response to track failures
  const originalJson = res.json.bind(res);
  res.json = function (body: any) {
    if (
      res.statusCode === 401 ||
      res.statusCode === 403 ||
      (body && (body.error || body.code === "UNAUTHORIZED"))
    ) {
      record!.failures++;
      if (record!.failures >= MAX_FAILED_LOGINS) {
        const lockoutMs =
          LOCKOUT_DURATION *
          Math.pow(
            PROGRESSIVE_LOCKOUT_MULTIPLIER,
            Math.floor(record!.failures / MAX_FAILED_LOGINS) - 1
          );
        record!.lockedUntil = now + Math.min(lockoutMs, 3_600_000); // Max 1 hour
        console.warn(
          `[ATO] Account ${identifier} locked for ${lockoutMs / 1000}s after ${record!.failures} failures`
        );
      }
    } else if (res.statusCode === 200) {
      // Successful login resets failure count
      record!.failures = 0;
      record!.lockedUntil = 0;
    }
    return originalJson(body);
  };

  next();
}

// ── Split Transaction Detection ──────────────────────────────────────
// Detects when a user splits a large transaction into many small ones to evade limits
interface SplitWindow {
  transactions: Array<{ amount: number; timestamp: number; type: string }>;
  windowStart: number;
}

const splitWindows = new Map<string, SplitWindow>();
const SPLIT_WINDOW_MS = 3_600_000; // 1 hour
const SPLIT_THRESHOLD_COUNT = 5; // 5+ transactions in window
const SPLIT_THRESHOLD_TOTAL = 500_000; // ₦500k total

export function splitTransactionDetection(
  agentId: string,
  amount: number,
  type: string
): {
  isSuspicious: boolean;
  reason: string;
  totalInWindow: number;
  countInWindow: number;
} {
  const now = Date.now();
  let window = splitWindows.get(agentId);
  if (!window || now - window.windowStart > SPLIT_WINDOW_MS) {
    window = { transactions: [], windowStart: now };
    splitWindows.set(agentId, window);
  }

  // Remove expired entries
  window.transactions = window.transactions.filter(
    t => now - t.timestamp < SPLIT_WINDOW_MS
  );
  window.transactions.push({ amount, timestamp: now, type });

  const totalAmount = window.transactions.reduce((sum, t) => sum + t.amount, 0);
  const count = window.transactions.length;

  if (count >= SPLIT_THRESHOLD_COUNT && totalAmount >= SPLIT_THRESHOLD_TOTAL) {
    return {
      isSuspicious: true,
      reason: `${count} transactions totaling ₦${totalAmount.toLocaleString()} in ${SPLIT_WINDOW_MS / 60000} minutes`,
      totalInWindow: totalAmount,
      countInWindow: count,
    };
  }

  return {
    isSuspicious: false,
    reason: "",
    totalInWindow: totalAmount,
    countInWindow: count,
  };
}

// ── Phantom Reversal Detection ───────────────────────────────────────
// Detects agents creating transactions then immediately reversing them for commission theft
interface ReversalWindow {
  created: number;
  reversed: number;
  windowStart: number;
}

const reversalWindows = new Map<string, ReversalWindow>();
const REVERSAL_WINDOW_MS = 3_600_000; // 1 hour
const REVERSAL_RATIO_THRESHOLD = 0.5; // 50% reversal rate is suspicious
const MIN_TX_FOR_REVERSAL_CHECK = 3;

export function phantomReversalDetection(
  agentId: string,
  isReversal: boolean
): {
  isSuspicious: boolean;
  reason: string;
  reversalRate: number;
} {
  const now = Date.now();
  let window = reversalWindows.get(agentId);
  if (!window || now - window.windowStart > REVERSAL_WINDOW_MS) {
    window = { created: 0, reversed: 0, windowStart: now };
    reversalWindows.set(agentId, window);
  }

  if (isReversal) window.reversed++;
  else window.created++;

  const total = window.created + window.reversed;
  const rate = total > 0 ? window.reversed / total : 0;

  if (total >= MIN_TX_FOR_REVERSAL_CHECK && rate >= REVERSAL_RATIO_THRESHOLD) {
    return {
      isSuspicious: true,
      reason: `${window.reversed}/${total} transactions reversed (${(rate * 100).toFixed(0)}% reversal rate)`,
      reversalRate: rate,
    };
  }

  return { isSuspicious: false, reason: "", reversalRate: rate };
}

// ── Collusion Detection ──────────────────────────────────────────────
// Detects suspicious patterns between agents (e.g., circular transfers)
interface TransferRecord {
  from: string;
  to: string;
  amount: number;
  timestamp: number;
}

const transferHistory: TransferRecord[] = [];
const COLLUSION_WINDOW_MS = 86_400_000; // 24 hours
const MAX_TRANSFER_HISTORY = 10_000;

export function recordTransfer(
  fromAgent: string,
  toAgent: string,
  amount: number
) {
  transferHistory.push({
    from: fromAgent,
    to: toAgent,
    amount,
    timestamp: Date.now(),
  });
  if (transferHistory.length > MAX_TRANSFER_HISTORY) {
    transferHistory.splice(0, transferHistory.length - MAX_TRANSFER_HISTORY);
  }
}

export function detectCollusion(agentId: string): {
  isSuspicious: boolean;
  patterns: string[];
} {
  const now = Date.now();
  const recent = transferHistory.filter(
    t => now - t.timestamp < COLLUSION_WINDOW_MS
  );
  const patterns: string[] = [];

  // Check for circular transfers (A→B→A)
  const outgoing = recent.filter(t => t.from === agentId);
  const incoming = recent.filter(t => t.to === agentId);

  for (const out of outgoing) {
    const circular = incoming.find(
      inc =>
        inc.from === out.to &&
        Math.abs(inc.amount - out.amount) < out.amount * 0.1 && // Within 10%
        Math.abs(inc.timestamp - out.timestamp) < 3_600_000 // Within 1 hour
    );
    if (circular) {
      patterns.push(
        `Circular transfer: ${agentId}→${out.to}→${agentId} (₦${out.amount}↔₦${circular.amount})`
      );
    }
  }

  // Check for high-frequency transfers to same agent
  const targetCounts = new Map<string, number>();
  for (const t of outgoing) {
    targetCounts.set(t.to, (targetCounts.get(t.to) || 0) + 1);
  }
  for (const [target, count] of targetCounts) {
    if (count >= 10) {
      patterns.push(`High-frequency transfers to ${target}: ${count} in 24h`);
    }
  }

  return { isSuspicious: patterns.length > 0, patterns };
}

// ── Credential Stuffing Detection ────────────────────────────────────
interface StuffingWindow {
  uniqueAccounts: Set<string>;
  totalAttempts: number;
  failures: number;
  windowStart: number;
}

const stuffingWindows = new Map<string, StuffingWindow>();

export function credentialStuffingDetection(
  req: Request,
  res: Response,
  next: NextFunction
) {
  if (!req.url.includes("login") && !req.url.includes("auth")) return next();
  if (req.method !== "POST") return next();

  const ip =
    (req.headers["x-forwarded-for"] as string)?.split(",")[0]?.trim() ||
    req.socket.remoteAddress ||
    "unknown";
  const now = Date.now();

  let window = stuffingWindows.get(ip);
  if (!window || now - window.windowStart > 600_000) {
    // 10 min window
    window = {
      uniqueAccounts: new Set(),
      totalAttempts: 0,
      failures: 0,
      windowStart: now,
    };
    stuffingWindows.set(ip, window);
  }

  try {
    const body = typeof req.body === "string" ? JSON.parse(req.body) : req.body;
    const account =
      body?.agentCode || body?.email || body?.["0"]?.json?.agentCode;
    if (account) window.uniqueAccounts.add(account);
  } catch (e) {
    /* ignore */
  }

  window.totalAttempts++;

  // Credential stuffing: many unique accounts from same IP
  if (window.uniqueAccounts.size > 10 && window.totalAttempts > 15) {
    console.warn(
      `[CredStuff] IP ${ip}: ${window.uniqueAccounts.size} unique accounts, ${window.totalAttempts} attempts`
    );
    res.status(429).json({
      error: "Suspicious login pattern detected",
      code: "CREDENTIAL_STUFFING_DETECTED",
    });
    return;
  }

  next();
}

// ── Enumeration Attack Prevention ────────────────────────────────────
// Prevents attackers from discovering valid usernames/agent codes
export function enumerationPrevention(
  req: Request,
  res: Response,
  next: NextFunction
) {
  if (!req.url.includes("login") && !req.url.includes("auth")) return next();

  const originalJson = res.json.bind(res);
  res.json = function (body: any) {
    // Normalize error messages to prevent user enumeration
    if (res.statusCode === 401 || res.statusCode === 404) {
      return originalJson({
        error: "Invalid credentials",
        code: "AUTH_FAILED",
      });
    }
    return originalJson(body);
  };

  next();
}

// ── Data Exfiltration Prevention ─────────────────────────────────────
const MAX_QUERY_RESULTS = 1000;
const EXPORT_RATE_LIMIT = new Map<
  string,
  { count: number; windowStart: number }
>();

export function dataExfiltrationPrevention(
  req: Request,
  res: Response,
  next: NextFunction
) {
  // Limit bulk data exports
  if (
    req.url.includes("export") ||
    req.url.includes("download") ||
    req.url.includes("bulk")
  ) {
    const userId = (req as any).userId || "anonymous";
    const now = Date.now();
    let window = EXPORT_RATE_LIMIT.get(userId);
    if (!window || now - window.windowStart > 3_600_000) {
      window = { count: 0, windowStart: now };
      EXPORT_RATE_LIMIT.set(userId, window);
    }
    window.count++;

    if (window.count > 20) {
      // Max 20 exports per hour
      res
        .status(429)
        .json({ error: "Export rate limit exceeded", maxPerHour: 20 });
      return;
    }
  }

  next();
}

// ── PII Masking Utility ──────────────────────────────────────────────
export function maskPII(data: any): any {
  if (typeof data === "string") {
    // Mask phone numbers: 080****1234
    data = data.replace(/(\d{3})\d{4}(\d{4})/g, "$1****$2");
    // Mask email: j***@example.com
    data = data.replace(/([a-zA-Z])[a-zA-Z.]+@/g, "$1***@");
    // Mask BVN: ****567890
    data = data.replace(/\b(\d{4})\d{6}\b/g, "****$1");
    return data;
  }
  if (Array.isArray(data)) return data.map(maskPII);
  if (data && typeof data === "object") {
    const masked: any = {};
    for (const [key, value] of Object.entries(data)) {
      const sensitiveKeys = [
        "phone",
        "email",
        "bvn",
        "nin",
        "ssn",
        "pan",
        "cardNumber",
        "accountNumber",
        "pin",
      ];
      if (sensitiveKeys.some(k => key.toLowerCase().includes(k))) {
        masked[key] =
          typeof value === "string" ? maskPII(value) : "***REDACTED***";
      } else {
        masked[key] = maskPII(value);
      }
    }
    return masked;
  }
  return data;
}

// ── Session Security ─────────────────────────────────────────────────
interface SessionRecord {
  userId: string;
  deviceFingerprint: string;
  ip: string;
  userAgent: string;
  createdAt: number;
  lastActive: number;
}

const activeSessions = new Map<string, SessionRecord[]>();
const MAX_CONCURRENT_SESSIONS = 3;

export function concurrentSessionControl(
  userId: string,
  deviceFingerprint: string,
  ip: string,
  userAgent: string
): {
  allowed: boolean;
  activeSessions: number;
  reason?: string;
} {
  const sessions = activeSessions.get(userId) || [];
  const now = Date.now();

  // Remove expired sessions (30 min inactive)
  const active = sessions.filter(s => now - s.lastActive < 1_800_000);

  // Check if this device already has a session
  const existing = active.find(s => s.deviceFingerprint === deviceFingerprint);
  if (existing) {
    existing.lastActive = now;
    existing.ip = ip;
    activeSessions.set(userId, active);
    return { allowed: true, activeSessions: active.length };
  }

  // Check concurrent session limit
  if (active.length >= MAX_CONCURRENT_SESSIONS) {
    return {
      allowed: false,
      activeSessions: active.length,
      reason: `Maximum ${MAX_CONCURRENT_SESSIONS} concurrent sessions allowed`,
    };
  }

  active.push({
    userId,
    deviceFingerprint,
    ip,
    userAgent,
    createdAt: now,
    lastActive: now,
  });
  activeSessions.set(userId, active);
  return { allowed: true, activeSessions: active.length };
}

export function terminateSession(userId: string, deviceFingerprint?: string) {
  if (deviceFingerprint) {
    const sessions = activeSessions.get(userId) || [];
    activeSessions.set(
      userId,
      sessions.filter(s => s.deviceFingerprint !== deviceFingerprint)
    );
  } else {
    activeSessions.delete(userId); // Terminate all
  }
}

// ── Immutable Audit Log ──────────────────────────────────────────────
interface ImmutableLogEntry {
  id: string;
  timestamp: number;
  action: string;
  actor: string;
  resource: string;
  details: any;
  hash: string;
  previousHash: string;
}

const immutableLog: ImmutableLogEntry[] = [];
let lastHash = "GENESIS";

export function appendImmutableLog(
  action: string,
  actor: string,
  resource: string,
  details: any
): string {
  const entry: ImmutableLogEntry = {
    id: crypto.randomUUID(),
    timestamp: Date.now(),
    action,
    actor,
    resource,
    details,
    hash: "",
    previousHash: lastHash,
  };

  // Create tamper-evident hash chain
  const hashInput = `${entry.id}|${entry.timestamp}|${entry.action}|${entry.actor}|${entry.resource}|${JSON.stringify(entry.details)}|${entry.previousHash}`;
  entry.hash = crypto.createHash("sha256").update(hashInput).digest("hex");
  lastHash = entry.hash;

  immutableLog.push(entry);

  // Keep last 100k entries in memory
  if (immutableLog.length > 100_000) {
    immutableLog.splice(0, immutableLog.length - 100_000);
  }

  return entry.hash;
}

export function verifyAuditChain(): { valid: boolean; brokenAt?: number } {
  for (let i = 1; i < immutableLog.length; i++) {
    const entry = immutableLog[i];
    const prev = immutableLog[i - 1];
    if (entry.previousHash !== prev.hash) {
      return { valid: false, brokenAt: i };
    }
    // Verify hash
    const hashInput = `${entry.id}|${entry.timestamp}|${entry.action}|${entry.actor}|${entry.resource}|${JSON.stringify(entry.details)}|${entry.previousHash}`;
    const expectedHash = crypto
      .createHash("sha256")
      .update(hashInput)
      .digest("hex");
    if (entry.hash !== expectedHash) {
      return { valid: false, brokenAt: i };
    }
  }
  return { valid: true };
}

export function getImmutableLogEntries(
  limit: number = 100
): ImmutableLogEntry[] {
  return immutableLog.slice(-limit);
}

// ── Apply All Financial Attack Prevention ────────────────────────────
export function applyFinancialAttackPrevention(app: any) {
  app.use(replayAttackPrevention);
  app.use(cardTestingDetection);
  app.use(accountTakeoverPrevention);
  app.use(credentialStuffingDetection);
  app.use(enumerationPrevention);
  app.use(dataExfiltrationPrevention);
  console.log(
    "[FinSec] Financial attack prevention applied: replay, card testing, ATO, credential stuffing, enumeration, data exfiltration"
  );
}
