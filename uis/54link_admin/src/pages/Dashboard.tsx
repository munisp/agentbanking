import { Activity, AlertCircle, Building2, DollarSign, TrendingUp, Users } from "lucide-react";
import { useEffect, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { LiveIndicator } from '../components/LiveIndicator';
import { useTenantBranding } from '../contexts/TenantBrandingContext';
import { useAnimatedCounter } from '../hooks/useRealTimeData';
import apiClient from '../services/api';
import type { FeatureFlagConfig, Tenant } from '../services/tenant';
import { tenantService } from '../services/tenant';

interface DashboardMetrics {
  total_customers: number;
  total_accounts: number;
  total_transactions: number;
  total_volume_kobo: number;
  customer_growth_pct: string;
  account_growth_pct: string;
  transaction_growth_pct: string;
  volume_growth_pct: string;
  revenue_trend: { month: string; revenue: number; growth: number }[];
}

interface MetricCardProps {
  icon: React.ReactNode;
  value: number;
  label: string;
  growth: string;
  iconBg: string;
  format?: 'number' | 'currency' | 'large';
  isLoading?: boolean;
}

function MetricCard({ icon, value, label, growth, iconBg, format = 'number', isLoading }: MetricCardProps) {
  const animatedValue = useAnimatedCounter(value, 1000);
  
  const formatValue = (val: number) => {
    if (format === 'currency') {
      return `₦${(val / 1000).toFixed(1)}B`;
    } else if (format === 'large') {
      return `₦${(val / 1000).toFixed(1)}T`;
    } else if (val >= 1000000) {
      return `${(val / 1000000).toFixed(1)}M`;
    }
    return val.toLocaleString();
  };

  if (isLoading) {
    return (
      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700 animate-pulse">
        <div className="flex items-center justify-between mb-4">
          <div className={`p-3 ${iconBg} rounded-lg opacity-50`}>
            {icon}
          </div>
          <div className="h-4 w-12 bg-slate-200 dark:bg-slate-700 rounded"></div>
        </div>
        <div className="h-8 w-24 bg-slate-200 dark:bg-slate-700 rounded mb-2"></div>
        <div className="h-4 w-32 bg-slate-200 dark:bg-slate-700 rounded"></div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
      <div className="flex items-center justify-between mb-4">
        <div className={`p-3 ${iconBg} rounded-lg`}>
          {icon}
        </div>
        <span className="text-sm font-semibold text-green-600 dark:text-green-400">{growth}</span>
      </div>
      <div className="text-3xl font-bold text-slate-900 dark:text-white">{formatValue(animatedValue)}</div>
      <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">{label}</div>
    </div>
  );
}


// Extend Tenant type for dashboard metrics (API returns these fields)
type TenantWithMetrics = Tenant & {
  total_customers?: number;
  total_accounts?: number;
  total_transactions?: number;
  total_volume?: number;
};

export default function Dashboard() {
  const { name, primaryColor, secondaryColor } = useTenantBranding();
  const [recentAlerts, setRecentAlerts] = useState<{
    alerts: Array<{ id: string; severity: string; title: string; message: string; createdAt: string }>;
    total: number;
  } | null>(null);

  // Real dashboard metrics from the reporting API
  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [metricsLoading, setMetricsLoading] = useState(true);

  // Tenants from tenant service
  const [tenants, setTenants] = useState<TenantWithMetrics[]>([]);
  const [tenantsLoading, setTenantsLoading] = useState(true);

  useEffect(() => {
    // Fetch real platform-level summary metrics
    apiClient.get('/v1/reports/dashboard-summary')
      .then((res) => {
        setMetrics(res.data);
        setMetricsLoading(false);
      })
      .catch(() => {
        // If reporting service is unavailable, show zeros — never show fake numbers
        setMetrics({
          total_customers: 0,
          total_accounts: 0,
          total_transactions: 0,
          total_volume_kobo: 0,
          customer_growth_pct: 'N/A',
          account_growth_pct: 'N/A',
          transaction_growth_pct: 'N/A',
          volume_growth_pct: 'N/A',
          revenue_trend: [],
        });
        setMetricsLoading(false);
      });

    tenantService.getAllTenants()
      .then(({ tenants }) => {
        setTenants(tenants);
        setTenantsLoading(false);
      })
      .catch(() => setTenantsLoading(false));

    apiClient.get('/v1/alerts/recent?limit=5')
      .then((res) => setRecentAlerts(res.data))
      .catch(() => setRecentAlerts(null));
  }, []);

  const totalCustomers = metrics?.total_customers ?? 0;
  const totalAccounts = metrics?.total_accounts ?? 0;
  const totalTransactions = metrics?.total_transactions ?? 0;
  const totalVolume = metrics ? Math.round(metrics.total_volume_kobo / 100) : 0;

  const customerGrowth = metrics?.customer_growth_pct ?? 'N/A';
  const revenueGrowth = metrics?.volume_growth_pct ?? 'N/A';
  const transactionGrowth = metrics?.transaction_growth_pct ?? 'N/A';
  const accountGrowth = metrics?.account_growth_pct ?? 'N/A';

  const revenueData = metrics?.revenue_trend ?? [];

  // Tier distribution from tenants data
  const tierCounts: Record<string, number> = {};
  tenants.forEach((t) => {
    const plan = t.billing?.plan || 'unknown';
    tierCounts[plan] = (tierCounts[plan] || 0) + 1;
  });
  const tierColors: Record<string, string> = {
    standard: '#3b82f6',
    premium: '#8b5cf6',
    enterprise: '#ec4899',
    unknown: '#64748b',
  };
  const tierData = Object.entries(tierCounts).map(([plan, count]) => ({
    name: plan.charAt(0).toUpperCase() + plan.slice(1),
    value: count,
    color: tierColors[plan] || '#64748b',
  }));

  // Top tenants: just show the list of tenant names
  const topTenants = tenants.map(t => t.name);

  // Feature usage: count enabled feature flags across tenants
  const featureFlagCounts: Record<string, number> = {};
  tenants.forEach((t) => {
    t.feature_flags?.forEach((flag: FeatureFlagConfig) => {
      if (flag.is_enabled) {
        featureFlagCounts[flag.name] = (featureFlagCounts[flag.name] || 0) + 1;
      }
    });
  });
  const featureUsage = Object.entries(featureFlagCounts).map(([feature, count]) => ({
    feature: feature.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase()),
    adoption: tenants.length > 0 ? Math.round((count / tenants.length) * 100) : 0,
  }));



  const isLoading = tenantsLoading || metricsLoading;

  return (
    <div className="p-6 space-y-6 bg-slate-50 dark:bg-slate-900 min-h-screen">
      {/* Header */}
      <div
        className="rounded-2xl px-8 py-7 flex items-center justify-between mb-2"
        style={{
          background: `linear-gradient(135deg, ${primaryColor} 0%, ${secondaryColor} 100%)`,
        }}
      >
        <div>
          <h1 className="text-3xl font-bold text-white tracking-tight">Dashboard</h1>
          <p className="text-white/70 mt-1 text-sm font-medium">{name} Super Admin Console</p>
        </div>
        <div className="flex items-center gap-3 bg-white/10 backdrop-blur-sm border border-white/20 rounded-xl px-4 py-2">
          <LiveIndicator isLive={!isLoading} />
          <span className="text-sm text-white/90 font-medium">Real-time archive-aligned view</span>
        </div>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          icon={<Users className="w-6 h-6 text-blue-600" />}
          value={totalCustomers}
          label="Total Customers"
          growth={customerGrowth}
          iconBg="bg-blue-100 dark:bg-blue-900/30"
          isLoading={isLoading}
        />
        <MetricCard
          icon={<Building2 className="w-6 h-6 text-purple-600" />}
          value={totalAccounts}
          label="Total Accounts"
          growth={accountGrowth}
          iconBg="bg-purple-100 dark:bg-purple-900/30"
          isLoading={isLoading}
        />
        <MetricCard
          icon={<TrendingUp className="w-6 h-6 text-green-600" />}
          value={totalTransactions}
          label="Total Transactions"
          growth={transactionGrowth}
          iconBg="bg-green-100 dark:bg-green-900/30"
          format="large"
          isLoading={isLoading}
        />
        <MetricCard
          icon={<DollarSign className="w-6 h-6 text-pink-600" />}
          value={totalVolume / 1000}
          label="Total Volume"
          growth={revenueGrowth}
          iconBg="bg-pink-100 dark:bg-pink-900/30"
          format="currency"
          isLoading={isLoading}
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Revenue Trend */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-bold text-slate-900 dark:text-white">Revenue Trend</h2>
            <LiveIndicator isLive={!isLoading} />
          </div>
          {isLoading ? (
            <div className="h-64 flex items-center justify-center">
              <Activity className="w-8 h-8 text-slate-400 animate-spin" />
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={revenueData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="month" stroke="#64748b" />
                <YAxis stroke="#64748b" />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '8px' }}
                  labelStyle={{ color: '#f1f5f9' }}
                />
                <Legend />
                <Line type="monotone" dataKey="revenue" stroke="#8b5cf6" strokeWidth={3} name="Revenue (₦B)" />
                <Line type="monotone" dataKey="growth" stroke="#10b981" strokeWidth={2} name="Growth (%)" />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Subscription Tiers */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
          <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-6">Subscription Distribution</h2>
          {isLoading ? (
            <div className="h-64 flex items-center justify-center">
              <Activity className="w-8 h-8 text-slate-400 animate-spin" />
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={tierData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, value }) => `${name}: ${value}`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {tierData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Bottom Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Tenants: just show names */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
          <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-6">Top Tenants</h2>
          {isLoading ? (
            <div className="space-y-4">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="h-4 w-32 bg-slate-200 dark:bg-slate-700 rounded animate-pulse"></div>
              ))}
            </div>
          ) : (
            <ul className="space-y-2">
              {topTenants.map((name, index) => (
                <li key={index} className="font-semibold text-slate-900 dark:text-white p-2 bg-slate-50 dark:bg-slate-700/50 rounded-lg">
                  {name}
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Feature Adoption */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
          <h2 className="text-xl font-bold text-slate-900 dark:text-white mb-6">Feature Adoption</h2>
          {isLoading ? (
            <div className="h-64 flex items-center justify-center">
              <Activity className="w-8 h-8 text-slate-400 animate-spin" />
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={featureUsage} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis type="number" stroke="#64748b" />
                <YAxis dataKey="feature" type="category" stroke="#64748b" width={120} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '8px' }}
                  labelStyle={{ color: '#f1f5f9' }}
                />
                <Bar dataKey="adoption" fill="#8b5cf6" radius={[0, 8, 8, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* Recent Alerts */}
      {recentAlerts && recentAlerts.alerts.length > 0 && (
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-bold text-slate-900 dark:text-white">Recent Alerts</h2>
            <span className="text-sm text-slate-600 dark:text-slate-400">{recentAlerts.total} unread</span>
          </div>
          <div className="space-y-3">
            {recentAlerts.alerts.map((alert) => (
              <div key={alert.id} className="flex items-start gap-3 p-3 bg-slate-50 dark:bg-slate-700/50 rounded-lg">
                <AlertCircle className={`w-5 h-5 mt-0.5 ${
                  alert.severity === 'critical' ? 'text-red-600' :
                  alert.severity === 'high' ? 'text-orange-600' :
                  alert.severity === 'medium' ? 'text-yellow-600' : 'text-blue-600'
                }`} />
                <div className="flex-1">
                  <div className="font-semibold text-slate-900 dark:text-white">{alert.title}</div>
                  <div className="text-sm text-slate-600 dark:text-slate-400">{alert.message}</div>
                  <div className="text-xs text-slate-500 dark:text-slate-500 mt-1">
                    {new Date(alert.createdAt).toLocaleString()}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
