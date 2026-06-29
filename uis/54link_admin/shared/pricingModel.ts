export interface PricingModelInputs {
  licenseCost: number;
  implementationCost: number;
  customizationCost: number;
  year1SupportCost: number;
  trainingAndGovernanceCost: number;
  vatAmount: number;

  recurringYear2Cost: number;
  recurringYear3Cost: number;
  recurringYear4Cost: number;
  recurringYear5Cost: number;

  requestedNamedUsers: number;
  requestedCustomerRecords: number;
  requestedBranches: number;
  requestedNonProductionEnvironments: number;

  userBlockSize: number;
  userBlockCharge: number;
  customerRecordBlockSize: number;
  customerRecordBlockCharge: number;
  branchChargePerExtraBranch: number;
  extraEnvironmentCharge: number;
  applyExpansionChargesToRenewalYears: boolean;
}

// Included baseline limits
const INCLUDED_NAMED_USERS = 100;
const INCLUDED_CUSTOMER_RECORDS = 100_000;
const INCLUDED_BRANCHES = 10;
const INCLUDED_NON_PRODUCTION_ENVIRONMENTS = 2;

export const defaultPricingModelInputs: PricingModelInputs = {
  licenseCost: 50_000_000,
  implementationCost: 20_000_000,
  customizationCost: 10_000_000,
  year1SupportCost: 10_000_000,
  trainingAndGovernanceCost: 5_000_000,
  vatAmount: 14_250_000,

  recurringYear2Cost: 25_000_000,
  recurringYear3Cost: 25_000_000,
  recurringYear4Cost: 27_500_000,
  recurringYear5Cost: 27_500_000,

  requestedNamedUsers: 100,
  requestedCustomerRecords: 100_000,
  requestedBranches: 10,
  requestedNonProductionEnvironments: 2,

  userBlockSize: 25,
  userBlockCharge: 500_000,
  customerRecordBlockSize: 10_000,
  customerRecordBlockCharge: 200_000,
  branchChargePerExtraBranch: 1_000_000,
  extraEnvironmentCharge: 500_000,
  applyExpansionChargesToRenewalYears: false,
};

interface OverageBreakdown {
  additionalUserBlocks: number;
  namedUserCharge: number;
  additionalCustomerRecordBlocks: number;
  customerRecordCharge: number;
  additionalBranches: number;
  branchCharge: number;
  additionalNonProductionEnvironments: number;
  environmentCharge: number;
}

interface YearlyTotal {
  year: number;
  baseCost: number;
  expansionCost: number;
  totalCost: number;
}

interface PricingResult {
  year1BaseTotal: number;
  year1ExpansionTotal: number;
  year1Total: number;
  renewalBaseTotal: number;
  renewalExpansionTotal: number;
  years2To5Total: number;
  fiveYearTotal: number;
  overageBreakdown: OverageBreakdown;
  yearlyTotals: YearlyTotal[];
}

export function calculatePlatformPricing(inputs: PricingModelInputs): PricingResult {
  const year1BaseTotal =
    inputs.licenseCost +
    inputs.implementationCost +
    inputs.customizationCost +
    inputs.year1SupportCost +
    inputs.trainingAndGovernanceCost +
    inputs.vatAmount;

  const additionalUserBlocks = Math.max(
    0,
    Math.ceil((inputs.requestedNamedUsers - INCLUDED_NAMED_USERS) / inputs.userBlockSize),
  );
  const namedUserCharge = additionalUserBlocks * inputs.userBlockCharge;

  const additionalCustomerRecordBlocks = Math.max(
    0,
    Math.ceil(
      (inputs.requestedCustomerRecords - INCLUDED_CUSTOMER_RECORDS) /
        inputs.customerRecordBlockSize,
    ),
  );
  const customerRecordCharge = additionalCustomerRecordBlocks * inputs.customerRecordBlockCharge;

  const additionalBranches = Math.max(
    0,
    inputs.requestedBranches - INCLUDED_BRANCHES,
  );
  const branchCharge = additionalBranches * inputs.branchChargePerExtraBranch;

  const additionalNonProductionEnvironments = Math.max(
    0,
    inputs.requestedNonProductionEnvironments - INCLUDED_NON_PRODUCTION_ENVIRONMENTS,
  );
  const environmentCharge =
    additionalNonProductionEnvironments * inputs.extraEnvironmentCharge;

  const year1ExpansionTotal =
    namedUserCharge + customerRecordCharge + branchCharge + environmentCharge;

  const year1Total = year1BaseTotal + year1ExpansionTotal;

  const renewalExpansionPerYear = inputs.applyExpansionChargesToRenewalYears
    ? year1ExpansionTotal
    : 0;

  const recurringCosts = [
    inputs.recurringYear2Cost,
    inputs.recurringYear3Cost,
    inputs.recurringYear4Cost,
    inputs.recurringYear5Cost,
  ];

  const renewalBaseTotal = recurringCosts.reduce((a, b) => a + b, 0);
  const renewalExpansionTotal = renewalExpansionPerYear * 4;
  const years2To5Total = renewalBaseTotal + renewalExpansionTotal;
  const fiveYearTotal = year1Total + years2To5Total;

  const yearlyTotals: YearlyTotal[] = [
    { year: 1, baseCost: year1BaseTotal, expansionCost: year1ExpansionTotal, totalCost: year1Total },
    ...recurringCosts.map((base, i) => ({
      year: i + 2,
      baseCost: base,
      expansionCost: renewalExpansionPerYear,
      totalCost: base + renewalExpansionPerYear,
    })),
  ];

  return {
    year1BaseTotal,
    year1ExpansionTotal,
    year1Total,
    renewalBaseTotal,
    renewalExpansionTotal,
    years2To5Total,
    fiveYearTotal,
    overageBreakdown: {
      additionalUserBlocks,
      namedUserCharge,
      additionalCustomerRecordBlocks,
      customerRecordCharge,
      additionalBranches,
      branchCharge,
      additionalNonProductionEnvironments,
      environmentCharge,
    },
    yearlyTotals,
  };
}

export function formatNaira(amount: number): string {
  return `₦${amount.toLocaleString("en-NG")}`;
}
