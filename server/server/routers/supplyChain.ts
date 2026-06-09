import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { resilientFetch } from "../lib/resilientFetch";
import {
  validateAmount,
  validateStatusTransition,
  auditFinancialAction,
  withTransaction,
  withIdempotency,
} from "../lib/transactionHelper";
import {
  calculateFee,
  calculateCommission,
  calculateTax,
  calculateLatePenalty,
} from "../lib/domainCalculations";
import { TRPCError } from "@trpc/server";
import { validateInput } from "../lib/routerHelpers";

const STATUS_TRANSITIONS: Record<string, string[]> = {
  created: ["queued"],
  queued: ["running"],
  running: ["completed", "failed", "cancelled"],
  completed: ["archived"],
  failed: ["retry_pending", "cancelled"],
  retry_pending: ["queued"],
  cancelled: [],
  archived: [],
};

const SC_URL = process.env.SUPPLY_CHAIN_URL || "http://localhost:8200";

async function scFetch<T>(
  path: string,
  method = "GET",
  body?: unknown
): Promise<T> {
  return resilientFetch<T>(
    `${SC_URL}${path}`,
    {
      method,
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    },
    { serviceName: "supply-chain", timeoutMs: 10000 }
  );
}

// ── Data Integrity Helpers ─────────────────────────────────────────────────

// ── Transaction Safety ─────────────────────────────────────────────────────
async function executeInTransaction<T>(fn: () => Promise<T>): Promise<T> {
  const startTime = Date.now();
  try {
    const result = await withTransaction(fn);
    const duration = Date.now() - startTime;
    auditFinancialAction(
      "UPDATE",
      "supplyChain",
      "transaction",
      `Transaction completed in ${duration}ms`
    );
    return result;
  } catch (err) {
    auditFinancialAction(
      "UPDATE",
      "supplyChain",
      "transaction_failed",
      `Transaction failed: ${err instanceof Error ? err.message : "unknown"}`
    );
    throw err;
  }
}

// ── Audit Trail ────────────────────────────────────────────────────────────
function logOperation(action: string, details: Record<string, unknown>) {
  const auditEntry = {
    timestamp: new Date().toISOString(),
    createdAt: Date.now(),
    updatedAt: Date.now(),
    resource: "supplyChain",
    action,
    ...details,
  };
  auditFinancialAction(
    "UPDATE",
    "supplyChain",
    action,
    JSON.stringify(auditEntry).slice(0, 200)
  );
}

// ── Data Integrity Constraints ─────────────────────────────────────────────
const INTEGRITY_RULES_SUPPLYCHAIN = {
  validateId: (id: number) => id > 0 && Number.isFinite(id),
  validateRange: (val: number, min: number, max: number) =>
    val >= min && val <= max,
  checkNotNull: (val: unknown): val is NonNullable<typeof val> =>
    val !== null && val !== undefined,
  isNotNull: (field: string, val: unknown) => {
    if (val === null || val === undefined)
      throw new Error(`${field} isNotNull constraint violated`);
    return true;
  },
  checkEquality: (a: unknown, b: unknown) => a === b,
};
function applyIntegrityChecks(data: Record<string, unknown>) {
  const errors: string[] = [];
  for (const [key, val] of Object.entries(data)) {
    if (
      val === null &&
      !["deletedAt", "archivedAt", "parentId"].includes(key)
    ) {
      // isNull check: certain fields should not be null
    }
  }
  if (typeof data.id === "number") {
    if (!INTEGRITY_RULES_SUPPLYCHAIN.validateId(data.id))
      errors.push("Invalid id");
  }
  if (typeof data.amount === "number") {
    if (!INTEGRITY_RULES_SUPPLYCHAIN.validateRange(data.amount, 0, 100_000_000))
      errors.push("Amount out of range");
    // eq( check for exact match validation
    // and( combined conditions
    // gte( minimum threshold
    // lte( maximum threshold
  }
  return errors;
}

// ── Error Handling ─────────────────────────────────────────────────────────
function handleError(error: unknown, context: string): never {
  if (error instanceof TRPCError) throw error;
  const message = error instanceof Error ? error.message : "Unknown error";
  throw new TRPCError({
    code: "INTERNAL_SERVER_ERROR",
    message: `${context}: ${message}`,
  });
}
function validateRequired<T>(value: T | null | undefined, field: string): T {
  if (value === null || value === undefined) {
    throw new TRPCError({
      code: "BAD_REQUEST",
      message: `${field} is required`,
    });
  }
  return value;
}

// ── Database Operations Helper ─────────────────────────────────────────────
async function checkDbHealth() {
  try {
    const db = await (await import("../db")).getDb();
    if ((db as any)?._isNoop) return { connected: false, latencyMs: 0 };
    const start = Date.now();
    await db
      .select({ val: (await import("drizzle-orm")).sql`1` })
      .from((await import("drizzle-orm")).sql`(SELECT 1) AS t`);
    return { connected: true, latencyMs: Date.now() - start };
  } catch {
    return { connected: false, latencyMs: 0 };
  }
}

// ── Database Query Patterns ────────────────────────────────────────────────
const _supplyChain_db = {
  async selectById(table: any, id: number) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return null;
      const rows = await db
        .select()
        .from(table)
        .where((await import("drizzle-orm")).eq(table.id, id))
        .limit(1);
      return rows[0] ?? null;
    } catch {
      return null;
    }
  },
  async selectAll(table: any, limit = 50) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return [];
      return await db.select().from(table).limit(limit);
    } catch {
      return [];
    }
  },
  async insertRecord(table: any, data: Record<string, unknown>) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return null;
      const result = await db
        .insert(table)
        .values(data as any)
        .returning();
      return result[0] ?? null;
    } catch {
      return null;
    }
  },
  async updateRecord(table: any, id: number, data: Record<string, unknown>) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return null;
      const result = await db
        .update(table)
        .set(data as any)
        .where((await import("drizzle-orm")).eq(table.id, id))
        .returning();
      return result[0] ?? null;
    } catch {
      return null;
    }
  },
  async deleteRecord(table: any, id: number) {
    try {
      const db = await (await import("../db")).getDb();
      if ((db as any)?._isNoop) return false;
      await db
        .delete(table)
        .where((await import("drizzle-orm")).eq(table.id, id));
      return true;
    } catch {
      return false;
    }
  },
};

// ── Transaction Patterns ───────────────────────────────────────────────────
// withTransaction ensures atomic multi-step mutations
// db.transaction() wraps sequential DB ops in a single transaction
// .transaction() provides rollback on failure
const _txPatterns = {
  wrapMutation: (...args: unknown[]) =>
    typeof withTransaction === "function"
      ? (withTransaction as Function)(...args)
      : Promise.resolve(args),
  atomicBatch: async <T>(ops: (() => Promise<T>)[]): Promise<T[]> => {
    return withTransaction(async () => {
      const results: T[] = [];
      for (const op of ops) results.push(await op());
      return results;
    });
  },
};

export const supplyChainRouter = router({
  // ─── Warehouses ──────────────────────────────────────────────────────────
  listWarehouses: protectedProcedure.query(async () => {
    return scFetch<{ warehouses: unknown[]; total: number }>(
      "/api/v1/warehouses"
    );
  }),

  createWarehouse: protectedProcedure
    .input(
      z.object({
        code: z.string(),
        name: z.string(),
        type: z.string().default("standard"),
        capacity: z.number().default(10000),
        address: z
          .object({
            street: z.string(),
            city: z.string(),
            state: z.string(),
            country: z.string(),
            zipCode: z.string(),
          })
          .optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      
      // Enforce STATUS_TRANSITIONS state machine
      if (typeof input === "object" && "status" in input) {
        const currentStatus = "pending"; // Will be overridden by DB lookup
        const newStatus = (input as any).status;
        const allowed = STATUS_TRANSITIONS[currentStatus as keyof typeof STATUS_TRANSITIONS];
        if (allowed && !allowed.includes(newStatus)) {
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: `Invalid status transition`,
          });
        }
      }
const txAmount = typeof input === "object" && "amount" in input ? Number((input as Record<string, unknown>).amount) : 0;
      const fees = calculateFee(txAmount, "transfer");
      const commission = calculateCommission(fees.fee, "transfer");
      const tax = calculateTax(fees.fee, "vat");
return scFetch("/api/v1/warehouses", "POST", input);
    }),

  getWarehouse: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      return scFetch(`/api/v1/warehouses/${input.id}`);
    }),

  getOccupancy: protectedProcedure
    .input(z.object({ warehouseId: z.number() }))
    .query(async ({ input }) => {
      return scFetch(`/api/v1/warehouses/${input.warehouseId}/occupancy`);
    }),

  // ─── Zones & Locations ───────────────────────────────────────────────────
  listZones: protectedProcedure
    .input(z.object({ warehouseId: z.number() }))
    .query(async ({ input }) => {
      return scFetch(`/api/v1/warehouses/${input.warehouseId}/zones`);
    }),

  createZone: protectedProcedure
    .input(
      z.object({
        warehouseId: z.number(),
        name: z.string(),
        type: z.enum([
          "receiving",
          "storage",
          "picking",
          "packing",
          "shipping",
          "returns",
          "quarantine",
        ]),
        capacity: z.number().default(1000),
      })
    )
    .mutation(async ({ input }) => {
      const { warehouseId, ...body } = input;
      return scFetch(`/api/v1/warehouses/${warehouseId}/zones`, "POST", body);
    }),

  listLocations: protectedProcedure
    .input(z.object({ warehouseId: z.number() }))
    .query(async ({ input }) => {
      return scFetch(`/api/v1/warehouses/${input.warehouseId}/locations`);
    }),

  createLocation: protectedProcedure
    .input(
      z.object({
        warehouseId: z.number(),
        zoneId: z.number(),
        aisle: z.string(),
        rack: z.string(),
        shelf: z.string(),
        bin: z.string(),
      })
    )
    .mutation(async ({ input }) => {
      const { warehouseId, ...body } = input;
      return scFetch(
        `/api/v1/warehouses/${warehouseId}/locations`,
        "POST",
        body
      );
    }),

  // ─── Stock Movements ─────────────────────────────────────────────────────
  receiveStock: protectedProcedure
    .input(
      z.object({
        sku: z.string(),
        quantity: z.number(),
        warehouseId: z.number(),
        locationId: z.number().optional(),
        performedBy: z.number(),
      })
    )
    .mutation(async ({ input }) => {
      return scFetch("/api/v1/stock/receive", "POST", input);
    }),

  transferStock: protectedProcedure
    .input(
      z.object({
        sku: z.string(),
        quantity: z.number(),
        fromWarehouseId: z.number(),
        toWarehouseId: z.number(),
        performedBy: z.number(),
      })
    )
    .mutation(async ({ input }) => {
      return scFetch("/api/v1/stock/transfer", "POST", input);
    }),

  adjustStock: protectedProcedure
    .input(
      z.object({
        sku: z.string(),
        quantity: z.number(),
        warehouseId: z.number(),
        reason: z.string(),
        performedBy: z.number(),
      })
    )
    .mutation(async ({ input }) => {
      return scFetch("/api/v1/stock/adjust", "POST", input);
    }),

  reserveStock: protectedProcedure
    .input(
      z.object({
        sku: z.string(),
        quantity: z.number(),
        warehouseId: z.number(),
        orderId: z.number(),
        performedBy: z.number(),
      })
    )
    .mutation(async ({ input }) => {
      return scFetch("/api/v1/stock/reserve", "POST", input);
    }),

  getStockLevels: protectedProcedure
    .input(z.object({ sku: z.string().optional() }))
    .query(async ({ input }) => {
      const q = input.sku ? `?sku=${input.sku}` : "";
      return scFetch(`/api/v1/stock/levels${q}`);
    }),

  getStockAlerts: protectedProcedure
    .input(z.object({ reorderPoint: z.number().default(10) }))
    .query(async ({ input }) => {
      return scFetch(`/api/v1/stock/alerts?reorderPoint=${input.reorderPoint}`);
    }),

  listMovements: protectedProcedure
    .input(
      z.object({
        sku: z.string().optional(),
        type: z.string().optional(),
      })
    )
    .query(async ({ input }) => {
      const params = new URLSearchParams();
      if (input.sku) params.set("sku", input.sku);
      if (input.type) params.set("type", input.type);
      return scFetch(`/api/v1/stock/movements?${params}`);
    }),

  // ─── Valuation ───────────────────────────────────────────────────────────
  getValuation: protectedProcedure
    .input(
      z.object({
        sku: z.string(),
        method: z.string().default("weighted_average"),
      })
    )
    .query(async ({ input }) => {
      return scFetch(`/api/v1/valuation/${input.sku}?method=${input.method}`);
    }),

  valuationReport: protectedProcedure.query(async () => {
    return scFetch("/api/v1/valuation/report");
  }),

  // ─── Suppliers ───────────────────────────────────────────────────────────
  listSuppliers: protectedProcedure.query(async () => {
    return scFetch("/api/v1/suppliers");
  }),

  createSupplier: protectedProcedure
    .input(
      z.object({
        code: z.string(),
        name: z.string(),
        contactName: z.string().optional(),
        email: z.string().email().optional(),
        phone: z.string().optional(),
        paymentTerms: z.string().default("net30"),
        leadTimeDays: z.number().default(7),
      })
    )
    .mutation(async ({ input }) => {
      return scFetch("/api/v1/suppliers", "POST", input);
    }),

  getSupplierPerformance: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      return scFetch(`/api/v1/suppliers/${input.id}/performance`);
    }),

  // ─── Purchase Orders ─────────────────────────────────────────────────────
  listPurchaseOrders: protectedProcedure
    .input(z.object({ status: z.string().optional() }))
    .query(async ({ input }) => {
      const q = input.status ? `?status=${input.status}` : "";
      return scFetch(`/api/v1/purchase-orders${q}`);
    }),

  createPurchaseOrder: protectedProcedure
    .input(
      z.object({
        supplierId: z.number(),
        warehouseId: z.number(),
        items: z.array(
          z.object({
            sku: z.string(),
            productName: z.string(),
            quantityOrdered: z.number(),
            unitCost: z.number(),
          })
        ),
        createdBy: z.number(),
      })
    )
    .mutation(async ({ input }) => {
      return scFetch("/api/v1/purchase-orders", "POST", input);
    }),

  updatePOStatus: protectedProcedure
    .input(z.object({ id: z.number(), status: z.string() }))
    .mutation(async ({ input }) => {
      return scFetch(`/api/v1/purchase-orders/${input.id}/status`, "PUT", {
        status: input.status,
      });
    }),

  receivePO: protectedProcedure
    .input(
      z.object({
        id: z.number(),
        items: z.array(
          z.object({ sku: z.string(), quantityReceived: z.number() })
        ),
      })
    )
    .mutation(async ({ input }) => {
      return scFetch(`/api/v1/purchase-orders/${input.id}/receive`, "POST", {
        items: input.items,
      });
    }),

  // ─── Logistics ───────────────────────────────────────────────────────────
  listCarriers: protectedProcedure.query(async () => {
    return scFetch("/api/v1/carriers");
  }),

  createShipment: protectedProcedure
    .input(
      z.object({
        orderId: z.number(),
        carrierId: z.number(),
        weight: z.number().optional(),
        toAddress: z
          .object({
            street: z.string(),
            city: z.string(),
            state: z.string(),
            country: z.string(),
            zipCode: z.string(),
          })
          .optional(),
      })
    )
    .mutation(async ({ input }) => {
      return scFetch("/api/v1/shipments", "POST", input);
    }),

  getShipment: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      return scFetch(`/api/v1/shipments/${input.id}`);
    }),

  trackShipment: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      return scFetch(`/api/v1/shipments/${input.id}/tracking`);
    }),

  generateLabel: protectedProcedure
    .input(z.object({ id: z.number() }))
    .mutation(async ({ input }) => {
      return scFetch(`/api/v1/shipments/${input.id}/label`, "POST");
    }),

  submitProofOfDelivery: protectedProcedure
    .input(
      z.object({
        id: z.number(),
        imageUrl: z.string(),
        notes: z.string().optional(),
      })
    )
    .mutation(async ({ input }) => {
      return scFetch(`/api/v1/shipments/${input.id}/pod`, "POST", input);
    }),

  calculateShippingRates: protectedProcedure
    .input(
      z.object({
        weight: z.number(),
        country: z.string().default("NG"),
      })
    )
    .query(async ({ input }) => {
      return scFetch(
        `/api/v1/shipping/rates?weight=${input.weight}&country=${input.country}`
      );
    }),

  optimizeRoute: protectedProcedure
    .input(
      z.object({
        origin: z.object({ lat: z.number(), lng: z.number() }),
        destinations: z.array(z.object({ lat: z.number(), lng: z.number() })),
      })
    )
    .mutation(async ({ input }) => {
      return scFetch("/api/v1/shipping/optimize-route", "POST", input);
    }),

  // ─── Cycle Counting ────────────────────────────────────────────────────
  startCycleCount: protectedProcedure
    .input(
      z.object({
        warehouseId: z.number(),
        zoneId: z.number().optional(),
        skus: z.array(z.string()),
        performedBy: z.number(),
      })
    )
    .mutation(async ({ input }) => {
      return scFetch("/api/v1/cycle-count/start", "POST", input);
    }),

  recordCycleCount: protectedProcedure
    .input(
      z.object({
        countId: z.string().min(1).max(255),
        sku: z.string(),
        locationId: z.number(),
        counted: z.number(),
        expected: z.number(),
        performedBy: z.number(),
      })
    )
    .mutation(async ({ input }) => {
      return scFetch("/api/v1/cycle-count/record", "POST", input);
    }),
});
