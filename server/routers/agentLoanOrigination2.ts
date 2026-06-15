/**
 * Agent Loan Origination v2 — wraps the main agentLoanOrigination router
 * with identical procedures, maintained for backward compatibility.
 */
import { protectedProcedure, router } from "../_core/trpc";
import { agentLoanOriginationRouter } from "./agentLoanOrigination";

export const agentLoanOrigination2Router = router({
  ...agentLoanOriginationRouter._def.procedures,
});
