// React Native Offline Service
import AsyncStorage from '@react-native-async-storage/async-storage';
import NetInfo from '@react-native-community/netinfo';

interface QueuedRequest {
  id: string;
  url: string;
  method: string;
  body?: any;
  headers?: Record<string, string>;
  timestamp: number;
  retryCount: number;
}

interface CachedData {
  data: any;
  timestamp: number;
  expiresAt: number;
}

export class OfflineService {
  private static readonly QUEUE_KEY = 'offline_queue';
  private static readonly CACHE_KEY_PREFIX = 'cache_';
  private static isOnline: boolean = true;
  private static listeners: Array<(isOnline: boolean) => void> = [];

  // Initialize
  static async initialize(): Promise<void> {
    // Monitor network status
    NetInfo.addEventListener(state => {
      const wasOnline = this.isOnline;
      this.isOnline = state.isConnected ?? false;
      
      if (!wasOnline && this.isOnline) {
        // Just came back online, process queue
        this.processQueue();
      }
      
      // Notify listeners
      this.listeners.forEach(listener => listener(this.isOnline));
    });

    // Process any pending requests
    if (this.isOnline) {
      await this.processQueue();
    }
  }

  // Network Status
  static getOnlineStatus(): boolean {
    return this.isOnline;
  }

  static addOnlineStatusListener(listener: (isOnline: boolean) => void): () => void {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  // Request Queue
  static async queueRequest(
    url: string,
    method: string,
    body?: any,
    headers?: Record<string, string>
  ): Promise<void> {
    const request: QueuedRequest = {
      id: `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      url,
      method,
      body,
      headers,
      timestamp: Date.now(),
      retryCount: 0,
    };

    const queue = await this.getQueue();
    queue.push(request);
    await this.saveQueue(queue);
  }

  private static async getQueue(): Promise<QueuedRequest[]> {
    const queueJson = await AsyncStorage.getItem(this.QUEUE_KEY);
    return queueJson ? JSON.parse(queueJson) : [];
  }

  private static async saveQueue(queue: QueuedRequest[]): Promise<void> {
    await AsyncStorage.setItem(this.QUEUE_KEY, JSON.stringify(queue));
  }

  static async processQueue(): Promise<void> {
    if (!this.isOnline) return;

    const queue = await this.getQueue();
    const failedRequests: QueuedRequest[] = [];

    for (const request of queue) {
      try {
        await fetch(request.url, {
          method: request.method,
          headers: request.headers,
          body: request.body ? JSON.stringify(request.body) : undefined,
        });
      } catch (error) {
        console.error('Failed to process queued request:', error);
        
        request.retryCount++;
        if (request.retryCount < 3) {
          failedRequests.push(request);
        }
      }
    }

    await this.saveQueue(failedRequests);
  }

  // Data Caching
  static async cacheData(key: string, data: any, ttl: number = 3600000): Promise<void> {
    const cached: CachedData = {
      data,
      timestamp: Date.now(),
      expiresAt: Date.now() + ttl,
    };

    await AsyncStorage.setItem(
      this.CACHE_KEY_PREFIX + key,
      JSON.stringify(cached)
    );
  }

  static async getCachedData(key: string): Promise<any | null> {
    const cachedJson = await AsyncStorage.getItem(this.CACHE_KEY_PREFIX + key);
    
    if (!cachedJson) return null;

    const cached: CachedData = JSON.parse(cachedJson);
    
    // Check if expired
    if (Date.now() > cached.expiresAt) {
      await this.clearCache(key);
      return null;
    }

    return cached.data;
  }

  static async clearCache(key: string): Promise<void> {
    await AsyncStorage.removeItem(this.CACHE_KEY_PREFIX + key);
  }

  static async clearAllCache(): Promise<void> {
    const keys = await AsyncStorage.getAllKeys();
    const cacheKeys = keys.filter(k => k.startsWith(this.CACHE_KEY_PREFIX));
    await AsyncStorage.multiRemove(cacheKeys);
  }

  // Offline-First Data Access
  static async fetchWithCache(
    url: string,
    options?: RequestInit,
    cacheKey?: string,
    ttl?: number
  ): Promise<any> {
    const key = cacheKey || url;

    // Try cache first
    const cached = await this.getCachedData(key);
    if (cached) {
      return cached;
    }

    // If offline, return null
    if (!this.isOnline) {
      return null;
    }

    // Fetch from network
    try {
      const response = await fetch(url, options);
      const data = await response.json();
      
      // Cache the response
      await this.cacheData(key, data, ttl);
      
      return data;
    } catch (error) {
      console.error('Fetch failed:', error);
      return null;
    }
  }

  // Sync Status
  static async getSyncStatus(): Promise<{
    queuedRequests: number;
    cachedItems: number;
    lastSync: number | null;
  }> {
    const queue = await this.getQueue();
    const keys = await AsyncStorage.getAllKeys();
    const cacheKeys = keys.filter(k => k.startsWith(this.CACHE_KEY_PREFIX));
    const lastSyncStr = await AsyncStorage.getItem('last_sync');
    
    return {
      queuedRequests: queue.length,
      cachedItems: cacheKeys.length,
      lastSync: lastSyncStr ? parseInt(lastSyncStr) : null,
    };
  }

  static async markSynced(): Promise<void> {
    await AsyncStorage.setItem('last_sync', Date.now().toString());
  }
}
