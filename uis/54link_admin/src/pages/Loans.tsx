import { exportToExcel, exportToPDF } from '@/lib/exportUtils';
import { Activity, Calendar, CheckCircle, Clock, DollarSign, Download, Eye, FileText, Search, TrendingUp, X, XCircle } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { toast } from 'sonner';
import { useTenantBranding } from '../contexts/TenantBrandingContext';
import apiClient from '../services/api';

interface LoanApplication {
  id: string;
  tenant_id: string;
  loan_application_id: string;
  status: string;
  applicant_id: string;
  loan_amount: number;
  loan_purpose: string;
  LoanInterestRatePercent: number;
  requested_term: number;
  monthly_income: number;
  existing_debt: number;
  collateral_value: number;
  credit_score: number;
  employment_status: string;
  employment_duration: number;
  bank_statement_score: number;
  bvn_verified: boolean;
  nin_verified: boolean;
  LoanStartedAt: string | null;
  payments: any | null;
}

export default function Loans() {
  const { primaryColor } = useTenantBranding();
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [applications, setApplications] = useState<LoanApplication[]>([]);
  const [applicationsLoading, setApplicationsLoading] = useState(true);
  const [applicationsTotal, setApplicationsTotal] = useState(0);
  const [processingIds, setProcessingIds] = useState<Set<string>>(new Set());
  
  // Loan details and schedule state
  const [selectedLoan, setSelectedLoan] = useState<LoanApplication | null>(null);
  const [showLoanDetails, setShowLoanDetails] = useState(false);
  const [showRepaymentSchedule, setShowRepaymentSchedule] = useState(false);
  const [loanDetails, setLoanDetails] = useState<LoanApplication | null>(null);
  const [repaymentSchedule, setRepaymentSchedule] = useState<any[]>([]);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [scheduleLoading, setScheduleLoading] = useState(false);

  const fetchLoanApplications = async (setLoading = true) => {
    if (setLoading) {
      setApplicationsLoading(true);
    }
    try {
      const response = await apiClient.get<LoanApplication[]>(`/loan/api/v1/loans/applications/administration`);
      const data = response.data;
      const applicationsData: LoanApplication[] = Array.isArray(data) ? data : [];
      setApplications(applicationsData);
      setApplicationsTotal(applicationsData.length);
    } catch (error) {
      console.error('Error fetching loan applications:', error);
      if (setLoading) {
        setApplications([]);
        setApplicationsTotal(0);
      }
    } finally {
      if (setLoading) {
        setApplicationsLoading(false);
      }
    }
  };

  // Fetch loan applications
  useEffect(() => {
    fetchLoanApplications(true);
    // Refresh every 10 seconds (silently in background)
    const interval = setInterval(() => fetchLoanApplications(false), 10000);
    return () => clearInterval(interval);
  }, []);

  // Filter applications
  const filteredApplications = useMemo(() => {
    return applications.filter(app => {
      const matchesSearch = !searchTerm || 
        app.id?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        app.loan_application_id?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        app.applicant_id?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        app.loan_purpose?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        app.loan_amount?.toString().includes(searchTerm);
      
      const matchesStatus = statusFilter === 'all' || app.status?.toLowerCase() === statusFilter.toLowerCase();
      
      return matchesSearch && matchesStatus;
    });
  }, [applications, searchTerm, statusFilter]);

  // Calculate statistics
  const stats = useMemo(() => {
    const total = filteredApplications.length;
    const totalAmount = filteredApplications.reduce((sum, app) => sum + (app.loan_amount || 0), 0);
    const pending = filteredApplications.filter(app => app.status?.toLowerCase() === 'pending' || app.status?.toLowerCase() === 'submitted').length;
    const approved = filteredApplications.filter(app => app.status?.toLowerCase() === 'approved' || app.status?.toLowerCase() === 'active').length;
    const rejected = filteredApplications.filter(app => app.status?.toLowerCase() === 'rejected' || app.status?.toLowerCase() === 'declined').length;
    const active = filteredApplications.filter(app => app.LoanStartedAt !== null).length;
    
    return {
      total,
      totalAmount,
      pending,
      approved,
      rejected,
      active,
      approvalRate: total > 0 ? ((approved / total) * 100).toFixed(1) : '0.0',
    };
  }, [filteredApplications]);

  // Status distribution
  const statusDistribution = useMemo(() => {
    const statusMap = new Map<string, number>();
    filteredApplications.forEach(app => {
      const status = app.status || 'unknown';
      statusMap.set(status, (statusMap.get(status) || 0) + 1);
    });
    
    return Array.from(statusMap.entries()).map(([name, value]) => ({
      name: name.charAt(0).toUpperCase() + name.slice(1),
      value,
    }));
  }, [filteredApplications]);

  const getStatusColor = (status: string) => {
    const statusLower = status?.toLowerCase();
    if (statusLower === 'approved' || statusLower === 'active') {
      return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300';
    }
    if (statusLower === 'rejected' || statusLower === 'declined') {
      return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300';
    }
    if (statusLower === 'pending' || statusLower === 'submitted') {
      return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300';
    }
    return 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300';
  };

  const getStatusIcon = (status: string) => {
    const statusLower = status?.toLowerCase();
    if (statusLower === 'approved' || statusLower === 'active') {
      return <CheckCircle className="w-4 h-4" />;
    }
    if (statusLower === 'rejected' || statusLower === 'declined') {
      return <XCircle className="w-4 h-4" />;
    }
    if (statusLower === 'pending' || statusLower === 'submitted') {
      return <Clock className="w-4 h-4" />;
    }
    return null;
  };

  const handleExportExcel = () => {
    const data = filteredApplications.map(app => ({
      'Loan Application ID': app.loan_application_id,
      'Applicant ID': app.applicant_id,
      'Loan Amount': `₦${(app.loan_amount || 0).toLocaleString()}`,
      'Loan Purpose': app.loan_purpose,
      'Interest Rate': `${app.LoanInterestRatePercent}%`,
      'Requested Term': `${app.requested_term} month(s)`,
      'Monthly Income': `₦${(app.monthly_income || 0).toLocaleString()}`,
      'Credit Score': app.credit_score,
      'Employment Status': app.employment_status,
      'BVN Verified': app.bvn_verified ? 'Yes' : 'No',
      'NIN Verified': app.nin_verified ? 'Yes' : 'No',
      'Status': app.status,
    }));
    exportToExcel(data, 'loan-applications');
  };

  const handleExportPDF = () => {
    const pdfData = filteredApplications.map(app => ({
      'Loan Application ID': app.loan_application_id || app.id,
      'Applicant ID': app.applicant_id,
      'Loan Amount': `₦${(app.loan_amount || 0).toLocaleString()}`,
      'Loan Purpose': app.loan_purpose,
      'Status': app.status,
    }));
    exportToPDF(
      pdfData,
      ['Loan Application ID', 'Applicant ID', 'Loan Amount', 'Loan Purpose', 'Status'],
      'loan-applications-report',
      'Loan Applications Report'
    );
  };

  const handleApproveLoan = async (loanApplicationId: string) => {
    if (processingIds.has(loanApplicationId)) return;
    
    setProcessingIds(prev => new Set(prev).add(loanApplicationId));
    
    try {
      await apiClient.post(`/loan/api/v1/loans/applications/${loanApplicationId}/approve`);
      toast.success('Loan application approved successfully');
      await fetchLoanApplications();
    } catch (error: any) {
      console.error('Error approving loan:', error);
      const errorMessage = error?.response?.data?.message || error?.message || 'Failed to approve loan application';
      toast.error(errorMessage);
    } finally {
      setProcessingIds(prev => {
        const newSet = new Set(prev);
        newSet.delete(loanApplicationId);
        return newSet;
      });
    }
  };

  const handleRejectLoan = async (loanApplicationId: string, reason?: string) => {
    if (processingIds.has(loanApplicationId)) return;
    
    const rejectionReason = reason || prompt('Please provide a reason for rejection:');
    if (!rejectionReason) {
      toast.error('Rejection reason is required');
      return;
    }
    
    setProcessingIds(prev => new Set(prev).add(loanApplicationId));
    
    try {
      await apiClient.post(`/loan/api/v1/loans/applications/${loanApplicationId}/reject`, {
        reason: rejectionReason
      });
      toast.success('Loan application rejected successfully');
      await fetchLoanApplications();
    } catch (error: any) {
      console.error('Error rejecting loan:', error);
      const errorMessage = error?.response?.data?.message || error?.message || 'Failed to reject loan application';
      toast.error(errorMessage);
    } finally {
      setProcessingIds(prev => {
        const newSet = new Set(prev);
        newSet.delete(loanApplicationId);
        return newSet;
      });
    }
  };

  // Disburse loan
  const handleDisburseLoan = async (loanApplicationId: string) => {
    if (processingIds.has(loanApplicationId)) return;
    
    if (!confirm(`Are you sure you want to disburse loan ${loanApplicationId}?`)) {
      return;
    }
    
    setProcessingIds(prev => new Set(prev).add(loanApplicationId));
    
    try {
      await apiClient.post(`/loan/api/v1/loans/${loanApplicationId}/disburse`);
      toast.success('Loan disbursed successfully');
      await fetchLoanApplications();
    } catch (error: any) {
      console.error('Error disbursing loan:', error);
      const errorMessage = error?.response?.data?.message || error?.message || 'Failed to disburse loan';
      toast.error(errorMessage);
    } finally {
      setProcessingIds(prev => {
        const newSet = new Set(prev);
        newSet.delete(loanApplicationId);
        return newSet;
      });
    }
  };

  // Fetch loan details
  const fetchLoanDetails = async (loanApplicationId: string) => {
    setDetailsLoading(true);
    try {
      const response = await apiClient.get<LoanApplication>(`loan/api/v1/loans/applications/${loanApplicationId}`);
      setLoanDetails(response.data);
    } catch (error: any) {
      console.error('Error fetching loan details:', error);
      const errorMessage = error?.response?.data?.message || error?.message || 'Failed to fetch loan details';
      toast.error(errorMessage);
      setLoanDetails(null);
    } finally {
      setDetailsLoading(false);
    }
  };

  // Fetch repayment schedule
  const fetchRepaymentSchedule = async (loanApplicationId: string) => {
    setScheduleLoading(true);
    try {
      const response = await apiClient.get<any>(`/loan/api/v1/loans/${loanApplicationId}/schedule`);
      const data = response.data;
      
      // Handle different response structures
      let schedule: any[] = [];
      if (Array.isArray(data)) {
        schedule = data;
      } else if (data.schedule && Array.isArray(data.schedule)) {
        schedule = data.schedule;
      } else if (data.data && Array.isArray(data.data)) {
        schedule = data.data;
      } else if (data.payments && Array.isArray(data.payments)) {
        schedule = data.payments;
      }
      
      setRepaymentSchedule(schedule);
    } catch (error: any) {
      console.error('Error fetching repayment schedule:', error);
      const errorMessage = error?.response?.data?.message || error?.message || 'Failed to fetch repayment schedule';
      toast.error(errorMessage);
      setRepaymentSchedule([]);
    } finally {
      setScheduleLoading(false);
    }
  };

  // Handle view loan details
  const handleViewLoanDetails = async (loan: LoanApplication) => {
    setSelectedLoan(loan);
    setShowLoanDetails(true);
    await fetchLoanDetails(loan.loan_application_id);
  };

  // Handle view repayment schedule
  const handleViewRepaymentSchedule = async (loan: LoanApplication) => {
    setSelectedLoan(loan);
    setShowRepaymentSchedule(true);
    await fetchRepaymentSchedule(loan.loan_application_id);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-purple-50 dark:from-slate-900 dark:via-slate-900 dark:to-slate-900">
      {/* Header */}
      <div className="border-b border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-sm">
        <div className="container py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
                <TrendingUp className="w-8 h-8" style={{ color: primaryColor }} />
                Loan Applications
              </h1>
              <p className="text-slate-600 dark:text-slate-400 mt-1">
                View and manage loan applications
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleExportExcel}
                className="px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 flex items-center gap-2"
                disabled={applicationsLoading}
              >
                <Download className="w-5 h-5" />
                Excel
              </button>
              <button
                onClick={handleExportPDF}
                className="px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 flex items-center gap-2"
                disabled={applicationsLoading}
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
              <div className="text-sm text-slate-600 dark:text-slate-400">Total Applications</div>
              <TrendingUp className="w-5 h-5" style={{ color: primaryColor }} />
            </div>
            <div className="text-3xl font-bold text-slate-900 dark:text-white">
              {stats.total.toLocaleString()}
            </div>
            <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">
              {applicationsTotal} total
            </div>
          </div>

          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
            <div className="text-sm text-slate-600 dark:text-slate-400 mb-2">Total Loan Amount</div>
            <div className="text-3xl font-bold text-green-600 dark:text-green-400">
              ₦{(stats.totalAmount / 1000).toFixed(1)}K
            </div>
            <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">
              {stats.approved} approved
            </div>
          </div>

          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
            <div className="text-sm text-slate-600 dark:text-slate-400 mb-2">Approval Rate</div>
            <div className="text-3xl font-bold text-green-600 dark:text-green-400">
              {stats.approvalRate}%
            </div>
            <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">
              {stats.pending} pending
            </div>
          </div>

          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
            <div className="text-sm text-slate-600 dark:text-slate-400 mb-2">Rejected</div>
            <div className="text-3xl font-bold text-red-600 dark:text-red-400">
              {stats.rejected}
            </div>
            <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">
              {stats.pending} pending review
            </div>
          </div>
        </div>

        {/* Status Distribution Chart */}
        {statusDistribution.length > 0 && (
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700 mb-8">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-6">Application Status Distribution</h3>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={statusDistribution}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="name" stroke="#64748b" />
                <YAxis stroke="#64748b" />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '8px' }}
                  labelStyle={{ color: '#f1f5f9' }}
                />
                <Legend />
                <Bar dataKey="value" fill={primaryColor} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Filters */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700 mb-8">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Search */}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-slate-400" />
              <input
                type="text"
                placeholder="Search applications..."
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
              <option value="submitted">Submitted</option>
              <option value="approved">Approved</option>
              <option value="active">Active</option>
              <option value="rejected">Rejected</option>
              <option value="declined">Declined</option>
            </select>
          </div>
        </div>

        {/* Applications Table */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
          <div className="p-6 border-b border-slate-200 dark:border-slate-700">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
              Loan Applications ({filteredApplications.length})
            </h3>
          </div>

          {applicationsLoading ? (
            <div className="p-12 text-center">
              <Activity className="w-12 h-12 text-slate-400 animate-spin mx-auto mb-4" />
              <p className="text-slate-600 dark:text-slate-400">Loading applications...</p>
            </div>
          ) : filteredApplications.length === 0 ? (
            <div className="p-12 text-center">
              <FileText className="w-12 h-12 text-slate-400 mx-auto mb-4" />
              <p className="text-slate-600 dark:text-slate-400">No loan applications found</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-50 dark:bg-slate-700/50 border-b border-slate-200 dark:border-slate-700">
                  <tr>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Loan Application ID</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Applicant ID</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Loan Amount</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Loan Purpose</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Status</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Interest Rate</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Term</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Credit Score</th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                  {filteredApplications.map((app) => {
                    const isPending = app.status?.toLowerCase() === 'pending';
                    const isProcessing = processingIds.has(app.loan_application_id);
                    
                    return (
                      <tr key={app.id} className="hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors">
                        <td className="px-6 py-4 font-mono text-sm text-slate-900 dark:text-white">
                          {app.loan_application_id}
                        </td>
                        <td className="px-6 py-4 font-mono text-sm text-slate-600 dark:text-slate-400">
                          {app.applicant_id}
                        </td>
                        <td className="px-6 py-4 font-semibold text-slate-900 dark:text-white">
                          ₦{(app.loan_amount || 0).toLocaleString()}
                        </td>
                        <td className="px-6 py-4 text-slate-600 dark:text-slate-400">
                          {app.loan_purpose}
                        </td>
                        <td className="px-6 py-4">
                          <span className={`px-3 py-1 rounded-full text-xs font-semibold capitalize flex items-center gap-1 w-fit ${getStatusColor(app.status || '')}`}>
                            {getStatusIcon(app.status || '')}
                            {app.status || 'Unknown'}
                          </span>
                        </td>
                        <td className="px-6 py-4 text-slate-600 dark:text-slate-400">
                          {app.LoanInterestRatePercent}%
                        </td>
                        <td className="px-6 py-4 text-slate-600 dark:text-slate-400">
                          {app.requested_term} month(s)
                        </td>
                        <td className="px-6 py-4 text-slate-600 dark:text-slate-400">
                          {app.credit_score}
                        </td>
                        <td className="px-6 py-4">
                          <div className="flex items-center gap-2 flex-wrap">
                            {isPending && (
                              <>
                                <button
                                  onClick={() => handleApproveLoan(app.loan_application_id)}
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
                                      Approve
                                    </>
                                  )}
                                </button>
                                <button
                                  onClick={() => handleRejectLoan(app.loan_application_id)}
                                  disabled={isProcessing}
                                  className="px-3 py-1.5 text-xs font-semibold text-red-600 dark:text-red-400 border border-red-300 dark:border-red-700 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                                >
                                  <XCircle className="w-3 h-3" />
                                  Reject
                                </button>
                              </>
                            )}
                            {(app.status?.toLowerCase() === 'approved' || app.status?.toLowerCase() === 'active') && !app.LoanStartedAt && (
                              <button
                                onClick={() => handleDisburseLoan(app.loan_application_id)}
                                disabled={isProcessing}
                                className="px-3 py-1.5 text-xs font-semibold text-white rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                                style={{ backgroundColor: '#10b981' }}
                              >
                                {isProcessing ? (
                                  <>
                                    <Activity className="w-3 h-3 animate-spin" />
                                    Processing...
                                  </>
                                ) : (
                                  <>
                                    <DollarSign className="w-3 h-3" />
                                    Disburse
                                  </>
                                )}
                              </button>
                            )}
                            <button
                              onClick={() => handleViewLoanDetails(app)}
                              className="px-3 py-1.5 text-xs font-semibold border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 flex items-center gap-1"
                            >
                              <Eye className="w-3 h-3" />
                              Details
                            </button>
                            {app.LoanStartedAt && (
                              <button
                                onClick={() => handleViewRepaymentSchedule(app)}
                                className="px-3 py-1.5 text-xs font-semibold border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 flex items-center gap-1"
                              >
                                <Calendar className="w-3 h-3" />
                                Schedule
                              </button>
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

        {/* Pagination Info */}
        {filteredApplications.length > 0 && (
          <div className="mt-4 text-center text-sm text-slate-600 dark:text-slate-400">
            Showing {filteredApplications.length} of {applicationsTotal} applications
          </div>
        )}
      </div>

      {/* Loan Details Modal */}
      {showLoanDetails && selectedLoan && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700 w-full max-w-3xl max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between sticky top-0 bg-white dark:bg-slate-800 z-10">
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                Loan Details: {selectedLoan.loan_application_id}
              </h3>
              <button
                onClick={() => {
                  setShowLoanDetails(false);
                  setSelectedLoan(null);
                  setLoanDetails(null);
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
                  <p className="text-slate-600 dark:text-slate-400">Loading loan details...</p>
                </div>
              ) : loanDetails ? (
                <>
                  {/* Loan Information */}
                  <div className="bg-slate-50 dark:bg-slate-900 rounded-lg p-6 border border-slate-200 dark:border-slate-700">
                    <h4 className="text-md font-semibold text-slate-900 dark:text-white mb-4">Loan Information</h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="text-xs text-slate-500 dark:text-slate-400">Loan Application ID</label>
                        <p className="text-sm font-medium text-slate-900 dark:text-white font-mono">{loanDetails.loan_application_id}</p>
                      </div>
                      <div>
                        <label className="text-xs text-slate-500 dark:text-slate-400">Applicant ID</label>
                        <p className="text-sm font-medium text-slate-900 dark:text-white font-mono">{loanDetails.applicant_id}</p>
                      </div>
                      <div>
                        <label className="text-xs text-slate-500 dark:text-slate-400">Loan Amount</label>
                        <p className="text-sm font-medium text-slate-900 dark:text-white">₦{(loanDetails.loan_amount || 0).toLocaleString()}</p>
                      </div>
                      <div>
                        <label className="text-xs text-slate-500 dark:text-slate-400">Loan Purpose</label>
                        <p className="text-sm font-medium text-slate-900 dark:text-white">{loanDetails.loan_purpose}</p>
                      </div>
                      <div>
                        <label className="text-xs text-slate-500 dark:text-slate-400">Interest Rate</label>
                        <p className="text-sm font-medium text-slate-900 dark:text-white">{loanDetails.LoanInterestRatePercent}%</p>
                      </div>
                      <div>
                        <label className="text-xs text-slate-500 dark:text-slate-400">Requested Term</label>
                        <p className="text-sm font-medium text-slate-900 dark:text-white">{loanDetails.requested_term} month(s)</p>
                      </div>
                      <div>
                        <label className="text-xs text-slate-500 dark:text-slate-400">Status</label>
                        <p className="text-sm">
                          <span className={`px-3 py-1 rounded-full text-xs font-semibold capitalize flex items-center gap-1 w-fit ${getStatusColor(loanDetails.status || '')}`}>
                            {getStatusIcon(loanDetails.status || '')}
                            {loanDetails.status || 'Unknown'}
                          </span>
                        </p>
                      </div>
                      {loanDetails.LoanStartedAt && (
                        <div>
                          <label className="text-xs text-slate-500 dark:text-slate-400">Loan Started At</label>
                          <p className="text-sm font-medium text-slate-900 dark:text-white">{new Date(loanDetails.LoanStartedAt).toLocaleString()}</p>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Financial Information */}
                  <div className="bg-slate-50 dark:bg-slate-900 rounded-lg p-6 border border-slate-200 dark:border-slate-700">
                    <h4 className="text-md font-semibold text-slate-900 dark:text-white mb-4">Financial Information</h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="text-xs text-slate-500 dark:text-slate-400">Monthly Income</label>
                        <p className="text-sm font-medium text-slate-900 dark:text-white">₦{(loanDetails.monthly_income || 0).toLocaleString()}</p>
                      </div>
                      <div>
                        <label className="text-xs text-slate-500 dark:text-slate-400">Existing Debt</label>
                        <p className="text-sm font-medium text-slate-900 dark:text-white">₦{(loanDetails.existing_debt || 0).toLocaleString()}</p>
                      </div>
                      <div>
                        <label className="text-xs text-slate-500 dark:text-slate-400">Collateral Value</label>
                        <p className="text-sm font-medium text-slate-900 dark:text-white">₦{(loanDetails.collateral_value || 0).toLocaleString()}</p>
                      </div>
                      <div>
                        <label className="text-xs text-slate-500 dark:text-slate-400">Credit Score</label>
                        <p className="text-sm font-medium text-slate-900 dark:text-white">{loanDetails.credit_score}</p>
                      </div>
                    </div>
                  </div>

                  {/* Employment Information */}
                  <div className="bg-slate-50 dark:bg-slate-900 rounded-lg p-6 border border-slate-200 dark:border-slate-700">
                    <h4 className="text-md font-semibold text-slate-900 dark:text-white mb-4">Employment Information</h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="text-xs text-slate-500 dark:text-slate-400">Employment Status</label>
                        <p className="text-sm font-medium text-slate-900 dark:text-white capitalize">{loanDetails.employment_status}</p>
                      </div>
                      <div>
                        <label className="text-xs text-slate-500 dark:text-slate-400">Employment Duration</label>
                        <p className="text-sm font-medium text-slate-900 dark:text-white">{loanDetails.employment_duration} months</p>
                      </div>
                      <div>
                        <label className="text-xs text-slate-500 dark:text-slate-400">Bank Statement Score</label>
                        <p className="text-sm font-medium text-slate-900 dark:text-white">{loanDetails.bank_statement_score}</p>
                      </div>
                    </div>
                  </div>

                  {/* Verification Status */}
                  <div className="bg-slate-50 dark:bg-slate-900 rounded-lg p-6 border border-slate-200 dark:border-slate-700">
                    <h4 className="text-md font-semibold text-slate-900 dark:text-white mb-4">Verification Status</h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <div>
                        <label className="text-xs text-slate-500 dark:text-slate-400">BVN Verified</label>
                        <p className="text-sm font-medium text-slate-900 dark:text-white">
                          <span className={`px-3 py-1 rounded-full text-xs font-semibold ${
                            loanDetails.bvn_verified 
                              ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
                              : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
                          }`}>
                            {loanDetails.bvn_verified ? 'Verified' : 'Not Verified'}
                          </span>
                        </p>
                      </div>
                      <div>
                        <label className="text-xs text-slate-500 dark:text-slate-400">NIN Verified</label>
                        <p className="text-sm font-medium text-slate-900 dark:text-white">
                          <span className={`px-3 py-1 rounded-full text-xs font-semibold ${
                            loanDetails.nin_verified 
                              ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
                              : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
                          }`}>
                            {loanDetails.nin_verified ? 'Verified' : 'Not Verified'}
                          </span>
                        </p>
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                <div className="text-center py-12 text-slate-600 dark:text-slate-400">
                  Failed to load loan details
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Repayment Schedule Modal */}
      {showRepaymentSchedule && selectedLoan && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700 w-full max-w-4xl max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between sticky top-0 bg-white dark:bg-slate-800 z-10">
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                Repayment Schedule: {selectedLoan.loan_application_id}
              </h3>
              <button
                onClick={() => {
                  setShowRepaymentSchedule(false);
                  setSelectedLoan(null);
                  setRepaymentSchedule([]);
                }}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <div className="p-6">
              {scheduleLoading ? (
                <div className="text-center py-12">
                  <Activity className="w-12 h-12 text-slate-400 animate-spin mx-auto mb-4" />
                  <p className="text-slate-600 dark:text-slate-400">Loading repayment schedule...</p>
                </div>
              ) : repaymentSchedule.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-slate-50 dark:bg-slate-700/50 border-b border-slate-200 dark:border-slate-700">
                      <tr>
                        <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Payment #</th>
                        <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Due Date</th>
                        <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Principal</th>
                        <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Interest</th>
                        <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Total Amount</th>
                        <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Status</th>
                        <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Paid Date</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                      {repaymentSchedule.map((payment: any, index: number) => (
                        <tr key={payment.id || index} className="hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors">
                          <td className="px-6 py-4 font-semibold text-slate-900 dark:text-white">
                            {payment.payment_number || payment.installment_number || index + 1}
                          </td>
                          <td className="px-6 py-4 text-slate-600 dark:text-slate-400">
                            {payment.due_date || payment.dueDate 
                              ? new Date(payment.due_date || payment.dueDate).toLocaleDateString()
                              : 'N/A'}
                          </td>
                          <td className="px-6 py-4 font-semibold text-slate-900 dark:text-white">
                            ₦{(parseFloat(payment.principal || payment.principal_amount || '0')).toLocaleString()}
                          </td>
                          <td className="px-6 py-4 text-slate-600 dark:text-slate-400">
                            ₦{(parseFloat(payment.interest || payment.interest_amount || '0')).toLocaleString()}
                          </td>
                          <td className="px-6 py-4 font-semibold text-green-600 dark:text-green-400">
                            ₦{(parseFloat(payment.total_amount || payment.amount || payment.totalAmount || '0')).toLocaleString()}
                          </td>
                          <td className="px-6 py-4">
                            <span className={`px-3 py-1 rounded-full text-xs font-semibold capitalize ${
                              (payment.status || '').toLowerCase() === 'paid' || (payment.status || '').toLowerCase() === 'completed'
                                ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
                                : (payment.status || '').toLowerCase() === 'overdue'
                                ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
                                : 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300'
                            }`}>
                              {payment.status || 'Pending'}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-slate-600 dark:text-slate-400">
                            {payment.paid_date || payment.paidDate 
                              ? new Date(payment.paid_date || payment.paidDate).toLocaleDateString()
                              : '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-center py-12 text-slate-600 dark:text-slate-400">
                  No repayment schedule available
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

