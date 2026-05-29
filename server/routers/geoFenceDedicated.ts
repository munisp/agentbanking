import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb } from "../db";
import { agents } from "../../drizzle/schema";
import { sql, eq, desc, count } from "drizzle-orm";
import {
  calculateFee,
  calculateCommission,
  calculateTax,
  calculateLatePenalty,
} from "../lib/domainCalculations";

const STATUS_TRANSITIONS: Record<string, string[]> = {
  pending: ["active", "completed", "cancelled", "rejected"],
  active: ["completed", "suspended", "cancelled"],
  completed: ["archived"],
  suspended: ["active", "cancelled"],
  cancelled: [],
  rejected: [],
  archived: [],
};

export const geoFenceDedicatedRouter = router({
  zones: protectedProcedure.query(async () => {
    const db = await getDb();
    if (!db) return { zones: [] };

    try {
      const agentsByLocation = await db
        .select({
          location: agents.location,
          agentCount: count(),
        })
        .from(agents)
        .groupBy(agents.location)
        .limit(50);

      return {
        zones: agentsByLocation.map(
          (r: { location: string | null; agentCount: number }, i: number) => ({
            id: `GZ-${String(i + 1).padStart(3, "0")}`,
            name: r.location ?? "Unknown",
            status: "active",
            agentCount: Number(r.agentCount),
          })
        ),
      };
    } catch {
      return { zones: [] };
    }
  }),

  agentLocations: protectedProcedure.query(async () => {
    const db = await getDb();
    if (!db) return { locations: [] };

    try {
      const activeAgents = await db
        .select({
          id: agents.id,
          name: agents.name,
          location: agents.location,
          lastLoginAt: agents.lastLoginAt,
        })
        .from(agents)
        .orderBy(desc(agents.lastLoginAt))
        .limit(100);

      return {
        locations: activeAgents.map(
          (a: {
            id: number;
            name: string;
            location: string | null;
            lastLoginAt: Date | null;
          }) => ({
            agentId: `AGT-${a.id}`,
            name: a.name,
            zone: a.location ?? "Unknown",
            lastSeen: a.lastLoginAt?.toISOString() ?? new Date().toISOString(),
          })
        ),
      };
    } catch {
      return { locations: [] };
    }
  }),

  analytics: protectedProcedure.query(async () => {
    const db = await getDb();
    if (!db) {
      return {
        totalZones: 0,
        activeZones: 0,
        totalAgentsTracked: 0,
        complianceRate: 0,
        onlineAgents: 0,
      };
    }

    try {
      const [agentStats] = await db
        .select({
          total: count(),
          active: sql<number>`COUNT(CASE WHEN ${agents.isActive} = true THEN 1 END)`,
          locations: sql<number>`COUNT(DISTINCT ${agents.location})`,
        })
        .from(agents);

      const totalAgents = Number(agentStats?.total ?? 0);
      const activeAgents = Number(agentStats?.active ?? 0);
      const totalZones = Number(agentStats?.locations ?? 0);

      return {
        totalZones,
        activeZones: totalZones,
        totalAgentsTracked: totalAgents,
        complianceRate:
          totalAgents > 0 ? Math.round((activeAgents / totalAgents) * 100) : 0,
        onlineAgents: activeAgents,
      };
    } catch {
      return {
        totalZones: 0,
        activeZones: 0,
        totalAgentsTracked: 0,
        complianceRate: 0,
        onlineAgents: 0,
      };
    }
  }),
});
