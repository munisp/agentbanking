/**
 * Lakehouse Analytics Pipeline Client
 * Ingests data into bronze/silver/gold tier data lake tables.
 * Fail-open: returns gracefully when Lakehouse API is unavailable.
 */

const LAKEHOUSE_URL = process.env.LAKEHOUSE_URL || "http://localhost:8320";

export async function lakehouseIngest(
  table: string,
  data: Record<string, unknown>,
  options?: { tier?: "bronze" | "silver" | "gold"; source?: string }
): Promise<boolean> {
  try {
    const payload = {
      table,
      data,
      tier: options?.tier || "bronze",
      source: options?.source || "agentbanking-ts",
      timestamp: new Date().toISOString(),
    };
    const response = await fetch(`${LAKEHOUSE_URL}/v1/ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(5000),
    });
    return response.ok;
  } catch {
    return false;
  }
}

export async function lakehouseQuery(
  query: string,
  params?: Record<string, unknown>
): Promise<unknown[] | null> {
  try {
    const response = await fetch(`${LAKEHOUSE_URL}/v1/query`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sql: query, params }),
      signal: AbortSignal.timeout(30000),
    });
    if (!response.ok) return null;
    const result = await response.json() as { rows?: unknown[] };
    return result.rows || [];
  } catch {
    return null;
  }
}

export async function lakehouseBatchIngest(
  table: string,
  records: Record<string, unknown>[],
  options?: { tier?: "bronze" | "silver" | "gold"; source?: string }
): Promise<boolean> {
  try {
    const payload = {
      table,
      records,
      tier: options?.tier || "bronze",
      source: options?.source || "agentbanking-ts",
      timestamp: new Date().toISOString(),
    };
    const response = await fetch(`${LAKEHOUSE_URL}/v1/batch-ingest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(15000),
    });
    return response.ok;
  } catch {
    return false;
  }
}
