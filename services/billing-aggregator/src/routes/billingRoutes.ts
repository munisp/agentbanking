import { Router } from "express";

// Base
import { putBillingPlan } from "../controllers/billing/putBillingPlan";
import { getBilling } from "../controllers/billing/getBilling";
import { getBillingInfo } from "../controllers/billing/getBillingInfo";
import { getBillingDashboard } from "../controllers/billing/getBillingDashboard";

// Ledger
import { recordSplit } from "../controllers/billing/recordSplit";
import { queryLedger } from "../controllers/billing/queryLedger";
import { aggregateRevenue } from "../controllers/billing/aggregateRevenue";
import { getLiveSplitMetrics } from "../controllers/billing/getLiveSplitMetrics";
import { getClientBillingConfig } from "../controllers/billing/getClientBillingConfig";

// Invoice
import { getInvoices } from "../controllers/billing/getInvoices";
import { generateInvoice } from "../controllers/billing/generateInvoice";
import { markPaid } from "../controllers/billing/markPaid";
import { generateCreditNote } from "../controllers/billing/generateCreditNote";
import { exportInvoices } from "../controllers/billing/exportInvoices";
import { convertCurrency } from "../controllers/billing/convertCurrency";

// Lifecycle
import { renewContract } from "../controllers/billing/renewContract";
import { suspendBilling } from "../controllers/billing/suspendBilling";
import { terminateContract } from "../controllers/billing/terminateContract";
import { reactivateBilling } from "../controllers/billing/reactivateBilling";
import { getAlerts } from "../controllers/billing/getAlerts";
import { getSlaMetrics } from "../controllers/billing/getSlaMetrics";
import { getRevenueForecast } from "../controllers/billing/getRevenueForecast";
import { fileDispute } from "../controllers/billing/fileDispute";
import { listDisputes } from "../controllers/billing/listDisputes";
import { resolveDispute } from "../controllers/billing/resolveDispute";

// Payment gateway
import { initializePayment } from "../controllers/billing/initializePayment";
import { verifyPayment } from "../controllers/billing/verifyPayment";
import { paymentWebhook } from "../controllers/billing/paymentWebhook";

// Production
import { generateMonthlyInvoices } from "../controllers/billing/generateMonthlyInvoices";
import { getDunningStatus } from "../controllers/billing/getDunningStatus";
import { applyGracePeriod } from "../controllers/billing/applyGracePeriod";
import { triggerReconciliation } from "../controllers/billing/triggerReconciliation";
import { calculateTax } from "../controllers/billing/calculateTax";
import { migratePlan } from "../controllers/billing/migratePlan";
import { getCreditBalance } from "../controllers/billing/getCreditBalance";
import { topUpCredits } from "../controllers/billing/topUpCredits";
import { getExchangeRates } from "../controllers/billing/getExchangeRates";
import { generateComplianceReport } from "../controllers/billing/generateComplianceReport";

// Audit
import { queryAuditLogs } from "../controllers/billing/queryAuditLogs";
import { getAuditSummary } from "../controllers/billing/getAuditSummary";
import { getResourceHistory } from "../controllers/billing/getResourceHistory";
import { exportAuditCsv } from "../controllers/billing/exportAuditCsv";

// Plan definitions
import { getBillingPlans } from "../controllers/billing/getBillingPlans";
import { createBillingPlan } from "../controllers/billing/createBillingPlan";
import { updateBillingPlan } from "../controllers/billing/updateBillingPlan";
import { deleteBillingPlan } from "../controllers/billing/deleteBillingPlan";
import { getBillingRateCards } from "../controllers/billing/getBillingRateCards";
import { createBillingRateCard } from "../controllers/billing/createBillingRateCard";

const router = Router();

// ─── Base billing ─────────────────────────────────────────────────────────────
router.route("/").get(getBilling).put(putBillingPlan);
router.get("/info", getBillingInfo);
router.get("/dashboard", getBillingDashboard);

// ─── Billing Ledger ───────────────────────────────────────────────────────────
router.post("/ledger/split", recordSplit);
router.get("/ledger", queryLedger);
router.get("/ledger/aggregate", aggregateRevenue);
router.get("/ledger/metrics", getLiveSplitMetrics);
router.get("/ledger/config", getClientBillingConfig);

// ─── Invoices ─────────────────────────────────────────────────────────────────
router.get("/invoices", getInvoices);
router.post("/invoice", generateInvoice);
router.put("/invoice/:invoice_id/paid", markPaid);
router.post("/invoice/:invoice_id/credit", generateCreditNote);
router.get("/invoice/export", exportInvoices);
router.get("/currency/convert", convertCurrency);

// ─── Lifecycle ────────────────────────────────────────────────────────────────
router.post("/lifecycle/renew", renewContract);
router.post("/lifecycle/suspend", suspendBilling);
router.post("/lifecycle/terminate", terminateContract);
router.post("/lifecycle/reactivate", reactivateBilling);
router.get("/lifecycle/alerts", getAlerts);
router.get("/lifecycle/sla", getSlaMetrics);
router.get("/lifecycle/forecast", getRevenueForecast);
router.post("/lifecycle/disputes", fileDispute);
router.get("/lifecycle/disputes", listDisputes);
router.put("/lifecycle/disputes/:dispute_id/resolve", resolveDispute);

// ─── Production ───────────────────────────────────────────────────────────────
router.post("/production/invoices/monthly", generateMonthlyInvoices);
router.get("/production/dunning", getDunningStatus);
router.post("/production/dunning/grace", applyGracePeriod);
router.post("/production/reconciliation", triggerReconciliation);
router.get("/production/tax", calculateTax);
router.post("/production/migrate-plan", migratePlan);
router.get("/production/credits", getCreditBalance);
router.post("/production/credits/top-up", topUpCredits);
router.get("/production/exchange-rates", getExchangeRates);
router.post("/production/compliance", generateComplianceReport);

// ─── Payment gateway ──────────────────────────────────────────────────────────
router.post("/payment/initialize", initializePayment);
router.post("/payment/verify", verifyPayment);
router.post("/payment/webhook", paymentWebhook);

// ─── Audit ────────────────────────────────────────────────────────────────────
router.get("/audit/logs", queryAuditLogs);
router.get("/audit/summary", getAuditSummary);
router.get("/audit/history", getResourceHistory);
router.get("/audit/export", exportAuditCsv);

// ─── Plan definitions ─────────────────────────────────────────────────────────
router.get("/plans", getBillingPlans);
router.post("/plans", createBillingPlan);
router.put("/plans/:id", updateBillingPlan);
router.delete("/plans/:id", deleteBillingPlan);

// ─── Rate cards ───────────────────────────────────────────────────────────────
router.get("/rate-cards", getBillingRateCards);
router.post("/rate-cards", createBillingRateCard);

export default router;
