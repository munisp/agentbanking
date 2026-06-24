/**
 * Dapr Sidecar Client
 * Pub/sub messaging and state store operations via Dapr HTTP API.
 * Fail-open: returns gracefully when Dapr sidecar is unavailable.
 */

const DAPR_URL = process.env.DAPR_URL || "http://localhost:3500";

export async function daprPublish(
  pubsubName: string,
  topic: string,
  data: Record<string, unknown>
): Promise<boolean> {
  try {
    const response = await fetch(
      `${DAPR_URL}/v1.0/publish/${pubsubName}/${topic}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
        signal: AbortSignal.timeout(5000),
      }
    );
    return response.ok;
  } catch {
    return false;
  }
}

export async function daprStateGet(
  storeName: string,
  key: string
): Promise<unknown | null> {
  try {
    const response = await fetch(
      `${DAPR_URL}/v1.0/state/${storeName}/${key}`,
      { signal: AbortSignal.timeout(3000) }
    );
    if (!response.ok) return null;
    return response.json();
  } catch {
    return null;
  }
}

export async function daprStateSave(
  storeName: string,
  key: string,
  value: unknown
): Promise<boolean> {
  try {
    const response = await fetch(
      `${DAPR_URL}/v1.0/state/${storeName}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify([{ key, value }]),
        signal: AbortSignal.timeout(5000),
      }
    );
    return response.ok;
  } catch {
    return false;
  }
}

export async function daprInvokeService(
  appId: string,
  method: string,
  data?: unknown
): Promise<unknown | null> {
  try {
    const response = await fetch(
      `${DAPR_URL}/v1.0/invoke/${appId}/method/${method}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: data ? JSON.stringify(data) : undefined,
        signal: AbortSignal.timeout(10000),
      }
    );
    if (!response.ok) return null;
    return response.json();
  } catch {
    return null;
  }
}
