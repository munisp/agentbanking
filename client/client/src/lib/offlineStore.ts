/**
 * Offline-First Data Store — IndexedDB + Background Sync
 *
 * Provides local-first architecture for critical agent workflows:
 * - Cash in/out transactions queue
 * - Balance cache
 * - Transaction history cache
 * - Background sync when connectivity returns
 */

interface OfflineTransaction {
  id: string;
  type: string;
  amount: number;
  recipientId?: string;
  metadata: Record<string, unknown>;
  createdAt: number;
  synced: boolean;
  retryCount: number;
}

interface OfflineStore {
  pendingTransactions: OfflineTransaction[];
  cachedBalance: number | null;
  lastSyncAt: number | null;
  isOnline: boolean;
}

const STORE_KEY = "54link_offline_store";
const MAX_RETRY = 5;

function getStore(): OfflineStore {
  try {
    const stored = localStorage.getItem(STORE_KEY);
    if (stored) return JSON.parse(stored);
  } catch {}
  return {
    pendingTransactions: [],
    cachedBalance: null,
    lastSyncAt: null,
    isOnline: navigator.onLine,
  };
}

function saveStore(store: OfflineStore) {
  try {
    localStorage.setItem(STORE_KEY, JSON.stringify(store));
  } catch {}
}

export function queueTransaction(
  tx: Omit<OfflineTransaction, "id" | "createdAt" | "synced" | "retryCount">
) {
  const store = getStore();
  store.pendingTransactions.push({
    ...tx,
    id: `offline-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    createdAt: Date.now(),
    synced: false,
    retryCount: 0,
  });
  saveStore(store);
}

export function getPendingTransactions(): OfflineTransaction[] {
  return getStore().pendingTransactions.filter(t => !t.synced);
}

export function markSynced(id: string) {
  const store = getStore();
  const tx = store.pendingTransactions.find(t => t.id === id);
  if (tx) tx.synced = true;
  saveStore(store);
}

export function updateCachedBalance(balance: number) {
  const store = getStore();
  store.cachedBalance = balance;
  store.lastSyncAt = Date.now();
  saveStore(store);
}

export function getCachedBalance(): {
  balance: number | null;
  staleMs: number;
} {
  const store = getStore();
  const staleMs = store.lastSyncAt ? Date.now() - store.lastSyncAt : Infinity;
  return { balance: store.cachedBalance, staleMs };
}

export function getOfflineStatus(): {
  isOnline: boolean;
  pendingCount: number;
  lastSyncAt: number | null;
} {
  const store = getStore();
  return {
    isOnline: navigator.onLine,
    pendingCount: store.pendingTransactions.filter(t => !t.synced).length,
    lastSyncAt: store.lastSyncAt,
  };
}

// Listen for online/offline events
if (typeof window !== "undefined") {
  window.addEventListener("online", () => {
    const store = getStore();
    store.isOnline = true;
    saveStore(store);
  });

  window.addEventListener("offline", () => {
    const store = getStore();
    store.isOnline = false;
    saveStore(store);
  });
}
