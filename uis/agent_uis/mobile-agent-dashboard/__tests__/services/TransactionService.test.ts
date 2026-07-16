import { TransactionService } from '../../src/services/TransactionService';

const mockGet = jest.fn();

jest.mock('../../src/api/APIClient', () => ({
  APIClient: jest.fn().mockImplementation(() => ({ get: mockGet })),
}));

describe('TransactionService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('getAllTransactions', () => {
    it('returns all transactions from API', async () => {
      const transactions = [
        { id: 'tx1', type: 'credit', amount: 5000, currency: 'NGN', status: 'completed', date: '2024-01-01', paymentSystem: 'mojaloop', reference: 'REF001' },
        { id: 'tx2', type: 'debit', amount: 2000, currency: 'NGN', status: 'pending', date: '2024-01-02', paymentSystem: 'mojaloop', reference: 'REF002' },
      ];
      mockGet.mockResolvedValue({ data: transactions });

      const result = await TransactionService.getAllTransactions();

      expect(mockGet).toHaveBeenCalledWith('/transactions');
      expect(result).toEqual(transactions);
    });

    it('propagates API errors', async () => {
      mockGet.mockRejectedValue(new Error('Network error'));

      await expect(TransactionService.getAllTransactions()).rejects.toThrow('Network error');
    });
  });

  describe('getRecentTransactions', () => {
    it('fetches with default limit of 5', async () => {
      mockGet.mockResolvedValue({ data: [] });

      await TransactionService.getRecentTransactions();

      expect(mockGet).toHaveBeenCalledWith('/transactions/recent?limit=5');
    });

    it('fetches with custom limit', async () => {
      mockGet.mockResolvedValue({ data: [] });

      await TransactionService.getRecentTransactions(10);

      expect(mockGet).toHaveBeenCalledWith('/transactions/recent?limit=10');
    });

    it('returns transaction array', async () => {
      const recent = [{ id: 'tx1', type: 'credit', amount: 100, currency: 'NGN', status: 'completed', date: '2024-01-01', paymentSystem: 'mojaloop', reference: 'REF001' }];
      mockGet.mockResolvedValue({ data: recent });

      const result = await TransactionService.getRecentTransactions(1);

      expect(result).toEqual(recent);
    });
  });

  describe('getTransactionById', () => {
    it('fetches transaction by id', async () => {
      const tx = { id: 'tx1', amount: 5000 };
      mockGet.mockResolvedValue({ data: tx });

      const result = await TransactionService.getTransactionById('tx1');

      expect(mockGet).toHaveBeenCalledWith('/transactions/tx1');
      expect(result).toEqual(tx);
    });

    it('propagates error when transaction not found', async () => {
      mockGet.mockRejectedValue(new Error('Not found'));

      await expect(TransactionService.getTransactionById('missing')).rejects.toThrow('Not found');
    });
  });

  describe('exportTransactions', () => {
    it('exports as csv by default', async () => {
      mockGet.mockResolvedValue({});

      await TransactionService.exportTransactions();

      expect(mockGet).toHaveBeenCalledWith('/transactions/export?format=csv');
    });

    it('exports as pdf when specified', async () => {
      mockGet.mockResolvedValue({});

      await TransactionService.exportTransactions('pdf');

      expect(mockGet).toHaveBeenCalledWith('/transactions/export?format=pdf');
    });

    it('exports as csv when explicitly specified', async () => {
      mockGet.mockResolvedValue({});

      await TransactionService.exportTransactions('csv');

      expect(mockGet).toHaveBeenCalledWith('/transactions/export?format=csv');
    });
  });
});
