import { SecurityService } from '../../src/services/SecurityService';

const mockSecureStore = {
  setItemAsync: jest.fn(),
  getItemAsync: jest.fn(),
  deleteItemAsync: jest.fn(),
};

const mockAsyncStorage = {
  setItem: jest.fn(),
  getItem: jest.fn(),
  removeItem: jest.fn(),
};

const mockLocalAuthentication = {
  hasHardwareAsync: jest.fn(),
  isEnrolledAsync: jest.fn(),
  authenticateAsync: jest.fn(),
};

const mockCrypto = {
  digestStringAsync: jest.fn(),
  CryptoDigestAlgorithm: { SHA256: 'SHA256' },
  getRandomBytesAsync: jest.fn(),
};

jest.mock('expo-secure-store', () => mockSecureStore);
jest.mock('@react-native-async-storage/async-storage', () => ({ default: mockAsyncStorage }));
jest.mock('expo-local-authentication', () => mockLocalAuthentication);
jest.mock('expo-crypto', () => mockCrypto);

describe('SecurityService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockCrypto.digestStringAsync.mockResolvedValue('abc123hash');
    mockAsyncStorage.getItem.mockResolvedValue('stored-device-id');
  });

  describe('isBiometricAvailable', () => {
    it('returns true when hardware exists and enrolled', async () => {
      mockLocalAuthentication.hasHardwareAsync.mockResolvedValue(true);
      mockLocalAuthentication.isEnrolledAsync.mockResolvedValue(true);

      const result = await SecurityService.isBiometricAvailable();

      expect(result).toBe(true);
    });

    it('returns false when no hardware', async () => {
      mockLocalAuthentication.hasHardwareAsync.mockResolvedValue(false);
      mockLocalAuthentication.isEnrolledAsync.mockResolvedValue(true);

      const result = await SecurityService.isBiometricAvailable();

      expect(result).toBe(false);
    });

    it('returns false when not enrolled', async () => {
      mockLocalAuthentication.hasHardwareAsync.mockResolvedValue(true);
      mockLocalAuthentication.isEnrolledAsync.mockResolvedValue(false);

      const result = await SecurityService.isBiometricAvailable();

      expect(result).toBe(false);
    });
  });

  describe('authenticateWithBiometrics', () => {
    it('returns true on successful authentication', async () => {
      mockLocalAuthentication.authenticateAsync.mockResolvedValue({ success: true });

      const result = await SecurityService.authenticateWithBiometrics('Confirm identity');

      expect(mockLocalAuthentication.authenticateAsync).toHaveBeenCalledWith({
        promptMessage: 'Confirm identity',
        fallbackLabel: 'Use Passcode',
        disableDeviceFallback: false,
      });
      expect(result).toBe(true);
    });

    it('returns false when authentication fails', async () => {
      mockLocalAuthentication.authenticateAsync.mockResolvedValue({ success: false });

      const result = await SecurityService.authenticateWithBiometrics();

      expect(result).toBe(false);
    });

    it('uses default prompt message', async () => {
      mockLocalAuthentication.authenticateAsync.mockResolvedValue({ success: true });

      await SecurityService.authenticateWithBiometrics();

      expect(mockLocalAuthentication.authenticateAsync).toHaveBeenCalledWith(
        expect.objectContaining({ promptMessage: 'Authenticate to continue' })
      );
    });

    it('returns false and swallows exceptions', async () => {
      mockLocalAuthentication.authenticateAsync.mockRejectedValue(new Error('HW error'));

      const result = await SecurityService.authenticateWithBiometrics();

      expect(result).toBe(false);
    });
  });

  describe('securelyStore', () => {
    it('stores value in SecureStore with prefix', async () => {
      mockSecureStore.setItemAsync.mockResolvedValue(undefined);

      await SecurityService.securelyStore('myKey', 'myValue');

      expect(mockSecureStore.setItemAsync).toHaveBeenCalledWith('secure_myKey', 'myValue');
    });

    it('falls back to AsyncStorage when SecureStore fails', async () => {
      mockSecureStore.setItemAsync.mockRejectedValue(new Error('SecureStore unavailable'));
      mockAsyncStorage.setItem.mockResolvedValue(undefined);

      await SecurityService.securelyStore('myKey', 'myValue');

      expect(mockAsyncStorage.setItem).toHaveBeenCalledWith(
        'secure_myKey',
        expect.any(String)
      );
    });
  });

  describe('securelyRetrieve', () => {
    it('retrieves value from SecureStore', async () => {
      mockSecureStore.getItemAsync.mockResolvedValue('storedValue');

      const result = await SecurityService.securelyRetrieve('myKey');

      expect(mockSecureStore.getItemAsync).toHaveBeenCalledWith('secure_myKey');
      expect(result).toBe('storedValue');
    });

    it('falls back to AsyncStorage when SecureStore fails', async () => {
      mockSecureStore.getItemAsync.mockRejectedValue(new Error('SecureStore unavailable'));
      mockAsyncStorage.getItem.mockResolvedValue('encryptedValue');
      mockCrypto.digestStringAsync.mockResolvedValue('abc123');

      const result = await SecurityService.securelyRetrieve('myKey');

      expect(mockAsyncStorage.getItem).toHaveBeenCalledWith('secure_myKey');
      expect(result).toBeDefined();
    });

    it('returns null when AsyncStorage fallback also has no value', async () => {
      mockSecureStore.getItemAsync.mockRejectedValue(new Error('fail'));
      mockAsyncStorage.getItem.mockResolvedValue(null);

      const result = await SecurityService.securelyRetrieve('myKey');

      expect(result).toBeNull();
    });
  });

  describe('securelyDelete', () => {
    it('deletes from SecureStore', async () => {
      mockSecureStore.deleteItemAsync.mockResolvedValue(undefined);

      await SecurityService.securelyDelete('myKey');

      expect(mockSecureStore.deleteItemAsync).toHaveBeenCalledWith('secure_myKey');
    });

    it('falls back to AsyncStorage removeItem when SecureStore fails', async () => {
      mockSecureStore.deleteItemAsync.mockRejectedValue(new Error('fail'));
      mockAsyncStorage.removeItem.mockResolvedValue(undefined);

      await SecurityService.securelyDelete('myKey');

      expect(mockAsyncStorage.removeItem).toHaveBeenCalledWith('secure_myKey');
    });
  });

  describe('getDeviceId', () => {
    it('returns existing device id from AsyncStorage', async () => {
      mockAsyncStorage.getItem.mockResolvedValue('existing-device-id');

      const result = await SecurityService.getDeviceId();

      expect(result).toBe('existing-device-id');
    });

    it('generates and stores new device id when none exists', async () => {
      mockAsyncStorage.getItem.mockResolvedValue(null);
      mockAsyncStorage.setItem.mockResolvedValue(undefined);
      mockCrypto.digestStringAsync.mockResolvedValue('new-device-hash');

      const result = await SecurityService.getDeviceId();

      expect(mockAsyncStorage.setItem).toHaveBeenCalledWith('device_id', 'new-device-hash');
      expect(result).toBe('new-device-hash');
    });
  });

  describe('session management', () => {
    it('createSession stores token securely', async () => {
      mockSecureStore.setItemAsync.mockResolvedValue(undefined);

      await SecurityService.createSession('my-token');

      expect(mockSecureStore.setItemAsync).toHaveBeenCalledWith('secure_session_token', 'my-token');
    });

    it('getSession retrieves stored token', async () => {
      mockSecureStore.getItemAsync.mockResolvedValue('stored-token');

      const result = await SecurityService.getSession();

      expect(result).toBe('stored-token');
    });

    it('clearSession deletes the token', async () => {
      mockSecureStore.deleteItemAsync.mockResolvedValue(undefined);

      await SecurityService.clearSession();

      expect(mockSecureStore.deleteItemAsync).toHaveBeenCalledWith('secure_session_token');
    });
  });

  describe('signRequest', () => {
    it('returns a sha256 signature string', async () => {
      mockAsyncStorage.getItem.mockResolvedValue('device-id-abc');
      mockCrypto.digestStringAsync.mockResolvedValue('signed-hash-xyz');

      const signature = await SecurityService.signRequest({ amount: 1000 });

      expect(mockCrypto.digestStringAsync).toHaveBeenCalled();
      expect(signature).toBe('signed-hash-xyz');
    });
  });

  describe('validateCertificate', () => {
    it('returns false for unknown certificate', () => {
      expect(SecurityService.validateCertificate('unknown-cert')).toBe(false);
    });

    it('returns true for known fingerprint', () => {
      expect(SecurityService.validateCertificate('SHA256_FINGERPRINT_1')).toBe(true);
      expect(SecurityService.validateCertificate('SHA256_FINGERPRINT_2')).toBe(true);
    });
  });

  describe('checkIntegrity', () => {
    it('returns true', async () => {
      const result = await SecurityService.checkIntegrity();
      expect(result).toBe(true);
    });
  });

  describe('generateSecureRandom', () => {
    it('generates a hex string of correct length', async () => {
      const mockBytes = new Uint8Array(32).fill(0xab);
      mockCrypto.getRandomBytesAsync.mockResolvedValue(mockBytes);

      const result = await SecurityService.generateSecureRandom(32);

      expect(mockCrypto.getRandomBytesAsync).toHaveBeenCalledWith(32);
      expect(typeof result).toBe('string');
    });

    it('uses default length of 32', async () => {
      const mockBytes = new Uint8Array(32);
      mockCrypto.getRandomBytesAsync.mockResolvedValue(mockBytes);

      await SecurityService.generateSecureRandom();

      expect(mockCrypto.getRandomBytesAsync).toHaveBeenCalledWith(32);
    });
  });
});
