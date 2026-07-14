/**
 * Domain Calculations — fee, commission, interest, tax, and penalty
 * calculations for all financial operations across the 54agent platform.
 */

// ── Fee Calculations ────────────────────────────────────────────────────────

export interface FeeSchedule {
  flatFee: number;
  percentageFee: number;
  minFee: number;
  maxFee: number;
  currency?: string;
}

const DEFAULT_FEE_SCHEDULES: Record<string, FeeSchedule> = {
  cashIn: { flatFee: 50, percentageFee: 0.5, minFee: 50, maxFee: 5000 },
  cashOut: { flatFee: 100, percentageFee: 1.0, minFee: 100, maxFee: 10000 },
  transfer: { flatFee: 25, percentageFee: 0.25, minFee: 25, maxFee: 2500 },
  billPayment: { flatFee: 100, percentageFee: 0, minFee: 100, maxFee: 100 },
  airtimeVending: {
    flatFee: 0,
    percentageFee: 2.5,
    minFee: 10,
    maxFee: 500,
  },
  crossBorder: {
    flatFee: 500,
    percentageFee: 1.5,
    minFee: 500,
    maxFee: 50000,
  },
  merchantPayment: {
    flatFee: 0,
    percentageFee: 1.5,
    minFee: 25,
    maxFee: 15000,
  },
  loanDisbursement: {
    flatFee: 200,
    percentageFee: 1.0,
    minFee: 200,
    maxFee: 20000,
  },
  insurance: { flatFee: 50, percentageFee: 0.5, minFee: 50, maxFee: 5000 },
  settlement: { flatFee: 0, percentageFee: 0.1, minFee: 10, maxFee: 1000 },
};

export function calculateFee(
  amount: number,
  txType: string,
  overrides?: Partial<FeeSchedule>
): { fee: number; breakdown: { flat: number; percentage: number } } {
  const schedule = {
    ...(DEFAULT_FEE_SCHEDULES[txType] ?? DEFAULT_FEE_SCHEDULES.transfer),
    ...overrides,
  };

  const flat = schedule.flatFee;
  const percentage = amount * (schedule.percentageFee / 100);
  const rawFee = flat + percentage;
  const fee = Math.min(Math.max(rawFee, schedule.minFee), schedule.maxFee);

  return {
    fee: Math.round(fee * 100) / 100,
    breakdown: {
      flat: Math.round(flat * 100) / 100,
      percentage: Math.round(percentage * 100) / 100,
    },
  };
}

// ── Commission Calculations ─────────────────────────────────────────────────

export interface CommissionSplit {
  agentShare: number;
  platformShare: number;
  superAgentShare: number;
  aggregatorShare: number;
}

const DEFAULT_COMMISSION_RATES: Record<
  string,
  { agent: number; platform: number; superAgent: number; aggregator: number }
> = {
  cashIn: { agent: 40, platform: 30, superAgent: 20, aggregator: 10 },
  cashOut: { agent: 45, platform: 25, superAgent: 20, aggregator: 10 },
  transfer: { agent: 35, platform: 35, superAgent: 20, aggregator: 10 },
  billPayment: { agent: 50, platform: 20, superAgent: 20, aggregator: 10 },
  airtimeVending: { agent: 60, platform: 15, superAgent: 15, aggregator: 10 },
  crossBorder: { agent: 30, platform: 40, superAgent: 20, aggregator: 10 },
  merchantPayment: {
    agent: 25,
    platform: 45,
    superAgent: 20,
    aggregator: 10,
  },
  loanOrigination: {
    agent: 20,
    platform: 50,
    superAgent: 20,
    aggregator: 10,
  },
  insurance: { agent: 30, platform: 40, superAgent: 20, aggregator: 10 },
};

export function calculateCommission(
  fee: number,
  txType: string,
  overrides?: Partial<{
    agent: number;
    platform: number;
    superAgent: number;
    aggregator: number;
  }>
): CommissionSplit {
  const rates = {
    ...(DEFAULT_COMMISSION_RATES[txType] ?? DEFAULT_COMMISSION_RATES.transfer),
    ...overrides,
  };

  const total =
    rates.agent + rates.platform + rates.superAgent + rates.aggregator;

  return {
    agentShare: Math.round(((fee * rates.agent) / total) * 100) / 100,
    platformShare: Math.round(((fee * rates.platform) / total) * 100) / 100,
    superAgentShare: Math.round(((fee * rates.superAgent) / total) * 100) / 100,
    aggregatorShare: Math.round(((fee * rates.aggregator) / total) * 100) / 100,
  };
}

// ── Interest Calculations ───────────────────────────────────────────────────

export function calculateSimpleInterest(
  principal: number,
  annualRate: number,
  days: number
): number {
  return (
    Math.round(((principal * annualRate * days) / (100 * 365)) * 100) / 100
  );
}

export function calculateCompoundInterest(
  principal: number,
  annualRate: number,
  periods: number,
  compoundingFrequency: number = 12
): number {
  const rate = annualRate / 100 / compoundingFrequency;
  const amount = principal * Math.pow(1 + rate, periods);
  return Math.round((amount - principal) * 100) / 100;
}

export function calculateLoanRepayment(
  principal: number,
  annualRate: number,
  termMonths: number
): {
  monthlyPayment: number;
  totalInterest: number;
  totalPayment: number;
  amortizationSchedule: Array<{
    month: number;
    payment: number;
    principal: number;
    interest: number;
    balance: number;
  }>;
} {
  const monthlyRate = annualRate / 100 / 12;

  let monthlyPayment: number;
  if (monthlyRate === 0) {
    monthlyPayment = principal / termMonths;
  } else {
    monthlyPayment =
      (principal * monthlyRate * Math.pow(1 + monthlyRate, termMonths)) /
      (Math.pow(1 + monthlyRate, termMonths) - 1);
  }

  monthlyPayment = Math.round(monthlyPayment * 100) / 100;

  const schedule: Array<{
    month: number;
    payment: number;
    principal: number;
    interest: number;
    balance: number;
  }> = [];
  let balance = principal;

  for (let month = 1; month <= termMonths; month++) {
    const interestPortion = Math.round(balance * monthlyRate * 100) / 100;
    const principalPortion =
      Math.round((monthlyPayment - interestPortion) * 100) / 100;
    balance = Math.round((balance - principalPortion) * 100) / 100;
    if (balance < 0) balance = 0;

    schedule.push({
      month,
      payment: monthlyPayment,
      principal: principalPortion,
      interest: interestPortion,
      balance,
    });
  }

  const totalPayment = monthlyPayment * termMonths;
  const totalInterest = Math.round((totalPayment - principal) * 100) / 100;

  return {
    monthlyPayment,
    totalInterest,
    totalPayment: Math.round(totalPayment * 100) / 100,
    amortizationSchedule: schedule,
  };
}

// ── Tax Calculations ────────────────────────────────────────────────────────

export interface TaxResult {
  taxAmount: number;
  netAmount: number;
  taxRate: number;
  taxType: string;
}

const TAX_RATES: Record<string, number> = {
  VAT: 7.5, // Nigeria VAT
  WHT: 10, // Withholding tax on commissions
  STAMP_DUTY: 0.0075, // NGN 50 stamp duty per transaction > 10,000
  CGT: 10, // Capital gains tax
};

export function calculateTax(
  amount: number,
  taxType: string,
  customRate?: number
): TaxResult {
  const rate = customRate ?? TAX_RATES[taxType] ?? 0;

  if (taxType === "STAMP_DUTY") {
    const taxAmount = amount > 10000 ? 50 : 0;
    return { taxAmount, netAmount: amount - taxAmount, taxRate: rate, taxType };
  }

  const taxAmount = Math.round(amount * (rate / 100) * 100) / 100;
  return {
    taxAmount,
    netAmount: Math.round((amount - taxAmount) * 100) / 100,
    taxRate: rate,
    taxType,
  };
}

export function calculateWithholdingTax(commissionAmount: number): TaxResult {
  return calculateTax(commissionAmount, "WHT");
}

export function calculateVAT(amount: number): TaxResult {
  return calculateTax(amount, "VAT");
}

// ── Penalty Calculations ────────────────────────────────────────────────────

export function calculateLatePenalty(
  amount: number,
  daysOverdue: number,
  dailyRate: number = 0.1,
  maxPenaltyPercent: number = 25
): { penalty: number; daysOverdue: number; effectiveRate: number } {
  const rawPenalty = amount * (dailyRate / 100) * daysOverdue;
  const maxPenalty = amount * (maxPenaltyPercent / 100);
  const penalty = Math.round(Math.min(rawPenalty, maxPenalty) * 100) / 100;
  const effectiveRate =
    Math.round(((penalty / amount) * 100 + Number.EPSILON) * 100) / 100;

  return { penalty, daysOverdue, effectiveRate };
}

// ── Exchange Rate Calculations ──────────────────────────────────────────────

export function convertCurrency(
  amount: number,
  rate: number,
  spread: number = 0.5,
  direction: "buy" | "sell" = "buy"
): {
  convertedAmount: number;
  effectiveRate: number;
  spreadAmount: number;
} {
  const spreadMultiplier =
    direction === "buy" ? 1 + spread / 100 : 1 - spread / 100;
  const effectiveRate = Math.round(rate * spreadMultiplier * 10000) / 10000;
  const convertedAmount = Math.round(amount * effectiveRate * 100) / 100;
  const spreadAmount =
    Math.round(Math.abs(convertedAmount - amount * rate) * 100) / 100;

  return { convertedAmount, effectiveRate, spreadAmount };
}

// ── Float Management ────────────────────────────────────────────────────────

export function calculateFloatRequirement(
  dailyVolume: number,
  bufferMultiplier: number = 1.5,
  peakFactor: number = 2.0
): {
  minimumFloat: number;
  recommendedFloat: number;
  peakFloat: number;
} {
  return {
    minimumFloat: Math.round(dailyVolume * 100) / 100,
    recommendedFloat: Math.round(dailyVolume * bufferMultiplier * 100) / 100,
    peakFloat: Math.round(dailyVolume * peakFactor * 100) / 100,
  };
}

// ── Reconciliation ──────────────────────────────────────────────────────────

export function calculateMatchRate(
  totalRecords: number,
  matchedRecords: number
): {
  matchRate: number;
  discrepancyRate: number;
  status: "excellent" | "good" | "review" | "critical";
} {
  if (totalRecords === 0)
    return { matchRate: 100, discrepancyRate: 0, status: "excellent" };

  const matchRate =
    Math.round(((matchedRecords / totalRecords) * 100 + Number.EPSILON) * 100) /
    100;
  const discrepancyRate = Math.round((100 - matchRate) * 100) / 100;

  let status: "excellent" | "good" | "review" | "critical";
  if (matchRate >= 99.9) status = "excellent";
  else if (matchRate >= 99) status = "good";
  else if (matchRate >= 95) status = "review";
  else status = "critical";

  return { matchRate, discrepancyRate, status };
}
