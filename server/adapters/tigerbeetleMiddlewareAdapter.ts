/**
 * TigerBeetle Middleware Integration Adapter
 *
 * Bridges the tRPC layer to the three TigerBeetle middleware services:
 *   - Go Hub (port 9300): Event pipeline with Kafka, Dapr, Temporal, Mojaloop, OpenSearch, Lakehouse, APISIX, Keycloak, Permify, OpenAppSec
 *   - Rust Bridge (port 9400): High-throughput Kafka producer, Redis caching, OpenSearch indexing
 *   - Python Orchestrator (port 9500): Workflow orchestration, reconciliation, search
 *
 * All calls use AbortController for timeout safety and graceful fallback.
 */

const TB_HUB_URL = process.env.TB_HUB_URL || "http://localhost:9300";
const TB_BRIDGE_URL = process.env.TB_BRIDGE_URL || "http://localhost:9400";
const TB_ORCHESTRATOR_URL =
  process.env.TB_ORCHESTRATOR_URL || "http://localhost:9500";
const MIDDLEWARE_TIMEOUT = 5000;

export interface MiddlewareTransferInput {
  id: string;
  debit_account_id: string;
  credit_account_id: string;
  amount: number;
  currency?: string;
  ledger?: number;
  code?: number;
  reference?: string;
  agent_code?: string;
  tx_type?: string;
  metadata?: Record<string, string>;
}

export interface MiddlewareStatus {
  service: string;
  status: string;
  latency_ms: number;
  details?: string;
}

export interface HubMetrics {
  transfers_processed: number;
  kafka_events_published: number;
  fluvio_events_streamed: number;
  temporal_workflows_started: number;
  dapr_invocations: number;
  mojaloop_transfers: number;
  opensearch_indexed: number;
  lakehouse_exported: number;
  redis_hits: number;
  redis_misses: number;
  permify_checks: number;
  uptime_seconds: number;
  middleware: MiddlewareStatus[];
}

export interface BridgeMetrics {
  transfers_processed: number;
  kafka_events_produced: number;
  redis_cache_updates: number;
  opensearch_indexed: number;
  lakehouse_exported: number;
  openappsec_logged: number;
  errors_total: number;
  uptime_seconds: number;
}

export interface OrchestratorMetrics {
  transfers_orchestrated: number;
  kafka_events_consumed: number;
  kafka_events_produced: number;
  temporal_workflows: number;
  fluvio_events: number;
  opensearch_queries: number;
  lakehouse_exports: number;
  mojaloop_transfers: number;
  reconciliations_run: number;
  keycloak_validations: number;
  permify_checks: number;
  errors_total: number;
  uptime_seconds: number;
}

async function safeFetch<T>(
  url: string,
  options?: RequestInit
): Promise<{ ok: true; data: T } | { ok: false; error: string }> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), MIDDLEWARE_TIMEOUT);
    const resp = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    clearTimeout(timeout);

    if (!resp.ok) {
      return { ok: false, error: `HTTP ${resp.status}` };
    }
    const data = (await resp.json()) as T;
    return { ok: true, data };
  } catch (e) {
    return {
      ok: false,
      error: e instanceof Error ? e.message : String(e),
    };
  }
}

// ── Go Middleware Hub ─────────────────────────────────────────────────────────

export async function hubSubmitTransfer(input: MiddlewareTransferInput) {
  return safeFetch<{ status: string; transfer_id: string }>(
    `${TB_HUB_URL}/transfer`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...input,
        currency: input.currency || "NGN",
        ledger: input.ledger || 1000,
        code: input.code || 1,
      }),
    }
  );
}

export async function hubGetMetrics() {
  return safeFetch<HubMetrics>(`${TB_HUB_URL}/metrics`);
}

export async function hubGetHealth() {
  return safeFetch<{ status: string; middleware: MiddlewareStatus[] }>(
    `${TB_HUB_URL}/health`
  );
}

export async function hubGetMiddlewareStatus() {
  return safeFetch<MiddlewareStatus[]>(`${TB_HUB_URL}/middleware/status`);
}

// ── Rust Middleware Bridge ────────────────────────────────────────────────────

export async function bridgeSubmitTransfer(input: MiddlewareTransferInput) {
  return safeFetch<{ status: string; transfer_id: string }>(
    `${TB_BRIDGE_URL}/transfer`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...input,
        currency: input.currency || "NGN",
        timestamp: new Date().toISOString(),
      }),
    }
  );
}

export async function bridgeGetMetrics() {
  return safeFetch<BridgeMetrics>(`${TB_BRIDGE_URL}/metrics`);
}

export async function bridgeGetHealth() {
  return safeFetch<{ status: string; language: string }>(
    `${TB_BRIDGE_URL}/health`
  );
}

export async function bridgeGetMiddlewareStatus() {
  return safeFetch<MiddlewareStatus[]>(`${TB_BRIDGE_URL}/middleware/status`);
}

// ── Python Middleware Orchestrator ────────────────────────────────────────────

export async function orchestratorSubmitTransfer(
  input: MiddlewareTransferInput
) {
  return safeFetch<{ status: string; transfer_id: string }>(
    `${TB_ORCHESTRATOR_URL}/transfer`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...input,
        currency: input.currency || "NGN",
      }),
    }
  );
}

export async function orchestratorGetMetrics() {
  return safeFetch<OrchestratorMetrics>(`${TB_ORCHESTRATOR_URL}/metrics`);
}

export async function orchestratorGetHealth() {
  return safeFetch<{ status: string; language: string }>(
    `${TB_ORCHESTRATOR_URL}/health`
  );
}

export async function orchestratorSearch(query: Record<string, unknown>) {
  return safeFetch<{ hits: { hits: unknown[]; total: { value: number } } }>(
    `${TB_ORCHESTRATOR_URL}/search`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(query),
    }
  );
}

export async function orchestratorReconcile() {
  return safeFetch<{ status: string; total_runs: number }>(
    `${TB_ORCHESTRATOR_URL}/reconcile`,
    { method: "POST" }
  );
}

export async function orchestratorGetMiddlewareStatus() {
  return safeFetch<MiddlewareStatus[]>(
    `${TB_ORCHESTRATOR_URL}/middleware/status`
  );
}

// ── Aggregated Middleware Status ──────────────────────────────────────────────

export async function getAllMiddlewareStatus(): Promise<{
  hub: MiddlewareStatus[];
  bridge: MiddlewareStatus[];
  orchestrator: MiddlewareStatus[];
}> {
  const [hub, bridge, orchestrator] = await Promise.all([
    hubGetMiddlewareStatus(),
    bridgeGetMiddlewareStatus(),
    orchestratorGetMiddlewareStatus(),
  ]);

  return {
    hub: hub.ok ? hub.data : [],
    bridge: bridge.ok ? bridge.data : [],
    orchestrator: orchestrator.ok ? orchestrator.data : [],
  };
}

export async function getAllMetrics(): Promise<{
  hub: HubMetrics | null;
  bridge: BridgeMetrics | null;
  orchestrator: OrchestratorMetrics | null;
}> {
  const [hub, bridge, orchestrator] = await Promise.all([
    hubGetMetrics(),
    bridgeGetMetrics(),
    orchestratorGetMetrics(),
  ]);

  return {
    hub: hub.ok ? hub.data : null,
    bridge: bridge.ok ? bridge.data : null,
    orchestrator: orchestrator.ok ? orchestrator.data : null,
  };
}

/**
 * Submit a transfer through all three middleware services in parallel
 * for maximum data distribution across Kafka, Redis, OpenSearch, Lakehouse.
 */
export async function fanOutTransfer(input: MiddlewareTransferInput) {
  const [hub, bridge, orchestrator] = await Promise.all([
    hubSubmitTransfer(input),
    bridgeSubmitTransfer(input),
    orchestratorSubmitTransfer(input),
  ]);

  return {
    hub: hub.ok ? "accepted" : hub.error,
    bridge: bridge.ok ? "accepted" : bridge.error,
    orchestrator: orchestrator.ok ? "accepted" : orchestrator.error,
  };
}
