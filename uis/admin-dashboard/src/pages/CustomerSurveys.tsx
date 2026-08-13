import { trpc } from "@/lib/trpc";
import { useState } from "react";
import { MessageSquare } from "lucide-react";

// Customer Surveys — Post-transaction NPS and CSAT collection
// Sprint 42: Final Production Features

export default function CustomerSurveys() {
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const {
    data: liveData,
    isLoading,
    isError,
  } = trpc.customerSurveys.listSurveys.useQuery({ limit: 50 }, { retry: 1 });
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const { data: stats } = trpc.customerSurveys.getSurveyStats.useQuery(
    {},
    { retry: 1 }
  );
  const [search, setSearch] = useState("");
  const [activeTab, setActiveTab] = useState<
    "overview" | "details" | "history" | "settings"
  >("overview");

  const records: any[] = liveData?.items ?? [];

  // NPS / CSAT aggregates are not provided by the surveys API — render "—"
  // rather than hardcoded figures.
  const kpis = [
    {
      label: "Total Records",
      value: stats ? String(stats.totalRecords) : "—",
    },
    { label: "NPS Score", value: "—" },
    { label: "CSAT Score", value: "—" },
    { label: "Response Rate", value: "—" },
  ];

  const columns = ["ID", "Customer", "Event Type", "Source", "Date"];

  const getField = (row: any, ...keys: string[]) => {
    for (const key of keys) {
      const value = row?.[key];
      if (value !== undefined && value !== null && value !== "") {
        return String(value);
      }
    }
    return "—";
  };

  const getDate = (row: any) => {
    const raw = row?.created_at ?? row?.createdAt;
    if (!raw) return "—";
    const d = new Date(raw);
    return isNaN(d.getTime()) ? "—" : d.toLocaleString();
  };

  const filtered = records.filter((r: any) => {
    const q = search.toLowerCase();
    return (
      getField(r, "customer_id", "customerId").toLowerCase().includes(q) ||
      getField(r, "event_type", "eventType").toLowerCase().includes(q)
    );
  });

  return (
    <div className="min-h-screen bg-[#0a0e17] text-white p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <MessageSquare className="w-6 h-6 text-blue-400" />
              Customer Surveys
            </h1>
            <p className="text-gray-400 text-sm mt-1">
              Post-transaction NPS and CSAT collection
            </p>
          </div>
          <button className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg text-sm font-medium transition-colors">
            New Entry
          </button>
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {kpis.map((kpi, i) => (
            <div
              key={i}
              className="bg-[#141a2a] border border-gray-800 rounded-lg p-4"
            >
              <p className="text-gray-400 text-xs uppercase tracking-wider">
                {kpi.label}
              </p>
              <p className="text-2xl font-bold mt-1 text-white">{kpi.value}</p>
            </div>
          ))}
        </div>

        {/* Tabs */}
        <div className="flex gap-2 mb-4">
          {(["overview", "details", "history", "settings"] as const).map(
            (tab: any) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  activeTab === tab
                    ? "bg-blue-600 text-white"
                    : "bg-[#141a2a] text-gray-400 hover:text-white"
                }`}
              >
                {tab.charAt(0).toUpperCase() + tab.slice(1)}
              </button>
            )
          )}
        </div>

        {/* Search */}
        <div className="mb-4">
          <input
            type="text"
            placeholder="Search records..."
            value={search}
            onChange={(e: any) => setSearch(e.target.value)}
            className="w-full max-w-md px-4 py-2 bg-[#141a2a] border border-gray-700 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-blue-500"
          />
        </div>

        {/* Records Table */}
        <div className="bg-[#141a2a] border border-gray-800 rounded-lg overflow-hidden">
          <div className="p-4 border-b border-gray-800">
            <h3 className="font-semibold">Records ({filtered.length})</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-800">
                  {columns.map((col: string, i: number) => (
                    <th
                      key={i}
                      className="text-left p-3 text-gray-400 font-medium"
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {isLoading ? (
                  <tr>
                    <td
                      colSpan={columns.length}
                      className="p-6 text-center text-gray-400"
                    >
                      Loading survey records…
                    </td>
                  </tr>
                ) : isError ? (
                  <tr>
                    <td
                      colSpan={columns.length}
                      className="p-6 text-center text-red-400"
                    >
                      Survey data could not be loaded. Please try again later.
                    </td>
                  </tr>
                ) : filtered.length === 0 ? (
                  <tr>
                    <td
                      colSpan={columns.length}
                      className="p-6 text-center text-gray-400"
                    >
                      No survey records found.
                    </td>
                  </tr>
                ) : (
                  filtered.map((row: any) => (
                    <tr
                      key={row.id}
                      className="border-b border-gray-800/50 hover:bg-[#1a2035] transition-colors"
                    >
                      <td className="p-3 font-mono text-blue-400">{row.id}</td>
                      <td className="p-3">
                        {getField(row, "customer_id", "customerId")}
                      </td>
                      <td className="p-3">
                        {getField(row, "event_type", "eventType")}
                      </td>
                      <td className="p-3">
                        {getField(row, "event_source", "eventSource")}
                      </td>
                      <td className="p-3 text-gray-400">{getDate(row)}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
