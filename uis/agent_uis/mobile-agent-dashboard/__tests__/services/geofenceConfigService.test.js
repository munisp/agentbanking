import geofenceConfigService from '../../src/services/geofenceConfigService';

let mockStore = {};

jest.mock('expo-secure-store', () => ({
  setItemAsync: jest.fn((key, value) => { mockStore[key] = value; return Promise.resolve(); }),
  getItemAsync: jest.fn((key) => Promise.resolve(mockStore[key] ?? null)),
  deleteItemAsync: jest.fn((key) => { delete mockStore[key]; return Promise.resolve(); }),
}));

describe('geofenceConfigService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockStore = {};
  });

  describe('configureGeofence', () => {
    it('stores all three geofence parameters in SecureStore', async () => {
      const result = await geofenceConfigService.configureGeofence(6.5244, 3.3792, 10);

      expect(mockStore['geofence_center_lat']).toBe('6.5244');
      expect(mockStore['geofence_center_lon']).toBe('3.3792');
      expect(mockStore['geofence_radius_km']).toBe('10');
      expect(result).toBe(true);
    });

    it('handles decimal radius values', async () => {
      await geofenceConfigService.configureGeofence(6.0, 3.0, 2.5);

      expect(mockStore['geofence_radius_km']).toBe('2.5');
    });

    it('propagates SecureStore errors', async () => {
      const { setItemAsync } = require('expo-secure-store');
      setItemAsync.mockRejectedValueOnce(new Error('Storage full'));

      await expect(geofenceConfigService.configureGeofence(6.0, 3.0, 5)).rejects.toThrow('Storage full');
    });
  });

  describe('getGeofenceConfig', () => {
    it('returns parsed geofence config when all values are stored', async () => {
      mockStore['geofence_center_lat'] = '6.5244';
      mockStore['geofence_center_lon'] = '3.3792';
      mockStore['geofence_radius_km'] = '10';

      const result = await geofenceConfigService.getGeofenceConfig();

      expect(result).toEqual({ centerLat: 6.5244, centerLon: 3.3792, radiusKm: 10 });
    });

    it('returns null when any value is missing', async () => {
      mockStore['geofence_center_lat'] = '6.5244';
      // lon and radius missing

      const result = await geofenceConfigService.getGeofenceConfig();

      expect(result).toBeNull();
    });

    it('returns null when nothing is stored', async () => {
      const result = await geofenceConfigService.getGeofenceConfig();

      expect(result).toBeNull();
    });

    it('returns null on SecureStore error', async () => {
      const { getItemAsync } = require('expo-secure-store');
      getItemAsync.mockRejectedValueOnce(new Error('Keychain error'));

      const result = await geofenceConfigService.getGeofenceConfig();

      expect(result).toBeNull();
    });
  });

  describe('clearGeofence', () => {
    it('removes all three geofence keys', async () => {
      mockStore['geofence_center_lat'] = '6.5244';
      mockStore['geofence_center_lon'] = '3.3792';
      mockStore['geofence_radius_km'] = '10';

      const result = await geofenceConfigService.clearGeofence();

      expect(mockStore['geofence_center_lat']).toBeUndefined();
      expect(mockStore['geofence_center_lon']).toBeUndefined();
      expect(mockStore['geofence_radius_km']).toBeUndefined();
      expect(result).toBe(true);
    });

    it('propagates errors on clear failure', async () => {
      const { deleteItemAsync } = require('expo-secure-store');
      deleteItemAsync.mockRejectedValueOnce(new Error('Delete failed'));

      await expect(geofenceConfigService.clearGeofence()).rejects.toThrow('Delete failed');
    });
  });

  describe('setGeofenceFromLocation', () => {
    it('configures geofence with provided coords and default radius of 5km', async () => {
      const result = await geofenceConfigService.setGeofenceFromLocation(6.5244, 3.3792);

      expect(mockStore['geofence_radius_km']).toBe('5');
      expect(result).toBe(true);
    });

    it('uses custom radius when provided', async () => {
      await geofenceConfigService.setGeofenceFromLocation(6.5244, 3.3792, 15);

      expect(mockStore['geofence_radius_km']).toBe('15');
    });
  });

  describe('setupTestGeofence', () => {
    it('sets up Lagos, Nigeria geofence with 10km radius', async () => {
      await geofenceConfigService.setupTestGeofence();

      expect(parseFloat(mockStore['geofence_center_lat'])).toBeCloseTo(6.5244, 3);
      expect(parseFloat(mockStore['geofence_center_lon'])).toBeCloseTo(3.3792, 3);
      expect(mockStore['geofence_radius_km']).toBe('10');
    });
  });
});
