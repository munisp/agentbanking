import { createHash, randomBytes } from "crypto";
import { z } from "zod";
import { router, adminProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, and, desc } from "drizzle-orm";
import { tenants, apiKeys, auditLog } from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";

/**
 * Tenant administration router (admin-only).
 * Delegation patterns mirror routers/tenantAdmin.ts:
 * adminProcedure + drizzle queries + auditLog inserts.
 */
export const tenantRouter = router({
  list: adminProcedure
    .input(
      z.object({
        limit: z.number().min(1).max(100).default(20),
        offset: z.number().min(0).default(0),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) return { tenants: [] };
        const rows = await db
          .select()
          .from(tenants)
          .orderBy(desc(tenants.createdAt))
          .limit(input.limit)
          .offset(input.offset);
        return { tenants: rows };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  update: adminProcedure
    .input(
      z.object({
        tenantId: z.string(),
        status: z.enum(["active", "suspended", "trial", "churned"]),
      })
    )
    .mutation(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) throw new Error("DB not available");
        const tenantId = Number(input.tenantId);
        if (!Number.isFinite(tenantId))
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: "tenantId must be numeric",
          });
        const [updated] = await db
          .update(tenants)
          .set({ status: input.status, updatedAt: new Date() })
          .where(eq(tenants.id, tenantId))
          .returning();
        if (!updated)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Tenant not found",
          });
        await db.insert(auditLog).values({
          action: "tenant_updated",
          resource: "tenants",
          resourceId: input.tenantId,
          status: "success",
          metadata: { status: input.status },
        });
        return { success: true, tenant: updated };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  delete: adminProcedure
    .input(z.object({ tenantId: z.string() }))
    .mutation(async ({ input }) => {
      try {
        const db = await getDb();
        if (!db) throw new Error("DB not available");
        const tenantId = Number(input.tenantId);
        if (!Number.isFinite(tenantId))
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: "tenantId must be numeric",
          });
        const [deleted] = await db
          .delete(tenants)
          .where(eq(tenants.id, tenantId))
          .returning();
        if (!deleted)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Tenant not found",
          });
        await db.insert(auditLog).values({
          action: "tenant_deleted",
          resource: "tenants",
          resourceId: input.tenantId,
          status: "success",
          metadata: { slug: deleted.slug, name: deleted.name },
        });
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

  rotateApiKey: adminProcedure
    .input(z.object({ tenantId: z.string() }))
    .mutation(async ({ input, ctx }) => {
      try {
        const db = await getDb();
        if (!db) throw new Error("DB not available");
        const tenantId = Number(input.tenantId);
        if (!Number.isFinite(tenantId))
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: "tenantId must be numeric",
          });
        // Revoke all currently-active keys for the tenant
        await db
          .update(apiKeys)
          .set({ status: "revoked", revokedAt: new Date() })
          .where(and(eq(apiKeys.tenantId, tenantId), eq(apiKeys.status, "active")));
        // Issue a fresh key (sha256 hash stored, raw key returned once)
        const rawKey = `ak_${randomBytes(32).toString("hex")}`;
        const keyHash = createHash("sha256").update(rawKey).digest("hex");
        const keyPrefix = rawKey.slice(0, 8);
        const [created] = await db
          .insert(apiKeys)
          .values({
            keyHash,
            keyPrefix,
            name: `tenant-${input.tenantId}-rotated`,
            userId: ctx.user.id,
            tenantId,
            status: "active",
          })
          .returning();
        await db.insert(auditLog).values({
          action: "tenant_api_key_rotated",
          resource: "api_keys",
          resourceId: String(created.id),
          status: "success",
          metadata: { tenantId: input.tenantId, keyPrefix },
        });
        return { success: true, apiKey: rawKey, keyPrefix, id: created.id };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
});
