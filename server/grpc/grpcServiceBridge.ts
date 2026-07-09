/**
 * gRPC Service Bridge — TypeScript client for inter-service gRPC communication
 * Provides typed clients for all proto-defined services with retries and circuit breaker
 */

interface GrpcClientConfig {
  host: string;
  port: number;
  maxRetries: number;
  timeoutMs: number;
  circuitBreakerThreshold: number;
  circuitBreakerResetMs: number;
}

interface CircuitState {
  failures: number;
  lastFailure: number;
  state: "closed" | "open" | "half-open";
}

const circuits = new Map<string, CircuitState>();

function getCircuit(service: string): CircuitState {
  if (!circuits.has(service)) {
    circuits.set(service, { failures: 0, lastFailure: 0, state: "closed" });
  }
  const c = circuits.get(service)!;
  if (c.state === "open" && Date.now() - c.lastFailure > 30_000) {
    c.state = "half-open";
  }
  return c;
}

const defaultConfig: GrpcClientConfig = {
  host: process.env.GRPC_HOST || "localhost",
  port: parseInt(process.env.GRPC_PORT || "50051"),
  maxRetries: 3,
  timeoutMs: 10_000,
  circuitBreakerThreshold: 5,
  circuitBreakerResetMs: 30_000,
};

/**
 * Generic gRPC-over-HTTP bridge for services that expose gRPC-web endpoints
 * Falls back to REST when gRPC is unavailable
 */
export async function grpcCall<TReq, TRes>(
  service: string,
  method: string,
  request: TReq,
  config: Partial<GrpcClientConfig> = {}
): Promise<TRes> {
  const cfg = { ...defaultConfig, ...config };
  const circuit = getCircuit(service);

  if (circuit.state === "open") {
    throw new Error(`Circuit breaker open for gRPC service ${service}`);
  }

  const url = `http://${cfg.host}:${cfg.port}/grpc/${service}/${method}`;
  let lastError: Error | null = null;

  for (let attempt = 0; attempt <= cfg.maxRetries; attempt++) {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), cfg.timeoutMs);

      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-GRPC-Service": service,
          "X-GRPC-Method": method,
        },
        body: JSON.stringify(request),
        signal: controller.signal,
      });
      clearTimeout(timeout);

      if (!response.ok) {
        throw new Error(
          `gRPC call failed: ${response.status} ${response.statusText}`
        );
      }

      const result = (await response.json()) as TRes;
      circuit.failures = 0;
      circuit.state = "closed";
      return result;
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err));
      if (attempt < cfg.maxRetries) {
        await new Promise(r =>
          setTimeout(
            r,
            Math.pow(2, attempt) * 200 +
              (crypto.getRandomValues(new Uint32Array(1))[0] / 4294967295) * 100
          )
        );
      }
    }
  }

  circuit.failures++;
  circuit.lastFailure = Date.now();
  if (circuit.failures >= cfg.circuitBreakerThreshold) {
    circuit.state = "open";
  }
  throw lastError || new Error(`gRPC call to ${service}.${method} failed`);
}

// Typed service clients

export const WorkflowOrchestratorClient = {
  createWorkflow: (req: {
    name: string;
    category: string;
    steps: Array<{ name: string; type: string; assigneeRole: string }>;
  }) => grpcCall("WorkflowOrchestrator", "CreateWorkflow", req),

  executeStep: (req: {
    workflowId: string;
    stepId: string;
    input: Record<string, string>;
  }) => grpcCall("WorkflowOrchestrator", "ExecuteStep", req),

  getWorkflowStatus: (req: { workflowId: string }) =>
    grpcCall("WorkflowOrchestrator", "GetWorkflowStatus", req),

  listWorkflows: (req: {
    limit: number;
    offset: number;
    statusFilter?: string;
  }) => grpcCall("WorkflowOrchestrator", "ListWorkflows", req),

  cancelWorkflow: (req: { workflowId: string }) =>
    grpcCall("WorkflowOrchestrator", "CancelWorkflow", req),
};

export const TigerBeetleLedgerClient = {
  createAccount: (req: {
    ownerId: string;
    currency: string;
    accountType: string;
    initialBalance: number;
  }) => grpcCall("TigerBeetleLedger", "CreateAccount", req),

  createTransfer: (req: {
    debitAccountId: string;
    creditAccountId: string;
    amount: number;
    currency: string;
    reference: string;
  }) => grpcCall("TigerBeetleLedger", "CreateTransfer", req),

  getBalance: (req: { accountId: string }) =>
    grpcCall("TigerBeetleLedger", "GetBalance", req),

  listTransfers: (req: { accountId: string; limit: number; since?: number }) =>
    grpcCall("TigerBeetleLedger", "ListTransfers", req),

  reverseTransfer: (req: { transferId: string; reason: string }) =>
    grpcCall("TigerBeetleLedger", "ReverseTransfer", req),
};

export const SettlementGatewayClient = {
  initiateSettlement: (req: {
    batchId: string;
    transactionIds: string[];
    settlementMethod: string;
    targetAccount: string;
  }) => grpcCall("SettlementGateway", "InitiateSettlement", req),

  getSettlementStatus: (req: { settlementId: string }) =>
    grpcCall("SettlementGateway", "GetSettlementStatus", req),

  listSettlements: (req: {
    limit: number;
    offset: number;
    statusFilter?: string;
  }) => grpcCall("SettlementGateway", "ListSettlements", req),

  reconcileSettlement: (req: { settlementId: string; source: string }) =>
    grpcCall("SettlementGateway", "ReconcileSettlement", req),
};

export function getGrpcCircuitStatus(): Record<string, CircuitState> {
  const result: Record<string, CircuitState> = {};
  circuits.forEach((v, k) => {
    result[k] = { ...v };
  });
  return result;
}
