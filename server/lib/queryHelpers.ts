/**
 * Drizzle ORM Query Helpers
 * ─────────────────────────────────────────────────────────────────────────────
 * Reusable query building blocks for common patterns across the codebase.
 *
 * Includes:
 * - Date range helpers
 * - Pagination builders
 * - Aggregation helpers
 * - Tenant context management
 * - Idempotency helpers
 * - Batch operation helpers
 * - Optimistic locking
 */

import {
  sql, eq, and, gte, lte, desc, asc, inArray, isNull, isNotNull,
  type SQL,
} from "drizzle-orm";
import type { NodePgDatabase } from "drizzle-orm/node-postgres";
import { getDb, getReadDb } from "../db";

// ─── Date Range Helpers ───────────────────────────────────────────────────────

export type DateRange = "today" | "yesterday" | "week" | "month" | "quarter" | "year";

export function dateRangeCondition(
  column: SQL,
  range: DateRange
): SQL {
  const ranges: Record<DateRange, SQL> = {
    today:     sql`${column} >= CURRENT_DATE`,
    yesterday: sql`${column} >= CURRENT_DATE - INTERVAL '1 day' AND ${column} < CURRENT_DATE`,
    week:      sql`${column} >= DATE_TRUNC('week', NOW())`,
    month:     sql`${column} >= DATE_TRUNC('month', NOW())`,
    quarter:   sql`${column} >= DATE_TRUNC('quarter', NOW())`,
    year:      sql`${column} >= DATE_TRUNC('year', NOW())`,
  };
  return ranges[range];
}

export function betweenDates(column: any, from: Date, to: Date): SQL {
  return and(gte(column, from), lte(column, to)) as SQL;
}

// ─── Pagination Helpers ───────────────────────────────────────────────────────

export interface PaginationInput {
  page?: number;
  limit?: number;
  cursor?: number;
}

export function paginationToOffset(input: PaginationInput): {
  limit: number;
  offset: number;
} {
  const limit = Math.min(Math.max(input.limit ?? 20, 1), 100);
  const page = Math.max(input.page ?? 1, 1);
  return { limit, offset: (page - 1) * limit };
}

export function buildPaginationMeta(
  total: number,
  limit: number,
  offset: number
) {
  const page = Math.floor(offset / limit) + 1;
  const totalPages = Math.ceil(total / limit);
  return {
    total,
    page,
    limit,
    totalPages,
    hasNextPage: page < totalPages,
    hasPrevPage: page > 1,
  };
}

// ─── Aggregation Helpers ──────────────────────────────────────────────────────

export const agg = {
  count: () => sql<number>`count(*)::int`,
  countDistinct: (col: SQL) => sql<number>`count(DISTINCT ${col})::int`,
  sum: (col: SQL) => sql<string>`COALESCE(sum(${col}), 0)::text`,
  avg: (col: SQL) => sql<string>`COALESCE(avg(${col}), 0)::text`,
  min: (col: SQL) => sql<string>`min(${col})::text`,
  max: (col: SQL) => sql<string>`max(${col})::text`,
  sumNumeric: (col: SQL) => sql<number>`COALESCE(sum(${col}), 0)::numeric`,
  percentile: (col: SQL, p: number) =>
    sql<string>`percentile_cont(${p}) WITHIN GROUP (ORDER BY ${col})::text`,
};

// ─── Tenant Context Management ────────────────────────────────────────────────

/**
 * Execute a callback within a tenant context.
 * Automatically sets app.current_tenant_id for RLS policies.
 */
export async function withTenant<T>(
  tenantId: number,
  fn: (db: NodePgDatabase<any>) => Promise<T>
): Promise<T> {
  const db = await getDb();
  return db.transaction(async (tx) => {
    await tx.execute(
      sql`SET LOCAL app.current_tenant_id = ${tenantId.toString()}`
    );
    return fn(tx as any);
  });
}

/**
 * Execute a read-only callback within a tenant context.
 */
export async function withTenantRead<T>(
  tenantId: number,
  fn: (db: NodePgDatabase<any>) => Promise<T>
): Promise<T> {
  const db = await getReadDb();
  await db.execute(
    sql`SET LOCAL app.current_tenant_id = ${tenantId.toString()}`
  );
  return fn(db as any);
}

// ─── Idempotency Helpers ──────────────────────────────────────────────────────

/**
 * Execute an operation with idempotency guarantee.
 * If the key already exists and hasn't expired, returns the cached response.
 * Otherwise executes the operation and caches the result.
 */
export async function withIdempotency<T>(
  key: string,
  ttlSeconds: number,
  operation: () => Promise<T>
): Promise<{ result: T; cached: boolean }> {
  const db = await getDb();

  // Check for existing idempotency key
  const existing = await db.execute(
    sql`SELECT "responseBody", "statusCode"
        FROM "idempotency_keys"
        WHERE "idempotencyKey" = ${key}
        AND "expiresAt" > NOW()
        LIMIT 1`
  );

  if (existing.rows.length > 0) {
    return {
      result: existing.rows[0].responseBody as T,
      cached: true,
    };
  }

  // Execute the operation
  const result = await operation();

  // Store the result
  await db.execute(
    sql`INSERT INTO "idempotency_keys"
        ("idempotencyKey", "responseBody", "statusCode", "expiresAt", "createdAt")
        VALUES (
          ${key},
          ${JSON.stringify(result)}::jsonb,
          200,
          NOW() + INTERVAL '${sql.raw(ttlSeconds.toString())} seconds',
          NOW()
        )
        ON CONFLICT ("idempotencyKey") DO NOTHING`
  );

  return { result, cached: false };
}

// ─── Batch Operation Helpers ──────────────────────────────────────────────────

/**
 * Process items in batches to avoid parameter limit issues.
 */
export async function batchProcess<T, R>(
  items: T[],
  batchSize: number,
  processor: (batch: T[]) => Promise<R[]>
): Promise<R[]> {
  const results: R[] = [];
  for (let i = 0; i < items.length; i += batchSize) {
    const batch = items.slice(i, i + batchSize);
    const batchResults = await processor(batch);
    results.push(...batchResults);
  }
  return results;
}

// ─── Optimistic Locking ───────────────────────────────────────────────────────

/**
 * Update a record with optimistic locking via version column.
 * Returns null if the version has changed (concurrent update detected).
 */
export async function updateWithVersion<T>(
  tableName: string,
  id: number,
  currentVersion: number,
  updates: Record<string, unknown>
): Promise<T | null> {
  const db = await getDb();
  const setClause = Object.entries(updates)
    .map(([k]) => `"${k}" = $${k}`)
    .join(", ");

  const result = await db.execute(
    sql`UPDATE "${sql.raw(tableName)}"
        SET ${sql.raw(
          Object.entries(updates)
            .map(([k, v]) => `"${k}" = ${JSON.stringify(v)}`)
            .join(", ")
        )},
            "version" = "version" + 1,
            "updatedAt" = NOW()
        WHERE "id" = ${id}
        AND "version" = ${currentVersion}
        RETURNING *`
  );

  return (result.rows[0] as T) ?? null;
}

// ─── JSONB Query Helpers ──────────────────────────────────────────────────────

/**
 * Build a JSONB containment query (@> operator).
 * Requires GIN index on the column.
 */
export function jsonbContains(column: SQL, value: Record<string, unknown>): SQL {
  return sql`${column} @> ${JSON.stringify(value)}::jsonb`;
}

/**
 * Extract a JSONB field value.
 */
export function jsonbGet(column: SQL, path: string): SQL {
  return sql`${column}->>${path}`;
}

/**
 * Check if JSONB array contains a value.
 */
export function jsonbArrayContains(column: SQL, value: unknown): SQL {
  return sql`${column} @> ${JSON.stringify([value])}::jsonb`;
}

// ─── Full-Text Search Helpers ─────────────────────────────────────────────────

/**
 * Build a full-text search condition using the search_vector column.
 * Requires GIN index on search_vector.
 */
export function ftsMatch(query: string, language = "english"): SQL {
  return sql`"search_vector" @@ plainto_tsquery(${language}, ${query})`;
}

/**
 * Full-text search with ranking.
 */
export function ftsRank(query: string, language = "english"): SQL {
  return sql`ts_rank("search_vector", plainto_tsquery(${language}, ${query}))`;
}

// ─── Window Function Helpers ──────────────────────────────────────────────────

export const window = {
  rowNumber: () => sql<number>`ROW_NUMBER() OVER ()`,
  rank: (orderBy: SQL) => sql<number>`RANK() OVER (ORDER BY ${orderBy})`,
  lag: (col: SQL, offset = 1) => sql`LAG(${col}, ${offset}) OVER ()`,
  lead: (col: SQL, offset = 1) => sql`LEAD(${col}, ${offset}) OVER ()`,
  runningSum: (col: SQL, partitionBy?: SQL) =>
    partitionBy
      ? sql`SUM(${col}) OVER (PARTITION BY ${partitionBy} ORDER BY "createdAt")`
      : sql`SUM(${col}) OVER (ORDER BY "createdAt")`,
};

// ─── Upsert Helper ────────────────────────────────────────────────────────────

/**
 * Type-safe upsert with conflict resolution.
 */
export async function upsertOne<T>(
  tableName: string,
  data: Record<string, unknown>,
  conflictColumns: string[],
  updateColumns?: string[]
): Promise<T> {
  const db = await getDb();
  const cols = Object.keys(data);
  const vals = Object.values(data);

  const colList = cols.map((c) => `"${c}"`).join(", ");
  const valList = vals.map((_, i) => `$${i + 1}`).join(", ");
  const conflictList = conflictColumns.map((c) => `"${c}"`).join(", ");
  const updateCols = updateColumns ?? cols.filter((c) => !conflictColumns.includes(c));
  const updateSet = updateCols
    .map((c) => `"${c}" = EXCLUDED."${c}"`)
    .join(", ");

  const result = await db.execute(
    sql.raw(
      `INSERT INTO "${tableName}" (${colList})
       VALUES (${vals.map((v) => `'${JSON.stringify(v)}'`).join(", ")})
       ON CONFLICT (${conflictList})
       DO UPDATE SET ${updateSet}, "updatedAt" = NOW()
       RETURNING *`
    )
  );

  return result.rows[0] as T;
}

// ─── Explain Analyze Helper (development only) ───────────────────────────────

export async function explainAnalyze(query: SQL): Promise<string> {
  if (process.env.NODE_ENV === "production") {
    throw new Error("explainAnalyze is not allowed in production");
  }
  const db = await getDb();
  const result = await db.execute(sql`EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) ${query}`);
  return result.rows.map((r: any) => r["QUERY PLAN"]).join("\n");
}
