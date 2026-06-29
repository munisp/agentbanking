import locationService from '../../src/services/locationService';

let mockStore = {};

const mockLocation = {
  requestForegroundPermissionsAsync: jest.fn(),
  requestBackgroundPermissionsAsync: jest.fn(),
  getForegroundPermissionsAsync: jest.fn(),
  getCurrentPositionAsync: jest.fn(),
  watchPositionAsync: jest.fn(),
  startLocationUpdatesAsync: jest.fn(),
  stopLocationUpdatesAsync: jest.fn(),
  hasServicesEnabledAsync: jest.fn(),
  Accuracy: { Balanced: 3 },
};

jest.mock('expo-location', () => mockLocation);
jest.mock('expo-task-manager', () => ({
  defineTask: jest.fn(),
  isTaskDefined: jest.fn().mockResolvedValue(false),
}));

jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn((key) => Promise.resolve(mockStore[key] ?? null)),
  setItemAsync: jest.fn((key, val) => { mockStore[key] = val; return Promise.resolve(); }),
}));

global.fetch = jest.fn();

// Mock lazy require of realtimeService
jest.mock('../../src/services/realtimeService', () => ({
  default: { isConnected: jest.fn().mockReturnValue(false), sendMessage: jest.fn() },
}), { virtual: true });

describe('locationService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockStore = {};
    locationService.isTracking = false;
    locationService.watchSubscription = null;
    (global.fetch as jest.Mock).mockResolvedValue({ ok: true, json: () => Promise.resolve({}) });
  });

  describe('requestPermissions', () => {
    it('returns granted true for both when both permissions are granted', async () => {
      mockLocation.requestForegroundPermissionsAsync.mockResolvedValue({ status: 'granted' });
      mockLocation.requestBackgroundPermissionsAsync.mockResolvedValue({ status: 'granted' });

      const result = await locationService.requestPermissions();

      expect(result).toEqual({ foreground: true, background: true });
    });

    it('throws when foreground permission is denied', async () => {
      mockLocation.requestForegroundPermissionsAsync.mockResolvedValue({ status: 'denied' });

      await expect(locationService.requestPermissions()).rejects.toThrow('Foreground location permission denied');
    });

    it('does not throw when only background permission is denied', async () => {
      mockLocation.requestForegroundPermissionsAsync.mockResolvedValue({ status: 'granted' });
      mockLocation.requestBackgroundPermissionsAsync.mockResolvedValue({ status: 'denied' });

      const result = await locationService.requestPermissions();

      expect(result.foreground).toBe(true);
      expect(result.background).toBe(false);
    });
  });

  describe('isLocationEnabled', () => {
    it('returns true when location services are enabled', async () => {
      mockLocation.hasServicesEnabledAsync.mockResolvedValue(true);

      const result = await locationService.isLocationEnabled();

      expect(result).toBe(true);
    });

    it('returns false when location services are disabled', async () => {
      mockLocation.hasServicesEnabledAsync.mockResolvedValue(false);

      const result = await locationService.isLocationEnabled();

      expect(result).toBe(false);
    });
  });

  describe('getCurrentLocation', () => {
    it('returns location data with coords', async () => {
      mockLocation.getForegroundPermissionsAsync.mockResolvedValue({ status: 'granted' });
      mockLocation.getCurrentPositionAsync.mockResolvedValue({
        coords: { latitude: 6.5244, longitude: 3.3792, accuracy: 10, speed: 0 },
        timestamp: 1700000000000,
      });

      const result = await locationService.getCurrentLocation();

      expect(result).toMatchObject({ latitude: 6.5244, longitude: 3.3792, accuracy: 10, speed: 0 });
      expect(result.timestamp).toBeInstanceOf(Date);
    });

    it('returns null when foreground permission is not granted', async () => {
      mockLocation.getForegroundPermissionsAsync.mockResolvedValue({ status: 'denied' });

      const result = await locationService.getCurrentLocation();

      expect(result).toBeNull();
    });

    it('returns null on permission error', async () => {
      mockLocation.getForegroundPermissionsAsync.mockResolvedValue({ status: 'granted' });
      mockLocation.getCurrentPositionAsync.mockRejectedValue(new Error('not authorized'));

      const result = await locationService.getCurrentLocation();

      expect(result).toBeNull();
    });
  });

  describe('startTracking', () => {
    it('starts foreground tracking after getting permission', async () => {
      mockLocation.requestForegroundPermissionsAsync.mockResolvedValue({ status: 'granted' });
      mockLocation.requestBackgroundPermissionsAsync.mockResolvedValue({ status: 'denied' });
      mockLocation.watchPositionAsync.mockResolvedValue({ remove: jest.fn() });

      await locationService.startTracking({});

      expect(mockLocation.watchPositionAsync).toHaveBeenCalled();
      expect(locationService.isTracking).toBe(true);
    });

    it('does not start if already tracking', async () => {
      locationService.isTracking = true;

      await locationService.startTracking({});

      expect(mockLocation.requestForegroundPermissionsAsync).not.toHaveBeenCalled();
    });

    it('starts background updates when background permission is granted', async () => {
      mockLocation.requestForegroundPermissionsAsync.mockResolvedValue({ status: 'granted' });
      mockLocation.requestBackgroundPermissionsAsync.mockResolvedValue({ status: 'granted' });
      mockLocation.watchPositionAsync.mockResolvedValue({ remove: jest.fn() });
      mockLocation.startLocationUpdatesAsync.mockResolvedValue(undefined);

      await locationService.startTracking({});

      expect(mockLocation.startLocationUpdatesAsync).toHaveBeenCalled();
    });

    it('throws when foreground permission is not granted', async () => {
      mockLocation.requestForegroundPermissionsAsync.mockResolvedValue({ status: 'denied' });

      await expect(locationService.startTracking({})).rejects.toThrow('Location permission required');
    });
  });

  describe('stopTracking', () => {
    it('removes watch subscription and sets isTracking to false', async () => {
      const mockRemove = jest.fn();
      locationService.watchSubscription = { remove: mockRemove };
      locationService.isTracking = true;

      await locationService.stopTracking();

      expect(mockRemove).toHaveBeenCalled();
      expect(locationService.isTracking).toBe(false);
    });

    it('does not throw when no subscription exists', async () => {
      locationService.watchSubscription = null;

      await expect(locationService.stopTracking()).resolves.toBeUndefined();
    });
  });

  describe('calculateDistance', () => {
    it('returns 0 for same coordinates', () => {
      const dist = locationService.calculateDistance(6.5244, 3.3792, 6.5244, 3.3792);
      expect(dist).toBe(0);
    });

    it('calculates approximate distance between two points', () => {
      // Lagos to Abuja ~485km
      const dist = locationService.calculateDistance(6.5244, 3.3792, 9.0765, 7.3986);
      expect(dist).toBeGreaterThan(400);
      expect(dist).toBeLessThan(600);
    });

    it('returns a positive value for different coordinates', () => {
      const dist = locationService.calculateDistance(0, 0, 1, 1);
      expect(dist).toBeGreaterThan(0);
    });
  });

  describe('getDeviceId', () => {
    it('returns existing device id from SecureStore', async () => {
      mockStore['deviceId'] = 'existing-device-id';

      const id = await locationService.getDeviceId();

      expect(id).toBe('existing-device-id');
    });

    it('generates and stores new device id when none exists', async () => {
      const id = await locationService.getDeviceId();

      expect(id).toMatch(/^POS-/);
      expect(mockStore['deviceId']).toBe(id);
    });
  });
});
