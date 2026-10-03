// resolve conflicts using last-write-wins or server-priority strategy
// Track sync status per item: pending | synced | failed | conflict
/**
 * offlineSyncQueue — Server-side offline sync queue handler
 *
 * Receives batched offline transactions from terminals that were queued
 * while offline. Processes them with idempotency, conflict detection,
 * and ordering guarantees.
 *
 * Endpoints:
 *   POST /api/sync/push    — push offline queue to server
 *   POST /api/sync/pull    — pull updates since last sync
 *   POST /api/sync/status  — check sync status for terminal
 */

import { Router, Request, Response } from "express";
import crypto from "crypto";

// ── Types ────────────────────────────────────────────────────────────────────

export interface OfflineTransaction {
  id: string;
  clientTimestamp: number;
  type: string; // cash_in, cash_out, transfer, airtime, bill_pay
  amount: number;
  currency: string;
  agentId: string;
  customerId?: string;
  customerPhone?: string;
  description?: string;
  idempotencyKey: string;
  terminalId: string;
  offlineDuration: number; // ms the terminal was offline when this was created
  retryCount: number;
  hash: string; // SHA-256 of transaction data for integrity
}

export interface SyncRequest {
  terminalId: string;
  agentId: string;
  transactions: OfflineTransaction[];
  lastSyncTimestamp: number;
  networkTier: string;
  queueDepth: number;
}

export interface SyncResponse {
  accepted: string[];
  rejected: Array<{ id: string; reason: string }>;
  duplicates: string[];
  serverTimestamp: number;
  nextSyncRecommendedMs: number;
  updates: ServerUpdate[];
}

export interface ServerUpdate {
  type: string;
  data: Record<string, unknown>;
  timestamp: number;
}

export interface SyncStatus {
  terminalId: string;
  lastSyncTimestamp: number;
  pendingUpdates: number;
  syncHealth: "healthy" | "degraded" | "stale";
  recommendedAction: string;
}

// ── Persistent store (round-11 wave-7 gap fix) ─────────────────────────────
// Previously: accepted offline transactions were "processed" into an
// in-memory Map and NEVER written to any database — money movements pushed
// by offline terminals were acknowledged and then lost on restart, and
// idempotency keys reset on restart (double-execution risk). Accepted
// transactions are now persisted in Postgres with the idempotency key as a
// UNIQUE constraint: the atomic INSERT ... ON CONFLICT check below is both
// the duplicate detector and the write. Fails closed (503) when the DB is
// unavailable rather than acknowledging data it cannot store.
import { getPool } from "../db";

let syncTableReady: Promise<void> | null = null;
function ensureSyncTable(): Promise<void> {
  if (!syncTableReady) {
    syncTableReady = (async () => {
      const pool = await getPool();
      if (!pool) throw new Error("database pool unavailable");
      await pool.query(`
        CREATE TABLE IF NOT EXISTS offline_sync_transactions (
          id BIGSERIAL PRIMARY KEY,
          tx_id VARCHAR(128) NOT NULL,
          idempotency_key VARCHAR(255) NOT NULL UNIQUE,
          terminal_id VARCHAR(128) NOT NULL,
          agent_id VARCHAR(128) NOT NULL,
          type VARCHAR(32) NOT NULL,
          amount NUMERIC(20, 2) NOT NULL,
          currency VARCHAR(8) NOT NULL,
          payload JSONB NOT NULL,
          status VARCHAR(16) NOT NULL DEFAULT 'accepted',
          created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_offline_sync_terminal
          ON offline_sync_transactions (terminal_id, created_at);
      `);
    })();
    syncTableReady.catch(() => {
      syncTableReady = null;
    });
  }
  return syncTableReady;
}

// ── Transaction Validation ───────────────────────────────────────────────────

function validateTransaction(tx: OfflineTransaction): string | null {
  if (!tx.id) return "Missing transaction ID";
  if (!tx.type) return "Missing transaction type";
  if (!tx.amount || tx.amount <= 0) return "Invalid amount";
  if (!tx.currency) return "Missing currency";
  if (!tx.agentId) return "Missing agent ID";
  if (!tx.idempotencyKey) return "Missing idempotency key";
  if (!tx.terminalId) return "Missing terminal ID";

  // Verify hash integrity
  const expectedHash = computeHash(tx);
  if (tx.hash && tx.hash !== expectedHash) {
    return "Hash mismatch — transaction may have been tampered with";
  }

  // Check if transaction is too old (> 7 days)
  if (Date.now() - tx.clientTimestamp > 7 * 24 * 60 * 60 * 1000) {
    return "Transaction too old (> 7 days). Manual reconciliation required.";
  }

  // Amount limits
  if (tx.amount > 5000000) return "Amount exceeds maximum limit";

  return null;
}

export function computeHash(tx: OfflineTransaction): string {
  const data = `${tx.id}:${tx.type}:${tx.amount}:${tx.currency}:${tx.agentId}:${tx.clientTimestamp}`;
  return crypto
    .createHash("sha256")
    .update(data)
    .digest("hex")
    .substring(0, 16);
}

// ── Sync Queue Stats ─────────────────────────────────────────────────────────

export const syncStats = {
  totalPushes: 0,
  totalPulls: 0,
  totalTransactionsProcessed: 0,
  totalAccepted: 0,
  totalRejected: 0,
  totalDuplicates: 0,
  activeTerminals: new Set<string>(),
  lastActivity: 0,
};

// ── Router ───────────────────────────────────────────────────────────────────

export const offlineSyncRouter = Router();

offlineSyncRouter.post("/push", async (req: Request, res: Response) => {
  const body = req.body as SyncRequest;

  if (
    !body.terminalId ||
    !body.transactions ||
    !Array.isArray(body.transactions)
  ) {
    res.status(400).json({ error: "Invalid sync request" });
    return;
  }

  syncStats.totalPushes++;
  syncStats.activeTerminals.add(body.terminalId);
  syncStats.lastActivity = Date.now();

  const accepted: string[] = [];
  const rejected: Array<{ id: string; reason: string }> = [];
  const duplicates: string[] = [];

  // Sort by client timestamp to process in order
  const sorted = [...body.transactions].sort(
    (a, b) => a.clientTimestamp - b.clientTimestamp
  );

  let pool;
  try {
    await ensureSyncTable();
    pool = await getPool();
    if (!pool) throw new Error("database pool unavailable");
  } catch (err) {
    // Fail closed: never acknowledge transactions we cannot persist.
    res.status(503).json({
      error: "Offline sync store unavailable — no transactions were accepted",
      detail: String(err),
    });
    return;
  }

  for (const tx of sorted) {
    syncStats.totalTransactionsProcessed++;

    // Validate
    const error = validateTransaction(tx);
    if (error) {
      rejected.push({ id: tx.id, reason: error });
      syncStats.totalRejected++;
      continue;
    }

    // Persist + idempotency in one atomic statement: the UNIQUE constraint on
    // idempotency_key makes the insert itself the duplicate check.
    try {
      const r = await pool.query(
        `INSERT INTO offline_sync_transactions
           (tx_id, idempotency_key, terminal_id, agent_id, type, amount, currency, payload, status)
         VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'accepted')
         ON CONFLICT (idempotency_key) DO NOTHING
         RETURNING id`,
        [
          tx.id,
          tx.idempotencyKey,
          tx.terminalId,
          tx.agentId,
          tx.type,
          tx.amount,
          tx.currency,
          JSON.stringify(tx),
        ]
      );
      if (r.rowCount === 0) {
        duplicates.push(tx.id);
        syncStats.totalDuplicates++;
        continue;
      }
      accepted.push(tx.id);
      syncStats.totalAccepted++;
    } catch (err) {
      rejected.push({ id: tx.id, reason: "persistence failure: not accepted" });
      syncStats.totalRejected++;
    }
  }

  // Determine next sync interval based on network tier
  const nextSync = getRecommendedSyncInterval(
    body.networkTier,
    body.queueDepth
  );

  const response: SyncResponse = {
    accepted,
    rejected,
    duplicates,
    serverTimestamp: Date.now(),
    nextSyncRecommendedMs: nextSync,
    updates: [], // Would contain server-side updates for the terminal
  };

  res.json(response);
});

offlineSyncRouter.post("/pull", (req: Request, res: Response) => {
  const { terminalId, lastSyncTimestamp } = req.body;

  syncStats.totalPulls++;
  syncStats.activeTerminals.add(terminalId);

  // In production, query DB for updates since lastSyncTimestamp
  const updates: ServerUpdate[] = [];

  res.json({
    terminalId,
    updates,
    serverTimestamp: Date.now(),
    hasMore: false,
  });
});

offlineSyncRouter.post("/status", (req: Request, res: Response) => {
  const { terminalId } = req.body;

  const lastSync = syncStats.lastActivity;
  const staleness = Date.now() - lastSync;

  let syncHealth: "healthy" | "degraded" | "stale" = "healthy";
  let recommendedAction = "Continue normal sync";

  if (staleness > 3600000) {
    syncHealth = "stale";
    recommendedAction =
      "Force full sync — terminal has been offline for over 1 hour";
  } else if (staleness > 300000) {
    syncHealth = "degraded";
    recommendedAction = "Increase sync frequency — terminal sync is delayed";
  }

  const status: SyncStatus = {
    terminalId,
    lastSyncTimestamp: lastSync,
    pendingUpdates: 0,
    syncHealth,
    recommendedAction,
  };

  res.json(status);
});

offlineSyncRouter.get("/stats", (_req: Request, res: Response) => {
  res.json({
    ...syncStats,
    activeTerminals: syncStats.activeTerminals.size,
  });
});

// ── Helpers ──────────────────────────────────────────────────────────────────

function getRecommendedSyncInterval(
  networkTier: string,
  queueDepth: number
): number {
  const baseIntervals: Record<string, number> = {
    "2g_gprs": 120000, // 2 min
    "2g_edge": 60000, // 1 min
    "3g": 30000, // 30s
    "4g_lte": 10000, // 10s
    "5g_wifi": 5000, // 5s
  };

  let interval = baseIntervals[networkTier] || 30000;

  // If queue is deep, sync more frequently
  if (queueDepth > 50) interval = Math.max(interval / 2, 5000);
  if (queueDepth > 100) interval = Math.max(interval / 4, 3000);

  return interval;
}
