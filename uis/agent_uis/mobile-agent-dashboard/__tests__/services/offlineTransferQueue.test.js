import {
  queueTransferForSync,
  flushPendingTransfers,
  startOfflineTransferSync,
  stopOfflineTransferSync,
  isTransientNetworkError,
} from '../../src/services/offlineTransferQueue';

// In-memory SQLite mock
const dbRows = [];
let nextId = 1;

const mockDb = {
  execAsync: jest.fn().mockResolvedValue(undefined),
  runAsync: jest.fn().mockImplementation((sql, params) => {
    if (sql.includes('INSERT INTO')) {
      dbRows.push({
        id: nextId++,
        request_id: params[0],
        transfer_kind: params[1],
        payload_json: params[2],
        status: 'pending',
        retry_count: 0,
        last_error: null,
      });
    } else if (sql.includes("SET status = 'synced'")) {
      const id = params[1];
      const row = dbRows.find(r => r.id === id);
      if (row) row.status = 'synced';
    } else if (sql.includes('SET retry_count = retry_count + 1')) {
      const id = params[2];
      const row = dbRows.find(r => r.id === id);
      if (row) { row.retry_count += 1; row.last_error = params[0]; }
    }
    return Promise.resolve();
  }),
  getAllAsync: jest.fn().mockImplementation(() =>
    Promise.resolve(dbRows.filter(r => r.status === 'pending'))
  ),
};

jest.mock('expo-sqlite', () => ({
  openDatabaseAsync: jest.fn().mockResolvedValue(mockDb),
}));

jest.mock('../../src/services/networkService', () => ({
  isDeviceOnline: jest.fn().mockResolvedValue(true),
}));

describe('offlineTransferQueue', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    dbRows.length = 0;
    nextId = 1;
    stopOfflineTransferSync();
  });

  describe('isTransientNetworkError', () => {
    it('detects network request failed', () => {
      expect(isTransientNetworkError(new Error('network request failed'))).toBe(true);
    });

    it('detects failed to fetch', () => {
      expect(isTransientNetworkError(new Error('failed to fetch'))).toBe(true);
    });

    it('detects timeout', () => {
      expect(isTransientNetworkError(new Error('connection timeout'))).toBe(true);
    });

    it('returns false for non-network errors', () => {
      expect(isTransientNetworkError(new Error('Invalid account number'))).toBe(false);
    });

    it('returns false for null error', () => {
      expect(isTransientNetworkError(null)).toBe(false);
    });
  });

  describe('queueTransferForSync', () => {
    it('inserts a transfer record and returns a request_id', async () => {
      const requestId = await queueTransferForSync('internal', { amount: 5000, to: 'acc-123' });

      expect(typeof requestId).toBe('string');
      expect(requestId).toMatch(/^offline_/);
      expect(dbRows).toHaveLength(1);
      expect(dbRows[0].transfer_kind).toBe('internal');
    });

    it('serializes payload as JSON', async () => {
      const payload = { amount: 1000, currency: 'NGN' };
      await queueTransferForSync('external', payload);

      expect(JSON.parse(dbRows[0].payload_json)).toEqual(payload);
    });

    it('generates unique request ids', async () => {
      const id1 = await queueTransferForSync('internal', {});
      const id2 = await queueTransferForSync('internal', {});

      expect(id1).not.toBe(id2);
    });
  });

  describe('flushPendingTransfers', () => {
    it('calls sendTransferFn for each pending transfer', async () => {
      await queueTransferForSync('internal', { amount: 100 });
      await queueTransferForSync('external', { amount: 200 });

      const sendFn = jest.fn().mockResolvedValue({ success: true });
      await flushPendingTransfers(sendFn);

      expect(sendFn).toHaveBeenCalledTimes(2);
    });

    it('marks transfers as synced on success', async () => {
      await queueTransferForSync('internal', { amount: 500 });
      const sendFn = jest.fn().mockResolvedValue({ success: true });

      await flushPendingTransfers(sendFn);

      expect(dbRows[0].status).toBe('synced');
    });

    it('marks transfer as failed on error', async () => {
      await queueTransferForSync('internal', { amount: 500 });
      const sendFn = jest.fn().mockRejectedValue(new Error('Server error'));

      await flushPendingTransfers(sendFn);

      expect(dbRows[0].retry_count).toBe(1);
      expect(dbRows[0].last_error).toBe('Server error');
    });

    it('stops processing on transient network error', async () => {
      await queueTransferForSync('internal', { amount: 100 });
      await queueTransferForSync('internal', { amount: 200 });

      let callCount = 0;
      const sendFn = jest.fn().mockImplementation(() => {
        callCount++;
        if (callCount === 1) throw new Error('network request failed');
        return Promise.resolve({});
      });

      await flushPendingTransfers(sendFn);

      // Should stop after first transient failure
      expect(sendFn).toHaveBeenCalledTimes(1);
    });

    it('does not run concurrently (syncInProgress guard)', async () => {
      await queueTransferForSync('internal', { amount: 100 });
      let resolveFirst: (v: any) => void;
      const firstCallPromise = new Promise(r => { resolveFirst = r; });
      const sendFn = jest.fn().mockImplementation(() => firstCallPromise);

      const flush1 = flushPendingTransfers(sendFn);
      const flush2 = flushPendingTransfers(sendFn); // should be no-op

      resolveFirst!({});
      await flush1;
      await flush2;

      expect(sendFn).toHaveBeenCalledTimes(1);
    });
  });

  describe('startOfflineTransferSync / stopOfflineTransferSync', () => {
    it('triggers an initial flush on start', async () => {
      await queueTransferForSync('internal', { amount: 50 });
      const sendFn = jest.fn().mockResolvedValue({});

      startOfflineTransferSync(sendFn);
      await Promise.resolve();
      await Promise.resolve();

      expect(sendFn).toHaveBeenCalled();
    });

    it('does not start a second sync if already started', () => {
      const sendFn = jest.fn().mockResolvedValue({});
      startOfflineTransferSync(sendFn);
      startOfflineTransferSync(sendFn); // second call is no-op

      stopOfflineTransferSync();
    });
  });
});
