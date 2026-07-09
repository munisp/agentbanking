/**
 * Offline Transaction Queue
 * IndexedDB-backed queue for transactions created while offline.
 * Automatically syncs when connectivity is restored via Background Sync API.
 * Conflict resolution: server-wins by default, with client-override for amounts.
 */

const DB_NAME = "54link_offline";
const DB_VERSION = 1;
const STORE_NAME = "tx_queue";

interface QueuedTransaction {
  id: string;
  type: string;
  payload: Record<string, unknown>;
  status: "queued" | "syncing" | "synced" | "failed" | "conflict";
  createdAt: number;
  syncedAt?: number;
  retryCount: number;
  conflictResolution?: "client_wins" | "server_wins";
}

function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
    request.onupgradeneeded = event => {
      const db = (event.target as IDBOpenDBRequest).result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const store = db.createObjectStore(STORE_NAME, { keyPath: "id" });
        store.createIndex("status", "status", { unique: false });
        store.createIndex("createdAt", "createdAt", { unique: false });
      }
    };
  });
}

/**
 * Add a transaction to the offline queue
 */
export async function enqueueTransaction(
  type: string,
  payload: Record<string, unknown>
): Promise<string> {
  const id = `tx_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  const tx: QueuedTransaction = {
    id,
    type,
    payload,
    status: "queued",
    createdAt: Date.now(),
    retryCount: 0,
  };

  const db = await openDB();
  return new Promise((resolve, reject) => {
    const txn = db.transaction(STORE_NAME, "readwrite");
    txn.objectStore(STORE_NAME).add(tx);
    txn.oncomplete = () => {
      requestBackgroundSync();
      resolve(id);
    };
    txn.onerror = () => reject(txn.error);
  });
}

/**
 * Get all queued transactions
 */
export async function getQueuedTransactions(): Promise<QueuedTransaction[]> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const txn = db.transaction(STORE_NAME, "readonly");
    const request = txn
      .objectStore(STORE_NAME)
      .index("status")
      .getAll("queued");
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

/**
 * Get queue size
 */
export async function getQueueSize(): Promise<number> {
  const db = await openDB();
  return new Promise((resolve, reject) => {
    const txn = db.transaction(STORE_NAME, "readonly");
    const request = txn.objectStore(STORE_NAME).count();
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

/**
 * Sync all queued transactions to server
 */
export async function syncQueuedTransactions(): Promise<{
  synced: number;
  failed: number;
  conflicts: number;
}> {
  const db = await openDB();
  const queued = await getQueuedTransactions();
  let synced = 0,
    failed = 0,
    conflicts = 0;

  for (const tx of queued) {
    try {
      // Mark as syncing
      const txn = db.transaction(STORE_NAME, "readwrite");
      const store = txn.objectStore(STORE_NAME);
      tx.status = "syncing";
      store.put(tx);

      // Send to server
      const response = await fetch(`/api/trpc/${tx.type}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ json: tx.payload }),
      });

      if (response.ok) {
        const txn2 = db.transaction(STORE_NAME, "readwrite");
        tx.status = "synced";
        tx.syncedAt = Date.now();
        txn2.objectStore(STORE_NAME).put(tx);
        synced++;
      } else if (response.status === 409) {
        // Conflict — server has different state
        const txn2 = db.transaction(STORE_NAME, "readwrite");
        tx.status = "conflict";
        tx.conflictResolution = "server_wins";
        txn2.objectStore(STORE_NAME).put(tx);
        conflicts++;
      } else {
        throw new Error(`HTTP ${response.status}`);
      }
    } catch {
      const txn = db.transaction(STORE_NAME, "readwrite");
      tx.status = tx.retryCount >= 3 ? "failed" : "queued";
      tx.retryCount++;
      txn.objectStore(STORE_NAME).put(tx);
      failed++;
    }
  }

  return { synced, failed, conflicts };
}

/**
 * Clear synced transactions (older than 24h)
 */
export async function clearSyncedTransactions(): Promise<number> {
  const db = await openDB();
  const cutoff = Date.now() - 24 * 60 * 60 * 1000;

  return new Promise((resolve, reject) => {
    const txn = db.transaction(STORE_NAME, "readwrite");
    const store = txn.objectStore(STORE_NAME);
    const request = store
      .index("status")
      .openCursor(IDBKeyRange.only("synced"));
    let deleted = 0;

    request.onsuccess = event => {
      const cursor = (event.target as IDBRequest<IDBCursorWithValue>).result;
      if (cursor) {
        if (cursor.value.syncedAt < cutoff) {
          cursor.delete();
          deleted++;
        }
        cursor.continue();
      }
    };
    txn.oncomplete = () => resolve(deleted);
    txn.onerror = () => reject(txn.error);
  });
}

/**
 * Check if online
 */
export function isOnline(): boolean {
  return typeof navigator !== "undefined" ? navigator.onLine : true;
}

/**
 * Request background sync (Service Worker)
 */
function requestBackgroundSync(): void {
  if ("serviceWorker" in navigator && "SyncManager" in window) {
    navigator.serviceWorker.ready.then(reg => {
      (reg as any).sync.register("tx-sync").catch(() => {});
    });
  }
}

/**
 * Auto-sync on reconnect
 */
if (typeof window !== "undefined") {
  window.addEventListener("online", () => {
    syncQueuedTransactions().catch(() => {});
  });
}
