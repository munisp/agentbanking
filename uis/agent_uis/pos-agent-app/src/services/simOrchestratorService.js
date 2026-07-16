/**
 * SIM Orchestrator Client
 *
 * Talks to the local sim-orchestrator daemon running on the POS terminal at
 * http://localhost:9200. All calls are fire-and-forget-safe: if the daemon
 * isn't running (dev mode, emulator), errors are swallowed silently so the
 * rest of the app continues normally.
 */

const ORCHESTRATOR_BASE_URL = 'http://localhost:9200';

const TIMEOUT_MS = 2000;

async function fetchWithTimeout(url, options = {}) {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    return response;
  } finally {
    clearTimeout(id);
  }
}

const simOrchestratorService = {
  /**
   * Fetch current SIM status from the orchestrator.
   * Returns null when the daemon is unreachable.
   *
   * Response shape:
   *   {
   *     transactionActive: boolean,
   *     activeSlot: number,         // 0-3 (Phys1 / Phys2 / eSIM1 / eSIM2)
   *     isWifi: boolean,
   *     txRef: string | null,
   *     readings: [
   *       { slot, carrier, rssi, latencyMs, packetLossX10, score, selected, regStatus },
   *       ...
   *     ],
   *     lastFailover: {
   *       fromSlot, toSlot, reason, latencyMs, lossX10, txRef, timestampUtc
   *     } | null,
   *   }
   */
  async getSIMStatus() {
    try {
      const response = await fetchWithTimeout(`${ORCHESTRATOR_BASE_URL}/sim/status`);
      if (!response.ok) return null;
      return response.json();
    } catch {
      return null;
    }
  },

  /**
   * Notify the orchestrator that a financial transaction is starting.
   * This arms the watchdog so it monitors the active SIM every 5 s and
   * triggers emergency failover if latency > 3 s or packet loss > 20 %.
   *
   * @param {string} txRef  - Transaction reference (used in failover reports).
   * @param {string} [terminalId] - Terminal serial number (optional).
   */
  async signalTransactionStart(txRef, terminalId) {
    try {
      await fetchWithTimeout(`${ORCHESTRATOR_BASE_URL}/sim/transaction/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ txRef, terminalId }),
      });
    } catch {
      // Orchestrator not running (dev/emulator) — carry on.
    }
  },

  /**
   * Notify the orchestrator that the transaction has completed or failed.
   * This disarms the watchdog.
   */
  async signalTransactionEnd() {
    try {
      await fetchWithTimeout(`${ORCHESTRATOR_BASE_URL}/sim/transaction/end`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({}),
      });
    } catch {
      // Ignore — daemon may not be running.
    }
  },
};

export default simOrchestratorService;
