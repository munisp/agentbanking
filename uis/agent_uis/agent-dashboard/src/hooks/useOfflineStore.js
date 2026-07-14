/**
 * Offline Transaction Store
 * Manages offline transactions, syncing, and network status
 */

import { useEffect, useState, useCallback, useRef } from "react";

const OFFLINE_DB_NAME = "54AgentBank";
const OFFLINE_STORE_NAME = "pending_transactions";
const OFFLINE_METADATA_STORE = "sync_metadata";

class OfflineStore {
  constructor() {
    this.db = null;
    this.isOnline = navigator.onLine;
    this.listeners = new Set();
  }

  async init() {
    return new Promise((resolve, reject) => {
      const request = indexedDB.open(OFFLINE_DB_NAME, 1);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.db = request.result;
        resolve();
      };

      request.onupgradeneeded = (event) => {
        const db = event.target.result;
        
        // Create stores if they don't exist
        if (!db.objectStoreNames.contains(OFFLINE_STORE_NAME)) {
          const store = db.createObjectStore(OFFLINE_STORE_NAME, {
            keyPath: "id",
            autoIncrement: true,
          });
          store.createIndex("status", "status", { unique: false });
          store.createIndex("type", "type", { unique: false });
          store.createIndex("createdAt", "createdAt", { unique: false });
        }

        if (!db.objectStoreNames.contains(OFFLINE_METADATA_STORE)) {
          db.createObjectStore(OFFLINE_METADATA_STORE, { keyPath: "key" });
        }
      };
    });
  }

  async addTransaction(transaction) {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const txn = this.db.transaction([OFFLINE_STORE_NAME], "readwrite");
      const store = txn.objectStore(OFFLINE_STORE_NAME);
      
      const offlineTransaction = {
        ...transaction,
        id: `offline_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        status: "pending",
        createdAt: new Date().toISOString(),
        retryCount: 0,
        lastError: null,
      };

      const request = store.add(offlineTransaction);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.notifyListeners();
        resolve(offlineTransaction);
      };
    });
  }

  async getPendingTransactions() {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const txn = this.db.transaction([OFFLINE_STORE_NAME], "readonly");
      const store = txn.objectStore(OFFLINE_STORE_NAME);
      const index = store.index("status");
      const request = index.getAll("pending");

      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve(request.result);
    });
  }

  async getAllTransactions() {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const txn = this.db.transaction([OFFLINE_STORE_NAME], "readonly");
      const store = txn.objectStore(OFFLINE_STORE_NAME);
      const request = store.getAll();

      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve(request.result);
    });
  }

  async updateTransaction(id, updates) {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const txn = this.db.transaction([OFFLINE_STORE_NAME], "readwrite");
      const store = txn.objectStore(OFFLINE_STORE_NAME);
      const getRequest = store.get(id);

      getRequest.onsuccess = () => {
        const transaction = getRequest.result;
        if (!transaction) return reject(new Error("Transaction not found"));

        const updated = { ...transaction, ...updates, updatedAt: new Date().toISOString() };
        const updateRequest = store.put(updated);

        updateRequest.onerror = () => reject(updateRequest.error);
        updateRequest.onsuccess = () => {
          this.notifyListeners();
          resolve(updated);
        };
      };

      getRequest.onerror = () => reject(getRequest.error);
    });
  }

  async deleteTransaction(id) {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const txn = this.db.transaction([OFFLINE_STORE_NAME], "readwrite");
      const store = txn.objectStore(OFFLINE_STORE_NAME);
      const request = store.delete(id);

      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.notifyListeners();
        resolve();
      };
    });
  }

  async deleteAllTransactions() {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const txn = this.db.transaction([OFFLINE_STORE_NAME], "readwrite");
      const store = txn.objectStore(OFFLINE_STORE_NAME);
      const request = store.clear();

      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        this.notifyListeners();
        resolve();
      };
    });
  }

  async getLastSyncTime() {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const txn = this.db.transaction([OFFLINE_METADATA_STORE], "readonly");
      const store = txn.objectStore(OFFLINE_METADATA_STORE);
      const request = store.get("lastSyncTime");

      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve(request.result?.value || null);
    });
  }

  async setLastSyncTime(time) {
    if (!this.db) await this.init();

    return new Promise((resolve, reject) => {
      const txn = this.db.transaction([OFFLINE_METADATA_STORE], "readwrite");
      const store = txn.objectStore(OFFLINE_METADATA_STORE);
      const request = store.put({ key: "lastSyncTime", value: time });

      request.onerror = () => reject(request.error);
      request.onsuccess = () => resolve();
    });
  }

  subscribe(listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  notifyListeners() {
    this.listeners.forEach((listener) => listener());
  }

  setOnline(isOnline) {
    if (this.isOnline !== isOnline) {
      this.isOnline = isOnline;
      this.notifyListeners();
    }
  }
}

// Global instance
const offlineStoreInstance = new OfflineStore();

// Initialize store
offlineStoreInstance.init().catch(console.error);

// Listen to online/offline events
window.addEventListener("online", () => offlineStoreInstance.setOnline(true));
window.addEventListener("offline", () => offlineStoreInstance.setOnline(false));

/**
 * Hook to use offline store
 */
export function useOfflineStore() {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [pendingTransactions, setPendingTransactions] = useState([]);
  const [allTransactions, setAllTransactions] = useState([]);
  const [lastSyncTime, setLastSyncTime] = useState(null);
  const [syncInProgress, setSyncInProgress] = useState(false);
  const updateRef = useRef(0);

  // Initialize and subscribe to changes
  useEffect(() => {
    const unsubscribe = offlineStoreInstance.subscribe(() => {
      updateRef.current += 1;
      setIsOnline(offlineStoreInstance.isOnline);
      loadTransactions();
    });

    loadTransactions();
    loadLastSyncTime();

    return unsubscribe;
  }, []);

  const loadTransactions = async () => {
    try {
      const pending = await offlineStoreInstance.getPendingTransactions();
      const all = await offlineStoreInstance.getAllTransactions();
      setPendingTransactions(pending);
      setAllTransactions(all);
    } catch (error) {
      console.error("Error loading transactions:", error);
    }
  };

  const loadLastSyncTime = async () => {
    try {
      const time = await offlineStoreInstance.getLastSyncTime();
      setLastSyncTime(time);
    } catch (error) {
      console.error("Error loading last sync time:", error);
    }
  };

  const addTransaction = useCallback(async (transaction) => {
    try {
      const result = await offlineStoreInstance.addTransaction(transaction);
      return result;
    } catch (error) {
      console.error("Error adding offline transaction:", error);
      throw error;
    }
  }, []);

  const updateTransaction = useCallback(async (id, updates) => {
    try {
      await offlineStoreInstance.updateTransaction(id, updates);
    } catch (error) {
      console.error("Error updating offline transaction:", error);
      throw error;
    }
  }, []);

  const deleteTransaction = useCallback(async (id) => {
    try {
      await offlineStoreInstance.deleteTransaction(id);
    } catch (error) {
      console.error("Error deleting offline transaction:", error);
      throw error;
    }
  }, []);

  const clearAllTransactions = useCallback(async () => {
    try {
      await offlineStoreInstance.deleteAllTransactions();
    } catch (error) {
      console.error("Error clearing transactions:", error);
      throw error;
    }
  }, []);

  const syncTransactions = useCallback(async (syncFunction) => {
    if (syncInProgress || !isOnline) return { synced: 0, failed: 0 };

    setSyncInProgress(true);
    try {
      const pending = await offlineStoreInstance.getPendingTransactions();
      let synced = 0;
      let failed = 0;

      for (const transaction of pending) {
        try {
          await syncFunction(transaction);
          await offlineStoreInstance.updateTransaction(transaction.id, {
            status: "synced",
            syncedAt: new Date().toISOString(),
          });
          synced++;
        } catch (error) {
          failed++;
          const retryCount = (transaction.retryCount || 0) + 1;
          const shouldRetry = retryCount < 3;

          await offlineStoreInstance.updateTransaction(transaction.id, {
            status: shouldRetry ? "pending" : "failed",
            retryCount,
            lastError: error.message,
          });
        }
      }

      await offlineStoreInstance.setLastSyncTime(new Date().toISOString());
      await loadLastSyncTime();

      return { synced, failed };
    } finally {
      setSyncInProgress(false);
      loadTransactions();
    }
  }, [isOnline]);

  return {
    isOnline,
    pendingTransactions,
    allTransactions,
    lastSyncTime,
    syncInProgress,
    addTransaction,
    updateTransaction,
    deleteTransaction,
    clearAllTransactions,
    syncTransactions,
    store: offlineStoreInstance,
  };
}

export default useOfflineStore;
