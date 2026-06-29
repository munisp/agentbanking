import simOrchestratorService from '../../src/services/simOrchestratorService';

global.fetch = jest.fn();

describe('simOrchestratorService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('getSIMStatus', () => {
    it('returns SIM status from orchestrator', async () => {
      const status = {
        transactionActive: false,
        activeSlot: 0,
        isWifi: false,
        txRef: null,
        readings: [{ slot: 0, carrier: 'MTN', rssi: -65, latencyMs: 80, score: 90, selected: true }],
        lastFailover: null,
      };
      (global.fetch as jest.Mock).mockResolvedValue({ ok: true, json: () => Promise.resolve(status) });

      const result = await simOrchestratorService.getSIMStatus();

      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:9200/sim/status',
        expect.objectContaining({ signal: expect.any(AbortSignal) })
      );
      expect(result).toEqual(status);
    });

    it('returns null when orchestrator is unreachable', async () => {
      (global.fetch as jest.Mock).mockRejectedValue(new Error('ECONNREFUSED'));

      const result = await simOrchestratorService.getSIMStatus();

      expect(result).toBeNull();
    });

    it('returns null when response is not ok', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({ ok: false, status: 503 });

      const result = await simOrchestratorService.getSIMStatus();

      expect(result).toBeNull();
    });

    it('returns null when request times out', async () => {
      (global.fetch as jest.Mock).mockRejectedValue(new DOMException('The operation was aborted', 'AbortError'));

      const result = await simOrchestratorService.getSIMStatus();

      expect(result).toBeNull();
    });
  });

  describe('signalTransactionStart', () => {
    it('posts transaction start with txRef and terminalId', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({ ok: true });

      await simOrchestratorService.signalTransactionStart('TX-REF-001', 'TERMINAL-A1');

      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:9200/sim/transaction/start',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ txRef: 'TX-REF-001', terminalId: 'TERMINAL-A1' }),
        })
      );
    });

    it('posts transaction start with txRef only when no terminalId', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({ ok: true });

      await simOrchestratorService.signalTransactionStart('TX-REF-002');

      const body = JSON.parse((global.fetch as jest.Mock).mock.calls[0][1].body);
      expect(body.txRef).toBe('TX-REF-002');
      expect(body.terminalId).toBeUndefined();
    });

    it('silently ignores errors when orchestrator is unavailable', async () => {
      (global.fetch as jest.Mock).mockRejectedValue(new Error('ECONNREFUSED'));

      await expect(simOrchestratorService.signalTransactionStart('TX-001')).resolves.toBeUndefined();
    });
  });

  describe('signalTransactionEnd', () => {
    it('posts transaction end to orchestrator', async () => {
      (global.fetch as jest.Mock).mockResolvedValue({ ok: true });

      await simOrchestratorService.signalTransactionEnd();

      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:9200/sim/transaction/end',
        expect.objectContaining({ method: 'POST' })
      );
    });

    it('silently ignores errors when orchestrator is unavailable', async () => {
      (global.fetch as jest.Mock).mockRejectedValue(new Error('daemon not running'));

      await expect(simOrchestratorService.signalTransactionEnd()).resolves.toBeUndefined();
    });
  });

  describe('request timeout', () => {
    it('aborts fetch after 2000ms', async () => {
      let abortCalled = false;
      const mockAbortController = {
        abort: jest.fn(() => { abortCalled = true; }),
        signal: { aborted: false },
      };
      jest.spyOn(global, 'AbortController').mockImplementation(() => mockAbortController as any);

      (global.fetch as jest.Mock).mockResolvedValue({ ok: true, json: () => Promise.resolve(null) });

      await simOrchestratorService.getSIMStatus();

      // Timer should be set for 2000ms
      jest.runAllTimers();

      expect(mockAbortController.abort).toHaveBeenCalled();
    });
  });
});
