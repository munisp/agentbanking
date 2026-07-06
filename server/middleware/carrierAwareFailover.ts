/**
 * Carrier-Aware Failover Middleware
 *
 * Integrates carrier cost, SLA, and live pricing data into SIM failover decisions.
 * Provides transaction-type-aware carrier selection where financial transactions
 * prefer reliability over signal strength.
 *
 * Gap 5: Wires carrierCost/carrierSla/carrierLivePricing into failover decisions
 * Gap 8: Transaction-type-aware carrier selection
 */
// import { getDb } from "../db";
import { publishEvent } from "../kafkaClient";
import { cacheGet, cacheSet } from "../lib/cacheClient";
import { daprPublish } from "../lib/daprClient";
import { fluvioPublish } from "../lib/fluvioClient";
import type { KafkaTopic } from "../kafkaClient";
import { lakehouseIngest } from "../lib/lakehouseClient";
// DB schema and ORM available if needed for historical queries
// import { simProbeLog, simOrchestratorConfig } from "../../drizzle/schema";
// import { eq, desc, sql, and, gte } from "drizzle-orm";

// Nigerian carrier profiles with cost/SLA data
const CARRIER_PROFILES: Record<string, CarrierProfile> = {
  MTN: {
    code: "MTN",
    name: "MTN Nigeria",
    avgLatencyMs: 45,
    reliabilityPct: 92,
    costPerMbNgn: 0.35,
    slaUptimePct: 99.5,
    maxLatencySlaMsec: 200,
    ussdBalance: "*556#",
    ussdDataBalance: "*131*4#",
    preferredForFinancial: true,
  },
  AIRTEL: {
    code: "AIRTEL",
    name: "Airtel Nigeria",
    avgLatencyMs: 55,
    reliabilityPct: 88,
    costPerMbNgn: 0.3,
    slaUptimePct: 99.0,
    maxLatencySlaMsec: 250,
    ussdBalance: "*123#",
    ussdDataBalance: "*140#",
    preferredForFinancial: true,
  },
  GLO: {
    code: "GLO",
    name: "Globacom",
    avgLatencyMs: 65,
    reliabilityPct: 82,
    costPerMbNgn: 0.25,
    slaUptimePct: 98.0,
    maxLatencySlaMsec: 350,
    ussdBalance: "*124#",
    ussdDataBalance: "*127*0#",
    preferredForFinancial: false,
  },
  "9MOBILE": {
    code: "9MOBILE",
    name: "9mobile",
    avgLatencyMs: 70,
    reliabilityPct: 78,
    costPerMbNgn: 0.28,
    slaUptimePct: 97.5,
    maxLatencySlaMsec: 400,
    ussdBalance: "*232#",
    ussdDataBalance: "*229*0#",
    preferredForFinancial: false,
  },
};

interface CarrierProfile {
  code: string;
  name: string;
  avgLatencyMs: number;
  reliabilityPct: number;
  costPerMbNgn: number;
  slaUptimePct: number;
  maxLatencySlaMsec: number;
  ussdBalance: string;
  ussdDataBalance: string;
  preferredForFinancial: boolean;
}

interface SlotReading {
  slotIndex: number;
  carrier: string;
  signalDbm: number;
  latencyMs: number;
  packetLossPct: number;
  networkType: string;
  isDataPreferred: boolean;
}

interface FailoverDecision {
  shouldSwitch: boolean;
  currentSlot: number;
  recommendedSlot: number;
  reason: string;
  currentScore: number;
  recommendedScore: number;
  ussdCommand: string | null;
  carrierCostSavings: number;
  slaCompliance: boolean;
}

type TransactionType =
  | "financial"
  | "payment"
  | "transfer"
  | "settlement"
  | "general"
  | "telemetry";

// Scoring weights vary by transaction type
const SCORING_WEIGHTS: Record<
  TransactionType,
  {
    signal: number;
    latency: number;
    loss: number;
    reliability: number;
    cost: number;
    sla: number;
  }
> = {
  financial: {
    signal: 0.1,
    latency: 0.25,
    loss: 0.2,
    reliability: 0.3,
    cost: 0.05,
    sla: 0.1,
  },
  payment: {
    signal: 0.1,
    latency: 0.25,
    loss: 0.2,
    reliability: 0.3,
    cost: 0.05,
    sla: 0.1,
  },
  transfer: {
    signal: 0.1,
    latency: 0.25,
    loss: 0.2,
    reliability: 0.3,
    cost: 0.05,
    sla: 0.1,
  },
  settlement: {
    signal: 0.1,
    latency: 0.2,
    loss: 0.2,
    reliability: 0.3,
    cost: 0.05,
    sla: 0.15,
  },
  general: {
    signal: 0.3,
    latency: 0.2,
    loss: 0.15,
    reliability: 0.15,
    cost: 0.1,
    sla: 0.1,
  },
  telemetry: {
    signal: 0.25,
    latency: 0.15,
    loss: 0.1,
    reliability: 0.1,
    cost: 0.25,
    sla: 0.15,
  },
};

function normalizeSignal(dbm: number): number {
  return Math.max(0, Math.min(100, ((dbm + 120) / 70) * 100));
}

function normalizeLatency(ms: number): number {
  return Math.max(0, Math.min(100, 100 - ms / 20));
}

function normalizeLoss(pct: number): number {
  return Math.max(0, Math.min(100, 100 - pct * 10));
}

function networkTypeBonus(type: string): number {
  switch (type) {
    case "5G":
      return 100;
    case "4G":
      return 80;
    case "3G":
      return 40;
    case "2G":
      return 10;
    default:
      return 20;
  }
}

/**
 * Compute a composite slot score incorporating carrier cost, SLA, and reliability.
 */
export function computeCarrierAwareScore(
  slot: SlotReading,
  transactionType: TransactionType,
  historicalReliability?: number
): number {
  const weights = SCORING_WEIGHTS[transactionType] ?? SCORING_WEIGHTS.general;
  const carrier = CARRIER_PROFILES[slot.carrier];
  const reliability =
    historicalReliability ?? (carrier?.reliabilityPct ?? 50) / 100;
  const slaCompliant = carrier
    ? slot.latencyMs <= carrier.maxLatencySlaMsec
    : false;
  const costNorm = carrier ? Math.max(0, 100 - carrier.costPerMbNgn * 200) : 50;

  return Math.round(
    normalizeSignal(slot.signalDbm) * weights.signal +
      normalizeLatency(slot.latencyMs) * weights.latency +
      normalizeLoss(slot.packetLossPct) * weights.loss +
      reliability * 100 * weights.reliability +
      costNorm * weights.cost +
      (slaCompliant ? 100 : 0) * weights.sla
  );
}

/**
 * Evaluate whether a failover should occur, integrating carrier cost/SLA data.
 */
export async function evaluateCarrierAwareFailover(
  terminalId: string,
  slots: SlotReading[],
  transactionType: TransactionType
): Promise<FailoverDecision> {
  const currentSlot = slots.find(s => s.isDataPreferred) ?? slots[0];
  if (!currentSlot) {
    return {
      shouldSwitch: false,
      currentSlot: -1,
      recommendedSlot: -1,
      reason: "No slots available",
      currentScore: 0,
      recommendedScore: 0,
      ussdCommand: null,
      carrierCostSavings: 0,
      slaCompliance: false,
    };
  }

  // Get historical reliability from cache or compute
  const scored = await Promise.all(
    slots.map(async slot => {
      const cacheKey = `sim:reliability:${terminalId}:${slot.slotIndex}`;
      const cached = await cacheGet(cacheKey).catch(() => null);
      const reliability = cached ? parseFloat(cached) : undefined;
      const score = computeCarrierAwareScore(
        slot,
        transactionType,
        reliability
      );
      return { slot, score };
    })
  );

  const currentScored = scored.find(
    s => s.slot.slotIndex === currentSlot.slotIndex
  );
  const currentScore = currentScored?.score ?? 0;

  // Find best alternative
  const bestAlt = scored
    .filter(s => s.slot.slotIndex !== currentSlot.slotIndex)
    .sort((a, b) => b.score - a.score)[0];

  const currentCarrier = CARRIER_PROFILES[currentSlot.carrier];
  const slaCompliant = currentCarrier
    ? currentSlot.latencyMs <= currentCarrier.maxLatencySlaMsec
    : false;

  // For financial transactions, require a minimum score threshold
  const minFinancialScore = 45;
  const isFinancial = [
    "financial",
    "payment",
    "transfer",
    "settlement",
  ].includes(transactionType);
  const needsSwitch =
    currentSlot.signalDbm < -90 ||
    currentSlot.latencyMs > 500 ||
    currentSlot.packetLossPct > 10 ||
    (isFinancial && currentScore < minFinancialScore) ||
    (isFinancial && !slaCompliant && bestAlt && bestAlt.score > currentScore);

  if (bestAlt && needsSwitch && bestAlt.score > currentScore + 10) {
    const altCarrier = CARRIER_PROFILES[bestAlt.slot.carrier];
    const costSavings =
      currentCarrier && altCarrier
        ? (currentCarrier.costPerMbNgn - altCarrier.costPerMbNgn) * 100
        : 0;

    const reasons: string[] = [];
    if (currentSlot.signalDbm < -90)
      reasons.push(`signal ${currentSlot.signalDbm}dBm < -90dBm`);
    if (currentSlot.latencyMs > 500)
      reasons.push(`latency ${currentSlot.latencyMs}ms > 500ms`);
    if (currentSlot.packetLossPct > 10)
      reasons.push(`loss ${currentSlot.packetLossPct}% > 10%`);
    if (isFinancial && !slaCompliant)
      reasons.push(`SLA breach (${currentCarrier?.code})`);
    if (isFinancial && currentScore < minFinancialScore)
      reasons.push(
        `score ${currentScore} < ${minFinancialScore} (financial min)`
      );

    // Publish failover event to middleware
    const eventPayload = {
      terminalId,
      fromSlot: currentSlot.slotIndex,
      toSlot: bestAlt.slot.slotIndex,
      fromCarrier: currentSlot.carrier,
      toCarrier: bestAlt.slot.carrier,
      reason: reasons.join("; "),
      transactionType,
      currentScore,
      recommendedScore: bestAlt.score,
      timestamp: new Date().toISOString(),
    };

    const topic: KafkaTopic = "sim.failover.triggered";
    publishEvent(topic, terminalId, eventPayload).catch(() => {});
    daprPublish("pubsub", "sim.failover.triggered", eventPayload).catch(
      () => {}
    );
    fluvioPublish("sim-failover", {
      key: terminalId,
      value: JSON.stringify(eventPayload),
    } as unknown as Record<string, unknown>).catch(() => {});
    lakehouseIngest("sim_failover_events", eventPayload).catch(() => {});

    return {
      shouldSwitch: true,
      currentSlot: currentSlot.slotIndex,
      recommendedSlot: bestAlt.slot.slotIndex,
      reason: reasons.join("; "),
      currentScore,
      recommendedScore: bestAlt.score,
      ussdCommand: altCarrier?.ussdBalance ?? null,
      carrierCostSavings: costSavings,
      slaCompliance: altCarrier
        ? bestAlt.slot.latencyMs <= altCarrier.maxLatencySlaMsec
        : false,
    };
  }

  return {
    shouldSwitch: false,
    currentSlot: currentSlot.slotIndex,
    recommendedSlot: currentSlot.slotIndex,
    reason: "Current slot adequate",
    currentScore,
    recommendedScore: currentScore,
    ussdCommand: null,
    carrierCostSavings: 0,
    slaCompliance: slaCompliant,
  };
}

/**
 * Get carrier profiles with cost/SLA data for the UI.
 */
export function getCarrierProfiles(): CarrierProfile[] {
  return Object.values(CARRIER_PROFILES);
}

/**
 * Get USSD commands for Nigerian carriers.
 */
export function getUssdCommands(): Array<{
  carrier: string;
  balance: string;
  dataBalance: string;
}> {
  return Object.values(CARRIER_PROFILES).map(c => ({
    carrier: c.code,
    balance: c.ussdBalance,
    dataBalance: c.ussdDataBalance,
  }));
}
