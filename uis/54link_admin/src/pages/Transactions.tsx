import { Activity, TrendingUp } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { useTenantBranding } from '../contexts/TenantBrandingContext';
import apiClient from '../services/api';

interface StatusBreakdown {
  success?: number;
  failed?: number;
  pending?: number;
  reversed?: number;
  fraud?: number;
}

interface TypeBreakdown {
  deposit?: number;
  withdrawal?: number;
  transfer?: number;
}

interface TransactionMetrics {
  total_count: number;
  total_volume: number;
  status_breakdown: StatusBreakdown;
  type_breakdown: TypeBreakdown;
}

const EMPTY_METRICS: TransactionMetrics = {
  total_count: 0,
  total_volume: 0,
  status_breakdown: {},
  type_breakdown: {},
};

export default function Transactions() {
  const { primaryColor, secondaryColor } = useTenantBranding();

  const [metrics, setMetrics] = useState<TransactionMetrics>(EMPTY_METRICS);
  const [metricsLoading, setMetricsLoading] = useState(true);

  useEffect(() => {
    apiClient.get('/ledger/txn/metrics')
      .then((res) => {
        const m = res.data.metrics ?? {};
        setMetrics({
          total_count: m.total_count ?? 0,
          total_volume: m.total_volume ?? 0,
          status_breakdown: m.status_breakdown ?? {},
          type_breakdown: m.type_breakdown ?? {},
        });
        setMetricsLoading(false);
      })
      .catch(() => {
        setMetrics(EMPTY_METRICS);
        setMetricsLoading(false);
      });
  }, []);

  const derivedStats = useMemo(() => {
    const { success = 0, failed = 0, pending = 0, fraud = 0 } = metrics.status_breakdown;
    const failedTotal = failed + fraud;
    const rate = metrics.total_count > 0 ? ((success / metrics.total_count) * 100).toFixed(1) : '0.0';
    return { successful: success, failed: failedTotal, pending, success_rate: rate };
  }, [metrics]);

  const typeDistribution = useMemo(() => {
    const { deposit = 0, withdrawal = 0, transfer = 0 } = metrics.type_breakdown;
    const colors: Record<string, string> = { Deposit: '#3b82f6', Withdrawal: '#8b5cf6', Transfer: '#ec4899' };
    return [
      { name: 'Deposit', value: deposit, color: colors.Deposit },
      { name: 'Withdrawal', value: withdrawal, color: colors.Withdrawal },
      { name: 'Transfer', value: transfer, color: colors.Transfer },
    ].filter((entry) => entry.value > 0);
  }, [metrics]);

  const v = metrics.total_volume;
  const totalVolumeStr = v >= 1_000_000_000 ? `₦${(v / 1_000_000_000).toFixed(1)}B` : v >= 1_000_000 ? `₦${(v / 1_000_000).toFixed(1)}M` : `₦${v.toLocaleString()}`;

  return (
    <div
      className="min-h-screen"
      style={{ background: `linear-gradient(to bottom right, ${primaryColor}15, ${secondaryColor}15)` }}
    >
      {/* Header */}
      <div className="border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 backdrop-blur-sm">
        <div className="container py-6">
          <h1 className="text-3xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
            <TrendingUp className="w-8 h-8" style={{ color: primaryColor }} />
            Transactions
          </h1>
          <p className="text-slate-600 dark:text-slate-400 mt-1">
            Aggregate transaction summary across tenants
          </p>
        </div>
      </div>

      <div className="container py-8">
        {metricsLoading ? (
          <div className="p-12 text-center">
            <Activity className="w-12 h-12 text-slate-400 animate-spin mx-auto mb-4" />
            <p className="text-slate-600 dark:text-slate-400">Loading summary...</p>
          </div>
        ) : (
          <>
            {/* Statistics Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
              <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
                <div className="text-sm text-slate-600 dark:text-slate-400 mb-2">Total Transactions</div>
                <div className="text-3xl font-bold text-slate-900 dark:text-white">{metrics.total_count.toLocaleString()}</div>
              </div>
              <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
                <div className="text-sm text-slate-600 dark:text-slate-400 mb-2">Total Volume</div>
                <div className="text-3xl font-bold text-green-600 dark:text-green-400">{totalVolumeStr}</div>
                <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">{derivedStats.successful.toLocaleString()} successful</div>
              </div>
              <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
                <div className="text-sm text-slate-600 dark:text-slate-400 mb-2">Success Rate</div>
                <div className="text-3xl font-bold text-green-600 dark:text-green-400">{derivedStats.success_rate}%</div>
                <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">{derivedStats.failed.toLocaleString()} failed</div>
              </div>
              <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
                <div className="text-sm text-slate-600 dark:text-slate-400 mb-2">Pending</div>
                <div className="text-3xl font-bold text-yellow-600 dark:text-yellow-400">{derivedStats.pending.toLocaleString()}</div>
                <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">awaiting processing</div>
              </div>
            </div>

            {/* Charts Row */}
            {typeDistribution.length > 0 && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
                  <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-6">Transaction Types</h3>
                  <ResponsiveContainer width="100%" height={250}>
                    <PieChart>
                      <Pie data={typeDistribution} cx="50%" cy="50%" labelLine={false} label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`} outerRadius={80} dataKey="value">
                        {typeDistribution.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.color} />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
