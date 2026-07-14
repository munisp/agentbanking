import { AlertTriangle, RefreshCw, Zap } from "lucide-react";
import React, { useEffect, useMemo, useState } from "react";
import { serviceIntegrationsApi } from "../../utils/api";

interface FraudStats {
  total_cases?: number;
  active_cases?: number;
  resolved_cases?: number;
  risk_score?: number;
  [key: string]: unknown;
}

interface FraudCase {
  id?: string;
  status?: string;
  risk_level?: string;
  created_at?: string;
  [key: string]: unknown;
}

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

const FraudEnginePage: React.FC = () => {
  const [fraudStats, setFraudStats] = useState<unknown>(null);
  const [fraudCases, setFraudCases] = useState<unknown>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const loadFraudEngineData = async (silent = false) => {
    if (!silent) {
      setIsLoading(true);
      setError(null);
      setSuccess(null);
    }

    try {
      const [statsResponse, casesResponse] = await Promise.all([
        serviceIntegrationsApi.fraudEngine.getStats(),
        serviceIntegrationsApi.fraudEngine.getCases(),
      ]);

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

      if (!silent) {
        setSuccess("Fraud engine data loaded successfully");
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Request failed";
      setError(message);
      if (silent) {
        console.error("Silent refresh failed:", message);
      }
    } finally {
      if (!silent) {
        setIsLoading(false);
      }
    }
  };

  useEffect(() => {
    loadFraudEngineData(false);
    // Auto-refresh every 30 seconds
    const interval = setInterval(() => loadFraudEngineData(true), 30000);
    return () => clearInterval(interval);
  }, []);

  // Extract stats for display
  const stats = useMemo(() => {
    if (!fraudStats || !isRecord(fraudStats)) {
      return {
        totalCases: 0,
        activeCases: 0,
        resolvedCases: 0,
      };
    }

    return {
      totalCases: (fraudStats.total_cases as number) || 0,
      activeCases: (fraudStats.active_cases as number) || 0,
      resolvedCases: (fraudStats.resolved_cases as number) || 0,
    };
  }, [fraudStats]);

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <AlertTriangle className="h-6 w-6 text-orange-600" />
            Fraud Engine
          </h1>
          <p className="text-gray-600 mt-1">
            Monitor fraud detection and case management
          </p>
        </div>
        <button
          onClick={() => loadFraudEngineData(false)}
          disabled={isLoading}
          className="inline-flex items-center px-4 py-2 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] disabled:opacity-60"
        >
          <RefreshCw className="h-5 w-5 mr-2" />
          Refresh
        </button>
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

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg shadow p-4 border-l-4 border-orange-600">
          <p className="text-sm text-gray-600">Total Cases</p>
          <p className="text-2xl font-bold mt-1 text-gray-900">
            {stats.totalCases}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-4 border-l-4 border-red-600">
          <p className="text-sm text-gray-600">Active Cases</p>
          <p className="text-2xl font-bold mt-1 text-red-600">
            {stats.activeCases}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-4 border-l-4 border-green-600">
          <p className="text-sm text-gray-600">Resolved Cases</p>
          <p className="text-2xl font-bold mt-1 text-green-600">
            {stats.resolvedCases}
          </p>
        </div>
      </div>

      {isLoading && fraudStats === null ? (
        <div className="text-center py-8 text-gray-500">Loading...</div>
      ) : (
        <div className="space-y-6">
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2 mb-4">
              <Zap className="h-5 w-5 text-blue-600" />
              Fraud Statistics
            </h2>
            <ResultPanel value={fraudStats} />
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2 mb-4">
              <AlertTriangle className="h-5 w-5 text-orange-600" />
              Active Fraud Cases
            </h2>
            <ResultPanel value={fraudCases} />
          </div>
        </div>
      )}
    </div>
  );
};

export default FraudEnginePage;
