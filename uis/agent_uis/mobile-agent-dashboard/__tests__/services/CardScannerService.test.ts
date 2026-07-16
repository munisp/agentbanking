import { cardScannerService } from '../../src/services/CardScannerService';

const mockRecognize = jest.fn();

jest.mock('react-native-text-recognition', () => ({
  default: { recognize: mockRecognize },
}));

describe('CardScannerService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('scanCard', () => {
    it('returns extracted card details from recognized text', async () => {
      mockRecognize.mockResolvedValue(['4111 1111 1111 1111', '12/26', 'JOHN DOE']);

      const result = await cardScannerService.scanCard('/path/to/image.jpg');

      expect(mockRecognize).toHaveBeenCalledWith('/path/to/image.jpg');
      expect(result.cardNumber).toBe('4111111111111111');
      expect(result.expiryDate).toBe('12/26');
      expect(result.cardType).toBe('visa');
    });

    it('detects Mastercard', async () => {
      mockRecognize.mockResolvedValue(['5234 5678 9012 3456 Expires 08/25']);

      const result = await cardScannerService.scanCard('/path/to/card.jpg');

      expect(result.cardNumber).toBe('5234567890123456');
      expect(result.cardType).toBe('mastercard');
    });

    it('detects Amex', async () => {
      mockRecognize.mockResolvedValue(['3782 822463 10005']);

      const result = await cardScannerService.scanCard('/path/to/card.jpg');

      expect(result.cardNumber).toBe('378282246310005');
      expect(result.cardType).toBe('amex');
    });

    it('returns unknown card type when prefix is unrecognized', async () => {
      mockRecognize.mockResolvedValue(['6011 1111 1111 1117']);

      const result = await cardScannerService.scanCard('/path/to/card.jpg');

      expect(result.cardType).toBe('unknown');
    });

    it('returns empty cardNumber when no card number found in text', async () => {
      mockRecognize.mockResolvedValue(['No card data here']);

      const result = await cardScannerService.scanCard('/path/to/image.jpg');

      expect(result.cardNumber).toBe('');
    });

    it('returns empty expiryDate when no expiry found', async () => {
      mockRecognize.mockResolvedValue(['4111 1111 1111 1111']);

      const result = await cardScannerService.scanCard('/path/to/image.jpg');

      expect(result.expiryDate).toBe('');
    });

    it('handles dashes in card number', async () => {
      mockRecognize.mockResolvedValue(['4111-1111-1111-1111 03/27']);

      const result = await cardScannerService.scanCard('/path/to/image.jpg');

      expect(result.cardNumber).toBe('4111111111111111');
    });

    it('re-throws recognition errors', async () => {
      mockRecognize.mockRejectedValue(new Error('Image too blurry'));

      await expect(cardScannerService.scanCard('/bad/image.jpg')).rejects.toThrow('Image too blurry');
    });
  });
});
