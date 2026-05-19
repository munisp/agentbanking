/**
 * geofencing.ts
 * ─────────────────────────────────────────────────────────────────────────────
 * Geofencing procedures for the POS Shell.
 *
 * Architecture:
 *  - Zone CRUD (create/update/delete/list) → platform geofencing service
 *    (supports Circle AND Polygon zones, 8 zone types, LGA/state metadata)
 *  - Agent assignment → local PostgreSQL (POS Shell owns agent↔zone mapping)
 *  - Location reporting → platform geofencing service (primary) with local
 *    device_locations record for audit trail
 *  - Geofence check → platform service (authoritative) with local fallback
 *    using Haversine formula when platform is unreachable
 *  - Fraud alert + Socket.IO emit → local (POS Shell owns real-time events)
 *  - Compliance reports → local (POS Shell owns PDF generation)
 *
 * Fail-open: if the platform service is unreachable, all zone checks fall
 * back to the local haversine implementation so transactions are never
 * blocked by a network partition.
 */

import { TRPCError } from "@trpc/server";
import { z } from "zod";
import { eq, and, desc, gte, sql } from "drizzle-orm";
import { adminProcedure, protectedProcedure, router } from "../_core/trpc";
import { getDb } from "../db";
import {
  geofenceZones,
  agentGeofenceZones,
  deviceLocations,
  fraudAlerts,
  auditLog,
  agents,
} from "../../drizzle/schema";
import { getIO } from "../socketSingleton";
import { geofencingPlatform, PlatformError } from "../_core/platformClient.js";

// ─── Haversine distance (metres) — local fallback ────────────────────────────
function haversineMetres(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number
): number {
  const R = 6_371_000;
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// ─── Helper: extract Keycloak access token from context ──────────────────────
function getToken(ctx: { req?: { cookies?: Record<string, string> } }): string {
  return ctx.req?.cookies?.["kc_access_token"] ?? "";
}

// ─── Zone type enum (matches platform service) ────────────────────────────────
const ZONE_TYPES = [
  "AGENT_OPERATING_AREA",
  "MERCHANT_DELIVERY_ZONE",
  "RESTRICTED_ZONE",
  "HIGH_RISK_AREA",
  "PREMIUM_ZONE",
  "MARKET_ZONE",
  "CAMPUS_ZONE",
  "INDUSTRIAL_ZONE",
] as const;

export const geofencingRouter = router({
  // ── Admin: list all zones ──────────────────────────────────────────────────
  // Always returns local DB rows (authoritative for agent assignments).
  // Platform zone data is synced on create/update; local DB is the source of truth.
  listZones: adminProcedure.query(async () => {
    const db = (await getDb())!;
    if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });
    return db
      .select()
      .from(geofenceZones)
      .orderBy(desc(geofenceZones.createdAt))
      .limit(100);
  }),

  // ── Admin: create zone (Circle or Polygon) ─────────────────────────────────
  createZone: adminProcedure
    .input(
      z.object({
        name: z.string().min(2).max(200),
        description: z.string().optional(),
        zoneType: z.enum(ZONE_TYPES).default("AGENT_OPERATING_AREA"),
        // Circle geometry
        latitude: z.number().min(-90).max(90).optional(),
        longitude: z.number().min(-180).max(180).optional(),
        radiusMetres: z.number().int().min(50).max(100_000).default(500),
        // Polygon geometry (GeoJSON coordinates array)
        polygonCoordinates: z
          .array(z.array(z.tuple([z.number(), z.number()])))
          .optional(),
        // Metadata
        state: z.string().optional(),
        lga: z.string().optional(),
        alertOnEntry: z.boolean().default(false),
        alertOnExit: z.boolean().default(true),
      })
    )
    .mutation(async ({ ctx, input }) => {
      try {
        const db = (await getDb())!;
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

        const isPolygon = !!input.polygonCoordinates?.length;
        const geometryType = isPolygon ? "Polygon" : "Circle";

        // ── Forward to platform service ─────────────────────────────────────────
        let platformZoneId: string | null = null;
        try {
          const token = getToken(ctx);
          const platformPayload: Record<string, unknown> = {
            name: input.name,
            description: input.description,
            zone_type: input.zoneType,
            geometry_type: geometryType,
            alert_on_entry: input.alertOnEntry,
            alert_on_exit: input.alertOnExit,
            state: input.state,
            lga: input.lga,
            created_by: ctx.user.name ?? ctx.user.keycloakSub,
          };
          if (isPolygon) {
            platformPayload.polygon_coordinates = input.polygonCoordinates;
          } else {
            platformPayload.center_lat = input.latitude;
            platformPayload.center_lng = input.longitude;
            platformPayload.radius_m = input.radiusMetres;
          }
          const resp = (await geofencingPlatform.createZone(
            platformPayload,
            token
          )) as { zone_id?: string };
          platformZoneId = resp.zone_id ?? null;
        } catch (err) {
          if (!(err instanceof PlatformError)) throw err;
          console.warn(
            "[geofencing] platform zone create failed, storing locally:",
            (err as Error).message
          );
        }

        // ── Always persist locally (source of truth for agent assignments) ──────
        const [zone] = await db
          .insert(geofenceZones)
          .values({
            name: input.name,
            description: input.description ?? null,
            latitude: String(input.latitude ?? 0),
            longitude: String(input.longitude ?? 0),
            radiusMetres: input.radiusMetres,
            isActive: true,
            createdBy: ctx.user.name ?? ctx.user.keycloakSub,
            // Store platform zone ID and polygon for reference
            ...(platformZoneId ? { platformZoneId } : {}),
            ...(isPolygon
              ? { polygonCoordinates: JSON.stringify(input.polygonCoordinates) }
              : {}),
            ...(input.zoneType !== "AGENT_OPERATING_AREA"
              ? { zoneType: input.zoneType }
              : {}),
          })
          .returning();

        await db.insert(auditLog).values({
          action: "GEOFENCE_ZONE_CREATED",
          resource: "geofence_zones",
          resourceId: String(zone.id),
          status: "success",
          metadata: {
            name: input.name,
            geometryType,
            radiusMetres: input.radiusMetres,
            zoneType: input.zoneType,
            platformZoneId,
          },
        });
        return zone;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // ── Admin: update zone ─────────────────────────────────────────────────────
  updateZone: adminProcedure
    .input(
      z.object({
        id: z.number().int(),
        name: z.string().min(2).max(200).optional(),
        description: z.string().optional(),
        zoneType: z.enum(ZONE_TYPES).optional(),
        latitude: z.number().min(-90).max(90).optional(),
        longitude: z.number().min(-180).max(180).optional(),
        radiusMetres: z.number().int().min(50).max(100_000).optional(),
        polygonCoordinates: z
          .array(z.array(z.tuple([z.number(), z.number()])))
          .optional(),
        isActive: z.boolean().optional(),
        alertOnEntry: z.boolean().optional(),
        alertOnExit: z.boolean().optional(),
      })
    )
    .mutation(async ({ ctx, input }) => {
      try {
        const db = (await getDb())!;
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

        // Get existing zone for platform zone ID
        const [existing] = await db
          .select()
          .from(geofenceZones)
          .where(eq(geofenceZones.id, input.id))
          .limit(100);
        if (!existing) throw new TRPCError({ code: "NOT_FOUND" });

        // Forward to platform if we have a platform zone ID
        const platformZoneId = (existing as Record<string, unknown>)
          .platformZoneId as string | null;
        if (platformZoneId) {
          try {
            const token = getToken(ctx);
            const platformPayload: Record<string, unknown> = {};
            if (input.name !== undefined) platformPayload.name = input.name;
            if (input.description !== undefined)
              platformPayload.description = input.description;
            if (input.zoneType !== undefined)
              platformPayload.zone_type = input.zoneType;
            if (input.latitude !== undefined)
              platformPayload.center_lat = input.latitude;
            if (input.longitude !== undefined)
              platformPayload.center_lng = input.longitude;
            if (input.radiusMetres !== undefined)
              platformPayload.radius_m = input.radiusMetres;
            if (input.polygonCoordinates !== undefined)
              platformPayload.polygon_coordinates = input.polygonCoordinates;
            if (input.isActive !== undefined)
              platformPayload.is_active = input.isActive;
            if (input.alertOnEntry !== undefined)
              platformPayload.alert_on_entry = input.alertOnEntry;
            if (input.alertOnExit !== undefined)
              platformPayload.alert_on_exit = input.alertOnExit;
            await geofencingPlatform.updateZone(
              platformZoneId,
              platformPayload,
              token
            );
          } catch (err) {
            if (!(err instanceof PlatformError)) throw err;
            console.warn(
              "[geofencing] platform zone update failed:",
              (err as Error).message
            );
          }
        }

        // Always update local DB
        const updates: Record<string, unknown> = { updatedAt: new Date() };
        if (input.name !== undefined) updates.name = input.name;
        if (input.description !== undefined)
          updates.description = input.description;
        if (input.latitude !== undefined)
          updates.latitude = String(input.latitude);
        if (input.longitude !== undefined)
          updates.longitude = String(input.longitude);
        if (input.radiusMetres !== undefined)
          updates.radiusMetres = input.radiusMetres;
        if (input.isActive !== undefined) updates.isActive = input.isActive;
        if (input.zoneType !== undefined) updates.zoneType = input.zoneType;
        if (input.polygonCoordinates !== undefined)
          updates.polygonCoordinates = JSON.stringify(input.polygonCoordinates);

        const [zone] = await db
          .update(geofenceZones)
          .set(updates)
          .where(eq(geofenceZones.id, input.id))
          .returning();
        return zone;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // ── Admin: delete zone ─────────────────────────────────────────────────────
  deleteZone: adminProcedure
    .input(z.object({ id: z.number().int() }))
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });
        await db
          .delete(agentGeofenceZones)
          .where(eq(agentGeofenceZones.zoneId, input.id));
        await db.delete(geofenceZones).where(eq(geofenceZones.id, input.id));
        return { success: true };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // ── Admin: assign agent to zone ────────────────────────────────────────────
  assignAgentToZone: adminProcedure
    .input(z.object({ agentId: z.number().int(), zoneId: z.number().int() }))
    .mutation(async ({ ctx, input }) => {
      try {
        const db = (await getDb())!;
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });
        const existing = await db
          .select()
          .from(agentGeofenceZones)
          .where(
            and(
              eq(agentGeofenceZones.agentId, input.agentId),
              eq(agentGeofenceZones.zoneId, input.zoneId)
            )
          );
        if (existing.length > 0)
          return { success: true, alreadyAssigned: true };
        await db.insert(agentGeofenceZones).values({
          agentId: input.agentId,
          zoneId: input.zoneId,
          assignedBy: ctx.user.name ?? ctx.user.keycloakSub,
        });
        return { success: true, alreadyAssigned: false };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // ── Admin: remove agent from zone ─────────────────────────────────────────
  removeAgentFromZone: adminProcedure
    .input(z.object({ agentId: z.number().int(), zoneId: z.number().int() }))
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });
        await db
          .delete(agentGeofenceZones)
          .where(
            and(
              eq(agentGeofenceZones.agentId, input.agentId),
              eq(agentGeofenceZones.zoneId, input.zoneId)
            )
          );
        return { success: true };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // ── Admin: list zones assigned to an agent ─────────────────────────────────
  getAgentZones: adminProcedure
    .input(z.object({ agentId: z.number().int() }))
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });
        const rows = await db
          .select({ zone: geofenceZones })
          .from(agentGeofenceZones)
          .innerJoin(
            geofenceZones,
            eq(agentGeofenceZones.zoneId, geofenceZones.id)
          )
          .where(eq(agentGeofenceZones.agentId, input.agentId));
        return rows.map((r: any) => r.zone);
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // ── Agent: report GPS location ─────────────────────────────────────────────
  reportLocation: protectedProcedure
    .input(
      z.object({
        deviceId: z.number().int(),
        latitude: z.number().min(-90).max(90),
        longitude: z.number().min(-180).max(180),
        accuracy: z.number().optional(),
      })
    )
    .mutation(async ({ ctx, input }) => {
      try {
        const db = (await getDb())!;
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

        // Resolve agent record
        const [agent] = await db
          .select()
          .from(agents)
          .where(eq(agents.id, ctx.user.id as unknown as number))
          .limit(1);

        // ── Try platform geofencing service first ─────────────────────────────
        let platformResult: {
          within_zone?: boolean;
          zone_name?: string;
        } | null = null;
        try {
          const token = getToken(ctx);
          const terminalId = agent?.agentCode ?? String(input.deviceId);
          platformResult = (await geofencingPlatform.reportLocation(
            terminalId,
            {
              lat: input.latitude,
              lng: input.longitude,
              accuracy: input.accuracy,
            },
            token
          )) as { within_zone?: boolean; zone_name?: string };
        } catch (err) {
          if (!(err instanceof PlatformError)) throw err;
          console.warn(
            "[geofencing] platform reportLocation failed, using local haversine:",
            (err as Error).message
          );
        }

        // ── Local haversine fallback ──────────────────────────────────────────
        let withinZone = true;
        let outsideZoneName: string | undefined;

        if (platformResult !== null) {
          withinZone = platformResult.within_zone ?? true;
          outsideZoneName = platformResult.zone_name;
        } else {
          // Local fallback: check assigned zones via haversine
          const resolvedAgentId = agent?.id;
          const assignedZones = resolvedAgentId
            ? await db
                .select({ zone: geofenceZones })
                .from(agentGeofenceZones)
                .innerJoin(
                  geofenceZones,
                  eq(agentGeofenceZones.zoneId, geofenceZones.id)
                )
                .where(
                  and(
                    eq(agentGeofenceZones.agentId, resolvedAgentId),
                    eq(geofenceZones.isActive, true)
                  )
                )
            : [];

          if (assignedZones.length > 0) {
            for (const { zone } of assignedZones) {
              const dist = haversineMetres(
                input.latitude,
                input.longitude,
                parseFloat(String(zone.latitude)),
                parseFloat(String(zone.longitude))
              );
              if (dist > (zone.radiusMetres ?? 0)) {
                withinZone = false;
                outsideZoneName = zone.name;
                break;
              }
            }
          }
        }

        // ── Always record locally for audit trail ─────────────────────────────
        await db.insert(deviceLocations).values({
          deviceId: input.deviceId,
          agentId: agent?.id ?? input.deviceId,
          latitude: String(input.latitude),
          longitude: String(input.longitude),
          accuracy: input.accuracy ? String(input.accuracy) : null,
          withinZone,
        });

        // ── Fraud alert + real-time socket emit if outside zone ───────────────
        if (!withinZone) {
          const [alert] = await db
            .insert(fraudAlerts)
            .values({
              agentId: agent?.id ?? null,
              severity: "high",
              type: "GEOFENCE_VIOLATION",
              reason: `Device outside assigned zone "${outsideZoneName}". Lat: ${input.latitude}, Lon: ${input.longitude}`,
              status: "open",
            })
            .returning();

          const io = getIO();
          if (io && agent?.agentCode) {
            io.of("/terminal")
              .to(`agent:${agent.agentCode}`)
              .emit("terminal:fraud_alert", {
                id: alert.id,
                severity: "high",
                type: "GEOFENCE_VIOLATION",
                reason: alert.reason,
                createdAt: alert.createdAt,
              });
          }
        }

        return { withinZone, outsideZoneName: outsideZoneName ?? null };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // ── Agent: check if a coordinate is within assigned zones ─────────────────
  checkLocation: protectedProcedure
    .input(
      z.object({
        agentId: z.number().int(),
        latitude: z.number().min(-90).max(90),
        longitude: z.number().min(-180).max(180),
      })
    )
    .query(async ({ ctx, input }) => {
      // Try platform first
      try {
        const token = getToken(ctx);
        const db = (await getDb())!;
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });
        const [agent] = await db
          .select()
          .from(agents)
          .where(eq(agents.id, input.agentId))
          .limit(1);
        if (agent?.agentCode) {
          const result = (await geofencingPlatform.checkZone(
            agent.agentCode,
            token
          )) as {
            within_zone?: boolean;
            zones?: Array<{
              zone_id: string;
              zone_name: string;
              distance_m: number;
              radius_m: number;
              within: boolean;
            }>;
          };
          if (result) {
            return {
              withinZone: result.within_zone ?? true,
              zones: (result.zones ?? []).map((z: any) => ({
                zoneId: z.zone_id,
                zoneName: z.zone_name,
                distanceMetres: Math.round(z.distance_m),
                radiusMetres: z.radius_m,
                withinZone: z.within,
              })),
            };
          }
        }
      } catch (err) {
        if (!(err instanceof PlatformError)) throw err;
        console.warn(
          "[geofencing] platform checkZone failed, using local haversine:",
          (err as Error).message
        );
      }

      // Local haversine fallback
      const db = (await getDb())!;
      if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });
      const assignedZones = await db
        .select({ zone: geofenceZones })
        .from(agentGeofenceZones)
        .innerJoin(
          geofenceZones,
          eq(agentGeofenceZones.zoneId, geofenceZones.id)
        )
        .where(
          and(
            eq(agentGeofenceZones.agentId, input.agentId),
            eq(geofenceZones.isActive, true)
          )
        );

      if (assignedZones.length === 0) return { withinZone: true, zones: [] };

      const results = assignedZones.map(({ zone }) => {
        const dist = haversineMetres(
          input.latitude,
          input.longitude,
          parseFloat(String(zone.latitude)),
          parseFloat(String(zone.longitude))
        );
        return {
          zoneId: zone.id,
          zoneName: zone.name,
          distanceMetres: Math.round(dist),
          radiusMetres: zone.radiusMetres ?? 0,
          withinZone: dist <= (zone.radiusMetres ?? 0),
        };
      });

      return {
        withinZone: results.every((r: any) => r.withinZone),
        zones: results,
      };
    }),

  // ── Admin: recent location history for a device ────────────────────────────
  getLocationHistory: adminProcedure
    .input(
      z.object({
        deviceId: z.number().int(),
        limit: z.number().int().min(1).max(200).default(50),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });
        return db
          .select()
          .from(deviceLocations)
          .where(eq(deviceLocations.deviceId, input.deviceId))
          .orderBy(desc(deviceLocations.reportedAt))
          .limit(input.limit);
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // ── Admin: list compliance reports ────────────────────────────────────────
  listComplianceReports: adminProcedure
    .input(z.object({ limit: z.number().int().min(1).max(52).default(12) }))
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });
        const { complianceReports } = await import("../../drizzle/schema.js");
        return db
          .select()
          .from(complianceReports)
          .orderBy(desc(complianceReports.createdAt))
          .limit(input.limit);
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  // ── Admin: geofencing stats for dashboard ─────────────────────────────────
  stats: adminProcedure.query(async () => {
    const db = (await getDb())!;
    if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

    const [totalZones] = await db
      .select({ count: sql<number>`count(*)::int` })
      .from(geofenceZones)
      .where(eq(geofenceZones.isActive, true));

    const [totalAssignments] = await db
      .select({ count: sql<number>`count(*)::int` })
      .from(agentGeofenceZones);

    const since24h = new Date(Date.now() - 86_400_000);
    const [violations] = await db
      .select({ count: sql<number>`count(*)::int` })
      .from(fraudAlerts)
      .where(
        and(
          eq(fraudAlerts.type, "GEOFENCE_VIOLATION"),
          gte(fraudAlerts.createdAt, since24h)
        )
      );

    return {
      activeZones: totalZones?.count ?? 0,
      agentAssignments: totalAssignments?.count ?? 0,
      violations24h: violations?.count ?? 0,
    };
  }),
});
