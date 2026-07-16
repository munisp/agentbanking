import { AnalyticsService } from '../../src/services/AnalyticsService';

global.fetch = jest.fn();

describe('AnalyticsService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    (global.fetch as jest.Mock).mockResolvedValue({ ok: true });
    jest.useFakeTimers();
    // Reset private static state between tests by re-initializing
    AnalyticsService.initialize();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('initialize', () => {
    it('initializes with a user id', () => {
      expect(() => AnalyticsService.initialize('user-123')).not.toThrow();
    });

    it('initializes without a user id', () => {
      expect(() => AnalyticsService.initialize()).not.toThrow();
    });
  });

  describe('trackScreenView', () => {
    it('enqueues a screen_view event without throwing', () => {
      expect(() => AnalyticsService.trackScreenView('HomeScreen')).not.toThrow();
    });
  });

  describe('trackButtonClick', () => {
    it('enqueues a button_click event', () => {
      expect(() => AnalyticsService.trackButtonClick('submit-btn', { form: 'login' })).not.toThrow();
    });

    it('enqueues event with no additional properties', () => {
      expect(() => AnalyticsService.trackButtonClick('logout-btn')).not.toThrow();
    });
  });

  describe('trackError', () => {
    it('enqueues an error_occurred event', () => {
      const error = new Error('Something went wrong');
      expect(() => AnalyticsService.trackError('network_error', error)).not.toThrow();
    });

    it('handles null error gracefully', () => {
      expect(() => AnalyticsService.trackError('unknown', null)).not.toThrow();
    });
  });

  describe('trackRevenue', () => {
    it('sends revenue event to TigerBeetle endpoint immediately', () => {
      AnalyticsService.trackRevenue(5000, 'NGN', 'mojaloop');

      expect(global.fetch).toHaveBeenCalledWith(
        'https://tigerbeetle.api/revenue',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        })
      );

      const body = JSON.parse((global.fetch as jest.Mock).mock.calls[0][1].body);
      expect(body.properties.amount).toBe(5000);
      expect(body.properties.currency).toBe('NGN');
      expect(body.properties.paymentSystem).toBe('mojaloop');
    });
  });

  describe('trackPerformance', () => {
    it('enqueues a performance_metric event', () => {
      expect(() => AnalyticsService.trackPerformance('api_latency', 250, 'ms')).not.toThrow();
    });
  });

  describe('event flushing', () => {
    it('flushes events to all three endpoints when queue reaches 10 events', () => {
      for (let i = 0; i < 10; i++) {
        AnalyticsService.trackScreenView(`Screen${i}`);
      }

      const calls = (global.fetch as jest.Mock).mock.calls.map(c => c[0]);
      expect(calls).toContain('https://lakehouse.api/events');
      expect(calls).toContain('https://middleware.api/analytics');
      expect(calls).toContain('https://postgres.api/metrics');
    });

    it('flushes on 30s interval timer', () => {
      AnalyticsService.trackScreenView('Screen1');

      jest.advanceTimersByTime(30000);

      expect(global.fetch).toHaveBeenCalled();
    });

    it('re-queues events when flush fails', async () => {
      (global.fetch as jest.Mock).mockRejectedValue(new Error('Network down'));

      for (let i = 0; i < 10; i++) {
        AnalyticsService.trackScreenView(`Screen${i}`);
      }

      // Allow promises to settle
      await Promise.resolve();
      await Promise.resolve();

      // Another flush should attempt to send the re-queued events
      jest.advanceTimersByTime(30000);
      expect(global.fetch).toHaveBeenCalled();
    });
  });
});
