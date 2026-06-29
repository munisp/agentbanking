import { useEffect, useState } from "react";
import { billingApi } from "@/utils/api";
import {
  Activity,
  AlertTriangle,
  BarChart3,
  RefreshCw,
  TrendingUp,
  Wallet,
} from "lucide-react";

function fmtNGN(n: number): string {
  return new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN", maximumFractionDigits: 0 }).format(n || 0);
}
function fmtNum(n: number): string {
  return new Intl.NumberFormat("en-NG").format(n || 0);
}

export default function BillingDashboardPage() {
  const [metrics, setMetrics] = useState<any>(null);
  const [config, setConfig] = useState<any>(null);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<"overview" | "alerts" | "config">("overview");

  const load = async () => {
    try {
      const [m, c, al] = await Promise.allSettled([
        billingApi.getLiveSplitMetrics(),
        billingApi.getClientBillingConfig(),
        billingApi.getAlerts(),
      ]);
      if (m.status === "fulfilled") setMetrics(m.value);
      if (c.status === "fulfilled") setConfig(c.value);
      if (al.status === "fulfilled") setAlerts(al.value?.alerts ?? []);
    } catch {
      // partial failures are handled by allSettled
    }
  };

  useEffect(() => { load(); }, []);

  const today = metrics?.today ?? {};
  const month = metrics?.thisMonth ?? {};

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Billing Engine Dashboard</h1>
          <p className="text-sm text-gray-500 mt-1">Real-time billing metrics and revenue split tracking</p>
        </div>
        <div className="flex gap-3 items-center">
          {config?.billing_model && (
            <span className="text-xs px-2 py-1 rounded border border-gray-300 text-gray-600">
              {config.billing_model.replace(/_/g, " ")}
            </span>
          )}
          <button
            onClick={load}
            className="flex items-center gap-1 text-sm px-3 py-1.5 rounded border border-gray-300 hover:bg-gray-50"
          >
            <RefreshCw size={14} /> Refresh
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center gap-2 mb-1">
            <Wallet size={16} className="text-gray-400" />
            <span className="text-sm text-gray-500">Today's Gross Fees</span>
          </div>
          <div className="text-2xl font-bold text-gray-900">{fmtNGN(today.grossFees ?? today.gross_fees ?? 0)}</div>
          <p className="text-xs text-gray-400 mt-1">{fmtNum(today.transactionCount ?? today.transaction_count ?? 0)} transactions</p>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center gap-2 mb-1">
            <TrendingUp size={16} className="text-green-500" />
            <span className="text-sm text-gray-500">Platform Revenue (Today)</span>
          </div>
          <div className="text-2xl font-bold text-green-600">{fmtNGN(today.netPlatformRevenue ?? today.platform_revenue ?? 0)}</div>
          <p className="text-xs text-gray-400 mt-1">Net after switch fees</p>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center gap-2 mb-1">
            <BarChart3 size={16} className="text-blue-500" />
            <span className="text-sm text-gray-500">Month-to-Date Revenue</span>
          </div>
          <div className="text-2xl font-bold text-gray-900">{fmtNGN(month.grossFees ?? month.gross_fees ?? 0)}</div>
          <p className="text-xs text-gray-400 mt-1">{fmtNum(month.transactionCount ?? month.transaction_count ?? 0)} total tx</p>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center gap-2 mb-1">
            <Activity size={16} className="text-purple-500" />
            <span className="text-sm text-gray-500">Audit Events (30d)</span>
          </div>
          <div className="text-2xl font-bold text-gray-900">{alerts.length}</div>
          <p className="text-xs text-gray-400 mt-1">{alerts.length} active alerts</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="bg-white rounded-xl border border-gray-200">
        <div className="flex border-b border-gray-200 px-4">
          {(["overview", "alerts", "config"] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-3 text-sm font-medium capitalize border-b-2 transition-colors ${
                activeTab === tab
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab === "config" ? "Tenant Config" : tab.replace(/([A-Z])/g, " $1")}
            </button>
          ))}
        </div>

        <div className="p-5">
          {activeTab === "overview" && (
            <div className="space-y-6">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <p className="text-xs text-gray-500">Platform Share (MTD)</p>
                  <p className="text-lg font-bold">{fmtNGN(month.platformShare ?? month.platform_share ?? 0)}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Client Share (MTD)</p>
                  <p className="text-lg font-bold">{fmtNGN(month.clientShare ?? month.client_share ?? 0)}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Agent Commissions (MTD)</p>
                  <p className="text-lg font-bold">{fmtNGN(month.agentCommissions ?? month.agent_commissions ?? 0)}</p>
                </div>
                <div>
                  <p className="text-xs text-gray-500">Switch Fees (MTD)</p>
                  <p className="text-lg font-bold">{fmtNGN(month.switchFees ?? month.switch_fees ?? 0)}</p>
                </div>
              </div>

            </div>
          )}

          {activeTab === "alerts" && (
            <div className="space-y-3">
              {alerts.length === 0 && (
                <div className="flex flex-col items-center py-8 text-gray-400">
                  <AlertTriangle size={32} className="mb-2 text-green-400" />
                  <p className="text-sm">No active alerts</p>
                </div>
              )}
              {alerts.map((alert: any, i: number) => (
                <div key={i} className={`flex items-start gap-3 p-4 rounded-lg border ${
                  alert.severity === "critical" ? "border-red-200 bg-red-50" :
                  alert.severity === "warning" ? "border-amber-200 bg-amber-50" :
                  "border-blue-200 bg-blue-50"
                }`}>
                  <AlertTriangle size={16} className={
                    alert.severity === "critical" ? "text-red-500 mt-0.5" :
                    alert.severity === "warning" ? "text-amber-500 mt-0.5" :
                    "text-blue-500 mt-0.5"
                  } />
                  <div>
                    <p className="text-sm font-medium text-gray-800">{alert.type?.replace(/_/g, " ") ?? "Alert"}</p>
                    <p className="text-xs text-gray-600">{alert.message}</p>
                  </div>
                </div>
              ))}
            </div>
          )}

          {activeTab === "config" && (
            <div className="grid grid-cols-2 gap-6">
              <div>
                <p className="text-xs text-gray-500 mb-1">Billing Model</p>
                <p className="text-sm font-medium">{config?.billing_model?.replace(/_/g, " ") ?? "Not configured"}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-1">Auto Renew</p>
                <p className="text-sm font-medium">{config?.auto_renew ? "Yes" : "No"}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-1">Effective Date</p>
                <p className="text-sm font-medium">
                  {config?.effective_date ? new Date(config.effective_date).toLocaleDateString() : "N/A"}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-1">Contract End</p>
                <p className="text-sm font-medium">
                  {config?.contract_end_date ? new Date(config.contract_end_date).toLocaleDateString() : "N/A"}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-1">Currency</p>
                <p className="text-sm font-medium">{config?.currency ?? "NGN"}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-1">Status</p>
                <p className="text-sm font-medium capitalize">{config?.status?.replace(/_/g, " ") ?? "—"}</p>
              </div>
              {config?.revenue_share_config && (
                <div className="col-span-2">
                  <p className="text-xs text-gray-500 mb-1">Revenue Share Config</p>
                  <pre className="text-xs bg-gray-50 p-3 rounded border border-gray-200 overflow-auto max-h-40">
                    {JSON.stringify(config.revenue_share_config, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
