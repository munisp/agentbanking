/**
 * Agent Repository
 * ─────────────────────────────────────────────────────────────────────────────
 * All database operations for the agents table.
 * Replaces scattered db.select().from(agents)... calls across router files.
 */

import { eq, and, ilike, or, sql, desc, isNull } from "drizzle-orm";
import { agents, transactions, fraudAlerts, kycSessions } from "../../drizzle/schema";
import type { Agent, InsertAgent } from "../../drizzle/schema";
import { BaseRepository } from "./base.repository";
import { getDb, getReadDb } from "../db";

export class AgentRepository extends BaseRepository<
  typeof agents,
  Agent,
  InsertAgent
> {
  protected readonly table = agents;
  protected readonly tableName = "agents";

  // ── Find by agent code ──────────────────────────────────────────────────────
  async findByCode(agentCode: string): Promise<Agent | null> {
    const db = await getReadDb();
    const rows = await db
      .select()
      .from(agents)
      .where(eq(agents.agentCode, agentCode))
      .limit(1);
    return rows[0] ?? null;
  }

  // ── Find by phone ───────────────────────────────────────────────────────────
  async findByPhone(phone: string): Promise<Agent | null> {
    const db = await getReadDb();
    const rows = await db
      .select()
      .from(agents)
      .where(eq(agents.phone, phone))
      .limit(1);
    return rows[0] ?? null;
  }

  // ── Full-text search (uses GIN index on search_vector) ──────────────────────
  async search(
    query: string,
    opts?: { limit?: number; tenantId?: number }
  ): Promise<Agent[]> {
    const db = await getReadDb();
    const limit = opts?.limit ?? 20;

    const conditions = [
      sql`"search_vector" @@ plainto_tsquery('english', ${query})`,
      isNull(agents.deletedAt),
    ];
    if (opts?.tenantId) {
      conditions.push(eq(agents.tenantId, opts.tenantId));
    }

    return db
      .select()
      .from(agents)
      .where(and(...conditions))
      .orderBy(
        sql`ts_rank("search_vector", plainto_tsquery('english', ${query})) DESC`
      )
      .limit(limit) as unknown as Agent[];
  }

  // ── Find by tier ────────────────────────────────────────────────────────────
  async findByTier(
    tier: "Bronze" | "Silver" | "Gold" | "Platinum",
    tenantId?: number
  ): Promise<Agent[]> {
    const db = await getReadDb();
    const conditions = [eq(agents.tier, tier), isNull(agents.deletedAt)];
    if (tenantId) conditions.push(eq(agents.tenantId, tenantId));
    return db
      .select()
      .from(agents)
      .where(and(...conditions))
      .orderBy(desc(agents.createdAt)) as unknown as Agent[];
  }

  // ── Dashboard summary (float balance, commission, tx count) ─────────────────
  async getDashboardSummary(agentId: number) {
    const db = await getReadDb();
    const [agent, txStats] = await Promise.all([
      db.select().from(agents).where(eq(agents.id, agentId)).limit(1),
      db
        .select({
          totalTx: sql<number>`count(*)::int`,
          totalVolume: sql<string>`COALESCE(sum("amount"), 0)::text`,
          todayTx: sql<number>`count(*) FILTER (WHERE "createdAt" >= CURRENT_DATE)::int`,
          todayVolume: sql<string>`COALESCE(sum("amount") FILTER (WHERE "createdAt" >= CURRENT_DATE), 0)::text`,
        })
        .from(transactions)
        .where(
          and(
            eq(transactions.agentId, agentId),
            sql`"createdAt" >= NOW() - INTERVAL '30 days'`
          )
        ),
    ]);

    return {
      agent: agent[0] ?? null,
      stats: txStats[0] ?? null,
    };
  }

  // ── Update float balance (atomic) ───────────────────────────────────────────
  async adjustFloatBalance(
    agentId: number,
    delta: string,
    operation: "credit" | "debit"
  ): Promise<Agent | null> {
    const db = await getDb();
    const op = operation === "credit" ? sql`+` : sql`-`;
    const rows = await db
      .update(agents)
      .set({
        floatBalance: sql`"floatBalance" ${op} ${delta}::numeric`,
        updatedAt: new Date(),
      } as any)
      .where(
        and(
          eq(agents.id, agentId),
          operation === "debit"
            ? sql`"floatBalance" >= ${delta}::numeric`
            : sql`true`
        )
      )
      .returning();
    return rows[0] ?? null;
  }

  // ── Suspend agent ───────────────────────────────────────────────────────────
  async suspend(
    agentId: number,
    reason: string,
    suspendedBy: number
  ): Promise<Agent | null> {
    const db = await getDb();
    const rows = await db
      .update(agents)
      .set({
        isActive: false,
        suspensionReason: reason,
        suspendedBy,
        suspendedAt: new Date(),
        updatedAt: new Date(),
      } as any)
      .where(eq(agents.id, agentId))
      .returning();
    return rows[0] ?? null;
  }

  // ── Get agents with pending KYC ─────────────────────────────────────────────
  async findWithPendingKyc(tenantId?: number): Promise<Agent[]> {
    const db = await getReadDb();
    const conditions = [
      sql`EXISTS (
        SELECT 1 FROM "kyc_sessions" ks
        WHERE ks."agentId" = "agents"."id"
        AND ks."status" IN ('pending', 'in_review')
      )`,
      isNull(agents.deletedAt),
    ];
    if (tenantId) conditions.push(eq(agents.tenantId, tenantId));
    return db
      .select()
      .from(agents)
      .where(and(...conditions))
      .orderBy(desc(agents.createdAt)) as unknown as Agent[];
  }
}

// Singleton instance
export const agentRepository = new AgentRepository();
