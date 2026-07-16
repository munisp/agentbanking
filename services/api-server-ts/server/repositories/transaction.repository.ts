/**
 * Transaction Repository
 * ─────────────────────────────────────────────────────────────────────────────
 * All database operations for the transactions table.
 * Includes analytics queries, idempotency checks, and bulk operations.
 */

import {
  eq, and, gte, lte, sql, desc, inArray, isNull, ne,
} from "drizzle-orm";
import { transactions, idempotencyKeys } from "../../drizzle/schema";
import type { Transaction, InsertTransaction } from "../../drizzle/schema";
import { BaseRepository, type PaginationOptions } from "./base.repository";
import { getDb, getReadDb } from "../db";

export interface TransactionFilters {
  agentId?: number;
  tenantId?: number;
  status?: string | string[];
  type?: string | string[];
  fromDate?: Date;
  toDate?: Date;
  minAmount?: string;
  maxAmount?: string;
  fraudScoreMin?: number;
  search?: string;
}

export interface TransactionAnalytics {
  totalCount: number;
  totalVolume: string;
  avgAmount: string;
  successRate: number;
  byType: Array<{ type: string; count: number; volume: string }>;
  byStatus: Array<{ status: string; count: number }>;
  hourlyDistribution: Array<{ hour: number; count: number; volume: string }>;
}

export class TransactionRepository extends BaseRepository<
  typeof transactions,
  Transaction,
  InsertTransaction
> {
  protected readonly table = transactions;
  protected readonly tableName = "transactions";

  // ── Find by txRef (unique) ──────────────────────────────────────────────────
  async findByRef(txRef: string): Promise<Transaction | null> {
    const db = await getReadDb();
    const rows = await db
      .select()
      .from(transactions)
      .where(eq(transactions.txRef, txRef))
      .limit(1);
    return rows[0] ?? null;
  }

  // ── Filtered list with full-text search ────────────────────────────────────
  async findFiltered(
    filters: TransactionFilters,
    pagination?: PaginationOptions
  ): Promise<{ data: Transaction[]; total: number }> {
    const db = await getReadDb();
    const limit = pagination?.limit ?? 20;
    const offset = pagination?.offset ?? 0;

    const conditions: ReturnType<typeof sql>[] = [];

    if (filters.agentId)
      conditions.push(eq(transactions.agentId, filters.agentId));
    if (filters.tenantId)
      conditions.push(eq(transactions.tenantId, filters.tenantId));
    if (filters.status) {
      const statuses = Array.isArray(filters.status)
        ? filters.status
        : [filters.status];
      conditions.push(inArray(transactions.status, statuses as any));
    }
    if (filters.type) {
      const types = Array.isArray(filters.type) ? filters.type : [filters.type];
      conditions.push(inArray(transactions.type, types as any));
    }
    if (filters.fromDate)
      conditions.push(gte(transactions.createdAt, filters.fromDate));
    if (filters.toDate)
      conditions.push(lte(transactions.createdAt, filters.toDate));
    if (filters.minAmount)
      conditions.push(
        sql`"amount" >= ${filters.minAmount}::numeric`
      );
    if (filters.maxAmount)
      conditions.push(
        sql`"amount" <= ${filters.maxAmount}::numeric`
      );
    if (filters.fraudScoreMin)
      conditions.push(
        sql`"fraudScore" >= ${filters.fraudScoreMin}`
      );
    if (filters.search)
      conditions.push(
        sql`"search_vector" @@ plainto_tsquery('english', ${filters.search})`
      );

    const whereClause = and(...conditions);

    const [rows, countResult] = await Promise.all([
      db
        .select()
        .from(transactions)
        .where(whereClause)
        .orderBy(desc(transactions.createdAt))
        .limit(limit)
        .offset(offset),
      db
        .select({ count: sql<number>`count(*)::int` })
        .from(transactions)
        .where(whereClause),
    ]);

    return {
      data: rows as Transaction[],
      total: countResult[0]?.count ?? 0,
    };
  }

  // ── Analytics for agent dashboard ───────────────────────────────────────────
  async getAnalytics(
    agentId: number,
    fromDate: Date,
    toDate: Date
  ): Promise<TransactionAnalytics> {
    const db = await getReadDb();
    const where = and(
      eq(transactions.agentId, agentId),
      gte(transactions.createdAt, fromDate),
      lte(transactions.createdAt, toDate)
    );

    const [summary, byType, byStatus, hourly] = await Promise.all([
      db
        .select({
          totalCount: sql<number>`count(*)::int`,
          totalVolume: sql<string>`COALESCE(sum("amount"), 0)::text`,
          avgAmount: sql<string>`COALESCE(avg("amount"), 0)::text`,
          successCount: sql<number>`count(*) FILTER (WHERE "status" = 'completed')::int`,
        })
        .from(transactions)
        .where(where),

      db
        .select({
          type: transactions.type,
          count: sql<number>`count(*)::int`,
          volume: sql<string>`COALESCE(sum("amount"), 0)::text`,
        })
        .from(transactions)
        .where(where)
        .groupBy(transactions.type),

      db
        .select({
          status: transactions.status,
          count: sql<number>`count(*)::int`,
        })
        .from(transactions)
        .where(where)
        .groupBy(transactions.status),

      db
        .select({
          hour: sql<number>`EXTRACT(HOUR FROM "createdAt")::int`,
          count: sql<number>`count(*)::int`,
          volume: sql<string>`COALESCE(sum("amount"), 0)::text`,
        })
        .from(transactions)
        .where(where)
        .groupBy(sql`EXTRACT(HOUR FROM "createdAt")`),
    ]);

    const s = summary[0];
    return {
      totalCount: s?.totalCount ?? 0,
      totalVolume: s?.totalVolume ?? "0",
      avgAmount: s?.avgAmount ?? "0",
      successRate:
        s?.totalCount > 0
          ? Math.round((s.successCount / s.totalCount) * 100)
          : 0,
      byType: byType as any,
      byStatus: byStatus as any,
      hourlyDistribution: hourly as any,
    };
  }

  // ── Idempotency check ───────────────────────────────────────────────────────
  async findByIdempotencyKey(
    key: string
  ): Promise<Transaction | null> {
    const db = await getReadDb();
    // Look up the idempotency key record
    const ikRows = await db
      .select()
      .from(idempotencyKeys)
      .where(
        and(
          eq(idempotencyKeys.idempotencyKey, key),
          sql`"expiresAt" > NOW()`
        )
      )
      .limit(1);

    if (!ikRows[0]?.responseBody) return null;

    // Return the cached response as a synthetic Transaction
    return ikRows[0].responseBody as unknown as Transaction;
  }

  // ── Daily volume for velocity check ─────────────────────────────────────────
  async getDailyVolume(agentId: number): Promise<{ count: number; volume: string }> {
    const db = await getReadDb();
    const result = await db
      .select({
        count: sql<number>`count(*)::int`,
        volume: sql<string>`COALESCE(sum("amount"), 0)::text`,
      })
      .from(transactions)
      .where(
        and(
          eq(transactions.agentId, agentId),
          sql`"createdAt" >= CURRENT_DATE`,
          ne(transactions.status, "failed" as any)
        )
      );
    return result[0] ?? { count: 0, volume: "0" };
  }

  // ── High-fraud transactions (uses partial index) ────────────────────────────
  async findHighFraud(
    agentId?: number,
    limit = 50
  ): Promise<Transaction[]> {
    const db = await getReadDb();
    const conditions = [sql`"fraudScore" > 70`];
    if (agentId) conditions.push(eq(transactions.agentId, agentId));
    return db
      .select()
      .from(transactions)
      .where(and(...conditions))
      .orderBy(desc(sql`"fraudScore"`))
      .limit(limit) as unknown as Transaction[];
  }

  // ── Reversal eligibility check ──────────────────────────────────────────────
  async isReversalEligible(txId: number): Promise<boolean> {
    const db = await getReadDb();
    const rows = await db
      .select({ id: transactions.id })
      .from(transactions)
      .where(
        and(
          eq(transactions.id, txId),
          eq(transactions.status, "completed" as any),
          sql`"createdAt" >= NOW() - INTERVAL '24 hours'`,
          sql`NOT EXISTS (
            SELECT 1 FROM "reversal_requests" rr
            WHERE rr."originalTxId" = "transactions"."id"
            AND rr."status" IN ('pending', 'approved', 'processed')
          )`
        )
      )
      .limit(1);
    return rows.length > 0;
  }
}

export const transactionRepository = new TransactionRepository();
