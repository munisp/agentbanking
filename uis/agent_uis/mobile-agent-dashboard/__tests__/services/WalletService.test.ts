import { WalletService } from '../../src/services/WalletService';

const mockGet = jest.fn();
const mockPut = jest.fn();
const mockPost = jest.fn();

jest.mock('../../src/api/APIClient', () => ({
  APIClient: jest.fn().mockImplementation(() => ({
    get: mockGet,
    put: mockPut,
    post: mockPost,
  })),
}));

describe('WalletService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('getWallets', () => {
    it('returns wallet balances from API', async () => {
      const balances = [
        { currency: 'NGN', balance: 50000, symbol: '₦' },
        { currency: 'USD', balance: 100, symbol: '$' },
      ];
      mockGet.mockResolvedValue({ data: balances });

      const result = await WalletService.getWallets();

      expect(mockGet).toHaveBeenCalledWith('/wallet/balances');
      expect(result).toEqual(balances);
    });

    it('propagates API errors', async () => {
      mockGet.mockRejectedValue(new Error('Unauthorized'));

      await expect(WalletService.getWallets()).rejects.toThrow('Unauthorized');
    });
  });

  describe('getUserProfile', () => {
    it('returns user profile from API', async () => {
      const profile = { id: 'u1', name: 'John Doe', email: 'john@example.com', phone: '08012345678', country: 'NG', kycStatus: 'verified' };
      mockGet.mockResolvedValue({ data: profile });

      const result = await WalletService.getUserProfile();

      expect(mockGet).toHaveBeenCalledWith('/user/profile');
      expect(result).toEqual(profile);
    });
  });

  describe('updateUserProfile', () => {
    it('sends partial profile update and returns updated profile', async () => {
      const updated = { id: 'u1', name: 'Jane Doe', email: 'jane@example.com', phone: '08012345678', country: 'NG', kycStatus: 'verified' };
      mockPut.mockResolvedValue({ data: updated });

      const result = await WalletService.updateUserProfile({ name: 'Jane Doe' });

      expect(mockPut).toHaveBeenCalledWith('/user/profile', { name: 'Jane Doe' });
      expect(result).toEqual(updated);
    });

    it('can update email only', async () => {
      const updated = { id: 'u1', name: 'John', email: 'new@example.com', phone: '080', country: 'NG', kycStatus: 'pending' };
      mockPut.mockResolvedValue({ data: updated });

      const result = await WalletService.updateUserProfile({ email: 'new@example.com' });

      expect(mockPut).toHaveBeenCalledWith('/user/profile', { email: 'new@example.com' });
      expect(result.email).toBe('new@example.com');
    });
  });

  describe('getExchangeRate', () => {
    it('fetches exchange rate between two currencies', async () => {
      const rate = { from: 'NGN', to: 'USD', rate: 0.00065 };
      mockGet.mockResolvedValue({ data: rate });

      const result = await WalletService.getExchangeRate('NGN', 'USD');

      expect(mockGet).toHaveBeenCalledWith('/wallet/exchange-rate?from=NGN&to=USD');
      expect(result).toEqual(rate);
    });
  });

  describe('exchangeCurrency', () => {
    it('exchanges currency and returns result', async () => {
      const exchangeResult = { transactionId: 'exch-1', from: 'NGN', to: 'USD', amount: 50000, convertedAmount: 32.5 };
      mockPost.mockResolvedValue({ data: exchangeResult });

      const result = await WalletService.exchangeCurrency('NGN', 'USD', 50000);

      expect(mockPost).toHaveBeenCalledWith('/wallet/exchange', { from: 'NGN', to: 'USD', amount: 50000 });
      expect(result).toEqual(exchangeResult);
    });

    it('propagates exchange errors', async () => {
      mockPost.mockRejectedValue(new Error('Insufficient balance'));

      await expect(WalletService.exchangeCurrency('NGN', 'USD', 10000000)).rejects.toThrow('Insufficient balance');
    });
  });
});
