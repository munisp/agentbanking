import * as SQLite from "expo-sqlite";
import { isDeviceOnline } from "./networkService";

const DB_NAME = "offline_transfer_queue.db";
const TABLE_NAME = "offline_transfers";

let dbPromise = null;
let syncInProgress = false;
let syncStarted = false;

function isTransientNetworkError(error) {
  const message = String(error?.message || "").toLowerCase();
  return (
    message.includes("network request failed") ||
    message.includes("failed to fetch") ||
    message.includes("network") ||
    message.includes("timeout")
  );
}

async function getDb() {
  if (!dbPromise) {
    dbPromise = SQLite.openDatabaseAsync(DB_NAME).then(async (db) => {
      await db.execAsync(`
        CREATE TABLE IF NOT EXISTS ${TABLE_NAME} (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          request_id TEXT NOT NULL UNIQUE,
          transfer_kind TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          status TEXT NOT NULL DEFAULT 'pending',
          retry_count INTEGER NOT NULL DEFAULT 0,
          last_error TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_${TABLE_NAME}_status
          ON ${TABLE_NAME}(status);
      `);
      return db;
    });
  }

  return dbPromise;
}

function generateRequestId() {
  return `offline_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

export { isDeviceOnline };

export async function queueTransferForSync(transferKind, payload) {
  const db = await getDb();
  const requestId = generateRequestId();
  const now = new Date().toISOString();

  await db.runAsync(
    `
      INSERT INTO ${TABLE_NAME}
      (request_id, transfer_kind, payload_json, status, retry_count, last_error, created_at, updated_at)
      VALUES (?, ?, ?, 'pending', 0, NULL, ?, ?)
    `,
    [requestId, transferKind, JSON.stringify(payload), now, now],
  );

  return requestId;
}

async function listPendingTransfers() {
  const db = await getDb();
  return db.getAllAsync(
    `
      SELECT id, request_id, transfer_kind, payload_json, retry_count
      FROM ${TABLE_NAME}
      WHERE status = 'pending'
      ORDER BY created_at ASC
    `,
  );
}

async function markSynced(id) {
  const db = await getDb();
  const now = new Date().toISOString();
  await db.runAsync(
    `
      UPDATE ${TABLE_NAME}
      SET status = 'synced', updated_at = ?, last_error = NULL
      WHERE id = ?
    `,
    [now, id],
  );
}

async function markFailed(id, errorMessage) {
  const db = await getDb();
  const now = new Date().toISOString();
  await db.runAsync(
    `
      UPDATE ${TABLE_NAME}
      SET retry_count = retry_count + 1,
          last_error = ?,
          updated_at = ?
      WHERE id = ?
    `,
    [String(errorMessage || "sync failed"), now, id],
  );
}

export async function flushPendingTransfers(sendTransferFn) {
  if (syncInProgress) {
    return;
  }

  syncInProgress = true;
  try {
    const pending = await listPendingTransfers();

    for (const item of pending) {
      try {
        const payload = JSON.parse(item.payload_json);
        await sendTransferFn(item.transfer_kind, payload);
        await markSynced(item.id);
      } catch (error) {
        await markFailed(item.id, error?.message || "sync error");
        if (isTransientNetworkError(error)) {
          break;
        }
      }
    }
  } finally {
    syncInProgress = false;
  }
}

export function startOfflineTransferSync(sendTransferFn) {
  if (syncStarted) {
    return;
  }

  syncStarted = true;

  flushPendingTransfers(sendTransferFn).catch((error) => {
    console.warn("Initial offline sync failed:", error?.message || error);
  });
}

export function stopOfflineTransferSync() {
  syncStarted = false;
}

export { isTransientNetworkError };
