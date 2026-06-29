import { OfflineService } from '../../src/services/OfflineService';

const mockStorage: Record<string, string> = {};

const mockAsyncStorage = {
  getItem: jest.fn((key: string) => Promise.resolve(mockStorage[key] ?? null)),
  setItem: jest.fn((key: string, value: string) => {
    mockStorage[key] = value;
    return Promise.resolve();
  }),
  removeItem: jest.fn((key: string) => {
    delete mockStorage[key];
    return Promise.resolve();
  }),
  getAllKeys: jest.fn(() => Promise.resolve(Object.keys(mockStorage))),
  multiRemove: jest.fn((keys: string[]) => {
    keys.forEach(k => delete mockStorage[k]);
    return Promise.resolve();
  }),
};

let netInfoCallback: ((state: any) => void) | null = null;
const mockNetInfo = {
  addEventListener: jest.fn((cb: (state: any) => void) => {
    netInfoCallback = cb;
    return jest.fn();
  }),
};

global.fetch = jest.fn();

jest.mock('@react-native-async-storage/async-storage', () => ({ default: mockAsyncStorage }));
jest.mock('@react-native-community/netinfo', () => ({ default: mockNetInfo }));

describe('OfflineService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    Object.keys(mockStorage).forEach(k => delete mockStorage[k]);
    netInfoCallback = null;
    (global.fetch as jest.Mock).mockReset();
  });

  describe('getOnlineStatus', () => {
    it('returns true by default', () => {
      expect(OfflineService.getOnlineStatus()).toBe(true);
    });
  });

  describe('addOnlineStatusListener', () => {
    it('adds a listener and returns an unsubscribe function', () => {
      const listener = jest.fn();
      const unsubscribe = OfflineService.addOnlineStatusListener(listener);

      expect(typeof unsubscribe).toBe('function');
      unsubscribe();
    });

    it('notifies listener when network status changes via initialize', async () => {
      const listener = jest.fn();
      OfflineService.addOnlineStatusListener(listener);
      (global.fetch as jest.Mock).mockResolvedValue({});

      await OfflineService.initialize();

      if (netInfoCallback) {
        netInfoCallback({ isConnected: false });
      }

      expect(listener).toHaveBeenCalled();
    });
  });

  describe('queueRequest', () => {
    it('adds a request to the offline queue', async () => {
      await OfflineService.queueRequest('https://api.example.com/data', 'POST', { amount: 100 });

      expect(mockAsyncStorage.setItem).toHaveBeenCalledWith(
        'offline_queue',
        expect.stringContaining('https://api.example.com/data')
      );
    });

    it('queues multiple requests', async () => {
      await OfflineService.queueRequest('https://api.example.com/a', 'GET');
      await OfflineService.queueRequest('https://api.example.com/b', 'POST', { x: 1 });

      const storedQueue = JSON.parse(mockStorage['offline_queue'] || '[]');
      expect(storedQueue).toHaveLength(2);
    });

    it('assigns unique ids to queued requests', async () => {
      await OfflineService.queueRequest('https://api.example.com/a', 'POST');
      await OfflineService.queueRequest('https://api.example.com/b', 'POST');

      const queue = JSON.parse(mockStorage['offline_queue']);
      expect(queue[0].id).not.toBe(queue[1].id);
    });
  });

  describe('cacheData', () => {
    it('stores data with expiry timestamp', async () => {
      await OfflineService.cacheData('my-key', { value: 42 }, 60000);

      const raw = mockStorage['cache_my-key'];
      expect(raw).toBeDefined();
      const parsed = JSON.parse(raw);
      expect(parsed.data).toEqual({ value: 42 });
      expect(parsed.expiresAt).toBeGreaterThan(Date.now());
    });
  });

  describe('getCachedData', () => {
    it('returns cached data when not expired', async () => {
      const cached = { data: { foo: 'bar' }, timestamp: Date.now(), expiresAt: Date.now() + 99999 };
      mockStorage['cache_test-key'] = JSON.stringify(cached);

      const result = await OfflineService.getCachedData('test-key');

      expect(result).toEqual({ foo: 'bar' });
    });

    it('returns null when cache entry is expired', async () => {
      const expired = { data: { foo: 'bar' }, timestamp: Date.now() - 10000, expiresAt: Date.now() - 1 };
      mockStorage['cache_test-key'] = JSON.stringify(expired);

      const result = await OfflineService.getCachedData('test-key');

      expect(result).toBeNull();
    });

    it('returns null when no cache entry exists', async () => {
      const result = await OfflineService.getCachedData('nonexistent-key');

      expect(result).toBeNull();
    });
  });

  describe('clearCache', () => {
    it('removes a specific cache entry', async () => {
      mockStorage['cache_my-key'] = JSON.stringify({ data: 'x', timestamp: 0, expiresAt: 999 });

      await OfflineService.clearCache('my-key');

      expect(mockAsyncStorage.removeItem).toHaveBeenCalledWith('cache_my-key');
    });
  });

  describe('clearAllCache', () => {
    it('removes all cache_ prefixed keys', async () => {
      mockStorage['cache_a'] = '{}';
      mockStorage['cache_b'] = '{}';
      mockStorage['offline_queue'] = '[]';

      await OfflineService.clearAllCache();

      expect(mockAsyncStorage.multiRemove).toHaveBeenCalledWith(
        expect.arrayContaining(['cache_a', 'cache_b'])
      );
    });
  });

  describe('getSyncStatus', () => {
    it('returns zero queued requests and cached items when storage is empty', async () => {
      mockStorage['offline_queue'] = JSON.stringify([]);

      const status = await OfflineService.getSyncStatus();

      expect(status.queuedRequests).toBe(0);
      expect(status.lastSync).toBeNull();
    });

    it('returns correct counts from storage', async () => {
      mockStorage['offline_queue'] = JSON.stringify([{ id: '1' }, { id: '2' }]);
      mockStorage['cache_x'] = '{}';
      mockStorage['last_sync'] = '1700000000000';

      const status = await OfflineService.getSyncStatus();

      expect(status.queuedRequests).toBe(2);
      expect(status.cachedItems).toBe(1);
      expect(status.lastSync).toBe(1700000000000);
    });
  });

  describe('markSynced', () => {
    it('stores current timestamp as last_sync', async () => {
      const before = Date.now();
      await OfflineService.markSynced();
      const after = Date.now();

      const stored = parseInt(mockStorage['last_sync']);
      expect(stored).toBeGreaterThanOrEqual(before);
      expect(stored).toBeLessThanOrEqual(after);
    });
  });
});
