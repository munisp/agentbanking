import { useMemo, useState } from "react";
import { Download, RefreshCcw } from "lucide-react";

import {
  calculatePlatformPricing,
  defaultPricingModelInputs,
  formatNaira,
  type PricingModelInputs,
} from "@shared/pricingModel";

function readNumber(value: string, fallback: number) {
  const parsed = Number(value.replace(/,/g, ""));
  return Number.isFinite(parsed) ? parsed : fallback;
}

function NumberField({
  label,
  value,
  onChange,
  hint,
  min = 0,
  step = 1,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  hint: string;
  min?: number;
  step?: number;
}) {
  return (
    <label className="block rounded-[1.2rem] bg-stone-50 p-4">
      <span className="text-sm font-semibold text-stone-900">{label}</span>
      <input
        type="number"
        min={min}
        step={step}
        value={value}
        onChange={(event) => onChange(readNumber(event.target.value, value))}
        className="mt-3 h-11 w-full rounded-xl border border-stone-200 bg-white px-4 text-sm text-stone-900 outline-none ring-0 transition focus:border-emerald-500"
      />
      <span className="mt-2 block text-xs leading-5 text-stone-500">{hint}</span>
    </label>
  );
}

function buildSummary(inputs: PricingModelInputs) {
  const result = calculatePlatformPricing(inputs);

  return `54link-dev dynamic pricing model summary\n\nYear 1 base total: ${formatNaira(result.year1BaseTotal)}\nYear 1 expansion total: ${formatNaira(result.year1ExpansionTotal)}\nYear 1 total: ${formatNaira(result.year1Total)}\nYears 2-5 total: ${formatNaira(result.years2To5Total)}\nFive-year total: ${formatNaira(result.fiveYearTotal)}\n\nRequested scope\n- Named users: ${inputs.requestedNamedUsers}\n- Customer records: ${inputs.requestedCustomerRecords}\n- Branches: ${inputs.requestedBranches}\n- Non-production environments: ${inputs.requestedNonProductionEnvironments}\n\nOverage breakdown\n- Additional user blocks: ${result.overageBreakdown.additionalUserBlocks}\n- Named user charge: ${formatNaira(result.overageBreakdown.namedUserCharge)}\n- Additional customer record blocks: ${result.overageBreakdown.additionalCustomerRecordBlocks}\n- Customer record charge: ${formatNaira(result.overageBreakdown.customerRecordCharge)}\n- Additional branches: ${result.overageBreakdown.additionalBranches}\n- Branch charge: ${formatNaira(result.overageBreakdown.branchCharge)}\n- Additional environments: ${result.overageBreakdown.additionalNonProductionEnvironments}\n- Environment charge: ${formatNaira(result.overageBreakdown.environmentCharge)}\n`;
}

export default function PricingModelTool() {
  const [inputs, setInputs] = useState<PricingModelInputs>(defaultPricingModelInputs);

  const result = useMemo(() => calculatePlatformPricing(inputs), [inputs]);

  function update<K extends keyof PricingModelInputs>(key: K, value: PricingModelInputs[K]) {
    setInputs((current) => ({ ...current, [key]: value }));
  }

  function resetModel() {
    setInputs(defaultPricingModelInputs);
  }

  function downloadSummary() {
    const blob = new Blob([buildSummary(inputs)], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "54link-dev-pricing-model-summary.txt";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  return (
    <section className="rounded-[1.8rem] bg-white p-6 shadow-[0_18px_60px_rgba(15,23,42,0.08)] sm:p-7">
      <div className="flex flex-col gap-5 border-b border-stone-100 pb-6 lg:flex-row lg:items-start lg:justify-between">
        <div className="max-w-3xl">
          <p className="text-xs uppercase tracking-[0.22em] text-stone-400">Dynamic commercial model</p>
          <h2 className="mt-3 text-2xl font-semibold text-stone-900 sm:text-3xl">Platform pricing calculator</h2>
          <p className="mt-3 text-sm leading-7 text-stone-600">
            Adjust the base licence, implementation, support, recurring years, and capacity assumptions to calculate
            Year 1 pricing, expansion charges, renewal-year exposure, and the five-year commercial value of the platform.
          </p>
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            onClick={resetModel}
            className="inline-flex items-center gap-2 rounded-xl border border-stone-200 bg-white px-4 py-3 text-sm font-semibold text-stone-700 transition hover:bg-stone-50"
          >
            <RefreshCcw size={16} />
            Reset to Mutual Benefits baseline
          </button>
          <button
            type="button"
            onClick={downloadSummary}
            className="inline-flex items-center gap-2 rounded-xl bg-stone-950 px-4 py-3 text-sm font-semibold text-white transition hover:bg-stone-800"
          >
            <Download size={16} />
            Download summary
          </button>
        </div>
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1.08fr)_minmax(360px,0.92fr)]">
        <div className="space-y-6">
          <div>
            <h3 className="text-lg font-semibold text-stone-900">Base Year 1 assumptions</h3>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <NumberField label="Licence cost" value={inputs.licenseCost} onChange={(value) => update("licenseCost", value)} hint="Base Year 1 software licence charge." step={100000} />
              <NumberField label="Implementation cost" value={inputs.implementationCost} onChange={(value) => update("implementationCost", value)} hint="Configuration, migration, SIT, UAT, and rollout." step={100000} />
              <NumberField label="Customization cost" value={inputs.customizationCost} onChange={(value) => update("customizationCost", value)} hint="Institution-specific tailoring and integration shaping." step={100000} />
              <NumberField label="Year 1 support cost" value={inputs.year1SupportCost} onChange={(value) => update("year1SupportCost", value)} hint="Stabilization and managed support during Year 1." step={100000} />
              <NumberField label="Training and governance" value={inputs.trainingAndGovernanceCost} onChange={(value) => update("trainingAndGovernanceCost", value)} hint="Training, handover, PMO, and deployment advisory." step={100000} />
              <NumberField label="VAT amount" value={inputs.vatAmount} onChange={(value) => update("vatAmount", value)} hint="Kept separate to match the proposal pricing structure." step={100000} />
            </div>
          </div>

          <div>
            <h3 className="text-lg font-semibold text-stone-900">Requested deployment scope</h3>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <NumberField label="Named internal users" value={inputs.requestedNamedUsers} onChange={(value) => update("requestedNamedUsers", value)} hint="Total named users required by the institution." />
              <NumberField label="Customer records" value={inputs.requestedCustomerRecords} onChange={(value) => update("requestedCustomerRecords", value)} hint="Projected onboarded customers covered by the licence." step={1000} />
              <NumberField label="Branches or service locations" value={inputs.requestedBranches} onChange={(value) => update("requestedBranches", value)} hint="Total branches included in the required scope." />
              <NumberField label="Non-production environments" value={inputs.requestedNonProductionEnvironments} onChange={(value) => update("requestedNonProductionEnvironments", value)} hint="Total UAT, staging, or other non-production environments requested." />
            </div>
          </div>

          <div>
            <h3 className="text-lg font-semibold text-stone-900">Renewal and overage assumptions</h3>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <NumberField label="Year 2 recurring cost" value={inputs.recurringYear2Cost} onChange={(value) => update("recurringYear2Cost", value)} hint="Annual recurring charge for Year 2." step={100000} />
              <NumberField label="Year 3 recurring cost" value={inputs.recurringYear3Cost} onChange={(value) => update("recurringYear3Cost", value)} hint="Annual recurring charge for Year 3." step={100000} />
              <NumberField label="Year 4 recurring cost" value={inputs.recurringYear4Cost} onChange={(value) => update("recurringYear4Cost", value)} hint="Annual recurring charge for Year 4." step={100000} />
              <NumberField label="Year 5 recurring cost" value={inputs.recurringYear5Cost} onChange={(value) => update("recurringYear5Cost", value)} hint="Annual recurring charge for Year 5." step={100000} />
              <NumberField label="User block size" value={inputs.userBlockSize} onChange={(value) => update("userBlockSize", value)} hint="Additional users are priced in this block size." />
              <NumberField label="User block charge" value={inputs.userBlockCharge} onChange={(value) => update("userBlockCharge", value)} hint="Charge per additional user block." step={100000} />
              <NumberField label="Customer-record block size" value={inputs.customerRecordBlockSize} onChange={(value) => update("customerRecordBlockSize", value)} hint="Additional customer records are priced in this block size." step={1000} />
              <NumberField label="Customer-record block charge" value={inputs.customerRecordBlockCharge} onChange={(value) => update("customerRecordBlockCharge", value)} hint="Charge per additional customer-record block." step={100000} />
              <NumberField label="Extra branch charge" value={inputs.branchChargePerExtraBranch} onChange={(value) => update("branchChargePerExtraBranch", value)} hint="Charge per branch above the included baseline." step={100000} />
              <NumberField label="Extra environment charge" value={inputs.extraEnvironmentCharge} onChange={(value) => update("extraEnvironmentCharge", value)} hint="Charge per non-production environment above the included baseline." step={100000} />
            </div>
            <label className="mt-4 flex items-start gap-3 rounded-[1.2rem] bg-emerald-50 px-4 py-4 text-sm text-emerald-900">
              <input
                type="checkbox"
                checked={inputs.applyExpansionChargesToRenewalYears}
                onChange={(event) => update("applyExpansionChargesToRenewalYears", event.target.checked)}
                className="mt-1 h-4 w-4 rounded border-emerald-300 text-emerald-700"
              />
              <span>
                Apply expansion charges to Years 2-5 as recurring annual capacity charges.
              </span>
            </label>
          </div>
        </div>

        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-1">
            <article className="rounded-[1.5rem] bg-stone-950 p-5 text-white shadow-[0_18px_60px_rgba(15,23,42,0.12)]">
              <p className="text-xs uppercase tracking-[0.18em] text-emerald-200/80">Year 1 total</p>
              <p className="mt-4 text-3xl font-semibold">{formatNaira(result.year1Total)}</p>
              <p className="mt-2 text-sm leading-6 text-stone-300">{formatNaira(result.year1BaseTotal)} base plus {formatNaira(result.year1ExpansionTotal)} expansion.</p>
            </article>
            <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
              <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Years 2-5 total</p>
              <p className="mt-4 text-3xl font-semibold text-stone-900">{formatNaira(result.years2To5Total)}</p>
              <p className="mt-2 text-sm leading-6 text-stone-500">{formatNaira(result.renewalBaseTotal)} recurring base plus {formatNaira(result.renewalExpansionTotal)} expansion.</p>
            </article>
            <article className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
              <p className="text-xs uppercase tracking-[0.18em] text-stone-400">Five-year total</p>
              <p className="mt-4 text-3xl font-semibold text-stone-900">{formatNaira(result.fiveYearTotal)}</p>
              <p className="mt-2 text-sm leading-6 text-stone-500">Dynamic total across initial delivery and renewal years.</p>
            </article>
          </div>

          <div className="rounded-[1.5rem] bg-stone-50 p-5">
            <h3 className="text-lg font-semibold text-stone-900">Expansion breakdown</h3>
            <div className="mt-4 space-y-3 text-sm text-stone-600">
              <div className="flex items-center justify-between gap-3"><span>Named user expansion</span><span className="font-semibold text-stone-900">{result.overageBreakdown.additionalUserBlocks} block(s) · {formatNaira(result.overageBreakdown.namedUserCharge)}</span></div>
              <div className="flex items-center justify-between gap-3"><span>Customer record expansion</span><span className="font-semibold text-stone-900">{result.overageBreakdown.additionalCustomerRecordBlocks} block(s) · {formatNaira(result.overageBreakdown.customerRecordCharge)}</span></div>
              <div className="flex items-center justify-between gap-3"><span>Branch expansion</span><span className="font-semibold text-stone-900">{result.overageBreakdown.additionalBranches} extra · {formatNaira(result.overageBreakdown.branchCharge)}</span></div>
              <div className="flex items-center justify-between gap-3"><span>Environment expansion</span><span className="font-semibold text-stone-900">{result.overageBreakdown.additionalNonProductionEnvironments} extra · {formatNaira(result.overageBreakdown.environmentCharge)}</span></div>
            </div>
          </div>

          <div className="rounded-[1.5rem] bg-white p-5 shadow-[0_18px_60px_rgba(15,23,42,0.08)]">
            <h3 className="text-lg font-semibold text-stone-900">Year-by-year pricing view</h3>
            <div className="mt-4 overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-stone-100 text-stone-500">
                    <th className="pb-3 pr-4 font-medium">Year</th>
                    <th className="pb-3 pr-4 font-medium">Base cost</th>
                    <th className="pb-3 pr-4 font-medium">Expansion</th>
                    <th className="pb-3 font-medium">Total</th>
                  </tr>
                </thead>
                <tbody>
                  {result.yearlyTotals.map((row) => (
                    <tr key={row.year} className="border-b border-stone-100 last:border-b-0">
                      <td className="py-3 pr-4 font-semibold text-stone-900">Year {row.year}</td>
                      <td className="py-3 pr-4 text-stone-600">{formatNaira(row.baseCost)}</td>
                      <td className="py-3 pr-4 text-stone-600">{formatNaira(row.expansionCost)}</td>
                      <td className="py-3 font-semibold text-stone-900">{formatNaira(row.totalCost)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
