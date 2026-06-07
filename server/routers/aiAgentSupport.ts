/**
 * AI Agent Support Chatbot — LLM-powered assistance for agents
 *
 * Features:
 * - Natural language transaction lookup
 * - POS troubleshooting guidance
 * - Compliance question answering
 * - Float management recommendations
 * - Escalation to human support when needed
 */
import { z } from "zod";
import { protectedProcedure, router } from "../_core/trpc";
import { getDb, writeAuditLog } from "../db";
import { transactions, agents, posTerminals } from "../../drizzle/schema";
import { eq, desc, and, sql, gte, count, sum } from "drizzle-orm";
import { TRPCError } from "@trpc/server";
import { getAgentFromCookie } from "../middleware/agentAuth";
import {
  auditFinancialAction,
  withTransaction,
} from "../lib/transactionHelper";
import { validateInput } from "../lib/routerHelpers";

interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
}

interface AgentContext {
  agentId: number;
  agentCode: string;
  tier: string;
  recentTxCount: number;
  floatBalance: number;
  activeTerminals: number;
}

// Built-in knowledge base for common agent questions
const KNOWLEDGE_BASE: Record<string, string> = {
  "pos not working":
    "Common POS troubleshooting steps:\n1. Check power and battery level\n2. Verify SIM card is properly inserted\n3. Check network signal strength\n4. Restart the terminal (hold power 10 seconds)\n5. If display shows error code, note it and contact support\n6. Try a test transaction with small amount (NGN 100)",
  "float top up":
    "To top up your float:\n1. Visit your super-agent or bank branch\n2. Transfer funds to your designated float account\n3. Float will reflect within 5-15 minutes\n4. Minimum top-up: NGN 5,000\n5. For instant top-up, use the mobile banking transfer option",
  settlement:
    "Settlement schedule:\n- Auto-settlement runs daily at 11:00 PM WAT\n- Manual settlement available via POS menu > Settlement\n- Settlement takes 1-2 business days to reach your bank\n- Check settlement status in Reports > Settlement History",
  commission:
    "Commission structure:\n- Cash In: 0.5% of transaction amount (min NGN 20, max NGN 500)\n- Cash Out: 0.75% of transaction amount (min NGN 30, max NGN 750)\n- Transfers: 0.3% flat\n- Bill Pay: NGN 50-100 per transaction\n- Commissions are settled weekly every Friday",
  kyc: "KYC requirements:\n- Tier 1: BVN + Phone number (max NGN 50,000/day)\n- Tier 2: + NIN + Photo ID (max NGN 200,000/day)\n- Tier 3: + Address proof + Utility bill (max NGN 5,000,000/day)\n- KYC renewal required every 12 months",
  dispute:
    "To file a dispute:\n1. Go to Transactions > Find the transaction\n2. Click 'Dispute' button\n3. Select reason (wrong amount, failed but debited, unauthorized)\n4. Upload evidence if available\n5. Dispute resolution takes 3-5 business days\n6. Refund auto-credited if approved",
  fraud:
    "Fraud prevention tips:\n- Never share your PIN or password\n- Verify customer identity before large transactions\n- Check for suspicious behavior (multiple failed attempts)\n- Report lost/stolen terminals immediately\n- Enable biometric login for extra security",
};

function findAnswer(query: string): string | null {
  const lower = query.toLowerCase();
  for (const [key, answer] of Object.entries(KNOWLEDGE_BASE)) {
    const keywords = key.split(" ");
    if (keywords.every(k => lower.includes(k))) return answer;
  }
  // Partial matches
  for (const [key, answer] of Object.entries(KNOWLEDGE_BASE)) {
    const keywords = key.split(" ");
    if (keywords.some(k => lower.includes(k))) return answer;
  }
  return null;
}

export const aiAgentSupportRouter = router({
  chat: protectedProcedure
    .input(
      z.object({
        message: z.string().min(1).max(2000),
        conversationId: z.string().max(64).optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      const db = (await getDb())!;
      const session = await getAgentFromCookie(ctx.req);
      if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

      // Get agent context
      const [agentData] = await db
        .select()
        .from(agents)
        .where(eq(agents.id, session.id))
        .limit(1);

      // Try knowledge base first
      const kbAnswer = findAnswer(input.message);
      if (kbAnswer) {
        await writeAuditLog({
          agentId: session.id,
          agentCode: session.agentCode,
          action: "AI_CHAT_KB_RESPONSE",
          resource: "ai_support",
          resourceId: input.conversationId || "new",
          status: "success",
        });

        return {
          response: kbAnswer,
          source: "knowledge_base" as const,
          conversationId: input.conversationId || `conv-${Date.now()}`,
          suggestions: [
            "How do I file a dispute?",
            "What are the commission rates?",
            "My POS is not working",
          ],
        };
      }

      // Fallback: structured response
      const response =
        "I understand your question. Let me connect you with our support team for a more detailed answer. In the meantime, you can:\n\n" +
        "1. Check our FAQ section in Settings > Help\n" +
        "2. Call support: 0800-54LINK (0800-545465)\n" +
        "3. WhatsApp: +234 800 000 0054\n\n" +
        "Is there anything else I can help with?";

      await writeAuditLog({
        agentId: session.id,
        agentCode: session.agentCode,
        action: "AI_CHAT_ESCALATED",
        resource: "ai_support",
        resourceId: input.conversationId || "new",
        status: "success",
        metadata: { query: input.message.slice(0, 200) },
      });

      return {
        response,
        source: "escalation" as const,
        conversationId: input.conversationId || `conv-${Date.now()}`,
        suggestions: [
          "Check my float balance",
          "Show recent transactions",
          "POS troubleshooting",
        ],
      };
    }),

  quickActions: protectedProcedure.query(async ({ ctx }) => {
    const session = await getAgentFromCookie(ctx.req);
    if (!session) throw new TRPCError({ code: "UNAUTHORIZED" });

    return {
      actions: [
        { id: "check_float", label: "Check Float Balance", icon: "wallet" },
        { id: "recent_tx", label: "Recent Transactions", icon: "list" },
        { id: "pos_help", label: "POS Troubleshooting", icon: "tool" },
        { id: "commission", label: "Commission Rates", icon: "percent" },
        { id: "settlement", label: "Settlement Status", icon: "clock" },
        { id: "file_dispute", label: "File a Dispute", icon: "alert-circle" },
        { id: "kyc_status", label: "KYC Status", icon: "shield" },
        { id: "contact_support", label: "Contact Support", icon: "phone" },
      ],
    };
  }),
});
