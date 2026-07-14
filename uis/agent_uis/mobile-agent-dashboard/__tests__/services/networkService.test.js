import {
  addNetworkListener,
  startNetworkMonitor,
  stopNetworkMonitor,
  isDeviceOnline,
  getCachedNetworkState,
} from '../../src/services/networkService';

global.fetch = jest.fn();

describe('networkService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    stopNetworkMonitor();
  });

  afterEach(() => {
    stopNetworkMonitor();
    jest.useRealTimers();
  });

  describe('getCachedNetworkState', () => {
    it('returns an object with isOnline property', () => {
      const state = getCachedNetworkState();
      expect(state).toHaveProperty('isOnline');
      expect(typeof state.isOnline).toBe('boolean');
    });
  });

  describe('isDeviceOnline', () => {
    it('returns true when ping succeeds', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({ ok: true });

      const result = await isDeviceOnline();

      expect(result).toBe(true);
    });

    it('returns false when ping fails (network error)', async () => {
      (global.fetch as jest.Mock).mockRejectedValue(new Error('Network error'));

      const result = await isDeviceOnline();

      expect(result).toBe(false);
    });

    it('returns false when fetch is aborted (timeout)', async () => {
      (global.fetch as jest.Mock).mockRejectedValue(new DOMException('AbortError', 'AbortError'));

      const result = await isDeviceOnline();

      expect(result).toBe(false);
    });

    it('pings the correct URL', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({ ok: true });

      await isDeviceOnline();

      expect(global.fetch).toHaveBeenCalledWith(
        'https://54agent.upi.dev',
        expect.objectContaining({ method: 'HEAD', cache: 'no-store' })
      );
    });
  });

  describe('addNetworkListener', () => {
    it('returns an unsubscribe function', () => {
      const listener = jest.fn();
      const unsubscribe = addNetworkListener(listener);

      expect(typeof unsubscribe).toBe('function');
      unsubscribe();
    });

    it('calls listener when online status changes', async () => {
      const listener = jest.fn();
      addNetworkListener(listener);

      // Simulate going offline then online
      (global.fetch as jest.Mock).mockResolvedValueOnce({ ok: true }); // initial online
      await isDeviceOnline();

      (global.fetch as jest.Mock).mockRejectedValueOnce(new Error('down')); // now offline
      await isDeviceOnline();

      expect(listener).toHaveBeenCalledWith(
        expect.objectContaining({ isOnline: false, wasOnline: true })
      );
    });

    it('unsubscribed listener is not called', async () => {
      const listener = jest.fn();
      const unsubscribe = addNetworkListener(listener);
      unsubscribe();

      (global.fetch as jest.Mock).mockRejectedValue(new Error('offline'));
      await isDeviceOnline();

      expect(listener).not.toHaveBeenCalled();
    });
  });

  describe('startNetworkMonitor', () => {
    it('starts polling without error', () => {
      (global.fetch as jest.Mock).mockResolvedValue({ ok: true });

      expect(() => startNetworkMonitor()).not.toThrow();
    });

    it('does not start a second timer if already started', () => {
      (global.fetch as jest.Mock).mockResolvedValue({ ok: true });

      startNetworkMonitor();
      startNetworkMonitor(); // second call should be no-op

      // Both calls should not double-register; just verify no error
      stopNetworkMonitor();
    });
  });

  describe('stopNetworkMonitor', () => {
    it('stops the polling timer', () => {
      (global.fetch as jest.Mock).mockResolvedValue({ ok: true });

      startNetworkMonitor();
      stopNetworkMonitor();

      // Advancing time should not trigger additional fetch calls after stop
      const callsBefore = (global.fetch as jest.Mock).mock.calls.length;
      jest.advanceTimersByTime(60000);
      const callsAfter = (global.fetch as jest.Mock).mock.calls.length;

      expect(callsAfter).toBe(callsBefore);
    });

    it('can be called when monitor is not running without error', () => {
      expect(() => stopNetworkMonitor()).not.toThrow();
    });
  });
});
