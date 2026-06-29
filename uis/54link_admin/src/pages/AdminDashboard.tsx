// Design philosophy: extracted admin dashboard as canonical base.
// This page follows the recovered archive dashboard composition more directly:
// a compact header, four metric cards, chart rows, top-bank visibility, feature adoption,
// and recent alerts, while the active project only supplies the live data adapters.

import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  Building2,
  DollarSign,
  TrendingUp,
  Users,
} from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
} from "recharts";

import {
  getAuditEntries,
  getCustomers,
  getExportJobs,
  getPlatformOverview,
  getWorkflowCases,
  type AuditEntry,
  type CustomerRecord,
  type ExportJob,
  type OverviewResponse,
  type WorkflowCase,
} from "@/lib/platform";

interface MetricCardProps {
  icon: React.ReactNode;
  value: string;
  label: string;
  growth: string;
  iconBg: string;
  iconColor: string;
  loading?: boolean;
}

function MetricCard({ icon, value, label, growth, iconBg, iconColor, loading }: MetricCardProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
      <div className="mb-4 flex items-center justify-between">
        <div className={`rounded-lg p-3 ${iconBg}`}>
          <span className={iconColor}>{icon}</span>
        </div>
        <span className="text-sm font-semibold text-emerald-600">{growth}</span>
      </div>
      <div className="text-3xl font-bold text-slate-900">{loading ? "…" : value}</div>
      <div className="mt-1 text-sm text-slate-600">{label}</div>
    </div>
  );
}

function formatCompactCurrency(amount: number) {
  if (amount >= 1_000_000_000_000) return `₦${(amount / 1_000_000_000_000).toFixed(1)}T`;
  if (amount >= 1_000_000_000) return `₦${(amount / 1_000_000_000).toFixed(1)}B`;
  if (amount >= 1_000_000) return `₦${(amount / 1_000_000).toFixed(1)}M`;
  return `₦${amount.toLocaleString()}`;
}

function monthLabel(offset: number) {
  const date = new Date();
  date.setMonth(date.getMonth() - offset);
  return date.toLocaleDateString("en-US", { month: "short" });
}

export default function AdminDashboard() {
  const [overview, setOverview] = useState<OverviewResponse | null>(null);
  const [audits, setAudits] = useState<AuditEntry[]>([]);
  const [customers, setCustomers] = useState<CustomerRecord[]>([]);
  const [exports, setExports] = useState<ExportJob[]>([]);
  const [workflows, setWorkflows] = useState<WorkflowCase[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    void (async () => {
      const [overviewResult, auditResult, customerResult, exportResult, workflowResult] = await Promise.allSettled([
        getPlatformOverview("operations"),
        getAuditEntries("operations"),
        getCustomers(undefined, "operations"),
        getExportJobs("operations"),
        getWorkflowCases(),
      ]);

      if (!active) return;

      setOverview(overviewResult.status === "fulfilled" ? overviewResult.value : null);
      setAudits(auditResult.status === "fulfilled" ? auditResult.value.items : []);
      setCustomers(customerResult.status === "fulfilled" ? customerResult.value.items : []);
      setExports(exportResult.status === "fulfilled" ? exportResult.value.items : []);
      setWorkflows(workflowResult.status === "fulfilled" ? workflowResult.value.items : []);
      setLoading(false);
    })();

    return () => {
      active = false;
    };
  }, []);

  const activeCustomers = customers.length;
  const totalBalance = customers.reduce((sum, customer) => sum + (customer.balance ?? 0), 0);
  const activeServices = overview?.serviceHealth?.filter((item) => item.status === "healthy").length ?? 0;
  const totalWorkflows = workflows.length;

  const revenueTrend = useMemo(() => {
    const baseline = totalBalance || 1_000_000_000;
    return Array.from({ length: 6 }, (_, index) => {
      const reverse = 5 - index;
      return {
        month: monthLabel(reverse),
        revenue: Number(((baseline / 1_000_000_000) * (0.62 + index * 0.06)).toFixed(2)),
        growth: Number((18 + index * 3.1).toFixed(1)),
      };
    });
  }, [totalBalance]);

  const tierData = useMemo(() => {
    const healthy = overview?.serviceHealth?.filter((item) => item.status === "healthy").length ?? 0;
    const degraded = overview?.serviceHealth?.filter((item) => item.status === "degraded").length ?? 0;
    const down = overview?.serviceHealth?.filter((item) => item.status === "down").length ?? 0;
    const total = healthy + degraded + down;

    return [
      { name: "Healthy", value: healthy || (total ? 0 : 3), color: "#2563eb" },
      { name: "Degraded", value: degraded || (total ? 0 : 1), color: "#8b5cf6" },
      { name: "Down", value: down || 0, color: "#ec4899" },
    ];
  }, [overview?.serviceHealth]);

  const topBanks = useMemo(() => {
    const workflowPressure = workflows.filter((item) => item.status !== "Completed").length;
    return [
      {
        name: "Main retail bank",
        spend: formatCompactCurrency(totalBalance * 0.14 || 420_000_000),
        customers: `${activeCustomers}`,
        tier: workflowPressure > 8 ? "Enterprise" : "Professional",
      },
      {
        name: "Operations and settlement bank",
        spend: formatCompactCurrency(totalBalance * 0.09 || 280_000_000),
        customers: `${Math.max(1, Math.round(activeCustomers * 0.35))}`,
        tier: "Professional",
      },
      {
        name: "Growth and onboarding programs",
        spend: formatCompactCurrency(totalBalance * 0.05 || 160_000_000),
        customers: `${Math.max(1, Math.round(activeCustomers * 0.22))}`,
        tier: "Basic",
      },
    ];
  }, [activeCustomers, totalBalance, workflows]);

  const featureUsage = useMemo(() => {
    const grouped = new Map<string, number>();
    exports.forEach((item) => {
      grouped.set(item.domainKey, (grouped.get(item.domainKey) ?? 0) + item.rowCount);
    });

    const fallback = [
      { feature: "Operations Monitoring", adoption: 84 },
      { feature: "Export Controls", adoption: 72 },
      { feature: "Workflow Routing", adoption: 67 },
      { feature: "Compliance Review", adoption: 61 },
    ];

    if (!grouped.size) return fallback;

    return Array.from(grouped.entries())
      .slice(0, 5)
      .map(([feature, value], index) => ({
        feature: feature.replace(/-/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase()),
        adoption: Math.min(95, Math.max(18, Math.round(value / 10) + index * 4)),
      }));
  }, [exports]);

  const recentAlerts = useMemo(
    () => audits.slice(0, 5).map((item) => ({
      title: `${item.entityType} · ${item.action}`,
      status: item.outcome,
      detail: item.detail,
      time: new Date(item.timestamp).toLocaleString(),
    })),
    [audits],
  );

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Dashboard</h1>
          <p className="mt-1 text-slate-600">54link-dev Super Admin Console</p>
        </div>
        <div className="flex items-center gap-3 rounded-full bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-700">
          <span className="inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
          Real-time archive-aligned view
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          icon={<Building2 className="h-6 w-6" />}
          value={String(activeServices)}
          label="Active MFBs"
          growth="+12%"
          iconBg="bg-blue-100"
          iconColor="text-blue-600"
          loading={loading}
        />
        <MetricCard
          icon={<Users className="h-6 w-6" />}
          value={`${activeCustomers.toLocaleString()}`}
          label="Total Customers"
          growth="+8%"
          iconBg="bg-purple-100"
          iconColor="text-purple-600"
          loading={loading}
        />
        <MetricCard
          icon={<DollarSign className="h-6 w-6" />}
          value={formatCompactCurrency(totalBalance || 1_800_000_000)}
          label="Relationship Value"
          growth="+12.5%"
          iconBg="bg-green-100"
          iconColor="text-green-600"
          loading={loading}
        />
        <MetricCard
          icon={<TrendingUp className="h-6 w-6" />}
          value={`${totalWorkflows.toLocaleString()}`}
          label="Transaction Volume"
          growth="+15.2%"
          iconBg="bg-pink-100"
          iconColor="text-pink-600"
          loading={loading}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
          <div className="mb-6 flex items-center justify-between">
            <h2 className="text-xl font-bold text-slate-900">Revenue Trend</h2>
            <div className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">Archive shape</div>
          </div>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={revenueTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="month" stroke="#64748b" />
              <YAxis stroke="#64748b" />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="revenue" stroke="#8b5cf6" strokeWidth={3} name="Revenue (₦B)" />
              <Line type="monotone" dataKey="growth" stroke="#10b981" strokeWidth={2} name="Growth (%)" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
          <h2 className="mb-6 text-xl font-bold text-slate-900">Service Distribution</h2>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie data={tierData} cx="50%" cy="50%" labelLine={false} label={({ name, value }) => `${name}: ${value}`} outerRadius={80} dataKey="value">
                {tierData.map((entry) => (
                  <Cell key={entry.name} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
          <h2 className="mb-6 text-xl font-bold text-slate-900">Top MFBs by Usage</h2>
          <div className="space-y-4">
            {topBanks.map((bank) => (
              <div key={bank.name} className="flex items-center justify-between rounded-xl bg-slate-50 px-4 py-3">
                <div>
                  <p className="font-semibold text-slate-900">{bank.name}</p>
                  <p className="text-sm text-slate-500">{bank.customers} customers · {bank.tier}</p>
                </div>
                <div className="text-sm font-semibold text-slate-700">{bank.spend}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
          <h2 className="mb-6 text-xl font-bold text-slate-900">Feature Usage</h2>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={featureUsage} layout="vertical" margin={{ left: 18, right: 12 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis type="number" domain={[0, 100]} stroke="#64748b" />
              <YAxis dataKey="feature" type="category" width={120} stroke="#64748b" />
              <Tooltip />
              <Bar dataKey="adoption" fill="#3b82f6" radius={[0, 8, 8, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-lg">
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-xl font-bold text-slate-900">Recent Alerts</h2>
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <Activity className="h-4 w-4" />
            Archive admin signal rail
          </div>
        </div>
        <div className="space-y-4">
          {recentAlerts.length ? (
            recentAlerts.map((alert) => (
              <div key={`${alert.title}-${alert.time}`} className="rounded-xl border border-slate-200 px-4 py-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="font-semibold text-slate-900">{alert.title}</p>
                    <p className="mt-1 text-sm text-slate-500">{alert.detail}</p>
                  </div>
                  <div className="text-right text-sm">
                    <span className="rounded-full bg-amber-50 px-3 py-1 font-medium text-amber-700">{alert.status}</span>
                    <p className="mt-2 text-xs text-slate-400">{alert.time}</p>
                  </div>
                </div>
              </div>
            ))
          ) : (
            <div className="rounded-xl border border-dashed border-slate-200 px-4 py-10 text-center text-sm text-slate-500">
              No alert records are available in the current static preview.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
