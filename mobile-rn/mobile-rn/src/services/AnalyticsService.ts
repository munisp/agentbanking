// React Native Comprehensive Analytics Service
// Integrates with Lakehouse, Middleware, Postgres, TigerBeetle

export class AnalyticsService {
  private static sessionId: string = this.generateSessionId();
  private static userId: string | null = null;
  private static eventQueue: any[] = [];

  private static readonly LAKEHOUSE_ENDPOINT = 'https://lakehouse.api/events';
  private static readonly MIDDLEWARE_ENDPOINT = 'https://middleware.api/analytics';
  private static readonly POSTGRES_ENDPOINT = 'https://postgres.api/metrics';
  private static readonly TIGERBEETLE_ENDPOINT = 'https://tigerbeetle.api/revenue';

  static initialize(userId?: string) {
    this.userId = userId || null;
    this.sessionId = this.generateSessionId();
    this.trackEvent('session_start', { platform: 'ReactNative' });
    setInterval(() => this.flushEvents(), 30000);
  }

  static trackScreenView(screenName: string) {
    this.trackEvent('screen_view', { screenName });
  }

  static trackButtonClick(buttonId: string, additionalProperties?: any) {
    this.trackEvent('button_click', { buttonId, ...additionalProperties });
  }

  static trackError(errorType: string, error: any) {
    this.trackEvent('error_occurred', {
      errorType,
      errorMessage: error?.message || 'Unknown error',
      errorStack: error?.stack,
    });
  }

  static trackRevenue(amount: number, currency: string, paymentSystem: string) {
    const revenueEvent = {
      eventName: 'revenue_tracked',
      properties: { amount, currency, paymentSystem },
      timestamp: Date.now(),
      userId: this.userId || 'anonymous',
      sessionId: this.sessionId,
    };

    fetch(this.TIGERBEETLE_ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(revenueEvent),
    }).catch(console.error);

    this.trackEvent('revenue', revenueEvent.properties);
  }

  static trackPerformance(metricName: string, value: number, unit: string) {
    this.trackEvent('performance_metric', { metricName, value, unit });
  }

  private static trackEvent(eventName: string, properties: any) {
    const event = {
      eventName,
      properties: { ...properties, platform: 'ReactNative' },
      timestamp: Date.now(),
      userId: this.userId,
      sessionId: this.sessionId,
    };

    this.eventQueue.push(event);

    if (this.eventQueue.length >= 10) {
      this.flushEvents();
    }
  }

  private static async flushEvents() {
    if (this.eventQueue.length === 0) return;

    const eventsToSend = [...this.eventQueue];
    this.eventQueue = [];

    try {
      await Promise.all([
        fetch(this.LAKEHOUSE_ENDPOINT, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ events: eventsToSend }),
        }),
        fetch(this.MIDDLEWARE_ENDPOINT, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ events: eventsToSend }),
        }),
        fetch(this.POSTGRES_ENDPOINT, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ events: eventsToSend }),
        }),
      ]);
    } catch (error) {
      console.error('Failed to flush analytics events:', error);
      this.eventQueue.unshift(...eventsToSend);
    }
  }

  private static generateSessionId(): string {
    return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }
}
