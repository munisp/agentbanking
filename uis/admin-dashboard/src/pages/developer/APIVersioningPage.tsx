import { GitBranch, RefreshCw, AlertTriangle, ExternalLink, CheckCircle, Clock, XCircle } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_PLATFORM_MGMT_URL || import.meta.env.VITE_API_URL || "http://localhost:8010";

interface APIVersion {
  id: string;
  version: string;
  status: "active" | "deprecated" | "sunset";
  releaseDate: string;
  deprecationDate: string | null;
  sunsetDate: string | null;
  endpointCount: number;
  migrationGuide: string;
  breakingChanges: string[];
}

const MOCK_VERSIONS: APIVersion[] = [
  {
    id: "v3", version: "v3", status: "active",
    releaseDate: "2024-07-01", deprecationDate: null, sunsetDate: null,
    endpointCount: 84, migrationGuide: "https://docs.54agent.ng/api/v3/migration",
    breakingChanges: [
      "Unified /payment-hub endpoints replace split /bills and /transfers",
      "Pagination now uses cursor-based instead of offset",
      "Webhook payloads include new 'meta.version' field",
    ],
  },
  {
    id: "v2", version: "v2", status: "deprecated",
    releaseDate: "2023-01-15", deprecationDate: "2024-07-01", sunsetDate: "2025-01-15",
    endpointCount: 62, migrationGuide: "https://docs.54agent.ng/api/v2/migration",
    breakingChanges: [
      "Agent onboarding endpoint path changed from /onboard to /agents",
      "Transaction response now returns 'amount_ngn' instead of 'amount'",
    ],
  },
  {
    id: "v1", version: "v1", status: "sunset",
    releaseDate: "2022-03-01", deprecationDate: "2023-01-15", sunsetDate: "2024-01-15",
    endpointCount: 38, migrationGuide: "https://docs.54agent.ng/api/v1/migration",
    breakingChanges: [],
  },
];

const STATUS_CONFIG: Record<APIVersion["status"], { label: string; bg: string; text: string; icon: React.FC<{className?: string}> }> = {
  active: { label: "Active", bg: "bg-green-100", text: "text-green-700", icon: CheckCircle },
  deprecated: { label: "Deprecated", bg: "bg-amber-100", text: "text-amber-700", icon: AlertTriangle },
  sunset: { label: "Sunset", bg: "bg-red-100", text: "text-red-700", icon: XCircle },
};

const COMPARE_KEYS: Array<{ label: string; key: keyof APIVersion }> = [
  { label: "Status", key: "status" },
  { label: "Release Date", key: "releaseDate" },
  { label: "Deprecation Date", key: "deprecationDate" },
  { label: "Sunset Date", key: "sunsetDate" },
  { label: "Endpoints", key: "endpointCount" },
];

const APIVersioningPage: React.FC = () => {
  const [versions, setVersions] = useState<APIVersion[]>([]);
  const [loading, setLoading] = useState(false);
  const [compareA, setCompareA] = useState("v3");
  const [compareB, setCompareB] = useState("v2");

  useEffect(() => { fetchVersions(); }, []);

  const fetchVersions = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/developer/api/v1/versions`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) { const d = await res.json(); setVersions(Array.isArray(d.versions) ? d.versions : MOCK_VERSIONS); }
      else { setVersions(MOCK_VERSIONS); }
    } catch { setVersions(MOCK_VERSIONS); }
    finally { setLoading(false); }
  };

  const deprecated = versions.filter(v => v.status === "deprecated");
  const vA = versions.find(v => v.version === compareA);
  const vB = versions.find(v => v.version === compareB);

  const daysUntilSunset = (sunsetDate: string | null) => {
    if (!sunsetDate) return null;
    const diff = new Date(sunsetDate).getTime() - Date.now();
    return Math.ceil(diff / (1000 * 60 * 60 * 24));
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <GitBranch className="w-7 h-7 text-blue-600" /> API Version Management
          </h1>
          <p className="text-gray-500 text-sm mt-1">Track API lifecycle, deprecation timelines and migration guides</p>
        </div>
        <button onClick={fetchVersions} disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium disabled:opacity-50">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
        </button>
      </div>

      {deprecated.map(v => {
        const days = daysUntilSunset(v.sunsetDate);
        if (!days || days < 0) return null;
        return (
          <div key={v.id} className="flex items-center gap-3 bg-amber-50 border border-amber-200 rounded-xl px-5 py-3">
            <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0" />
            <p className="text-sm text-amber-800">
              <span className="font-semibold">API {v.version}</span> is deprecated and will be sunset in <span className="font-semibold">{days} days</span> ({v.sunsetDate}).
              Please migrate to v3 using the <a href={v.migrationGuide} target="_blank" rel="noreferrer" className="underline hover:text-amber-900">migration guide</a>.
            </p>
          </div>
        );
      })}

      <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm overflow-x-auto">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">All API Versions</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-gray-500 border-b border-gray-100">
              <th className="text-left pb-2 pr-4">Version</th>
              <th className="text-left pb-2 pr-4">Status</th>
              <th className="text-left pb-2 pr-4">Release Date</th>
              <th className="text-left pb-2 pr-4">Deprecation Date</th>
              <th className="text-left pb-2 pr-4">Sunset Date</th>
              <th className="text-right pb-2 pr-4">Endpoints</th>
              <th className="text-left pb-2">Migration Guide</th>
            </tr>
          </thead>
          <tbody>
            {versions.map(v => {
              const cfg = STATUS_CONFIG[v.status];
              const Icon = cfg.icon;
              return (
                <tr key={v.id} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-3 pr-4 font-bold text-gray-900">{v.version}</td>
                  <td className="py-3 pr-4">
                    <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${cfg.bg} ${cfg.text}`}>
                      <Icon className="w-3 h-3" /> {cfg.label}
                    </span>
                  </td>
                  <td className="py-3 pr-4 text-gray-600">{v.releaseDate}</td>
                  <td className="py-3 pr-4 text-gray-600">{v.deprecationDate ?? <span className="text-gray-300">—</span>}</td>
                  <td className="py-3 pr-4 text-gray-600">{v.sunsetDate ?? <span className="text-gray-300">—</span>}</td>
                  <td className="py-3 pr-4 text-right font-medium text-gray-900">{v.endpointCount}</td>
                  <td className="py-3">
                    <a href={v.migrationGuide} target="_blank" rel="noreferrer"
                      className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-blue-800 font-medium">
                      View Guide <ExternalLink className="w-3 h-3" />
                    </a>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
        <h2 className="text-sm font-semibold text-gray-700 mb-4 flex items-center gap-2">
          <Clock className="w-4 h-4 text-blue-500" /> Version Comparison
        </h2>
        <div className="flex items-center gap-3 mb-5">
          <select value={compareA} onChange={e => setCompareA(e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
            {versions.map(v => <option key={v.version} value={v.version}>{v.version}</option>)}
          </select>
          <span className="text-gray-400 font-medium">vs</span>
          <select value={compareB} onChange={e => setCompareB(e.target.value)}
            className="border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
            {versions.map(v => <option key={v.version} value={v.version}>{v.version}</option>)}
          </select>
        </div>
        {vA && vB && (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-xs text-gray-500 border-b border-gray-100">
                  <th className="text-left pb-2 pr-6 w-1/3">Property</th>
                  <th className="text-left pb-2 pr-6">{vA.version}</th>
                  <th className="text-left pb-2">{vB.version}</th>
                </tr>
              </thead>
              <tbody>
                {COMPARE_KEYS.map(({ label, key }) => (
                  <tr key={key} className="border-b border-gray-50">
                    <td className="py-2 pr-6 text-gray-500 text-xs font-medium">{label}</td>
                    <td className="py-2 pr-6 text-gray-800">{String(vA[key] ?? "—")}</td>
                    <td className="py-2 text-gray-800">{String(vB[key] ?? "—")}</td>
                  </tr>
                ))}
                <tr className="border-b border-gray-50 align-top">
                  <td className="py-2 pr-6 text-gray-500 text-xs font-medium">Breaking Changes</td>
                  <td className="py-2 pr-6">
                    {vA.breakingChanges.length > 0
                      ? <ul className="list-disc list-inside space-y-1">{vA.breakingChanges.map((c, i) => <li key={i} className="text-xs text-gray-700">{c}</li>)}</ul>
                      : <span className="text-gray-400 text-xs">None</span>}
                  </td>
                  <td className="py-2">
                    {vB.breakingChanges.length > 0
                      ? <ul className="list-disc list-inside space-y-1">{vB.breakingChanges.map((c, i) => <li key={i} className="text-xs text-gray-700">{c}</li>)}</ul>
                      : <span className="text-gray-400 text-xs">None</span>}
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default APIVersioningPage;
