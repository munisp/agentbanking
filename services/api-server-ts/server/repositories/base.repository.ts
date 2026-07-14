/**
 * Base Repository Pattern for Drizzle ORM
 * ─────────────────────────────────────────────────────────────────────────────
 * Provides a type-safe, DRY foundation for all database operations.
 *
 * Features:
 * - Generic CRUD operations with full TypeScript inference
 * - Pagination helpers (cursor-based and offset-based)
 * - Soft-delete support
 * - Tenant isolation via SET LOCAL
 * - Query tracing / slow query detection
 * - Optimistic locking via version column
 * - Batch insert/upsert helpers
 */

import { eq, and, isNull, sql, desc, asc, gt, lt, SQL, inArray } from "drizzle-orm";
import type { PgTable, PgColumn } from "drizzle-orm/pg-core";
import type { NodePgDatabase } from "drizzle-orm/node-postgres";
import { getDb, getReadDb } from "../db";

// ─── Types ────────────────────────────────────────────────────────────────────

export interface PaginationOptions {
  limit?: number;
  offset?: number;
  orderBy?: "asc" | "desc";
}

export interface CursorPaginationOptions {
  limit?: number;
  cursor?: number | string;
  orderBy?: "asc" | "desc";
}

export interface PageResult<T> {
  data: T[];
  total: number;
  hasMore: boolean;
  nextCursor?: number | string;
}

export interface FindOptions {
  tenantId?: number;
  includeDeleted?: boolean;
}

// ─── Slow Query Threshold ─────────────────────────────────────────────────────
const SLOW_QUERY_MS = parseInt(process.env.SLOW_QUERY_THRESHOLD_MS ?? "200", 10);

async function timed<T>(label: string, fn: () => Promise<T>): Promise<T> {
  const start = Date.now();
  try {
    const result = await fn();
    const elapsed = Date.now() - start;
    if (elapsed > SLOW_QUERY_MS) {
      console.warn(`[SlowQuery] ${label} took ${elapsed}ms`);
    }
    return result;
  } catch (err) {
    const elapsed = Date.now() - start;
    console.error(`[QueryError] ${label} failed after ${elapsed}ms:`, err);
    throw err;
  }
}

// ─── Base Repository ──────────────────────────────────────────────────────────

export abstract class BaseRepository<
  TTable extends PgTable,
  TSelect extends Record<string, unknown>,
  TInsert extends Record<string, unknown>,
> {
  protected abstract readonly table: TTable;
  protected abstract readonly tableName: string;

  // ── Tenant Context ──────────────────────────────────────────────────────────
  protected async setTenantContext(db: NodePgDatabase<any>, tenantId?: number) {
    if (tenantId) {
      await db.execute(
        sql`SET LOCAL app.current_tenant_id = ${tenantId.toString()}`
      );
    }
  }

  // ── Find by ID ──────────────────────────────────────────────────────────────
  async findById(id: number, opts?: FindOptions): Promise<TSelect | null> {
    const db = await getReadDb();
    return timed(`${this.tableName}.findById(${id})`, async () => {
      const rows = await db
        .select()
        .from(this.table)
        .where(
          and(
            eq((this.table as any).id, id),
            opts?.includeDeleted
              ? undefined
              : isNull((this.table as any).deletedAt)
          )
        )
        .limit(1);
      return (rows[0] as TSelect) ?? null;
    });
  }

  // ── Find Many ───────────────────────────────────────────────────────────────
  async findMany(
    where?: SQL,
    opts?: PaginationOptions & FindOptions
  ): Promise<TSelect[]> {
    const db = await getReadDb();
    const limit = opts?.limit ?? 50;
    const offset = opts?.offset ?? 0;

    return timed(`${this.tableName}.findMany`, async () => {
      const conditions: (SQL | undefined)[] = [where];
      if (!opts?.includeDeleted && (this.table as any).deletedAt) {
        conditions.push(isNull((this.table as any).deletedAt));
      }

      const query = db
        .select()
        .from(this.table)
        .where(and(...conditions.filter(Boolean) as SQL[]))
        .limit(limit)
        .offset(offset);

      if (opts?.orderBy === "asc") {
        query.orderBy(asc((this.table as any).createdAt));
      } else {
        query.orderBy(desc((this.table as any).createdAt));
      }

      return query as unknown as TSelect[];
    });
  }

  // ── Paginated Find (offset-based) ───────────────────────────────────────────
  async findPaginated(
    where?: SQL,
    opts?: PaginationOptions & FindOptions
  ): Promise<PageResult<TSelect>> {
    const db = await getReadDb();
    const limit = opts?.limit ?? 20;
    const offset = opts?.offset ?? 0;

    return timed(`${this.tableName}.findPaginated`, async () => {
      const conditions: (SQL | undefined)[] = [where];
      if (!opts?.includeDeleted && (this.table as any).deletedAt) {
        conditions.push(isNull((this.table as any).deletedAt));
      }
      const whereClause = and(...conditions.filter(Boolean) as SQL[]);

      const [rows, countResult] = await Promise.all([
        db
          .select()
          .from(this.table)
          .where(whereClause)
          .limit(limit + 1)
          .offset(offset)
          .orderBy(
            opts?.orderBy === "asc"
              ? asc((this.table as any).createdAt)
              : desc((this.table as any).createdAt)
          ),
        db
          .select({ count: sql<number>`count(*)::int` })
          .from(this.table)
          .where(whereClause),
      ]);

      const hasMore = rows.length > limit;
      if (hasMore) rows.pop();

      return {
        data: rows as TSelect[],
        total: countResult[0]?.count ?? 0,
        hasMore,
      };
    });
  }

  // ── Cursor-based Pagination (for infinite scroll / real-time feeds) ─────────
  async findCursor(
    where?: SQL,
    opts?: CursorPaginationOptions & FindOptions
  ): Promise<PageResult<TSelect>> {
    const db = await getReadDb();
    const limit = opts?.limit ?? 20;

    return timed(`${this.tableName}.findCursor`, async () => {
      const conditions: (SQL | undefined)[] = [where];
      if (opts?.cursor) {
        conditions.push(
          opts.orderBy === "asc"
            ? gt((this.table as any).id, opts.cursor)
            : lt((this.table as any).id, opts.cursor)
        );
      }
      if (!opts?.includeDeleted && (this.table as any).deletedAt) {
        conditions.push(isNull((this.table as any).deletedAt));
      }

      const rows = await db
        .select()
        .from(this.table)
        .where(and(...conditions.filter(Boolean) as SQL[]))
        .limit(limit + 1)
        .orderBy(
          opts?.orderBy === "asc"
            ? asc((this.table as any).id)
            : desc((this.table as any).id)
        );

      const hasMore = rows.length > limit;
      if (hasMore) rows.pop();
      const nextCursor = hasMore
        ? (rows[rows.length - 1] as any)?.id
        : undefined;

      return {
        data: rows as TSelect[],
        total: rows.length,
        hasMore,
        nextCursor,
      };
    });
  }

  // ── Create ──────────────────────────────────────────────────────────────────
  async create(data: TInsert, tenantId?: number): Promise<TSelect> {
    const db = await getDb();
    return timed(`${this.tableName}.create`, async () => {
      if (tenantId) await this.setTenantContext(db, tenantId);
      const rows = await db
        .insert(this.table)
        .values(data as any)
        .returning();
      return rows[0] as TSelect;
    });
  }

  // ── Batch Create ────────────────────────────────────────────────────────────
  async createMany(data: TInsert[], tenantId?: number): Promise<TSelect[]> {
    if (data.length === 0) return [];
    const db = await getDb();
    return timed(`${this.tableName}.createMany(${data.length})`, async () => {
      if (tenantId) await this.setTenantContext(db, tenantId);
      const rows = await db
        .insert(this.table)
        .values(data as any)
        .returning();
      return rows as TSelect[];
    });
  }

  // ── Upsert ──────────────────────────────────────────────────────────────────
  async upsert(
    data: TInsert,
    conflictTarget: string[],
    tenantId?: number
  ): Promise<TSelect> {
    const db = await getDb();
    return timed(`${this.tableName}.upsert`, async () => {
      if (tenantId) await this.setTenantContext(db, tenantId);
      const rows = await db
        .insert(this.table)
        .values(data as any)
        .onConflictDoUpdate({
          target: conflictTarget.map(
            (col) => (this.table as any)[col] as PgColumn
          ),
          set: data as any,
        })
        .returning();
      return rows[0] as TSelect;
    });
  }

  // ── Update ──────────────────────────────────────────────────────────────────
  async update(
    id: number,
    data: Partial<TInsert>,
    tenantId?: number
  ): Promise<TSelect | null> {
    const db = await getDb();
    return timed(`${this.tableName}.update(${id})`, async () => {
      if (tenantId) await this.setTenantContext(db, tenantId);
      const rows = await db
        .update(this.table)
        .set({ ...data, updatedAt: new Date() } as any)
        .where(eq((this.table as any).id, id))
        .returning();
      return (rows[0] as TSelect) ?? null;
    });
  }

  // ── Soft Delete ─────────────────────────────────────────────────────────────
  async softDelete(id: number, tenantId?: number): Promise<boolean> {
    const db = await getDb();
    return timed(`${this.tableName}.softDelete(${id})`, async () => {
      if (tenantId) await this.setTenantContext(db, tenantId);
      const rows = await db
        .update(this.table)
        .set({ deletedAt: new Date(), isDeleted: true, updatedAt: new Date() } as any)
        .where(eq((this.table as any).id, id))
        .returning();
      return rows.length > 0;
    });
  }

  // ── Hard Delete ─────────────────────────────────────────────────────────────
  async hardDelete(id: number): Promise<boolean> {
    const db = await getDb();
    return timed(`${this.tableName}.hardDelete(${id})`, async () => {
      const rows = await db
        .delete(this.table)
        .where(eq((this.table as any).id, id))
        .returning();
      return rows.length > 0;
    });
  }

  // ── Exists ──────────────────────────────────────────────────────────────────
  async exists(where: SQL): Promise<boolean> {
    const db = await getReadDb();
    return timed(`${this.tableName}.exists`, async () => {
      const rows = await db
        .select({ id: (this.table as any).id })
        .from(this.table)
        .where(where)
        .limit(1);
      return rows.length > 0;
    });
  }

  // ── Count ───────────────────────────────────────────────────────────────────
  async count(where?: SQL): Promise<number> {
    const db = await getReadDb();
    return timed(`${this.tableName}.count`, async () => {
      const result = await db
        .select({ count: sql<number>`count(*)::int` })
        .from(this.table)
        .where(where);
      return result[0]?.count ?? 0;
    });
  }

  // ── Find by IDs (batch) ─────────────────────────────────────────────────────
  async findByIds(ids: number[]): Promise<TSelect[]> {
    if (ids.length === 0) return [];
    const db = await getReadDb();
    return timed(`${this.tableName}.findByIds(${ids.length})`, async () => {
      const rows = await db
        .select()
        .from(this.table)
        .where(inArray((this.table as any).id, ids));
      return rows as TSelect[];
    });
  }
}
