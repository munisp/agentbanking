import {
  isNfcSupported,
  initNfc,
  readCardNFC,
  cancelNfcRead,
} from '../../src/services/cardReaderService';

const mockNfcManager = {
  isSupported: jest.fn(),
  start: jest.fn(),
  requestTechnology: jest.fn(),
  cancelTechnologyRequest: jest.fn().mockResolvedValue(undefined),
  isoDepHandler: {
    transceive: jest.fn(),
  },
};

jest.mock('react-native-nfc-manager', () => ({
  default: mockNfcManager,
  NfcTech: { IsoDep: 'IsoDep' },
}));

// Build a mock APDU response with a Visa PAN (4111111111111111) and expiry (12/25)
function buildSuccessAPDU(extraBytes = []) {
  return [...extraBytes, 0x90, 0x00];
}

function buildFailAPDU() {
  return [0x6a, 0x82]; // File not found SW
}

// PAN tag 5A = [0x41, 0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0xFF]
// Expiry tag 5F 24 = [0x25, 0x12, 0x31] (25/12 = Dec 2025)
function buildRecordWithPAN() {
  const panBytes = [0x41, 0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0xff];
  const expiryBytes = [0x25, 0x12, 0x31];
  return [
    0x5a, panBytes.length, ...panBytes,
    0x5f, 0x24, expiryBytes.length, ...expiryBytes,
    0x90, 0x00,
  ];
}

describe('cardReaderService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    // Reset module-level nfcInitialized flag by re-requiring the module
    jest.resetModules();
  });

  describe('isNfcSupported', () => {
    it('returns true when NFC is supported', async () => {
      mockNfcManager.isSupported.mockResolvedValue(true);

      const result = await isNfcSupported();

      expect(result).toBe(true);
    });

    it('returns false when NFC is not supported', async () => {
      mockNfcManager.isSupported.mockResolvedValue(false);

      const result = await isNfcSupported();

      expect(result).toBe(false);
    });

    it('returns false when isSupported throws', async () => {
      mockNfcManager.isSupported.mockRejectedValue(new Error('Hardware error'));

      const result = await isNfcSupported();

      expect(result).toBe(false);
    });
  });

  describe('initNfc', () => {
    it('returns false when NFC is not supported', async () => {
      mockNfcManager.isSupported.mockResolvedValue(false);

      const result = await initNfc();

      expect(result).toBe(false);
      expect(mockNfcManager.start).not.toHaveBeenCalled();
    });

    it('initializes NFC and returns true when supported', async () => {
      mockNfcManager.isSupported.mockResolvedValue(true);
      mockNfcManager.start.mockResolvedValue(undefined);

      const result = await initNfc();

      expect(mockNfcManager.start).toHaveBeenCalled();
      expect(result).toBe(true);
    });
  });

  describe('readCardNFC', () => {
    beforeEach(() => {
      mockNfcManager.isSupported.mockResolvedValue(true);
      mockNfcManager.start.mockResolvedValue(undefined);
      mockNfcManager.requestTechnology.mockResolvedValue(undefined);
    });

    it('reads card details using EMV protocol', async () => {
      // PPSE select returns an AID
      const ppseResponse = [
        0x4f, 0x07, 0xa0, 0x00, 0x00, 0x00, 0x03, 0x10, 0x10, // AID for Visa
        0x90, 0x00,
      ];
      // AID select success
      const aidSelectResponse = buildSuccessAPDU();
      // Record with PAN and expiry
      const recordResponse = buildRecordWithPAN();

      let transceiveCallCount = 0;
      mockNfcManager.isoDepHandler.transceive.mockImplementation(() => {
        transceiveCallCount++;
        if (transceiveCallCount === 1) return Promise.resolve(ppseResponse);    // PPSE
        if (transceiveCallCount === 2) return Promise.resolve(aidSelectResponse); // AID select
        if (transceiveCallCount === 3) return Promise.resolve(recordResponse);  // Record SFI1/Rec1
        return Promise.resolve(buildFailAPDU());
      });

      const result = await readCardNFC();

      expect(result.cardNumber).toBeDefined();
      expect(result.cardNumber.length).toBeGreaterThan(0);
      expect(result.cardProvider).toBe('Visa');
    });

    it('tries fallback AIDs when PPSE parse fails', async () => {
      // PPSE returns success but no AID tag
      const ppseNoAid = [0x84, 0x02, 0x01, 0x02, 0x90, 0x00]; // No 4F tag
      const aidSelectResponse = buildSuccessAPDU();
      const recordResponse = buildRecordWithPAN();

      let transceiveCallCount = 0;
      mockNfcManager.isoDepHandler.transceive.mockImplementation(() => {
        transceiveCallCount++;
        if (transceiveCallCount === 1) return Promise.resolve(ppseNoAid);
        if (transceiveCallCount === 2) return Promise.resolve(aidSelectResponse); // Visa fallback AID
        if (transceiveCallCount === 3) return Promise.resolve(aidSelectResponse); // App select
        if (transceiveCallCount === 4) return Promise.resolve(recordResponse);
        return Promise.resolve(buildFailAPDU());
      });

      const result = await readCardNFC();

      expect(result.cardNumber).toBeDefined();
      expect(mockNfcManager.cancelTechnologyRequest).toHaveBeenCalled();
    });

    it('throws when no payment application found', async () => {
      // PPSE fails, all fallback AIDs fail
      mockNfcManager.isoDepHandler.transceive.mockResolvedValue(buildFailAPDU());

      await expect(readCardNFC()).rejects.toThrow('No payment application found');
      expect(mockNfcManager.cancelTechnologyRequest).toHaveBeenCalled();
    });

    it('always calls cancelTechnologyRequest even on error', async () => {
      mockNfcManager.requestTechnology.mockRejectedValue(new Error('NFC busy'));

      await expect(readCardNFC()).rejects.toThrow();

      expect(mockNfcManager.cancelTechnologyRequest).toHaveBeenCalled();
    });
  });

  describe('cancelNfcRead', () => {
    it('calls cancelTechnologyRequest on NfcManager', () => {
      cancelNfcRead();

      expect(mockNfcManager.cancelTechnologyRequest).toHaveBeenCalled();
    });

    it('swallows errors from cancel', () => {
      mockNfcManager.cancelTechnologyRequest.mockRejectedValue(new Error('Already cancelled'));

      expect(() => cancelNfcRead()).not.toThrow();
    });
  });
});
