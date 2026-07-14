import React, { useEffect, useState } from "react";
import { serviceIntegrationsApi } from "../utils/api";

type IntegrationTab =
  | "erpnext"
  | "fraud-engine"
  | "nigeria-vat"
  | "stablecoin"
  | "storefront-advertising";

type ServiceIntegrationsProps = {
  initialTab?: IntegrationTab;
};

const tabs: { key: IntegrationTab; label: string }[] = [
  { key: "erpnext", label: "ERPNext" },
  { key: "fraud-engine", label: "Fraud Engine" },
  { key: "nigeria-vat", label: "Nigeria VAT" },
  { key: "stablecoin", label: "Stablecoin" },
  { key: "storefront-advertising", label: "Storefront Ads" },
];

const tabLabels: Record<IntegrationTab, string> = {
  erpnext: "ERPNext",
  "fraud-engine": "Fraud Engine",
  "nigeria-vat": "Nigeria VAT",
  stablecoin: "Stablecoin",
  "storefront-advertising": "Storefront Ads",
};

const inputClass =
  "border border-gray-300 rounded-lg px-3 py-2 w-full text-sm focus:outline-none focus:ring-2 focus:ring-primary";
const selectClass = inputClass;
const buttonClass =
  "bg-primary text-white px-4 py-2 rounded-lg font-semibold text-sm hover:opacity-90 disabled:opacity-60";

const storefrontAdTypeOptions = [
  "BANNER",
  "FEATURED_PRODUCT",
  "FLASH_SALE",
  "PUSH_NOTIFICATION",
  "SMS_BROADCAST",
  "SOCIAL_CARD",
  "SPONSORED_LISTING",
  "POPUP",
];

const storefrontTargetAudienceOptions = [
  "ALL",
  "NEW_CUSTOMERS",
  "RETURNING_CUSTOMERS",
  "HIGH_VALUE",
  "INACTIVE",
  "BY_LOCATION",
  "BY_AGE_GROUP",
];

type ResultPanelProps = {
  value: unknown;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (value instanceof Date) return value.toISOString();
  return JSON.stringify(value);
}

function extractPrimaryRows(value: unknown): unknown[] | null {
  if (Array.isArray(value)) return value;
  if (!isRecord(value)) return null;

  const preferredKeys = ["cases", "items", "data", "results", "records"];
  for (const key of preferredKeys) {
    const candidate = value[key];
    if (Array.isArray(candidate)) {
      return candidate;
    }
  }

  for (const candidate of Object.values(value)) {
    if (Array.isArray(candidate)) {
      return candidate;
    }
  }

  return null;
}

const DataTable: React.FC<{ rows: unknown[] }> = ({ rows }) => {
  if (rows.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 p-6 text-sm text-gray-500">
        No records returned.
      </div>
    );
  }

  const allKeys = Array.from(
    new Set(
      rows.flatMap((row) =>
        isRecord(row) ? Object.keys(row).slice(0, 8) : ["value"],
      ),
    ),
  );

  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
      <div className="overflow-auto">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
            <tr>
              <th className="px-4 py-3">#</th>
              {allKeys.map((key) => (
                <th key={key} className="px-4 py-3">
                  {key}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {rows.map((row, index) => (
              <tr key={index} className="hover:bg-gray-50">
                <td className="px-4 py-3 text-gray-500">{index + 1}</td>
                {allKeys.map((key) => (
                  <td key={key} className="px-4 py-3 align-top">
                    {isRecord(row) ? formatValue(row[key]) : formatValue(row)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

const ResultPanel: React.FC<ResultPanelProps> = ({ value }) => {
  if (value === null || value === undefined) {
    return (
      <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 p-6 text-sm text-gray-500">
        Run an action to see structured results here.
      </div>
    );
  }

  const primaryRows = extractPrimaryRows(value);

  if (primaryRows) {
    if (isRecord(value) && !Array.isArray(value)) {
      const metaEntries = Object.entries(value).filter(
        ([, item]) => !Array.isArray(item),
      );

      return (
        <div className="space-y-4">
          {metaEntries.length > 0 && (
            <div className="grid gap-3 md:grid-cols-2">
              {metaEntries.slice(0, 6).map(([key, item]) => (
                <div
                  key={key}
                  className="rounded-xl border bg-white p-4 shadow-sm"
                >
                  <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                    {key}
                  </div>
                  <div className="mt-1 break-words text-sm text-gray-800">
                    {formatValue(item)}
                  </div>
                </div>
              ))}
            </div>
          )}

          <DataTable rows={primaryRows} />
        </div>
      );
    }

    return <DataTable rows={primaryRows} />;
  }

  if (isRecord(value)) {
    const entries = Object.entries(value).slice(0, 12);
    return (
      <div className="grid gap-3 md:grid-cols-2">
        {entries.map(([key, item]) => (
          <div key={key} className="rounded-xl border bg-white p-4 shadow-sm">
            <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">
              {key}
            </div>
            <div className="mt-1 break-words text-sm text-gray-800">
              {formatValue(item)}
            </div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="rounded-xl border bg-white p-4 text-sm text-gray-800 shadow-sm">
      {formatValue(value)}
    </div>
  );
};

const serviceCopy: Record<
  IntegrationTab,
  {
    description: string;
    summary: string;
  }
> = {
  erpnext: {
    description: "Review ERP sync status and performance reporting for agents.",
    summary:
      "Operational sync tracking and performance insights in tabular form.",
  },
  "fraud-engine": {
    description: "Inspect fraud case volume and live risk stats.",
    summary: "Risk scoring and case oversight.",
  },
  "nigeria-vat": {
    description: "Check VAT summary data and exempt categories for an entity.",
    summary: "VAT filing support and compliance lookups in structured views.",
  },
  stablecoin: {
    description: "Review stablecoin inventories and managed accounts.",
    summary: "Token and account inventory management with table-first output.",
  },
  "storefront-advertising": {
    description: "Inspect active promotions and merchant campaign activity.",
    summary: "Merchant promo and ad management in business-list style.",
  },
};

const ServiceIntegrations: React.FC<ServiceIntegrationsProps> = ({
  initialTab,
}) => {
  const [activeTab, setActiveTab] = useState<IntegrationTab>(
    initialTab ?? "erpnext",
  );
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [result, setResult] = useState<unknown>(null);
  const [fraudStats, setFraudStats] = useState<unknown>(null);
  const [fraudCases, setFraudCases] = useState<unknown>(null);

  const [erpAgentId, setErpAgentId] = useState("");
  const [erpFromDate, setErpFromDate] = useState("");
  const [erpToDate, setErpToDate] = useState("");

  const [vatEntityId, setVatEntityId] = useState("");
  const [vatPeriod, setVatPeriod] = useState("");
  const [vatSummary, setVatSummary] = useState<unknown>(null);
  const [vatBusinesses, setVatBusinesses] = useState<unknown>(null);
  const [vatTransactions, setVatTransactions] = useState<unknown>(null);
  const [vatExemptCategories, setVatExemptCategories] = useState<unknown>(null);

  const [merchantId, setMerchantId] = useState("");
  const [merchantName, setMerchantName] = useState("");
  const [adType, setAdType] = useState("BANNER");
  const [adTitle, setAdTitle] = useState("");
  const [adDescription, setAdDescription] = useState("");
  const [adImageUrl, setAdImageUrl] = useState("");
  const [adCtaText, setAdCtaText] = useState("");
  const [adCtaUrl, setAdCtaUrl] = useState("");
  const [adTargetAudience, setAdTargetAudience] = useState("ALL");
  const [adBudget, setAdBudget] = useState("");
  const [adStartDate, setAdStartDate] = useState("");
  const [adEndDate, setAdEndDate] = useState("");
  const [adPriority, setAdPriority] = useState("5");
  const [storefrontCreateResult, setStorefrontCreateResult] =
    useState<unknown>(null);
  const [storefrontAds, setStorefrontAds] = useState<unknown>(null);
  const [storefrontCampaigns, setStorefrontCampaigns] = useState<unknown>(null);
  const singleServiceMode = Boolean(initialTab);

  const currentCopy = serviceCopy[activeTab];

  useEffect(() => {
    if (initialTab) {
      setActiveTab(initialTab);
    }
  }, [initialTab]);

  useEffect(() => {
    if (activeTab !== "nigeria-vat") return;

    let cancelled = false;

    const loadVatData = async () => {
      setLoading(true);
      setError("");
      setSuccess("");
      try {
        const [
          healthResponse,
          businessesResponse,
          transactionsResponse,
          exemptResponse,
        ] = await Promise.all([
          serviceIntegrationsApi.nigeriaVat.health(),
          serviceIntegrationsApi.nigeriaVat.listBusinesses(),
          serviceIntegrationsApi.nigeriaVat.listTransactions(),
          serviceIntegrationsApi.nigeriaVat.getExemptCategories(),
        ]);

        if (cancelled) return;

        setVatBusinesses(businessesResponse);
        setVatTransactions(transactionsResponse);
        setVatExemptCategories(exemptResponse);
        setResult(businessesResponse);
        setSuccess("Nigeria VAT data loaded");
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Request failed");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void loadVatData();

    return () => {
      cancelled = true;
    };
  }, [activeTab]);

  useEffect(() => {
    if (activeTab !== "nigeria-vat" || !vatEntityId || !vatPeriod) {
      return;
    }

    let cancelled = false;

    const loadSummary = async () => {
      try {
        const response = await serviceIntegrationsApi.nigeriaVat.getSummary(
          vatEntityId,
          vatPeriod,
        );
        if (!cancelled) {
          setVatSummary(response);
        }
      } catch {
        if (!cancelled) {
          setVatSummary(null);
        }
      }
    };

    void loadSummary();

    return () => {
      cancelled = true;
    };
  }, [activeTab, vatEntityId, vatPeriod]);

  useEffect(() => {
    if (activeTab !== "storefront-advertising") return;

    let cancelled = false;

    const loadStorefrontData = async () => {
      setLoading(true);
      setError("");
      setSuccess("");
      try {
        const activeAdsResponse =
          await serviceIntegrationsApi.storefrontAdvertising.getActiveAds();
        const campaignsResponse = merchantId
          ? await serviceIntegrationsApi.storefrontAdvertising.getActiveCampaigns(
              merchantId,
            )
          : [];

        if (cancelled) return;

        setStorefrontAds(activeAdsResponse);
        setStorefrontCampaigns(campaignsResponse);
        setResult(activeAdsResponse);
        setSuccess("Storefront advertising data loaded");
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Request failed");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void loadStorefrontData();

    return () => {
      cancelled = true;
    };
  }, [activeTab, merchantId]);

  const handleCreateStorefrontAd = async () => {
    setLoading(true);
    setError("");
    setSuccess("");

    const payload: Record<string, unknown> = {
      merchant_id: merchantId.trim(),
      merchant_name: merchantName.trim(),
      ad_type: adType,
      title: adTitle.trim(),
      target_audience: adTargetAudience,
    };

    if (adDescription.trim()) payload.description = adDescription.trim();
    if (adImageUrl.trim()) payload.image_url = adImageUrl.trim();
    if (adCtaText.trim()) payload.cta_text = adCtaText.trim();
    if (adCtaUrl.trim()) payload.cta_url = adCtaUrl.trim();
    if (adBudget.trim()) payload.budget_ngn = Number(adBudget);
    if (adStartDate.trim())
      payload.start_date = new Date(adStartDate).toISOString();
    if (adEndDate.trim()) payload.end_date = new Date(adEndDate).toISOString();
    if (adPriority.trim()) payload.priority = Number(adPriority);

    try {
      const response =
        await serviceIntegrationsApi.storefrontAdvertising.createAd(
          payload as {
            merchant_id: string;
            merchant_name: string;
            ad_type: string;
            title: string;
            description?: string;
            image_url?: string;
            cta_text?: string;
            cta_url?: string;
            target_audience?: string;
            target_states?: string[];
            target_lgas?: string[];
            budget_ngn?: number;
            cost_per_click_ngn?: number;
            start_date?: string;
            end_date?: string;
            priority?: number;
          },
        );

      setStorefrontCreateResult(response);
      setResult(response);
      setSuccess("Storefront ad created and pending approval");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (activeTab !== "fraud-engine") {
      return;
    }

    let cancelled = false;

    const loadFraudEngineData = async () => {
      setLoading(true);
      setError("");
      setSuccess("");
      try {
        const [statsResponse, casesResponse] = await Promise.all([
          serviceIntegrationsApi.fraudEngine.getStats(),
          serviceIntegrationsApi.fraudEngine.getCases(),
        ]);

        if (cancelled) return;

        setFraudStats(statsResponse);
        const casesPayload = casesResponse as unknown;
        setFraudCases(
          Array.isArray(casesPayload)
            ? casesPayload
            : isRecord(casesPayload) &&
                Array.isArray((casesPayload as Record<string, unknown>).cases)
              ? (casesPayload as Record<string, unknown>).cases
              : casesPayload,
        );
        setResult(statsResponse);
        setSuccess("Fraud engine data loaded");
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Request failed");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void loadFraudEngineData();

    return () => {
      cancelled = true;
    };
  }, [activeTab]);

  const run = async (
    action: () => Promise<unknown>,
    successMessage: string,
  ) => {
    setLoading(true);
    setError("");
    setSuccess("");
    try {
      const response = await action();
      setResult(response);
      setSuccess(successMessage);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 p-6">
      <div className="bg-primary rounded-2xl shadow-lg p-6 text-white">
        <h1 className="text-2xl font-bold">
          {singleServiceMode
            ? `${tabLabels[activeTab]} Integrations`
            : "Service Integrations"}
        </h1>
        <p className="opacity-90">
          {singleServiceMode
            ? currentCopy.description
            : "Setup and monitor ERPNext, fraud, VAT, stablecoin, and storefront services."}
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border bg-white p-4 shadow-sm">
          <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            Focus
          </div>
          <div className="mt-1 text-sm font-medium text-gray-900">
            {tabLabels[activeTab]}
          </div>
        </div>
        <div className="rounded-xl border bg-white p-4 shadow-sm md:col-span-2">
          <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            What this page shows
          </div>
          <div className="mt-1 text-sm text-gray-700">
            {currentCopy.summary}
          </div>
        </div>
      </div>

      {error && (
        <div className="bg-red-100 text-red-700 p-3 rounded-lg">{error}</div>
      )}
      {success && (
        <div className="bg-green-100 text-green-700 p-3 rounded-lg">
          {success}
        </div>
      )}

      {!singleServiceMode && (
        <div className="bg-white border rounded-xl p-2">
          <div className="flex flex-wrap gap-2">
            {tabs.map((tab) => (
              <button
                key={tab.key}
                className={`px-4 py-2 rounded-lg text-sm font-semibold ${
                  activeTab === tab.key
                    ? "bg-primary text-white"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                }`}
                onClick={() => setActiveTab(tab.key)}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {activeTab === "erpnext" && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <div className="bg-white border rounded-xl p-4 space-y-3">
            <h2 className="text-lg font-semibold">ERPNext Actions</h2>
            <input
              className={inputClass}
              placeholder="Agent ID"
              value={erpAgentId}
              onChange={(event) => setErpAgentId(event.target.value)}
            />
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <input
                className={inputClass}
                placeholder="From Date (YYYY-MM-DD)"
                value={erpFromDate}
                onChange={(event) => setErpFromDate(event.target.value)}
              />
              <input
                className={inputClass}
                placeholder="To Date (YYYY-MM-DD)"
                value={erpToDate}
                onChange={(event) => setErpToDate(event.target.value)}
              />
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                className={buttonClass}
                disabled={loading || !erpAgentId}
                onClick={() =>
                  run(
                    () =>
                      serviceIntegrationsApi.erpnext.getSyncStatus(erpAgentId),
                    "ERPNext sync status loaded",
                  )
                }
              >
                Load Sync Status
              </button>
              <button
                className={buttonClass}
                disabled={loading || !erpAgentId || !erpFromDate || !erpToDate}
                onClick={() =>
                  run(
                    () =>
                      serviceIntegrationsApi.erpnext.getPerformanceReport(
                        erpAgentId,
                        erpFromDate,
                        erpToDate,
                      ),
                    "ERPNext report loaded",
                  )
                }
              >
                Load Performance Report
              </button>
            </div>
          </div>
          <div className="bg-white border rounded-xl p-4">
            <h2 className="text-lg font-semibold mb-3">Data View</h2>
            <ResultPanel value={result} />
          </div>
        </div>
      )}

      {activeTab === "fraud-engine" && (
        <div className="space-y-6">
          <div className="bg-white border rounded-xl p-4 space-y-3">
            <h2 className="text-lg font-semibold">Fraud Engine Stats</h2>
            <ResultPanel value={fraudStats} />
          </div>
          <div className="bg-white border rounded-xl p-4 space-y-3">
            <h2 className="text-lg font-semibold">Fraud Cases</h2>
            <ResultPanel value={fraudCases} />
          </div>
        </div>
      )}

      {activeTab === "nigeria-vat" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="bg-white border rounded-xl p-4 shadow-sm">
              <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                Health
              </div>
              <div className="mt-1 text-sm text-gray-800">Auto-loaded</div>
            </div>
            <div className="bg-white border rounded-xl p-4 shadow-sm">
              <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                Businesses
              </div>
              <div className="mt-1 text-sm text-gray-800">Auto-loaded list</div>
            </div>
            <div className="bg-white border rounded-xl p-4 shadow-sm">
              <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                Transactions
              </div>
              <div className="mt-1 text-sm text-gray-800">Auto-loaded list</div>
            </div>
          </div>

          <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
            <div className="bg-white border rounded-xl p-4 space-y-3">
              <h2 className="text-lg font-semibold">VAT Summary</h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <input
                  className={inputClass}
                  placeholder="Entity ID"
                  value={vatEntityId}
                  onChange={(event) => setVatEntityId(event.target.value)}
                />
                <input
                  className={inputClass}
                  placeholder="Period (YYYY-MM)"
                  value={vatPeriod}
                  onChange={(event) => setVatPeriod(event.target.value)}
                />
              </div>
              <ResultPanel value={vatSummary} />
            </div>

            <div className="bg-white border rounded-xl p-4 space-y-3">
              <h2 className="text-lg font-semibold">Exempt Categories</h2>
              <ResultPanel value={vatExemptCategories} />
            </div>
          </div>

          <div className="bg-white border rounded-xl p-4 space-y-3">
            <h2 className="text-lg font-semibold">
              Businesses with VAT Activity
            </h2>
            <ResultPanel value={vatBusinesses} />
          </div>

          <div className="bg-white border rounded-xl p-4 space-y-3">
            <h2 className="text-lg font-semibold">All VAT Transactions</h2>
            <ResultPanel value={vatTransactions} />
          </div>
        </div>
      )}

      {activeTab === "stablecoin" && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <div className="bg-white border rounded-xl p-4 space-y-3">
            <h2 className="text-lg font-semibold">Stablecoin Actions</h2>
            <div className="flex flex-wrap gap-2">
              <button
                className={buttonClass}
                disabled={loading}
                onClick={() =>
                  run(
                    serviceIntegrationsApi.stablecoin.listStablecoins,
                    "Stablecoins loaded",
                  )
                }
              >
                Load Stablecoins
              </button>
              <button
                className={buttonClass}
                disabled={loading}
                onClick={() =>
                  run(
                    serviceIntegrationsApi.stablecoin.listAccounts,
                    "Stablecoin accounts loaded",
                  )
                }
              >
                Load Accounts
              </button>
            </div>
          </div>
          <div className="bg-white border rounded-xl p-4">
            <h2 className="text-lg font-semibold mb-3">Data View</h2>
            <ResultPanel value={result} />
          </div>
        </div>
      )}

      {activeTab === "storefront-advertising" && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-white border rounded-xl p-4 shadow-sm">
              <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                Active Ads
              </div>
              <div className="mt-1 text-sm text-gray-800">Auto-loaded</div>
            </div>
            <div className="bg-white border rounded-xl p-4 shadow-sm">
              <div className="text-xs font-semibold uppercase tracking-wide text-gray-500">
                Active Campaigns
              </div>
              <div className="mt-1 text-sm text-gray-800">
                Merchant filtered, auto-refreshes when Merchant ID changes
              </div>
            </div>
          </div>

          <div className="bg-white border rounded-xl p-4 space-y-3">
            <h2 className="text-lg font-semibold">Merchant ID</h2>
            <input
              className={inputClass}
              placeholder="Merchant ID"
              value={merchantId}
              onChange={(event) => setMerchantId(event.target.value)}
            />
          </div>

          <div className="bg-white border rounded-xl p-4 space-y-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <h2 className="text-lg font-semibold">Create Ad</h2>
                <p className="text-sm text-gray-500">
                  Submit a new storefront ad. It will start as pending approval.
                </p>
              </div>
              <button
                className={buttonClass}
                onClick={handleCreateStorefrontAd}
                disabled={loading}
              >
                Create Ad
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <input
                className={inputClass}
                placeholder="Merchant Name"
                value={merchantName}
                onChange={(event) => setMerchantName(event.target.value)}
              />
              <select
                className={selectClass}
                value={adType}
                onChange={(event) => setAdType(event.target.value)}
              >
                {storefrontAdTypeOptions.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
              <input
                className={inputClass}
                placeholder="Title"
                value={adTitle}
                onChange={(event) => setAdTitle(event.target.value)}
              />
              <select
                className={selectClass}
                value={adTargetAudience}
                onChange={(event) => setAdTargetAudience(event.target.value)}
              >
                {storefrontTargetAudienceOptions.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
              <input
                className={inputClass}
                placeholder="CTA text"
                value={adCtaText}
                onChange={(event) => setAdCtaText(event.target.value)}
              />
              <input
                className={inputClass}
                placeholder="CTA URL"
                value={adCtaUrl}
                onChange={(event) => setAdCtaUrl(event.target.value)}
              />
              <input
                className={inputClass}
                placeholder="Image URL"
                value={adImageUrl}
                onChange={(event) => setAdImageUrl(event.target.value)}
              />
              <input
                className={inputClass}
                placeholder="Budget NGN"
                inputMode="decimal"
                value={adBudget}
                onChange={(event) => setAdBudget(event.target.value)}
              />
              <input
                className={inputClass}
                placeholder="Start date"
                type="datetime-local"
                value={adStartDate}
                onChange={(event) => setAdStartDate(event.target.value)}
              />
              <input
                className={inputClass}
                placeholder="End date"
                type="datetime-local"
                value={adEndDate}
                onChange={(event) => setAdEndDate(event.target.value)}
              />
              <input
                className={inputClass}
                placeholder="Priority"
                type="number"
                min="1"
                max="10"
                value={adPriority}
                onChange={(event) => setAdPriority(event.target.value)}
              />
            </div>

            <textarea
              className={inputClass}
              placeholder="Description"
              rows={4}
              value={adDescription}
              onChange={(event) => setAdDescription(event.target.value)}
            />
          </div>

          <div className="bg-white border rounded-xl p-4 space-y-3">
            <h2 className="text-lg font-semibold">Latest Created Ad</h2>
            <ResultPanel value={storefrontCreateResult} />
          </div>

          <div className="bg-white border rounded-xl p-4 space-y-3">
            <h2 className="text-lg font-semibold">Active Ads</h2>
            <ResultPanel value={storefrontAds} />
          </div>

          <div className="bg-white border rounded-xl p-4 space-y-3">
            <h2 className="text-lg font-semibold">Active Campaigns</h2>
            <ResultPanel value={storefrontCampaigns} />
          </div>
        </div>
      )}
    </div>
  );
};

export default ServiceIntegrations;
