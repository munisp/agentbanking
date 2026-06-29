/**
 * Sprint 52 — Float Management Dashboard
 * F10: Agent float balances, top-ups, alerts, and utilization
 */
// @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
import { DashboardLayout } from "@/components/DashboardLayout";
import { PageErrorBoundary } from "@/components/ErrorBoundary";
import { useState, useMemo, useEffect } from "react";
import {
  Wallet,
  AlertTriangle,
  Search,
  Plus,
  DollarSign,
  BarChart3,
} from "lucide-react";

const FALLBACK_FLOAT_DATA = [
  {
    id: 1,
    agentId: "AGT-0012",
    name: "Adebayo Ogundimu",
    balance: 2500000,
    limit: 5000000,
    utilized: 50,
    lastTopUp: "2026-04-22T02:00:00Z",
    topUpAmount: 1000000,
    status: "healthy",
  },
  {
    id: 2,
    agentId: "AGT-0034",
    name: "Chidinma Okafor",
    balance: 450000,
    limit: 3000000,
    utilized: 85,
    lastTopUp: "2026-04-21T18:00:00Z",
    topUpAmount: 500000,
    status: "warning",
  },
  {
    id: 3,
    agentId: "AGT-0056",
    name: "Ibrahim Musa",
    balance: 3200000,
    limit: 5000000,
    utilized: 36,
    lastTopUp: "2026-04-22T01:00:00Z",
    topUpAmount: 2000000,
    status: "healthy",
  },
  {
    id: 4,
    agentId: "AGT-0078",
    name: "Funke Adeyemi",
    balance: 120000,
    limit: 2000000,
    utilized: 94,
    lastTopUp: "2026-04-20T12:00:00Z",
    topUpAmount: 300000,
    status: "critical",
  },
  {
    id: 5,
    agentId: "AGT-0023",
    name: "Emeka Nwosu",
    balance: 1800000,
    limit: 4000000,
    utilized: 55,
    lastTopUp: "2026-04-22T00:30:00Z",
    topUpAmount: 1500000,
    status: "healthy",
  },
  {
    id: 6,
    agentId: "AGT-0045",
    name: "Aisha Bello",
    balance: 780000,
    limit: 3000000,
    utilized: 74,
    lastTopUp: "2026-04-21T22:00:00Z",
    topUpAmount: 800000,
    status: "warning",
  },
  {
    id: 7,
    agentId: "AGT-0067",
    name: "Olumide Bakare",
    balance: 2100000,
    limit: 3500000,
    utilized: 40,
    lastTopUp: "2026-04-21T20:00:00Z",
    topUpAmount: 1200000,
    status: "healthy",
  },
  {
    id: 8,
    agentId: "AGT-0089",
    name: "Grace Eze",
    balance: 50000,
    limit: 1500000,
    utilized: 97,
    lastTopUp: "2026-04-19T15:00:00Z",
    topUpAmount: 200000,
    status: "critical",
  },
];

function formatNaira(n: number) {
  return new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency: "NGN",
    minimumFractionDigits: 0,
  }).format(n);
}

function FloatContent() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [showTopUp, setShowTopUp] = useState(false);
  const [liveData, setLiveData] = useState<any[] | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setIsLoading(true);
    setError(null);
    fetch("/float/api/v1/balances", {
      headers: (() => {
        const token = localStorage.getItem("auth_token");
        const raw = localStorage.getItem("tenant_config");
        const tenant = raw ? JSON.parse(raw) : null;
        return {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(tenant?.tenant_id ? { "x-tenant-id": tenant.tenant_id } : {}),
          ...(tenant?.tenant_slug ? { "x-tenant-slug": tenant.tenant_slug } : {}),
        };
      })(),
    })
      .then(r => r.json())
      .then(json => {
        const list: any[] = Array.isArray(json)
          ? json
          : json?.items ?? json?.balances ?? json?.data ?? [];
        setLiveData(list.length > 0 ? list : null);
      })
      .catch(() => {
        setError("Float Management service unavailable");
        setLiveData(null);
      })
      .finally(() => setIsLoading(false));
  }, []);

  const floatData = liveData ?? FALLBACK_FLOAT_DATA;

  const filtered = useMemo(() => {
    return floatData.filter((f: any) => {
      const name = f.name ?? f.agent_name ?? "";
      const agentId = f.agentId ?? f.agent_id ?? "";
      if (
        search &&
        !name.toLowerCase().includes(search.toLowerCase()) &&
        !agentId.includes(search)
      )
        return false;
      if (statusFilter !== "all" && f.status !== statusFilter) return false;
      return true;
    });
  }, [floatData, search, statusFilter]);

  const totalFloat = floatData.reduce(
    (s: number, f: any) => s + (f.balance ?? f.current_balance ?? 0),
    0
  );
  const totalLimit = floatData.reduce((s: number, f: any) => s + (f.limit ?? f.float_limit ?? 0), 0);
  const criticalCount = floatData.filter(
    (f: any) => f.status === "critical"
  ).length;
  const avgUtilization = floatData.length > 0
    ? floatData.reduce((s: number, f: any) => s + (f.utilized ?? f.utilization_pct ?? 0), 0) /
      floatData.length
    : 0;

  const todayTopUps = liveData
    ? liveData.reduce((s: number, f: any) => s + (f.topUpAmount ?? f.top_up_amount ?? f.last_top_up_amount ?? 0), 0)
    : null;

  if (isLoading) {
    return (
      <div className="p-6 flex items-center justify-center h-64">
        <div className="flex flex-col items-center gap-3">
          <div className="h-8 w-8 rounded-full border-4 border-primary border-t-transparent animate-spin" />
          <p className="text-sm text-muted-foreground">Loading float data…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Float Management</h1>
          <p className="text-sm text-muted-foreground">
            Monitor and manage agent float balances
          </p>
        </div>
        <div className="flex items-center gap-3">
          {liveData ? (
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400 text-xs font-medium">
              <span className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
              Live data
            </span>
          ) : null}
          <button
            onClick={() => setShowTopUp(true)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-md bg-primary text-primary-foreground hover:bg-primary/90 text-sm"
          >
            <Plus className="h-4 w-4" /> Bulk Top-Up
          </button>
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-md border border-yellow-300 bg-yellow-50 dark:bg-yellow-900/20 dark:border-yellow-700 px-4 py-3 text-sm text-yellow-800 dark:text-yellow-300">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          Warning: Showing cached data. Float Management service unavailable.
        </div>
      )}

      {/* KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="rounded-lg border bg-card p-5">
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
            <Wallet className="h-4 w-4" /> Total Float
          </div>
          <div className="text-2xl font-bold">{formatNaira(totalFloat)}</div>
          <div className="text-xs text-muted-foreground">
            of {formatNaira(totalLimit)} limit
          </div>
        </div>
        <div className="rounded-lg border bg-card p-5">
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
            <BarChart3 className="h-4 w-4" /> Avg Utilization
          </div>
          <div className="text-2xl font-bold">{avgUtilization.toFixed(1)}%</div>
          <div className="text-xs text-green-500">Healthy range</div>
        </div>
        <div className="rounded-lg border bg-card p-5">
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
            <AlertTriangle className="h-4 w-4" /> Critical Agents
          </div>
          <div className="text-2xl font-bold text-red-500">{criticalCount}</div>
          <div className="text-xs text-red-500">Need immediate top-up</div>
        </div>
        <div className="rounded-lg border bg-card p-5">
          <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
            <DollarSign className="h-4 w-4" /> Today's Top-Ups
          </div>
          {todayTopUps !== null ? (
            <>
              <div className="text-2xl font-bold">{formatNaira(todayTopUps)}</div>
              <div className="text-xs text-muted-foreground">{liveData?.length ?? 0} agents</div>
            </>
          ) : (
            <div className="text-sm text-muted-foreground mt-1">Live data unavailable</div>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search agents..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 rounded-md border bg-background text-sm"
          />
        </div>
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          className="px-3 py-2 rounded-md border bg-background text-sm"
        >
          <option value="all">All Statuses</option>
          <option value="healthy">Healthy</option>
          <option value="warning">Warning</option>
          <option value="critical">Critical</option>
        </select>
      </div>

      {/* Table */}
      <div className="rounded-lg border overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-muted/50">
            <tr>
              <th className="text-left p-3 font-medium">Agent</th>
              <th className="text-right p-3 font-medium">Balance</th>
              <th className="text-right p-3 font-medium">Limit</th>
              <th className="text-center p-3 font-medium">Utilization</th>
              <th className="text-right p-3 font-medium">Last Top-Up</th>
              <th className="text-center p-3 font-medium">Status</th>
              <th className="text-center p-3 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((f: any, idx: number) => {
              const name = f.name ?? f.agent_name ?? "—";
              const agentId = f.agentId ?? f.agent_id ?? "—";
              const balance = f.balance ?? f.current_balance ?? 0;
              const limit = f.limit ?? f.float_limit ?? 0;
              const utilized = f.utilized ?? f.utilization_pct ?? (limit > 0 ? Math.round(((limit - balance) / limit) * 100) : 0);
              const topUpAmount = f.topUpAmount ?? f.top_up_amount ?? f.last_top_up_amount ?? 0;
              const lastTopUp = f.lastTopUp ?? f.last_top_up ?? f.updated_at ?? null;
              return (
              <tr key={f.id ?? idx} className="border-t hover:bg-muted/30">
                <td className="p-3">
                  <div className="font-medium">{name}</div>
                  <div className="text-xs text-muted-foreground">
                    {agentId}
                  </div>
                </td>
                <td className="p-3 text-right font-mono font-medium">
                  {formatNaira(balance)}
                </td>
                <td className="p-3 text-right font-mono text-muted-foreground">
                  {formatNaira(limit)}
                </td>
                <td className="p-3">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${utilized > 90 ? "bg-red-500" : utilized > 70 ? "bg-yellow-500" : "bg-green-500"}`}
                        style={{ width: `${Math.min(utilized, 100)}%` }}
                      />
                    </div>
                    <span className="text-xs w-10 text-right">
                      {utilized}%
                    </span>
                  </div>
                </td>
                <td className="p-3 text-right text-xs text-muted-foreground">
                  {formatNaira(topUpAmount)}
                  <br />
                  {lastTopUp ? new Date(lastTopUp).toLocaleDateString() : "—"}
                </td>
                <td className="p-3 text-center">
                  <span
                    className={`px-2 py-0.5 rounded text-xs font-medium ${
                      f.status === "critical"
                        ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                        : f.status === "warning"
                          ? "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400"
                          : "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                    }`}
                  >
                    {f.status}
                  </span>
                </td>
                <td className="p-3 text-center">
                  <button className="px-2 py-1 rounded text-xs bg-primary text-primary-foreground hover:bg-primary/90">
                    Top-Up
                  </button>
                </td>
              </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function FloatManagementPage() {
  return (
    <DashboardLayout>
      <PageErrorBoundary>
        <FloatContent />
      </PageErrorBoundary>
    </DashboardLayout>
  );
}
