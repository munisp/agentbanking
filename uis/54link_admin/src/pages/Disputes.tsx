import { exportToExcel, exportToPDF } from '@/lib/exportUtils';
import { Activity, CheckCircle, Clock, Download, Eye, FileText, Search, Shield, X, XCircle } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import apiClient from '../services/api';
import { useTenantBranding } from '../contexts/TenantBrandingContext';

interface Dispute {
  id: string;
  dispute_id?: string;
  transaction_id?: string;
  customer_id?: string;
  amount?: string;
  currency?: string;
  status: string;
  reason?: string;
  description?: string;
  created_at: string;
  updated_at?: string;
  resolved_at?: string;
  resolved_by?: string;
  resolution?: string;
  [key: string]: any;
}

export default function Disputes() {
  const { primaryColor } = useTenantBranding();
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [disputes, setDisputes] = useState<Dispute[]>([]);
  const [disputesLoading, setDisputesLoading] = useState(true);
  const [selectedDispute, setSelectedDispute] = useState<Dispute | null>(null);
  const [showDetailsModal, setShowDetailsModal] = useState(false);
  const [disputeDetails, setDisputeDetails] = useState<Dispute | null>(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [processingIds, setProcessingIds] = useState<Set<string>>(new Set());

  const fetchDisputes = async (setLoading = true) => {
    if (setLoading) {
      setDisputesLoading(true);
    }
    try {
      const response = await apiClient.get<Dispute[]>(`/dispute/api/v1/disputes`);
      const data = response.data;
      
      // Handle different response structures
      let disputesData: Dispute[] = [];
      if (Array.isArray(data)) {
        disputesData = data;
      } else if (data && typeof data === 'object' && 'disputes' in data && Array.isArray((data as any).disputes)) {
        disputesData = (data as any).disputes;
      } else if (data && typeof data === 'object' && 'data' in data && Array.isArray((data as any).data)) {
        disputesData = (data as any).data;
      }
      
      setDisputes(disputesData);
    } catch (error) {
      console.error('Error fetching disputes:', error);
      if (setLoading) {
        setDisputes([]);
        toast.error('Failed to fetch disputes');
      }
    } finally {
      if (setLoading) {
        setDisputesLoading(false);
      }
    }
  };

  useEffect(() => {
    fetchDisputes(true);
    // Refresh every 10 seconds (silently in background)
    const interval = setInterval(() => fetchDisputes(false), 10000);
    return () => clearInterval(interval);
  }, []);

  const fetchDisputeDetails = async (disputeId: string) => {
    setDetailsLoading(true);
    try {
      const response = await apiClient.get<Dispute>(`/dispute/api/v1/disputes/${disputeId}`);
      setDisputeDetails(response.data);
    } catch (error) {
      console.error('Error fetching dispute details:', error);
      toast.error('Failed to fetch dispute details');
      setDisputeDetails(null);
    } finally {
      setDetailsLoading(false);
    }
  };

  const handleViewDispute = async (dispute: Dispute) => {
    const disputeId = dispute.dispute_id || dispute.id;
    setSelectedDispute(dispute);
    setShowDetailsModal(true);
    await fetchDisputeDetails(disputeId);
  };

  const handleResolveDispute = async (disputeId: string, resolution: 'resolved' | 'rejected') => {
    if (processingIds.has(disputeId)) return;
    
    setProcessingIds(prev => new Set(prev).add(disputeId));
    
    try {
      await apiClient.put(`/dispute/api/v1/administration/disputes/${disputeId}/resolve?resolution=${resolution}`);
      toast.success(`Dispute ${resolution === 'resolved' ? 'resolved' : 'rejected'} successfully`);
      await fetchDisputes();
      if (showDetailsModal && selectedDispute) {
        await fetchDisputeDetails(disputeId);
      }
    } catch (error: any) {
      console.error('Error resolving dispute:', error);
      const errorMessage = error?.response?.data?.message || error?.message || 'Failed to resolve dispute';
      toast.error(errorMessage);
    } finally {
      setProcessingIds(prev => {
        const newSet = new Set(prev);
        newSet.delete(disputeId);
        return newSet;
      });
    }
  };

  // Filter disputes
  const filteredDisputes = useMemo(() => {
    return disputes.filter(dispute => {
      const matchesSearch = !searchTerm || 
        dispute.id?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        dispute.dispute_id?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        dispute.transaction_id?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        dispute.customer_id?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        dispute.reason?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        dispute.description?.toLowerCase().includes(searchTerm.toLowerCase());
      
      const matchesStatus = statusFilter === 'all' || dispute.status?.toLowerCase() === statusFilter.toLowerCase();
      
      return matchesSearch && matchesStatus;
    });
  }, [disputes, searchTerm, statusFilter]);

  // Calculate statistics
  const stats = useMemo(() => {
    const total = filteredDisputes.length;
    const pending = filteredDisputes.filter(d => d.status?.toLowerCase() === 'pending' || d.status?.toLowerCase() === 'open').length;
    const resolved = filteredDisputes.filter(d => d.status?.toLowerCase() === 'resolved' || d.status?.toLowerCase() === 'closed').length;
    const rejected = filteredDisputes.filter(d => d.status?.toLowerCase() === 'rejected').length;
    const totalAmount = filteredDisputes.reduce((sum, d) => sum + parseFloat(d.amount || '0'), 0);
    
    return {
      total,
      pending,
      resolved,
      rejected,
      totalAmount,
      resolutionRate: total > 0 ? ((resolved / total) * 100).toFixed(1) : '0.0',
    };
  }, [filteredDisputes]);

  const getStatusColor = (status: string) => {
    const statusLower = status?.toLowerCase();
    if (statusLower === 'resolved' || statusLower === 'closed') {
      return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300';
    }
    if (statusLower === 'rejected') {
      return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300';
    }
    if (statusLower === 'pending' || statusLower === 'open') {
      return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300';
    }
    return 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300';
  };

  const getStatusIcon = (status: string) => {
    const statusLower = status?.toLowerCase();
    if (statusLower === 'resolved' || statusLower === 'closed') {
      return <CheckCircle className="w-4 h-4" />;
    }
    if (statusLower === 'rejected') {
      return <XCircle className="w-4 h-4" />;
    }
    if (statusLower === 'pending' || statusLower === 'open') {
      return <Clock className="w-4 h-4" />;
    }
    return null;
  };

  const handleExportExcel = () => {
    const data = filteredDisputes.map(dispute => ({
      'Dispute ID': dispute.dispute_id || dispute.id,
      'Transaction ID': dispute.transaction_id || 'N/A',
      'Customer ID': dispute.customer_id || 'N/A',
      'Amount': dispute.amount ? `${dispute.currency || 'NGN'} ${parseFloat(dispute.amount).toLocaleString()}` : 'N/A',
      'Status': dispute.status,
      'Reason': dispute.reason || 'N/A',
      'Created': new Date(dispute.created_at).toLocaleDateString(),
      'Resolved': dispute.resolved_at ? new Date(dispute.resolved_at).toLocaleDateString() : 'N/A',
    }));
    exportToExcel(data, 'disputes');
  };

  const handleExportPDF = () => {
    const data = filteredDisputes.map(dispute => ({
      'Dispute ID': dispute.dispute_id || dispute.id,
      'Transaction ID': dispute.transaction_id || 'N/A',
      'Status': dispute.status,
      'Amount': dispute.amount ? `${dispute.currency || 'NGN'} ${parseFloat(dispute.amount).toLocaleString()}` : 'N/A',
      'Created': new Date(dispute.created_at).toLocaleDateString(),
    }));
    exportToPDF(
      data,
      ['Dispute ID', 'Transaction ID', 'Status', 'Amount', 'Created'],
      'disputes-report',
      'Disputes Report'
    );
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-purple-50 dark:from-slate-900 dark:via-slate-900 dark:to-slate-900">
      {/* Header */}
      <div className="border-b border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-sm">
        <div className="container py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
                <Shield className="w-8 h-8" style={{ color: primaryColor }} />
                Disputes
              </h1>
              <p className="text-slate-600 dark:text-slate-400 mt-1">
                Manage and resolve transaction disputes
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleExportExcel}
                className="px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 flex items-center gap-2"
                disabled={disputesLoading}
              >
                <Download className="w-5 h-5" />
                Excel
              </button>
              <button
                onClick={handleExportPDF}
                className="px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 flex items-center gap-2"
                disabled={disputesLoading}
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
              <div className="text-sm text-slate-600 dark:text-slate-400">Total Disputes</div>
              <Shield className="w-5 h-5" style={{ color: primaryColor }} />
            </div>
            <div className="text-3xl font-bold text-slate-900 dark:text-white">
              {stats.total.toLocaleString()}
            </div>
            <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">
              {disputes.length} total
            </div>
          </div>

          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
            <div className="text-sm text-slate-600 dark:text-slate-400 mb-2">Pending</div>
            <div className="text-3xl font-bold text-yellow-600 dark:text-yellow-400">
              {stats.pending}
            </div>
            <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">
              Requires attention
            </div>
          </div>

          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
            <div className="text-sm text-slate-600 dark:text-slate-400 mb-2">Resolved</div>
            <div className="text-3xl font-bold text-green-600 dark:text-green-400">
              {stats.resolved}
            </div>
            <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">
              {stats.resolutionRate}% resolution rate
            </div>
          </div>

          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
            <div className="text-sm text-slate-600 dark:text-slate-400 mb-2">Total Amount</div>
            <div className="text-3xl font-bold text-slate-900 dark:text-white">
              ₦{(stats.totalAmount / 1000).toFixed(1)}K
            </div>
            <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">
              {stats.rejected} rejected
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700 mb-8">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-slate-400" />
              <input
                type="text"
                placeholder="Search disputes..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:outline-none focus:ring-2"
                style={{ '--tw-ring-color': primaryColor } as React.CSSProperties}
              />
            </div>

            {/* Status Filter */}
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:outline-none focus:ring-2"
            >
              <option value="all">All Statuses</option>
              <option value="pending">Pending</option>
              <option value="open">Open</option>
              <option value="resolved">Resolved</option>
              <option value="closed">Closed</option>
              <option value="rejected">Rejected</option>
            </select>
          </div>
        </div>

        {/* Disputes Table */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
          <div className="p-6 border-b border-slate-200 dark:border-slate-700">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
              Disputes ({filteredDisputes.length})
            </h3>
          </div>

          {disputesLoading ? (
            <div className="p-12 text-center">
              <Activity className="w-12 h-12 text-slate-400 animate-spin mx-auto mb-4" />
              <p className="text-slate-600 dark:text-slate-400">Loading disputes...</p>
            </div>
          ) : filteredDisputes.length === 0 ? (
            <div className="p-12 text-center">
              <FileText className="w-12 h-12 text-slate-400 mx-auto mb-4" />
              <p className="text-slate-600 dark:text-slate-400">No disputes found</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-50 dark:bg-slate-700/50 border-b border-slate-200 dark:border-slate-700">
                  <tr>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Dispute ID</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Transaction ID</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Customer ID</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Amount</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Reason</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Status</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Created</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                  {filteredDisputes.map((dispute) => {
                    const disputeId = dispute.dispute_id || dispute.id;
                    const isPending = dispute.status?.toLowerCase() === 'pending' || dispute.status?.toLowerCase() === 'open';
                    const isProcessing = processingIds.has(disputeId);
                    
                    return (
                      <tr key={dispute.id} className="hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors">
                        <td className="px-6 py-4 font-mono text-sm text-slate-900 dark:text-white">
                          {disputeId}
                        </td>
                        <td className="px-6 py-4 font-mono text-sm text-slate-600 dark:text-slate-400">
                          {dispute.transaction_id || 'N/A'}
                        </td>
                        <td className="px-6 py-4 font-mono text-sm text-slate-600 dark:text-slate-400">
                          {dispute.customer_id || 'N/A'}
                        </td>
                        <td className="px-6 py-4 font-semibold text-slate-900 dark:text-white">
                          {dispute.amount ? `${dispute.currency || 'NGN'} ${parseFloat(dispute.amount).toLocaleString()}` : 'N/A'}
                        </td>
                        <td className="px-6 py-4 text-slate-600 dark:text-slate-400">
                          {dispute.reason || 'N/A'}
                        </td>
                        <td className="px-6 py-4">
                          <span className={`px-3 py-1 rounded-full text-xs font-semibold capitalize flex items-center gap-1 w-fit ${getStatusColor(dispute.status || '')}`}>
                            {getStatusIcon(dispute.status || '')}
                            {dispute.status || 'Unknown'}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-slate-600 dark:text-slate-400">
                          {new Date(dispute.created_at).toLocaleDateString()}
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2">
                            <button
                              onClick={() => handleViewDispute(dispute)}
                              className="px-3 py-1.5 text-xs font-semibold border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 flex items-center gap-1"
                            >
                              <Eye className="w-3 h-3" />
                              View
                            </button>
                            {isPending && (
                              <>
                                <button
                                  onClick={() => handleResolveDispute(disputeId, 'resolved')}
                                  disabled={isProcessing}
                                  className="px-3 py-1.5 text-xs font-semibold text-white rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                                  style={{ backgroundColor: primaryColor }}
                                >
                                  {isProcessing ? (
                                    <>
                                      <Activity className="w-3 h-3 animate-spin" />
                                      Processing...
                                    </>
                                  ) : (
                                    <>
                                      <CheckCircle className="w-3 h-3" />
                                      Resolve
                                    </>
                                  )}
                                </button>
                                <button
                                  onClick={() => handleResolveDispute(disputeId, 'rejected')}
                                  disabled={isProcessing}
                                  className="px-3 py-1.5 text-xs font-semibold text-red-600 dark:text-red-400 border border-red-300 dark:border-red-700 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                                >
                                  <XCircle className="w-3 h-3" />
                                  Reject
                                </button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Dispute Details Modal */}
      {showDetailsModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700 w-full max-w-3xl max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between sticky top-0 bg-white dark:bg-slate-800 z-10">
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                Dispute Details: {selectedDispute?.dispute_id || selectedDispute?.id}
              </h3>
              <button
                onClick={() => {
                  setShowDetailsModal(false);
                  setSelectedDispute(null);
                  setDisputeDetails(null);
                }}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <div className="p-6 space-y-6">
              {detailsLoading ? (
                <div className="text-center py-12">
                  <Activity className="w-12 h-12 text-slate-400 animate-spin mx-auto mb-4" />
                  <p className="text-slate-600 dark:text-slate-400">Loading dispute details...</p>
                </div>
              ) : disputeDetails ? (
                <>
                  {/* Dispute Information */}
                  <div className="bg-slate-50 dark:bg-slate-900 rounded-lg p-6 border border-slate-200 dark:border-slate-700">
                    <h4 className="text-md font-semibold text-slate-900 dark:text-white mb-4">Dispute Information</h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="text-xs text-slate-500 dark:text-slate-400">Dispute ID</label>
                        <p className="text-sm font-medium text-slate-900 dark:text-white font-mono">{disputeDetails.dispute_id || disputeDetails.id}</p>
                      </div>
                      <div>
                        <label className="text-xs text-slate-500 dark:text-slate-400">Transaction ID</label>
                        <p className="text-sm font-medium text-slate-900 dark:text-white font-mono">{disputeDetails.transaction_id || 'N/A'}</p>
                      </div>
                      <div>
                        <label className="text-xs text-slate-500 dark:text-slate-400">Customer ID</label>
                        <p className="text-sm font-medium text-slate-900 dark:text-white font-mono">{disputeDetails.customer_id || 'N/A'}</p>
                      </div>
                      <div>
                        <label className="text-xs text-slate-500 dark:text-slate-400">Amount</label>
                        <p className="text-sm font-medium text-slate-900 dark:text-white">
                          {disputeDetails.amount ? `${disputeDetails.currency || 'NGN'} ${parseFloat(disputeDetails.amount).toLocaleString()}` : 'N/A'}
                        </p>
                      </div>
                      <div>
                        <label className="text-xs text-slate-500 dark:text-slate-400">Status</label>
                        <p className="text-sm">
                          <span className={`px-3 py-1 rounded-full text-xs font-semibold capitalize flex items-center gap-1 w-fit ${getStatusColor(disputeDetails.status || '')}`}>
                            {getStatusIcon(disputeDetails.status || '')}
                            {disputeDetails.status || 'Unknown'}
                          </span>
                        </p>
                      </div>
                      <div>
                        <label className="text-xs text-slate-500 dark:text-slate-400">Reason</label>
                        <p className="text-sm font-medium text-slate-900 dark:text-white">{disputeDetails.reason || 'N/A'}</p>
                      </div>
                      <div className="md:col-span-2">
                        <label className="text-xs text-slate-500 dark:text-slate-400">Description</label>
                        <p className="text-sm font-medium text-slate-900 dark:text-white">{disputeDetails.description || 'N/A'}</p>
                      </div>
                      <div>
                        <label className="text-xs text-slate-500 dark:text-slate-400">Created</label>
                        <p className="text-sm font-medium text-slate-900 dark:text-white">{new Date(disputeDetails.created_at).toLocaleString()}</p>
                      </div>
                      {disputeDetails.resolved_at && (
                        <div>
                          <label className="text-xs text-slate-500 dark:text-slate-400">Resolved</label>
                          <p className="text-sm font-medium text-slate-900 dark:text-white">{new Date(disputeDetails.resolved_at).toLocaleString()}</p>
                        </div>
                      )}
                      {disputeDetails.resolved_by && (
                        <div>
                          <label className="text-xs text-slate-500 dark:text-slate-400">Resolved By</label>
                          <p className="text-sm font-medium text-slate-900 dark:text-white">{disputeDetails.resolved_by}</p>
                        </div>
                      )}
                      {disputeDetails.resolution && (
                        <div className="md:col-span-2">
                          <label className="text-xs text-slate-500 dark:text-slate-400">Resolution</label>
                          <p className="text-sm font-medium text-slate-900 dark:text-white">{disputeDetails.resolution}</p>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Actions */}
                  {(disputeDetails.status?.toLowerCase() === 'pending' || disputeDetails.status?.toLowerCase() === 'open') && (
                    <div className="flex items-center gap-3 pt-4 border-t border-slate-200 dark:border-slate-700">
                      <button
                        onClick={() => handleResolveDispute(disputeDetails.dispute_id || disputeDetails.id, 'resolved')}
                        disabled={processingIds.has(disputeDetails.dispute_id || disputeDetails.id)}
                        className="flex-1 px-4 py-2 text-white rounded-lg font-semibold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                        style={{ backgroundColor: primaryColor }}
                      >
                        {processingIds.has(disputeDetails.dispute_id || disputeDetails.id) ? (
                          <>
                            <Activity className="w-4 h-4 animate-spin" />
                            Processing...
                          </>
                        ) : (
                          <>
                            <CheckCircle className="w-4 h-4" />
                            Resolve Dispute
                          </>
                        )}
                      </button>
                      <button
                        onClick={() => handleResolveDispute(disputeDetails.dispute_id || disputeDetails.id, 'rejected')}
                        disabled={processingIds.has(disputeDetails.dispute_id || disputeDetails.id)}
                        className="flex-1 px-4 py-2 text-red-600 dark:text-red-400 border border-red-300 dark:border-red-700 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                      >
                        <XCircle className="w-4 h-4" />
                        Reject Dispute
                      </button>
                    </div>
                  )}
                </>
              ) : (
                <div className="text-center py-12 text-slate-600 dark:text-slate-400">
                  Failed to load dispute details
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}



