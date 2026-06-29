import notificationService from '../../src/services/notificationService';

jest.mock('expo-av', () => ({
  Audio: {
    Sound: {
      createAsync: jest.fn().mockResolvedValue({
        sound: {
          playAsync: jest.fn().mockResolvedValue(undefined),
          unloadAsync: jest.fn().mockResolvedValue(undefined),
          setOnPlaybackStatusUpdate: jest.fn(),
        },
      }),
    },
  },
}));

jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn().mockResolvedValue(null),
}));

jest.mock('../../src/services/apiService', () => ({
  accountApi: {},
  authHeaders: jest.fn().mockResolvedValue({}),
  networkOperationsApi: {},
}));

class MockWebSocket {
  static OPEN = 1;
  readyState = 1;
  onopen = null;
  onmessage = null;
  onerror = null;
  onclose = null;
  send = jest.fn();
  close = jest.fn();

  constructor(url) {
    this.url = url;
    MockWebSocket.instance = this;
  }
}
MockWebSocket.instance = null;
global.WebSocket = MockWebSocket;

describe('notificationService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    notificationService.ws = null;
    notificationService.isConnected = false;
    notificationService.shouldConnect = false;
    notificationService.agentId = null;
    notificationService.retryCount = 0;
    notificationService.permanentlyDisabled = false;
    notificationService.listeners = [];
    notificationService.processedMessages = new Set();
    MockWebSocket.instance = null;
  });

  afterEach(() => {
    notificationService.disconnect();
    jest.useRealTimers();
  });

  describe('connect', () => {
    it('does nothing when agentId is not provided', async () => {
      await notificationService.connect(null);
      expect(MockWebSocket.instance).toBeNull();
    });

    it('creates a WebSocket connection with agent id in URL', async () => {
      await notificationService.connect('agent-123');

      expect(MockWebSocket.instance).not.toBeNull();
      expect(MockWebSocket.instance.url).toContain('agent-123');
    });

    it('does not reconnect when already connected with same agent', async () => {
      notificationService.isConnected = true;
      notificationService.agentId = 'agent-123';

      await notificationService.connect('agent-123');

      expect(MockWebSocket.instance).toBeNull();
    });

    it('sets isConnected on WebSocket open event', async () => {
      await notificationService.connect('agent-xyz');

      MockWebSocket.instance.onopen();

      expect(notificationService.isConnected).toBe(true);
      expect(notificationService.retryCount).toBe(0);
    });

    it('sets isConnected to false on WebSocket close', async () => {
      await notificationService.connect('agent-xyz');
      MockWebSocket.instance.onopen();

      notificationService.shouldConnect = false;
      MockWebSocket.instance.onclose({ code: 1000 });

      expect(notificationService.isConnected).toBe(false);
    });

    it('does not connect when permanently disabled', async () => {
      notificationService.permanentlyDisabled = true;

      await notificationService.connect('agent-123');

      expect(MockWebSocket.instance).toBeNull();
    });

    it('permanently disables after max retries', async () => {
      await notificationService.connect('agent-123');
      notificationService.retryCount = notificationService.maxRetries;
      notificationService.shouldConnect = true;

      MockWebSocket.instance.onclose({ code: 1000 });

      expect(notificationService.shouldConnect).toBe(false);
      expect(notificationService.permanentlyDisabled).toBe(true);
    });
  });

  describe('addListener', () => {
    it('adds a listener and returns unsubscribe function', async () => {
      const listener = jest.fn();
      const unsubscribe = notificationService.addListener(listener);

      expect(notificationService.listeners).toContain(listener);
      expect(typeof unsubscribe).toBe('function');

      unsubscribe();
      expect(notificationService.listeners).not.toContain(listener);
    });
  });

  describe('notifyListeners', () => {
    it('calls all registered listeners with the message', () => {
      const listener1 = jest.fn();
      const listener2 = jest.fn();
      notificationService.addListener(listener1);
      notificationService.addListener(listener2);

      const msg = { type: 'transaction_ping', message_id: 'm1' };
      notificationService.notifyListeners(msg);

      expect(listener1).toHaveBeenCalledWith(msg);
      expect(listener2).toHaveBeenCalledWith(msg);
    });

    it('swallows errors from individual listeners', () => {
      const badListener = jest.fn(() => { throw new Error('Listener error'); });
      notificationService.addListener(badListener);

      expect(() => notificationService.notifyListeners({ type: 'test' })).not.toThrow();
    });
  });

  describe('duplicate message deduplication', () => {
    it('skips processing for duplicate message_id', async () => {
      await notificationService.connect('agent-1');
      MockWebSocket.instance.onopen();

      const listener = jest.fn();
      notificationService.addListener(listener);

      const msg = { type: 'pong', message_id: 'unique-id-1' };
      await MockWebSocket.instance.onmessage({ data: JSON.stringify(msg) });
      await MockWebSocket.instance.onmessage({ data: JSON.stringify(msg) });

      expect(listener).toHaveBeenCalledTimes(1);
    });
  });

  describe('disconnect', () => {
    it('closes websocket and resets state', async () => {
      await notificationService.connect('agent-123');
      notificationService.isConnected = true;

      notificationService.disconnect();

      expect(notificationService.isConnected).toBe(false);
      expect(notificationService.shouldConnect).toBe(false);
      expect(notificationService.ws).toBeNull();
      expect(notificationService.processedMessages.size).toBe(0);
    });
  });

  describe('getConnectionStatus', () => {
    it('returns current connection status and agentId', () => {
      notificationService.isConnected = true;
      notificationService.agentId = 'agent-abc';

      const status = notificationService.getConnectionStatus();

      expect(status).toEqual({ isConnected: true, agentId: 'agent-abc' });
    });
  });

  describe('startPingInterval / stopPingInterval', () => {
    it('sends ping every 30 seconds when connected', async () => {
      await notificationService.connect('agent-1');
      notificationService.isConnected = true;
      notificationService.ws = MockWebSocket.instance;

      notificationService.startPingInterval();
      jest.advanceTimersByTime(30000);

      expect(MockWebSocket.instance.send).toHaveBeenCalledWith(JSON.stringify({ type: 'ping' }));
    });

    it('stops ping interval without error', () => {
      notificationService.startPingInterval();
      expect(() => notificationService.stopPingInterval()).not.toThrow();
    });
  });

  describe('sendLocationUpdate', () => {
    it('sends location when websocket is open and connected', async () => {
      await notificationService.connect('agent-loc');
      notificationService.isConnected = true;
      notificationService.ws = MockWebSocket.instance;
      MockWebSocket.instance.readyState = WebSocket.OPEN;

      await notificationService.sendLocationUpdate({
        latitude: 6.5244,
        longitude: 3.3792,
        accuracy: 10,
        speed: 0,
      });

      expect(MockWebSocket.instance.send).toHaveBeenCalledWith(
        expect.stringContaining('"type":"location_update"')
      );
    });

    it('does nothing when not connected', async () => {
      notificationService.isConnected = false;

      await notificationService.sendLocationUpdate({ latitude: 6.5, longitude: 3.4, accuracy: 5, speed: 0 });

      // No WebSocket created, no send call possible
      expect(MockWebSocket.instance).toBeNull();
    });
  });
});
