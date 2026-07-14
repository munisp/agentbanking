import { RefreshCw, Store } from "lucide-react";
import React, { useEffect, useState } from "react";
import { serviceIntegrationsApi } from "../../utils/api";

type StorefrontAdRecord = {
  id: string;
  title: string;
  merchant_id: string;
  merchant_name: string;
  ad_type: string;
  target_audience: string;
  status: string;
  budget_ngn?: number | null;
  spend_ngn?: number | null;
  impressions?: number;
  clicks?: number;
  conversions?: number;
  start_date?: string | null;
  end_date?: string | null;
  updated_at?: string | null;
  cta_text?: string | null;
  cta_url?: string | null;
  image_url?: string | null;
  priority?: number;
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

const ResultPanel: React.FC<{ value: unknown }> = ({ value }) => {
  if (value === null || value === undefined) {
    return (
      <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 p-6 text-sm text-gray-500">
        No data available.
      </div>
    );
  }

  if (Array.isArray(value)) {
    return <DataTable rows={value} />;
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

const normalizeAds = (value: unknown): StorefrontAdRecord[] => {
  if (Array.isArray(value)) {
    return value as StorefrontAdRecord[];
  }

  if (
    isRecord(value) &&
    "ads" in value &&
    Array.isArray((value as { ads?: unknown[] }).ads)
  ) {
    return (value as { ads: StorefrontAdRecord[] }).ads;
  }

  return [];
};

const ActiveAdsTable: React.FC<{ value: unknown }> = ({ value }) => {
  const rows = normalizeAds(value);

  if (rows.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-gray-300 bg-gray-50 p-6 text-sm text-gray-500">
        No active ads returned.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-gray-200 bg-white">
      <div className="overflow-auto">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
            <tr>
              <th className="px-4 py-3">Ad</th>
              <th className="px-4 py-3">Merchant</th>
              <th className="px-4 py-3">Type</th>
              <th className="px-4 py-3">Audience</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3">Budget / Spend</th>
              <th className="px-4 py-3">Performance</th>
              <th className="px-4 py-3">Schedule</th>
              <th className="px-4 py-3">Updated</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 bg-white">
            {rows.map((ad) => (
              <tr key={ad.id} className="hover:bg-gray-50 align-top">
                <td className="px-4 py-3">
                  <div className="flex items-start gap-3">
                    {ad.image_url ? (
                      <img
                        src={ad.image_url}
                        alt={ad.title}
                        className="h-12 w-12 rounded object-cover border border-gray-200"
                      />
                    ) : (
                      <div className="h-12 w-12 rounded border border-gray-200 bg-gray-100" />
                    )}
                    <div>
                      <p className="font-medium text-gray-900">
                        {ad.title || "—"}
                      </p>
                      <p className="text-xs text-gray-500">ID: {ad.id}</p>
                      <p className="text-xs text-gray-500">
                        CTA: {ad.cta_text || "—"}
                      </p>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-3">
                  <p className="font-medium text-gray-900">
                    {ad.merchant_name || "—"}
                  </p>
                  <p className="text-xs text-gray-500">
                    Merchant ID: {ad.merchant_id || "—"}
                  </p>
                </td>
                <td className="px-4 py-3">{ad.ad_type || "—"}</td>
                <td className="px-4 py-3">{ad.target_audience || "—"}</td>
                <td className="px-4 py-3">
                  <span className="inline-flex rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-800">
                    {ad.status || "—"}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <p>Budget: ₦{Number(ad.budget_ngn ?? 0).toLocaleString()}</p>
                  <p className="text-xs text-gray-500">
                    Spend: ₦{Number(ad.spend_ngn ?? 0).toLocaleString()}
                  </p>
                </td>
                <td className="px-4 py-3">
                  <p>Impr: {ad.impressions ?? 0}</p>
                  <p className="text-xs text-gray-500">
                    Clicks: {ad.clicks ?? 0} · Conv: {ad.conversions ?? 0}
                  </p>
                </td>
                <td className="px-4 py-3">
                  <p className="text-xs">
                    Start:{" "}
                    {ad.start_date
                      ? new Date(ad.start_date).toLocaleString()
                      : "—"}
                  </p>
                  <p className="text-xs text-gray-500">
                    End:{" "}
                    {ad.end_date ? new Date(ad.end_date).toLocaleString() : "—"}
                  </p>
                </td>
                <td className="px-4 py-3 text-xs text-gray-600">
                  {ad.updated_at
                    ? new Date(ad.updated_at).toLocaleString()
                    : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

const inputClass =
  "border border-gray-300 rounded-lg px-3 py-2 w-full text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-primary-color,#002082)]";
const selectClass = inputClass;
const buttonClass =
  "bg-[var(--tenant-primary-color,#002082)] text-white px-4 py-2 rounded-lg font-semibold text-sm hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] disabled:opacity-60 disabled:cursor-not-allowed";

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

const StorefrontAdvertisingPage: React.FC = () => {
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

  const [storefrontAds, setStorefrontAds] = useState<unknown>(null);
  const [storefrontCampaigns, setStorefrontCampaigns] = useState<unknown>(null);
  const [storefrontCreateResult, setStorefrontCreateResult] =
    useState<unknown>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const activeAdsCount = normalizeAds(storefrontAds).length;

  // Load initial data
  useEffect(() => {
    const loadStorefrontData = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const activeAdsResponse =
          await serviceIntegrationsApi.storefrontAdvertising.getActiveAds();
        setStorefrontAds(activeAdsResponse);
        setSuccess("Storefront data loaded successfully");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load data");
      } finally {
        setIsLoading(false);
      }
    };

    loadStorefrontData();
  }, []);

  // Load campaigns when merchant ID changes
  useEffect(() => {
    if (!merchantId.trim()) {
      setStorefrontCampaigns(null);
      return;
    }

    const loadCampaigns = async () => {
      try {
        const campaignsResponse =
          await serviceIntegrationsApi.storefrontAdvertising.getActiveCampaigns(
            merchantId,
          );
        setStorefrontCampaigns(campaignsResponse);
      } catch (err) {
        console.error("Failed to load campaigns:", err);
      }
    };

    loadCampaigns();
  }, [merchantId]);

  const handleCreateAd = async () => {
    setIsSubmitting(true);
    setError(null);
    setSuccess(null);

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
      setSuccess("Ad created successfully and is pending approval");

      // Reset form
      setAdTitle("");
      setAdDescription("");
      setAdImageUrl("");
      setAdCtaText("");
      setAdCtaUrl("");
      setAdBudget("");
      setAdStartDate("");
      setAdEndDate("");
      setAdPriority("5");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create ad");
    } finally {
      setIsSubmitting(false);
    }
  };

  const isFormValid =
    merchantId.trim().length > 0 &&
    merchantName.trim().length > 0 &&
    adTitle.trim().length > 0;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Store className="h-6 w-6 text-blue-600" />
            Storefront Advertising
          </h1>
          <p className="text-gray-600 mt-1">
            Manage merchant promotions and advertising campaigns
          </p>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}

      {success && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg">
          {success}
        </div>
      )}

      {/* Overview Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white rounded-lg shadow p-4 border-l-4 border-blue-600">
          <p className="text-sm text-gray-600">Active Ads</p>
          <p className="text-2xl font-bold mt-1 text-gray-900">
            {activeAdsCount}
          </p>
          <p className="text-xs text-gray-500 mt-1">
            Refreshes on merchant change
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-4 border-l-4 border-purple-600">
          <p className="text-sm text-gray-600">Active Campaigns</p>
          <p className="text-2xl font-bold mt-1 text-gray-900">
            {merchantId ? "Loaded" : "—"}
          </p>
          <p className="text-xs text-gray-500 mt-1">Enter merchant ID above</p>
        </div>
      </div>

      {isLoading ? (
        <div className="text-center py-8 text-gray-500">Loading...</div>
      ) : (
        <div className="space-y-6">
          {/* Merchant Filter */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Filter by Merchant
            </h2>
            <input
              className={inputClass}
              placeholder="Enter merchant ID to view their campaigns"
              value={merchantId}
              onChange={(e) => setMerchantId(e.target.value)}
            />
          </div>

          {/* Create Ad Form */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">
                Create New Ad
              </h2>
              <button
                className={buttonClass}
                onClick={handleCreateAd}
                disabled={isSubmitting || !isFormValid}
              >
                {isSubmitting ? "Creating..." : "Create Ad"}
              </button>
            </div>

            <div className="space-y-4">
              {/* Required Fields */}
              <div className="space-y-2">
                <h3 className="text-sm font-semibold text-gray-700">
                  Required Information
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <input
                    className={inputClass}
                    placeholder="Merchant ID *"
                    value={merchantId}
                    onChange={(e) => setMerchantId(e.target.value)}
                  />
                  <input
                    className={inputClass}
                    placeholder="Merchant Name *"
                    value={merchantName}
                    onChange={(e) => setMerchantName(e.target.value)}
                  />
                  <select
                    className={selectClass}
                    value={adType}
                    onChange={(e) => setAdType(e.target.value)}
                  >
                    {storefrontAdTypeOptions.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </div>
                <input
                  className={inputClass}
                  placeholder="Ad Title *"
                  value={adTitle}
                  onChange={(e) => setAdTitle(e.target.value)}
                />
              </div>

              {/* Ad Details */}
              <div className="space-y-2">
                <h3 className="text-sm font-semibold text-gray-700">
                  Ad Details
                </h3>
                <textarea
                  className={inputClass}
                  placeholder="Description"
                  rows={3}
                  value={adDescription}
                  onChange={(e) => setAdDescription(e.target.value)}
                />
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <input
                    className={inputClass}
                    placeholder="Image URL"
                    value={adImageUrl}
                    onChange={(e) => setAdImageUrl(e.target.value)}
                  />
                  <select
                    className={selectClass}
                    value={adTargetAudience}
                    onChange={(e) => setAdTargetAudience(e.target.value)}
                  >
                    {storefrontTargetAudienceOptions.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Call-to-Action */}
              <div className="space-y-2">
                <h3 className="text-sm font-semibold text-gray-700">
                  Call-to-Action
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <input
                    className={inputClass}
                    placeholder="CTA Text"
                    value={adCtaText}
                    onChange={(e) => setAdCtaText(e.target.value)}
                  />
                  <input
                    className={inputClass}
                    placeholder="CTA URL"
                    value={adCtaUrl}
                    onChange={(e) => setAdCtaUrl(e.target.value)}
                  />
                </div>
              </div>

              {/* Campaign Details */}
              <div className="space-y-2">
                <h3 className="text-sm font-semibold text-gray-700">
                  Campaign Details
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <input
                    className={inputClass}
                    placeholder="Budget (NGN)"
                    inputMode="decimal"
                    value={adBudget}
                    onChange={(e) => setAdBudget(e.target.value)}
                  />
                  <input
                    className={inputClass}
                    placeholder="Priority (1-10)"
                    type="number"
                    min="1"
                    max="10"
                    value={adPriority}
                    onChange={(e) => setAdPriority(e.target.value)}
                  />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                      Start Date
                    </label>
                    <input
                      className={inputClass}
                      type="datetime-local"
                      value={adStartDate}
                      onChange={(e) => setAdStartDate(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                      End Date
                    </label>
                    <input
                      className={inputClass}
                      type="datetime-local"
                      value={adEndDate}
                      onChange={(e) => setAdEndDate(e.target.value)}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Results */}
          {storefrontCreateResult && (
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Latest Created Ad
              </h2>
              <ResultPanel value={storefrontCreateResult} />
            </div>
          )}

          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              Active Ads
            </h2>
            <ActiveAdsTable value={storefrontAds} />
          </div>

          {merchantId && (
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">
                Campaigns for {merchantId}
              </h2>
              <ResultPanel value={storefrontCampaigns} />
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default StorefrontAdvertisingPage;
