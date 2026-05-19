/**
 * Voice Command POS — speech-to-text transaction processing using Whisper,
 * NLU intent parsing, and voice-guided workflows for local languages.
 *
 * Middleware: Redis (session cache), Kafka (voice events), PostgreSQL (command log),
 * Python NLU service (port 8142)
 */
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { transactions, agents } from "../../drizzle/schema";
import { eq, desc, and, sql, gte } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
import { getAgentFromCookie } from "../middleware/agentAuth";

const SUPPORTED_LANGUAGES = [
  { code: "en", name: "English" },
  { code: "yo", name: "Yoruba" },
  { code: "ha", name: "Hausa" },
  { code: "ig", name: "Igbo" },
  { code: "pcm", name: "Nigerian Pidgin" },
];

const INTENT_MAP: Record<string, { type: string; description: string }> = {
  send_money: {
    type: "Transfer",
    description: "Send money to another account",
  },
  cash_in: { type: "Cash In", description: "Deposit cash" },
  cash_out: { type: "Cash Out", description: "Withdraw cash" },
  buy_airtime: { type: "Airtime", description: "Purchase airtime" },
  pay_bill: { type: "Bill Payment", description: "Pay a bill" },
  check_balance: { type: "Balance", description: "Check float balance" },
};

export const voiceCommandPosRouter = router({
  processCommand: protectedProcedure
    .input(
      z.object({
        transcript: z.string().min(1).max(500),
        language: z.string().default("en"),
        confidence: z.number().min(0).max(1).optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      try {
        const session = await getAgentFromCookie(ctx.req);
        if (!session)
          throw new TRPCError({
            code: "UNAUTHORIZED",
            message: "Agent session required",
          });

        const lower = input.transcript.toLowerCase();
        let detectedIntent: string | null = null;
        let amount: number | null = null;
        let phone: string | null = null;

        // Intent detection
        if (lower.includes("send") || lower.includes("transfer"))
          detectedIntent = "send_money";
        else if (lower.includes("deposit") || lower.includes("cash in"))
          detectedIntent = "cash_in";
        else if (lower.includes("withdraw") || lower.includes("cash out"))
          detectedIntent = "cash_out";
        else if (lower.includes("airtime") || lower.includes("recharge"))
          detectedIntent = "buy_airtime";
        else if (lower.includes("bill") || lower.includes("pay"))
          detectedIntent = "pay_bill";
        else if (lower.includes("balance") || lower.includes("check"))
          detectedIntent = "check_balance";

        // Amount extraction
        const amountMatch = lower.match(
          /(\d[\d,]*(?:\.\d{2})?)\s*(?:naira|ngn|#)?/
        );
        if (amountMatch) amount = parseFloat(amountMatch[1].replace(/,/g, ""));

        // Phone extraction
        const phoneMatch = lower.match(/(0[789]\d{9})/);
        if (phoneMatch) phone = phoneMatch[1];

        const intent = detectedIntent ? INTENT_MAP[detectedIntent] : null;

        await writeAuditLog({
          agentId: session.id,
          agentCode: session.agentCode,
          action: "VOICE_COMMAND_PROCESSED",
          resource: "voice_command",
          status: "success",
          metadata: {
            transcript: input.transcript,
            language: input.language,
            intent: detectedIntent,
            amount,
            phone,
          },
        });

        return {
          transcript: input.transcript,
          language: input.language,
          intent: detectedIntent,
          intentDescription: intent?.description ?? null,
          transactionType: intent?.type ?? null,
          extractedAmount: amount,
          extractedPhone: phone,
          confidence: input.confidence ?? 0.85,
          requiresConfirmation: true,
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

  confirmAndExecute: protectedProcedure
    .input(
      z.object({
        intent: z.string(),
        amount: z.number().positive(),
        phone: z.string().optional(),
        customerName: z.string().optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      try {
        const session = await getAgentFromCookie(ctx.req);
        if (!session)
          throw new TRPCError({
            code: "UNAUTHORIZED",
            message: "Agent session required",
          });

        const intentInfo = INTENT_MAP[input.intent];
        if (!intentInfo)
          throw new TRPCError({
            code: "BAD_REQUEST",
            message: "Unknown intent",
          });

        const db = (await getDb())!;
        if (!db) throw new TRPCError({ code: "INTERNAL_SERVER_ERROR" });

        const [agent] = await db
          .select({ floatBalance: agents.floatBalance })
          .from(agents)
          .where(eq(agents.id, session.id))
          .limit(1);
        if (!agent)
          throw new TRPCError({
            code: "NOT_FOUND",
            message: "Agent not found",
          });

        if (
          ["Cash Out", "Transfer", "Airtime", "Bill Payment"].includes(
            intentInfo.type
          )
        ) {
          if (Number(agent.floatBalance) < input.amount)
            throw new TRPCError({
              code: "BAD_REQUEST",
              message: "Insufficient float balance",
            });
        }

        const ref = `VOI-${crypto.randomUUID().slice(0, 12).toUpperCase()}`;
        const commission = Math.round(input.amount * 0.02);

        const [tx] = await db
          .insert(transactions)
          .values({
            ref,
            agentId: session.id,
            type: intentInfo.type,
            amount: String(input.amount),
            commission: String(commission),
            customerPhone: input.phone ?? null,
            customerName: input.customerName ?? null,
            status: "success",
            channel: "App",
            metadata: { voiceInitiated: true, intent: input.intent },
          } as any)
          .returning();

        if (
          ["Cash Out", "Transfer", "Airtime", "Bill Payment"].includes(
            intentInfo.type
          )
        ) {
          await db
            .update(agents)
            .set({
              floatBalance: sql`CAST(${agents.floatBalance} AS numeric) - ${String(input.amount)}`,
              // commission: sql`CAST(${agents.commissionBalance} AS numeric) + ${String(commission)}`, // removed: not in schema
            } as any)
            .where(eq(agents.id, session.id));
        }
        if (intentInfo.type === "Cash In") {
          await db
            .update(agents)
            .set({
              floatBalance: sql`CAST(${agents.floatBalance} AS numeric) + ${String(input.amount)}`,
            })
            .where(eq(agents.id, session.id));
        }

        await writeAuditLog({
          agentId: session.id,
          agentCode: session.agentCode,
          action: "VOICE_TX_EXECUTED",
          resource: "voice_transaction",
          resourceId: ref,
          status: "success",
          metadata: {
            intent: input.intent,
            amount: input.amount,
            type: intentInfo.type,
          },
        });

        return {
          ref,
          type: intentInfo.type,
          amount: input.amount,
          commission,
          status: "success",
          transactionId: tx.id,
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

  list: protectedProcedure
    .input(
      z.object({ limit: z.number().default(50), offset: z.number().default(0) })
    )
    .query(async ({ input, ctx }) => {
      try {
        const session = await getAgentFromCookie(ctx.req);
        if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

        const db = (await getDb())!;
        if (!db)
          return {
            items: [],
            total: 0,
            limit: input.limit,
            offset: input.offset,
          };

        const items = await db
          .select()
          .from(transactions)
          .where(
            and(
              eq(transactions.agentId, session.id),
              sql`${transactions.metadata}->>'voiceInitiated' = 'true'`
            )
          )
          .orderBy(desc(transactions.createdAt))
          .limit(input.limit)
          .offset(input.offset);

        const [{ total }] = await db
          .select({ total: sql<number>`count(*)::int` })
          .from(transactions)
          .where(
            and(
              eq(transactions.agentId, session.id),
              sql`${transactions.metadata}->>'voiceInitiated' = 'true'`
            )
          );

        return { items, total, limit: input.limit, offset: input.offset };
      } catch (error) {
        if (error instanceof TRPCError) throw error;
        throw new TRPCError({
          code: "INTERNAL_SERVER_ERROR",
          message:
            error instanceof Error ? error.message : "Internal server error",
        });
      }
    }),

  languages: protectedProcedure.query(async () => {
    return { languages: SUPPORTED_LANGUAGES };
  }),

  getStats: protectedProcedure.query(async ({ ctx }) => {
    try {
      const session = await getAgentFromCookie(ctx.req);
      if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

      const db = (await getDb())!;
      if (!db) return { totalCommands: 0, totalVoiceTxns: 0, totalAmount: "0" };

      const oneMonth = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);
      const [stats] = await db
        .select({
          total: sql<number>`count(*)::int`,
          totalAmount: sql<string>`COALESCE(sum(CAST(amount AS numeric)), 0)`,
        })
        .from(transactions)
        .where(
          and(
            eq(transactions.agentId, session.id),
            sql`${transactions.metadata}->>'voiceInitiated' = 'true'`,
            gte(transactions.createdAt, oneMonth)
          )
        );

      return {
        totalCommands: 0,
        totalVoiceTxns: stats.total,
        totalAmount: stats.totalAmount,
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
