import transactionService from '../../src/services/transactionService';

let mockStore = {};

jest.mock('expo-secure-store', () => ({
  getItemAsync: jest.fn((key) => Promise.resolve(mockStore[key] ?? null)),
  setItemAsync: jest.fn((key, val) => { mockStore[key] = val; return Promise.resolve(); }),
}));

const mockNetworkOpsApi = {
  listTransactions: jest.fn(),
  getTransaction: jest.fn(),
  getAgentCashPosition: jest.fn(),
};

jest.mock('../../src/services/apiService', () => ({
  networkOperationsApi: mockNetworkOpsApi,
  authHeaders: jest.fn().mockResolvedValue({
    Authorization: 'Bearer token-abc',
    'x-tenant-id': 'bpmgd',
  }),
  accountApi: {},
}));

jest.mock('../../src/services/offlineTransferQueue', () => ({
  isDeviceOnline: jest.fn().mockResolvedValue(true),
  isTransientNetworkError: jest.fn().mockReturnValue(false),
  queueTransferForSync: jest.fn().mockResolvedValue('offline-queue-id-1'),
  startOfflineTransferSync: jest.fn(),
}));

global.fetch = jest.fn();

describe('transactionService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockStore = {};
    (global.fetch as jest.Mock).mockReset();
  });

  describe('buildTransferPayload', () => {
    it('builds external transfer payload correctly', () => {
      const headers = { 'x-tenant-id': 'bpmgd', 'x-tenant-name': 'bpmgd' };
      const data = {
        amount: 5000,
        currency: 'NGN',
        beneficiary_account_number: 'ACC-001',
        beneficiary_name: 'Jane Doe',
        from_account_number: 'ACC-SENDER',
        sender_name: 'John',
        beneficiary_bank_code: 'GTB',
        narration: 'Payment',
      };

      const payload = transactionService.buildTransferPayload('external', data, headers);

      expect(payload.to.idValue).toBe('ACC-001');
      expect(payload.from.idValue).toBe('ACC-SENDER');
      expect(payload.destination).toBe('GTB');
      expect(payload.note).toBe('Payment');
      expect(payload.amount).toBe('5000.00');
    });

    it('builds internal transfer payload correctly', () => {
      const headers = { 'x-tenant-id': 'bpmgd' };
      const data = {
        amount: 1000,
        to_account_number: 'ACC-TO',
        from_account_number: 'ACC-FROM',
        description: 'Internal move',
      };

      const payload = transactionService.buildTransferPayload('internal', data, headers);

      expect(payload.to.idValue).toBe('ACC-TO');
      expect(payload.from.idValue).toBe('ACC-FROM');
      expect(payload.destination).toBe('bpmgd');
      expect(payload.note).toBe('Internal move');
    });

    it('builds generic transfer payload', () => {
      const headers = { 'x-tenant-id': 'bpmgd' };
      const data = { amount: 500, to_account_id: 'payee-1', from_account_id: 'payer-1' };

      const payload = transactionService.buildTransferPayload('generic', data, headers);

      expect(payload.to.idValue).toBe('payee-1');
      expect(payload.from.idValue).toBe('payer-1');
    });

    it('formats amount to 2 decimal places', () => {
      const payload = transactionService.buildTransferPayload('internal', { amount: 1000.5 }, {});

      expect(payload.amount).toBe('1000.50');
    });

    it('defaults currency to NGN', () => {
      const payload = transactionService.buildTransferPayload('internal', { amount: 100 }, {});

      expect(payload.currency).toBe('NGN');
    });
  });

  describe('submitTransferWithOfflineFallback', () => {
    it('sends transfer online when device is online', async () => {
      const { isDeviceOnline } = require('../../src/services/offlineTransferQueue');
      isDeviceOnline.mockResolvedValue(true);

      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ transactionId: 'tx-1', status: 'success' }),
      });

      const result = await transactionService.submitTransferWithOfflineFallback('internal', {
        amount: 1000,
        to_account_number: 'ACC-TO',
        from_account_number: 'ACC-FROM',
      });

      expect(result.queued).toBe(false);
      expect(result.transactionId).toBe('tx-1');
    });

    it('queues transfer when device is offline', async () => {
      const { isDeviceOnline, queueTransferForSync } = require('../../src/services/offlineTransferQueue');
      isDeviceOnline.mockResolvedValue(false);

      const result = await transactionService.submitTransferWithOfflineFallback('internal', { amount: 500 });

      expect(queueTransferForSync).toHaveBeenCalledWith('internal', { amount: 500 });
      expect(result.queued).toBe(true);
      expect(result.queueId).toBe('offline-queue-id-1');
    });

    it('queues transfer on transient network error after both attempts fail', async () => {
      const { isDeviceOnline, isTransientNetworkError, queueTransferForSync } = require('../../src/services/offlineTransferQueue');
      isDeviceOnline.mockResolvedValue(true);
      isTransientNetworkError.mockReturnValue(true);

      (global.fetch as jest.Mock).mockRejectedValue(new Error('network request failed'));

      jest.useFakeTimers();
      const resultPromise = transactionService.submitTransferWithOfflineFallback('internal', { amount: 100 });
      jest.advanceTimersByTime(2000);
      const result = await resultPromise;
      jest.useRealTimers();

      expect(queueTransferForSync).toHaveBeenCalled();
      expect(result.queued).toBe(true);
    });

    it('re-throws non-transient errors immediately', async () => {
      const { isDeviceOnline, isTransientNetworkError } = require('../../src/services/offlineTransferQueue');
      isDeviceOnline.mockResolvedValue(true);

      const serverError = new Error('Insufficient funds');
      (serverError as any).statusCode = 400;
      isTransientNetworkError.mockReturnValue(false);

      (global.fetch as jest.Mock).mockResolvedValue({
        ok: false,
        status: 400,
        json: () => Promise.resolve({ message: 'Insufficient funds' }),
      });

      await expect(
        transactionService.submitTransferWithOfflineFallback('internal', { amount: 99999999 })
      ).rejects.toThrow('Insufficient funds');
    });
  });

  describe('getTransactions', () => {
    it('fetches transactions using keycloak id', async () => {
      mockStore['keycloakId'] = 'kc-user-1';
      const txList = [{ id: 'tx1' }, { id: 'tx2' }];
      mockNetworkOpsApi.listTransactions.mockResolvedValue(txList);

      const result = await transactionService.getTransactions({}, 1, 20);

      expect(mockNetworkOpsApi.listTransactions).toHaveBeenCalledWith('kc-user-1', {}, 1, 20);
      expect(result).toEqual(txList);
    });

    it('throws when not authenticated', async () => {
      await expect(transactionService.getTransactions()).rejects.toThrow('Not authenticated');
    });
  });

  describe('getTransactionById', () => {
    it('returns transaction by id', async () => {
      const tx = { id: 'tx-abc', amount: 1000 };
      mockNetworkOpsApi.getTransaction.mockResolvedValue(tx);

      const result = await transactionService.getTransactionById('tx-abc');

      expect(mockNetworkOpsApi.getTransaction).toHaveBeenCalledWith('tx-abc');
      expect(result).toEqual(tx);
    });

    it('propagates error when transaction not found', async () => {
      mockNetworkOpsApi.getTransaction.mockRejectedValue(new Error('Not found'));

      await expect(transactionService.getTransactionById('missing')).rejects.toThrow('Not found');
    });
  });

  describe('getTransactionsByAccountNumber', () => {
    it('fetches transactions by account number via HTTP', async () => {
      const data = { transactions: [{ id: 'tx1' }] };
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(data),
      });

      const result = await transactionService.getTransactionsByAccountNumber('ACC-001', 1, 10);

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/ledger/txn/account-number/ACC-001?limit=10&page=1'),
        expect.any(Object)
      );
      expect(result).toEqual(data);
    });

    it('throws when HTTP response is not ok', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({
        ok: false,
        status: 403,
        statusText: 'Forbidden',
        json: () => Promise.resolve({}),
      });

      await expect(transactionService.getTransactionsByAccountNumber('ACC-BAD')).rejects.toThrow('HTTP 403');
    });
  });

  describe('getTransactionReceipt', () => {
    it('returns formatted receipt with transaction details', async () => {
      const tx = { id: 'tx-r1', created_at: '2024-01-15T10:00:00Z', amount: 3000 };
      mockNetworkOpsApi.getTransaction.mockResolvedValue(tx);

      const receipt = await transactionService.getTransactionReceipt('tx-r1');

      expect(receipt.transaction).toEqual(tx);
      expect(receipt.formattedDate).toBeDefined();
    });
  });

  describe('getAgentCashPosition', () => {
    it('fetches cash position using keycloak id', async () => {
      mockStore['keycloakId'] = 'kc-agent-1';
      const position = { balance: 75000 };
      mockNetworkOpsApi.getAgentCashPosition.mockResolvedValue(position);

      const result = await transactionService.getAgentCashPosition();

      expect(mockNetworkOpsApi.getAgentCashPosition).toHaveBeenCalledWith('kc-agent-1');
      expect(result).toEqual(position);
    });

    it('throws when not authenticated', async () => {
      await expect(transactionService.getAgentCashPosition()).rejects.toThrow('Not authenticated');
    });
  });
});
