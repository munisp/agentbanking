import { toast } from 'sonner';
import { exportToExcel, exportToPDF } from '@/lib/exportUtils';
import { Activity, Download, PiggyBank, Search, Users } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import apiClient from '../services/api';
import { useTenantBranding } from '../contexts/TenantBrandingContext';

interface SavingsGoal {
  id: number;
  goal_id: string;
  customer_id: string;
  tenant_id: string;
  savings_account_id: number;
  enable_auto_save: boolean;
  goal_name: string;
  target_amount: number;
  target_date: string;
  interest_rate: number;
  status: string;
  created_at: string;
  [key: string]: any;
}

interface SavingsResponse {
  message?: string;
  savings?: SavingsGoal[];
  goals?: SavingsGoal[];
  data?: SavingsGoal[];
  [key: string]: any;
}

export default function Savings() {
  const { primaryColor } = useTenantBranding();
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [savings, setSavings] = useState<SavingsGoal[]>([]);
  const [savingsLoading, setSavingsLoading] = useState(true);

  // Fetch savings accounts
  const fetchSavings = async (setLoading = true) => {
    if (setLoading) {
      setSavingsLoading(true);
    }
    try {
      const response = await apiClient.get<SavingsResponse>(`/savings/api/v1/tenant/savings`);
      const data = response.data;
      
      // Handle different response structures
      let savingsData: SavingsGoal[] = [];
      if (Array.isArray(data)) {
        savingsData = data;
      } else if (Array.isArray(data.savings)) {
        savingsData = data.savings;
      } else if (Array.isArray(data.goals)) {
        savingsData = data.goals;
      } else if (Array.isArray(data.data)) {
        savingsData = data.data;
      }
      
      setSavings(savingsData);
    } catch (error: any) {
      console.error('Error fetching savings:', error);
      toast.error((error as any)?.message || 'Something went wrong. Please try again.');
      if (setLoading) {
        setSavings([]);
      }
    } finally {
      if (setLoading) {
        setSavingsLoading(false);
      }
    }
  };

  useEffect(() => {
    fetchSavings(true);
    // Refresh every 10 seconds (silently in background)
    const interval = setInterval(() => fetchSavings(false), 10000);
    return () => clearInterval(interval);
  }, []);

  // Filter savings goals
  const filteredSavings = useMemo(() => {
    return savings.filter(goal => {
      const matchesSearch = !searchTerm || 
        goal.goal_id?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        goal.goal_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        goal.customer_id?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        goal.savings_account_id?.toString().includes(searchTerm) ||
        goal.target_amount?.toString().includes(searchTerm);
      
      const matchesStatus = statusFilter === 'all' || 
        goal.status?.toLowerCase() === statusFilter.toLowerCase();
      
      return matchesSearch && matchesStatus;
    });
  }, [savings, searchTerm, statusFilter]);

  // Calculate statistics
  const stats = useMemo(() => {
    const total = filteredSavings.length;
    const totalTargetAmount = filteredSavings.reduce((sum, goal) => {
      return sum + (goal.target_amount || 0);
    }, 0);
    const active = filteredSavings.filter(goal => 
      goal.status?.toLowerCase() === 'active' || 
      goal.status?.toLowerCase() === 'open'
    ).length;
    const inactive = filteredSavings.filter(goal => 
      goal.status?.toLowerCase() === 'inactive' || 
      goal.status?.toLowerCase() === 'closed' ||
      goal.status?.toLowerCase() === 'suspended' ||
      goal.status?.toLowerCase() === 'completed'
    ).length;
    const averageTargetAmount = total > 0 ? totalTargetAmount / total : 0;
    const autoSaveEnabled = filteredSavings.filter(goal => goal.enable_auto_save).length;
    
    return {
      total,
      totalTargetAmount,
      active,
      inactive,
      averageTargetAmount,
      autoSaveEnabled,
    };
  }, [filteredSavings]);

  // Goals by status distribution
  const statusDistribution = useMemo(() => {
    const statusMap = new Map<string, number>();
    filteredSavings.forEach(goal => {
      const status = goal.status || 'unknown';
      statusMap.set(status, (statusMap.get(status) || 0) + 1);
    });
    
    const colors = ['#3b82f6', '#8b5cf6', '#ec4899', '#10b981', '#f59e0b', '#ef4444'];
    return Array.from(statusMap.entries()).map(([name, value], index) => ({
      name: name.charAt(0).toUpperCase() + name.slice(1).replace(/_/g, ' '),
      value,
      color: colors[index % colors.length],
    }));
  }, [filteredSavings]);

  // Daily goals created (last 7 days)
  const dailyGoals = useMemo(() => {
    const goalMap = new Map<string, number>();
    filteredSavings.forEach(goal => {
      try {
        const dateStr = goal.created_at?.replace(' ', 'T') || new Date().toISOString();
        const date = new Date(dateStr).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        goalMap.set(date, (goalMap.get(date) || 0) + 1);
      } catch (e) {
        // Skip invalid dates
      }
    });
    
    return Array.from(goalMap.entries())
      .map(([date, count]) => ({ date, count }))
      .sort((a, b) => a.date.localeCompare(b.date))
      .slice(-7); // Last 7 days
  }, [filteredSavings]);

  const getStatusColor = (status: string) => {
    const statusLower = status?.toLowerCase();
    if (statusLower === 'active' || statusLower === 'open') {
      return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300';
    }
    if (statusLower === 'inactive' || statusLower === 'closed' || statusLower === 'suspended') {
      return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300';
    }
    if (statusLower === 'pending' || statusLower === 'processing') {
      return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300';
    }
    return 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300';
  };

  const handleExportExcel = () => {
    const data = filteredSavings.map(goal => ({
      'Goal ID': goal.goal_id,
      'Goal Name': goal.goal_name || 'N/A',
      'Customer ID': goal.customer_id || 'N/A',
      'Target Amount': `₦${(goal.target_amount || 0).toLocaleString()}`,
      'Target Date': goal.target_date || 'N/A',
      'Interest Rate': goal.interest_rate ? `${goal.interest_rate}%` : 'N/A',
      'Status': goal.status || 'N/A',
      'Auto Save': goal.enable_auto_save ? 'Enabled' : 'Disabled',
      'Savings Account ID': goal.savings_account_id || 'N/A',
      'Created': goal.created_at,
    }));
    exportToExcel(data, 'savings-goals');
  };

  const handleExportPDF = () => {
    const pdfData = filteredSavings.map(goal => ({
      'Goal ID': goal.goal_id || goal.id,
      'Goal Name': goal.goal_name || 'N/A',
      'Customer ID': goal.customer_id || 'N/A',
      'Target Amount': `₦${(goal.target_amount || 0).toLocaleString()}`,
      'Target Date': goal.target_date || 'N/A',
      'Interest Rate': goal.interest_rate ? `${goal.interest_rate}%` : 'N/A',
      'Status': goal.status || 'N/A',
      'Auto Save': goal.enable_auto_save ? 'Enabled' : 'Disabled',
      'Created': goal.created_at,
    }));
    exportToPDF(
      pdfData,
      ['Goal ID', 'Goal Name', 'Customer ID', 'Target Amount', 'Target Date', 'Interest Rate', 'Status', 'Auto Save', 'Created'],
      'savings-goals-report',
      'Savings Goals Report'
    );
  };

  // Get unique statuses for filters
  const uniqueStatuses = useMemo(() => {
    const statuses = new Set<string>();
    savings.forEach(goal => {
      if (goal.status) statuses.add(goal.status.toLowerCase());
    });
    return Array.from(statuses);
  }, [savings]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-purple-50 dark:from-slate-900 dark:via-slate-900 dark:to-slate-900">
      {/* Header */}
      <div className="border-b border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-sm">
        <div className="container py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
                <PiggyBank className="w-8 h-8" style={{ color: primaryColor }} />
                Customer Savings
              </h1>
              <p className="text-slate-600 dark:text-slate-400 mt-1">
                View and manage all customer savings goals
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleExportExcel}
                className="px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 flex items-center gap-2"
                disabled={savingsLoading}
              >
                <Download className="w-5 h-5" />
                Excel
              </button>
              <button
                onClick={handleExportPDF}
                className="px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 flex items-center gap-2"
                disabled={savingsLoading}
              >
                <Download className="w-5 h-5" />
                PDF
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="container py-8">
        {/* Statistics Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
            <div className="flex items-center justify-between mb-2">
              <div className="text-sm text-slate-600 dark:text-slate-400">Total Accounts</div>
              <Users className="w-5 h-5" style={{ color: primaryColor }} />
            </div>
            <div className="text-3xl font-bold text-slate-900 dark:text-white">
              {stats.total.toLocaleString()}
            </div>
            <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">
              {stats.active} active
            </div>
          </div>

          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
            <div className="text-sm text-slate-600 dark:text-slate-400 mb-2">Total Target Amount</div>
            <div className="text-3xl font-bold text-green-600 dark:text-green-400">
              ₦{(stats.totalTargetAmount / 1000).toFixed(1)}K
            </div>
            <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">
              Average: ₦{(stats.averageTargetAmount / 1000).toFixed(1)}K
            </div>
          </div>

          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
            <div className="text-sm text-slate-600 dark:text-slate-400 mb-2">Active Accounts</div>
            <div className="text-3xl font-bold text-green-600 dark:text-green-400">
              {stats.active}
            </div>
            <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">
              {stats.inactive} inactive
            </div>
          </div>

          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
            <div className="text-sm text-slate-600 dark:text-slate-400 mb-2">Auto Save Enabled</div>
            <div className="text-3xl font-bold text-blue-600 dark:text-blue-400">
              {stats.autoSaveEnabled}
            </div>
            <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">
              {stats.total - stats.autoSaveEnabled} manual
            </div>
          </div>
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          {/* Goals Created Chart */}
          {dailyGoals.length > 0 && (
            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-6">Goals Created (Last 7 Days)</h3>
              <ResponsiveContainer width="100%" height={250}>
                <AreaChart data={dailyGoals}>
                  <defs>
                    <linearGradient id="goalsGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={primaryColor} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={primaryColor} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="date" stroke="#64748b" />
                  <YAxis stroke="#64748b" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'rgba(255, 255, 255, 0.95)',
                      border: '1px solid #e2e8f0',
                      borderRadius: '8px',
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="count"
                    stroke={primaryColor}
                    strokeWidth={2}
                    fill="url(#goalsGradient)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Status Distribution */}
          {statusDistribution.length > 0 && (
            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-6">Status Distribution</h3>
              <ResponsiveContainer width="100%" height={250}>
                <BarChart data={statusDistribution}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="name" stroke="#64748b" />
                  <YAxis stroke="#64748b" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'rgba(255, 255, 255, 0.95)',
                      border: '1px solid #e2e8f0',
                      borderRadius: '8px',
                    }}
                  />
                  <Bar dataKey="value" fill={primaryColor} radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        {/* Filters and Search */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700 mb-6">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-slate-400" />
              <input
                type="text"
                placeholder="Search by goal ID, goal name, customer ID..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:outline-none focus:ring-2"
                style={{ '--tw-ring-color': primaryColor } as React.CSSProperties}
              />
            </div>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:outline-none focus:ring-2"
              style={{ '--tw-ring-color': primaryColor } as React.CSSProperties}
            >
              <option value="all">All Statuses</option>
              {uniqueStatuses.map(status => (
                <option key={status} value={status}>
                  {status.charAt(0).toUpperCase() + status.slice(1)}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Savings Accounts Table */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700">
          {savingsLoading ? (
            <div className="p-12 text-center">
              <Activity className="w-12 h-12 animate-spin mx-auto mb-4" style={{ color: primaryColor }} />
              <p className="text-slate-600 dark:text-slate-400">Loading savings accounts...</p>
            </div>
          ) : filteredSavings.length === 0 ? (
            <div className="p-12 text-center">
              <PiggyBank className="w-12 h-12 mx-auto mb-4 text-slate-400" />
              <p className="text-slate-600 dark:text-slate-400">No savings goals found</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-50 dark:bg-slate-900 border-b border-slate-200 dark:border-slate-700">
                  <tr>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Goal ID</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Goal Name</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Customer ID</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Target Amount</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Target Date</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Interest Rate</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Status</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Auto Save</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Created</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                  {filteredSavings.map((goal) => (
                    <tr key={goal.id} className="hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors">
                      <td className="px-6 py-4 font-mono text-sm text-slate-900 dark:text-white">
                        {goal.goal_id}
                      </td>
                      <td className="px-6 py-4 font-medium text-slate-900 dark:text-white">
                        {goal.goal_name || 'N/A'}
                      </td>
                      <td className="px-6 py-4 font-mono text-sm text-slate-600 dark:text-slate-400">
                        {goal.customer_id || 'N/A'}
                      </td>
                      <td className="px-6 py-4 font-semibold text-slate-900 dark:text-white">
                        ₦{(goal.target_amount || 0).toLocaleString()}
                      </td>
                      <td className="px-6 py-4 text-slate-600 dark:text-slate-400">
                        {goal.target_date ? new Date(goal.target_date).toLocaleDateString() : 'N/A'}
                      </td>
                      <td className="px-6 py-4 text-slate-600 dark:text-slate-400">
                        {goal.interest_rate ? `${goal.interest_rate}%` : 'N/A'}
                      </td>
                      <td className="px-6 py-4">
                        <span className={`px-3 py-1 rounded-full text-xs font-semibold capitalize ${getStatusColor(goal.status || '')}`}>
                          {goal.status || 'Unknown'}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`px-3 py-1 rounded-full text-xs font-semibold ${
                          goal.enable_auto_save 
                            ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
                            : 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300'
                        }`}>
                          {goal.enable_auto_save ? 'Enabled' : 'Disabled'}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-slate-600 dark:text-slate-400">
                        {goal.created_at ? new Date(goal.created_at.replace(' ', 'T')).toLocaleDateString() : 'N/A'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

