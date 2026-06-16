import { OfflineService } from '../src/services/OfflineService';

describe('OfflineService', () => {
  beforeAll(async () => {
    await OfflineService.initialize();
  });

  describe('Cache Management', () => {
    it('should cache data', async () => {
      const data = { test: 'value' };
      await OfflineService.cacheData('test_key', data);
      const cached = await OfflineService.getCachedData('test_key');
      expect(cached).toEqual(data);
    });

    it('should return null for expired cache', async () => {
      const data = { test: 'value' };
      await OfflineService.cacheData('test_key', data, 1); // 1ms TTL
      await new Promise(resolve => setTimeout(resolve, 10));
      const cached = await OfflineService.getCachedData('test_key');
      expect(cached).toBeNull();
    });

    it('should clear specific cache', async () => {
      await OfflineService.cacheData('test_key', { test: 'value' });
      await OfflineService.clearCache('test_key');
      const cached = await OfflineService.getCachedData('test_key');
      expect(cached).toBeNull();
    });
  });

  describe('Request Queue', () => {
    it('should queue requests', async () => {
      await OfflineService.queueRequest('https://api.test.com', 'POST', { data: 'test' });
      const status = await OfflineService.getSyncStatus();
      expect(status.queuedRequests).toBeGreaterThan(0);
    });
  });

  describe('Online Status', () => {
    it('should return online status', () => {
      const isOnline = OfflineService.getOnlineStatus();
      expect(typeof isOnline).toBe('boolean');
    });
  });
});
