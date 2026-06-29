import { exportToExcel, exportToPDF } from '@/lib/exportUtils';
import { Activity, ArrowDownRight, ArrowUpRight, Download, FileText, Search, TrendingUp } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import { useTenantBranding } from '../contexts/TenantBrandingContext';
import apiClient from '../services/api';

interface Transaction {
  id: string;
  amount: string;
  ledger_id: string;
  status: string;
  transaction_id: string;
  created_at: string;
  completed_at: string | null;
  currency: string;
  deleted_at: string | null;
  note: string;
  payer: string;
  tag: string;
  payee: string;
  tenant_id: string;
  updated_at: string;
}

interface TransactionStats {
  total_count: number;
  total_volume: number;
}

const PAGE_SIZE = 50;

export default function Transactions() {
  const { primaryColor, secondaryColor } = useTenantBranding();

  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [typeFilter, setTypeFilter] = useState<string>('all');
  const [page, setPage] = useState(1);

  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [transactionsLoading, setTransactionsLoading] = useState(true);
  const [transactionsTotal, setTransactionsTotal] = useState(0);
  const [stats, setStats] = useState<TransactionStats>({ total_count: 0, total_volume: 0 });

  const fetchTransactions = useCallback(() => {
    setTransactionsLoading(true);
    const params: Record<string, string | number> = {
      page,
      limit: PAGE_SIZE,
    };
    if (searchTerm) params.search = searchTerm;
    if (statusFilter !== 'all') params.status = statusFilter;
    if (typeFilter !== 'all') params.type = typeFilter;

    apiClient.get('/ledger/txn/', { params })
      .then((res) => {
        const data = res.data;
        setTransactions(data.transactions ?? []);
        setTransactionsLoading(false);
      })
      .catch(() => {
        setTransactions([]);
        setTransactionsLoading(false);
      });
  }, [page, searchTerm, statusFilter, typeFilter]);

  useEffect(() => {
    fetchTransactions();
  }, [fetchTransactions]);

  useEffect(() => {
    apiClient.get('/ledger/txn/metrics')
      .then((res) => {
        const m = res.data.metrics ?? {};
        setStats({
          total_count: m.total_count ?? 0,
          total_volume: m.total_volume ?? 0,
        });
        setTransactionsTotal(m.total_count ?? 0);
      })
      .catch(() => {});
  }, []);

  const derivedStats = useMemo(() => {
    const successful = transactions.filter(t => ['success', 'completed'].includes(t.status?.toLowerCase())).length;
    const failed = transactions.filter(t => ['failed', 'error'].includes(t.status?.toLowerCase())).length;
    const pending = transactions.filter(t => ['pending', 'processing'].includes(t.status?.toLowerCase())).length;
    const rate = transactions.length > 0 ? ((successful / transactions.length) * 100).toFixed(1) : '0.0';
    return { successful, failed, pending, success_rate: rate };
  }, [transactions]);

  const typeDistribution = useMemo(() => {
    const typeMap = new Map<string, number>();
    transactions.forEach((txn) => {
      const type = txn.payer === 'MINT_ACCOUNT' ? 'deposit'
        : txn.payee === 'MINT_ACCOUNT' ? 'withdrawal'
        : 'transfer';
      typeMap.set(type, (typeMap.get(type) || 0) + 1);
    });
    const colors = ['#3b82f6', '#8b5cf6', '#ec4899'];
    return Array.from(typeMap.entries()).map(([name, value], idx) => ({
      name: name.charAt(0).toUpperCase() + name.slice(1),
      value,
      color: colors[idx % colors.length],
    }));
  }, [transactions]);

  const getStatusColor = (status: string) => {
    const s = status?.toLowerCase();
    if (s === 'success' || s === 'completed') return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300';
    if (s === 'failed' || s === 'error') return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300';
    if (s === 'pending' || s === 'processing') return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300';
    return 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300';
  };

  const getTypeIcon = (payer: string, payee: string) => {
    if (payer === 'MINT_ACCOUNT') return <ArrowDownRight className="w-4 h-4 text-green-600" />;
    if (payee === 'MINT_ACCOUNT') return <ArrowUpRight className="w-4 h-4 text-red-600" />;
    return <Activity className="w-4 h-4 text-blue-600" />;
  };

  const handleExportExcel = () => {
    const data = transactions.map((txn) => {
      const type = txn.payer === 'MINT_ACCOUNT' ? 'deposit'
        : txn.payee === 'MINT_ACCOUNT' ? 'withdrawal'
        : 'transfer';
      return {
        'Transaction ID': txn.transaction_id,
        Note: txn.note || 'N/A',
        Type: type,
        Amount: `${txn.currency} ${parseFloat(txn.amount || '0').toLocaleString()}`,
        Status: txn.status,
        Payer: txn.payer || 'N/A',
        Payee: txn.payee || 'N/A',
        Created: txn.created_at,
        Completed: txn.completed_at || 'N/A',
      };
    });
    exportToExcel(data, 'transactions');
  };

  const handleExportPDF = () => {
    const data = transactions.map((txn) => {
      const type = txn.payer === 'MINT_ACCOUNT' ? 'deposit'
        : txn.payee === 'MINT_ACCOUNT' ? 'withdrawal'
        : 'transfer';
      return {
        'Transaction ID': txn.transaction_id,
        Note: txn.note || 'N/A',
        Type: type,
        Amount: `${txn.currency} ${parseFloat(txn.amount || '0').toLocaleString()}`,
        Status: txn.status,
        Created: txn.created_at,
      };
    });
    exportToPDF(data, ['Transaction ID', 'Note', 'Type', 'Amount', 'Status', 'Created'], 'transactions-report', 'Transactions Report');
  };

  const totalPages = Math.ceil(transactionsTotal / PAGE_SIZE);
  const v = stats.total_volume;
  const totalVolumeStr = v >= 1_000_000_000 ? `₦${(v / 1_000_000_000).toFixed(1)}B` : v >= 1_000_000 ? `₦${(v / 1_000_000).toFixed(1)}M` : `₦${v.toLocaleString()}`;

  return (
    <div
      className="min-h-screen"
      style={{ background: `linear-gradient(to bottom right, ${primaryColor}15, ${secondaryColor}15)` }}
    >
      {/* Header */}
      <div className="border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900/50 backdrop-blur-sm">
        <div className="container py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
                <TrendingUp className="w-8 h-8" style={{ color: primaryColor }} />
                Transactions
              </h1>
              <p className="text-slate-600 dark:text-slate-400 mt-1">
                Real-time transaction ledger — {transactionsTotal.toLocaleString()} records
              </p>
            </div>
            <div className="flex gap-2">
              <button onClick={handleExportExcel} className="px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 flex items-center gap-2" disabled={transactionsLoading}>
                <Download className="w-5 h-5" /> Excel
              </button>
              <button onClick={handleExportPDF} className="px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 flex items-center gap-2" disabled={transactionsLoading}>
                <Download className="w-5 h-5" /> PDF
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="container py-8">
        {/* Statistics Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
            <div className="text-sm text-slate-600 dark:text-slate-400 mb-2">Total Transactions</div>
            <div className="text-3xl font-bold text-slate-900 dark:text-white">{stats.total_count.toLocaleString()}</div>
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
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {typeDistribution.length > 0 && (
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
          )}
        </div>

        {/* Filters */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700 mb-8">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
              <input
                type="text"
                placeholder="Search by ID, reference, note..."
                value={searchTerm}
                onChange={(e) => { setSearchTerm(e.target.value); setPage(1); }}
                className="w-full pl-10 pr-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:outline-none focus:ring-2"
              />
            </div>
            <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }} className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:outline-none focus:ring-2">
              <option value="all">All Statuses</option>
              <option value="success">Success</option>
              <option value="completed">Completed</option>
              <option value="pending">Pending</option>
              <option value="processing">Processing</option>
              <option value="failed">Failed</option>
            </select>
            <select value={typeFilter} onChange={(e) => { setTypeFilter(e.target.value); setPage(1); }} className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:outline-none focus:ring-2">
              <option value="all">All Types</option>
              <option value="deposit">Deposit</option>
              <option value="withdrawal">Withdrawal</option>
              <option value="transfer">Transfer</option>
            </select>
          </div>
        </div>

        {/* Transactions Table */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
          <div className="p-6 border-b border-slate-200 dark:border-slate-700">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
              Transaction List ({transactionsTotal.toLocaleString()})
            </h3>
          </div>

          {transactionsLoading ? (
            <div className="p-12 text-center">
              <Activity className="w-12 h-12 text-slate-400 animate-spin mx-auto mb-4" />
              <p className="text-slate-600 dark:text-slate-400">Loading transactions...</p>
            </div>
          ) : transactions.length === 0 ? (
            <div className="p-12 text-center">
              <FileText className="w-12 h-12 text-slate-400 mx-auto mb-4" />
              <p className="text-slate-600 dark:text-slate-400">No transactions found</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-50 dark:bg-slate-700/50 border-b border-slate-200 dark:border-slate-700">
                  <tr>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Transaction ID</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Reference</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Type</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Amount</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Status</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">From</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">To</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Created</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                  {transactions.map((txn) => {
                    const type = txn.payer === 'MINT_ACCOUNT' ? 'deposit'
                      : txn.payee === 'MINT_ACCOUNT' ? 'withdrawal'
                      : 'transfer';
                    return (
                      <tr key={txn.id} className="hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors">
                        <td className="px-6 py-4 font-mono text-sm text-slate-900 dark:text-white truncate max-w-[160px]">{txn.transaction_id}</td>
                        <td className="px-6 py-4 text-slate-600 dark:text-slate-400">{txn.note || '-'}</td>
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2">
                            {getTypeIcon(txn.payer, txn.payee)}
                            <span className="capitalize">{type}</span>
                          </div>
                        </td>
                        <td className="px-6 py-4 font-semibold text-slate-900 dark:text-white">
                          {txn.currency} {parseFloat(txn.amount || '0').toLocaleString()}
                        </td>
                        <td className="px-6 py-4">
                          <span className={`px-3 py-1 rounded-full text-xs font-semibold capitalize ${getStatusColor(txn.status || '')}`}>
                            {txn.status || 'Unknown'}
                          </span>
                        </td>
                        <td className="px-6 py-4 font-mono text-xs text-slate-600 dark:text-slate-400 truncate max-w-[120px]">{txn.payer || '-'}</td>
                        <td className="px-6 py-4 font-mono text-xs text-slate-600 dark:text-slate-400 truncate max-w-[120px]">{txn.payee || '-'}</td>
                        <td className="px-6 py-4 text-slate-600 dark:text-slate-400 whitespace-nowrap">
                          {new Date(txn.created_at.replace(' ', 'T')).toLocaleString()}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="mt-6 flex items-center justify-between">
            <p className="text-sm text-slate-600 dark:text-slate-400">
              Page {page} of {totalPages} — {transactionsTotal.toLocaleString()} total
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1 || transactionsLoading}
                className="px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg disabled:opacity-50 hover:bg-slate-50 dark:hover:bg-slate-700"
              >
                Previous
              </button>
              <button
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages || transactionsLoading}
                className="px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg disabled:opacity-50 hover:bg-slate-50 dark:hover:bg-slate-700"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
