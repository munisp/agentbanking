import { z } from "zod";
import { router, protectedProcedure } from "../_core/trpc";
import { getDb } from "../db";
import { eq, desc, and, sql, count } from "drizzle-orm";
import {
  disputes,
  disputeMessages,
  disputeEvidence,
  transactions,
  auditLog,
} from "../../drizzle/schema";
import { TRPCError } from "@trpc/server";

export const customerDisputePortalRouter = router({
  listMyDisputes: protectedProcedure
    .input(
      z.object({
        customerId: z.number(),
        limit: z.number().default(20),
        status: z.string().optional(),
      })
    )
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const rows = input.status
          ? await db
              .select()
              .from(disputes)
              .where(
                and(
                  eq(disputes.agentId, input.customerId),
                  eq(disputes.status, input.status)
                )
              )
              .orderBy(desc(disputes.createdAt))
              .limit(input.limit)
          : await db
              .select()
              .from(disputes)
              .where(eq(disputes.agentId, input.customerId))
              .orderBy(desc(disputes.createdAt))
              .limit(input.limit);
        return { disputes: rows, total: rows.length };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  getDispute: protectedProcedure
    .input(z.object({ id: z.number() }))
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [dispute] = await db
          .select()
          .from(disputes)
          .where(eq(disputes.id, input.id))
          .limit(1);
        if (!dispute) return null;
        const messages = await db
          .select()
          .from(disputeMessages)
          .where(eq(disputeMessages.disputeId, input.id))
          .orderBy(disputeMessages.createdAt)
          .limit(100);
        const evidence = await db
          .select()
          .from(disputeEvidence)
          .where(eq(disputeEvidence.disputeId, input.id))
          .limit(100);
        return { ...dispute, messages, evidence };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  fileDispute: protectedProcedure
    .input(
      z.object({
        customerId: z.number(),
        transactionId: z.number(),
        reason: z.string(),
        description: z.string(),
        amount: z.number().positive(),
      })
    )
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [dispute] = await db
          .insert(disputes)
          .values({
            customerId: input.customerId,
            transactionId: input.transactionId,
            reason: input.reason,
            description: input.description,
            amount: String(input.amount),
            status: "open",
            type: "customer",
          } as any)
          .returning();
        await db.insert(auditLog).values({
          action: "customer_dispute_filed",
          resource: "disputes",
          resourceId: String(dispute.id),
          status: "success",
          metadata: {
            customerId: input.customerId,
            transactionId: input.transactionId,
          },
        } as any);
        return dispute;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  addMessage: protectedProcedure
    .input(
      z.object({
        disputeId: z.number(),
        content: z.string(),
        senderType: z.string().default("customer"),
      })
    )
    .mutation(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [msg] = await db
          .insert(disputeMessages)
          .values({
            disputeId: input.disputeId,
            content: input.content,
            senderType: input.senderType,
          })
          .returning();
        return msg;
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),
  getStats: protectedProcedure
    .input(z.object({ customerId: z.number() }))
    .query(async ({ input }) => {
      try {
        const db = (await getDb())!;
        const [total] = await db
          .select({ value: count() })
          .from(disputes)
          .where(eq(disputes.agentId, input.customerId))
          .limit(100);
        const [open] = await db
          .select({ value: count() })
          .from(disputes)
          .where(
            and(
              eq(disputes.agentId, input.customerId),
              eq(disputes.status, "open")
            )
          )
          .limit(100);
        return {
          totalDisputes: Number(total.value),
          openDisputes: Number(open.value),
        };
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
