import { biometricService } from '../../src/services/BiometricService';

const mockIsSensorAvailable = jest.fn();
const mockSimplePrompt = jest.fn();
const mockCreateKeys = jest.fn();

jest.mock('react-native-biometrics', () => ({
  default: jest.fn().mockImplementation(() => ({
    isSensorAvailable: mockIsSensorAvailable,
    simplePrompt: mockSimplePrompt,
    createKeys: mockCreateKeys,
  })),
  BiometryTypes: {
    FaceID: 'FaceID',
    TouchID: 'TouchID',
    Biometrics: 'Biometrics',
  },
}));

describe('BiometricService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('checkAvailability', () => {
    it('reports Face ID availability', async () => {
      mockIsSensorAvailable.mockResolvedValue({ available: true, biometryType: 'FaceID' });

      const result = await biometricService.checkAvailability();

      expect(result).toEqual({ available: true, type: 'Face ID' });
    });

    it('reports Touch ID availability', async () => {
      mockIsSensorAvailable.mockResolvedValue({ available: true, biometryType: 'TouchID' });

      const result = await biometricService.checkAvailability();

      expect(result).toEqual({ available: true, type: 'Touch ID' });
    });

    it('reports generic Biometrics availability', async () => {
      mockIsSensorAvailable.mockResolvedValue({ available: true, biometryType: 'Biometrics' });

      const result = await biometricService.checkAvailability();

      expect(result).toEqual({ available: true, type: 'Biometrics' });
    });

    it('reports None when biometry type is unknown', async () => {
      mockIsSensorAvailable.mockResolvedValue({ available: false, biometryType: null });

      const result = await biometricService.checkAvailability();

      expect(result).toEqual({ available: false, type: 'None' });
    });
  });

  describe('authenticate', () => {
    it('returns true on successful prompt', async () => {
      mockSimplePrompt.mockResolvedValue({ success: true });

      const result = await biometricService.authenticate('Verify your identity');

      expect(mockSimplePrompt).toHaveBeenCalledWith({
        promptMessage: 'Verify your identity',
        cancelButtonText: 'Cancel',
      });
      expect(result).toBe(true);
    });

    it('returns false when user cancels', async () => {
      mockSimplePrompt.mockResolvedValue({ success: false });

      const result = await biometricService.authenticate('Verify');

      expect(result).toBe(false);
    });

    it('returns false and swallows errors', async () => {
      mockSimplePrompt.mockRejectedValue(new Error('HW error'));

      const result = await biometricService.authenticate('Verify');

      expect(result).toBe(false);
    });
  });

  describe('createKeys', () => {
    it('returns true when public key is created', async () => {
      mockCreateKeys.mockResolvedValue({ publicKey: 'pk_abc123' });

      const result = await biometricService.createKeys();

      expect(result).toBe(true);
    });

    it('returns false when no public key returned', async () => {
      mockCreateKeys.mockResolvedValue({ publicKey: null });

      const result = await biometricService.createKeys();

      expect(result).toBe(false);
    });

    it('returns false and swallows key creation errors', async () => {
      mockCreateKeys.mockRejectedValue(new Error('Key creation failed'));

      const result = await biometricService.createKeys();

      expect(result).toBe(false);
    });
  });
});
