import { Activity, CheckCircle, Clock, CreditCard, Download, Eye, RefreshCw, Search, XCircle } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import { useTenantBranding } from '../contexts/TenantBrandingContext';
import apiClient from '../services/api';

interface BNPLApplication {
  id: number;
  application_id: string;
  tenant_id: string;
  applicant_id: string;
  merchant_id: string;
  purchase_amount: number;
  installment_count: number;
  installment_amount: number;
  interest_rate: number;
  product_description: string;
  status: string;
  credit_score: number;
  bvn_verified: boolean;
  created_at: string;
  updated_at: string;
}

export default function BNPL() {
  const { primaryColor } = useTenantBranding();
  const [applications, setApplications] = useState<BNPLApplication[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [processingIds, setProcessingIds] = useState<Set<string>>(new Set());
  const [selectedApp, setSelectedApp] = useState<BNPLApplication | null>(null);

  const fetchApplications = async () => {
    setLoading(true);
    try {
      const res = await apiClient.get('/bnpl/v1/applications');
      const data = res.data as { items?: BNPLApplication[] };
      setApplications(data.items ?? []);
    } catch {
      toast.error('Failed to load BNPL applications');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchApplications(); }, []);

  const handleApprove = async (app: BNPLApplication) => {
    setProcessingIds((s) => new Set(s).add(app.application_id));
    try {
      await apiClient.post(`/bnpl/v1/applications/${app.application_id}/approve`);
      toast.success(`Application ${app.application_id} approved`);
      fetchApplications();
    } catch {
      toast.error('Failed to approve application');
    } finally {
      setProcessingIds((s) => { const next = new Set(s); next.delete(app.application_id); return next; });
    }
  };

  const handleDecline = async (app: BNPLApplication) => {
    setProcessingIds((s) => new Set(s).add(app.application_id));
    try {
      await apiClient.post(`/bnpl/v1/applications/${app.application_id}/decline`);
      toast.success(`Application ${app.application_id} declined`);
      fetchApplications();
    } catch {
      toast.error('Failed to decline application');
    } finally {
      setProcessingIds((s) => { const next = new Set(s); next.delete(app.application_id); return next; });
    }
  };

  const filtered = useMemo(() => {
    return applications.filter((a) => {
      const matchesSearch =
        a.application_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        a.applicant_id.toLowerCase().includes(searchTerm.toLowerCase()) ||
        (a.merchant_id ?? '').toLowerCase().includes(searchTerm.toLowerCase()) ||
        (a.product_description ?? '').toLowerCase().includes(searchTerm.toLowerCase());
      const matchesStatus = statusFilter === 'all' || a.status === statusFilter;
      return matchesSearch && matchesStatus;
    });
  }, [applications, searchTerm, statusFilter]);

  const stats = useMemo(() => ({
    total: applications.length,
    pending: applications.filter((a) => a.status === 'pending').length,
    approved: applications.filter((a) => a.status === 'approved').length,
    declined: applications.filter((a) => a.status === 'declined').length,
    totalValue: applications.reduce((s, a) => s + a.purchase_amount, 0),
  }), [applications]);

  const fmt = (n: number) => `₦${n.toLocaleString('en-NG', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  const fmtDate = (d: string) => new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

  const statusBadge = (status: string) => {
    const map: Record<string, string> = {
      pending: 'bg-yellow-100 text-yellow-800',
      approved: 'bg-green-100 text-green-800',
      declined: 'bg-red-100 text-red-800',
      active: 'bg-blue-100 text-blue-800',
      completed: 'bg-gray-100 text-gray-800',
    };
    return (
      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${map[status] ?? 'bg-gray-100 text-gray-700'}`}>
        {status.toUpperCase()}
      </span>
    );
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <CreditCard className="w-7 h-7" style={{ color: primaryColor }} />
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Buy Now Pay Later</h1>
            <p className="text-sm text-gray-500">Manage BNPL applications across all tenants</p>
          </div>
        </div>
        <button
          onClick={fetchApplications}
          className="flex items-center space-x-2 px-4 py-2 rounded-lg border border-gray-200 hover:bg-gray-50 text-sm text-gray-600"
        >
          <RefreshCw className="w-4 h-4" />
          <span>Refresh</span>
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        {[
          { label: 'Total Applications', value: stats.total, icon: Activity, color: 'text-blue-600' },
          { label: 'Pending Review', value: stats.pending, icon: Clock, color: 'text-yellow-600' },
          { label: 'Approved', value: stats.approved, icon: CheckCircle, color: 'text-green-600' },
          { label: 'Declined', value: stats.declined, icon: XCircle, color: 'text-red-600' },
          { label: 'Total Value', value: fmt(stats.totalValue), icon: Download, color: 'text-violet-600' },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-100 p-4 shadow-sm">
            <div className="flex items-center space-x-2 mb-1">
              <Icon className={`w-4 h-4 ${color}`} />
              <p className="text-xs text-gray-500">{label}</p>
            </div>
            <p className={`text-xl font-bold ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by application ID, applicant, merchant, product..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-violet-500 focus:border-transparent"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-violet-500 bg-white"
        >
          {['all', 'pending', 'approved', 'declined', 'active', 'completed'].map((s) => (
            <option key={s} value={s}>{s === 'all' ? 'All Statuses' : s.charAt(0).toUpperCase() + s.slice(1)}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-100 shadow-sm overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center h-40">
            <div className="animate-spin h-8 w-8 border-4 border-violet-500 border-t-transparent rounded-full" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-40 text-gray-400">
            <CreditCard className="w-10 h-10 mb-2 opacity-40" />
            <p className="text-sm">No BNPL applications found</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-100">
                <tr>
                  {['Application ID', 'Applicant', 'Product', 'Amount', 'Instalments', 'Rate', 'BVN', 'Status', 'Date', 'Actions'].map((h) => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wide whitespace-nowrap">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {filtered.map((app) => (
                  <tr key={app.application_id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 font-mono text-xs text-gray-600 whitespace-nowrap">{app.application_id}</td>
                    <td className="px-4 py-3 text-gray-700 text-xs whitespace-nowrap">{app.applicant_id}</td>
                    <td className="px-4 py-3 text-gray-600 max-w-[140px] truncate">{app.product_description || '—'}</td>
                    <td className="px-4 py-3 font-semibold text-gray-900 whitespace-nowrap">{fmt(app.purchase_amount)}</td>
                    <td className="px-4 py-3 text-center text-gray-700">{app.installment_count}</td>
                    <td className="px-4 py-3 text-gray-600 whitespace-nowrap">{app.interest_rate}%</td>
                    <td className="px-4 py-3">
                      {app.bvn_verified
                        ? <span className="text-green-600 font-medium text-xs">✓ Yes</span>
                        : <span className="text-gray-400 text-xs">No</span>}
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap">{statusBadge(app.status)}</td>
                    <td className="px-4 py-3 text-gray-500 text-xs whitespace-nowrap">{fmtDate(app.created_at)}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center space-x-1">
                        <button
                          onClick={() => setSelectedApp(app)}
                          className="p-1.5 rounded hover:bg-gray-100 text-gray-500 hover:text-gray-700"
                          title="View details"
                        >
                          <Eye className="w-3.5 h-3.5" />
                        </button>
                        {app.status === 'pending' && (
                          <>
                            <button
                              onClick={() => handleApprove(app)}
                              disabled={processingIds.has(app.application_id)}
                              className="px-2 py-1 rounded text-xs bg-green-50 text-green-700 hover:bg-green-100 disabled:opacity-50 font-medium"
                            >
                              Approve
                            </button>
                            <button
                              onClick={() => handleDecline(app)}
                              disabled={processingIds.has(app.application_id)}
                              className="px-2 py-1 rounded text-xs bg-red-50 text-red-700 hover:bg-red-100 disabled:opacity-50 font-medium"
                            >
                              Decline
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Detail modal */}
      {selectedApp && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => setSelectedApp(null)}>
          <div className="bg-white rounded-2xl shadow-xl max-w-lg w-full p-6 space-y-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-gray-900">BNPL Application Details</h2>
              <button onClick={() => setSelectedApp(null)} className="text-gray-400 hover:text-gray-600 text-xl leading-none">×</button>
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              {[
                ['Application ID', selectedApp.application_id],
                ['Tenant', selectedApp.tenant_id],
                ['Applicant', selectedApp.applicant_id],
                ['Merchant', selectedApp.merchant_id || '—'],
                ['Product', selectedApp.product_description || '—'],
                ['Purchase Amount', fmt(selectedApp.purchase_amount)],
                ['Instalments', String(selectedApp.installment_count)],
                ['Per Instalment', fmt(selectedApp.installment_amount)],
                ['Interest Rate', `${selectedApp.interest_rate}%`],
                ['Credit Score', selectedApp.credit_score ? String(selectedApp.credit_score) : '—'],
                ['BVN Verified', selectedApp.bvn_verified ? 'Yes' : 'No'],
                ['Status', selectedApp.status.toUpperCase()],
                ['Applied', fmtDate(selectedApp.created_at)],
                ['Updated', fmtDate(selectedApp.updated_at)],
              ].map(([label, val]) => (
                <div key={label} className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-400 mb-0.5">{label}</p>
                  <p className="font-medium text-gray-900 break-all">{val}</p>
                </div>
              ))}
            </div>
            {selectedApp.status === 'pending' && (
              <div className="flex space-x-3 pt-2">
                <button
                  onClick={() => { handleApprove(selectedApp); setSelectedApp(null); }}
                  className="flex-1 py-2 rounded-lg bg-green-600 hover:bg-green-700 text-white text-sm font-medium"
                >
                  Approve
                </button>
                <button
                  onClick={() => { handleDecline(selectedApp); setSelectedApp(null); }}
                  className="flex-1 py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white text-sm font-medium"
                >
                  Decline
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
