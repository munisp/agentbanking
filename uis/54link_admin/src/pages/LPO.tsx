import { exportToExcel } from '@/lib/exportUtils';
import { Activity, CheckCircle, Clock, Download, FileText, Search, XCircle, DollarSign, Users, Plus, Eye, X } from 'lucide-react';
import { useEffect, useMemo, useState } from 'react';
import { toast } from 'sonner';
import apiClient from '../services/api';
import { useTenantBranding } from '../contexts/TenantBrandingContext';

interface LPO {
  id: string;
  lpo_id?: string;
  supplier_id?: string;
  supplier_name?: string;
  amount: string;
  currency: string;
  status: string;
  created_at: string;
  updated_at: string;
  approved_at?: string;
  approved_by?: string;
  verified_at?: string;
  verified_by?: string;
  is_authentic?: boolean;
  disbursed_at?: string;
  disbursed_to?: string;
  [key: string]: any;
}

interface LPORepayment {
  id: string;
  lpo_id: string;
  amount: string;
  currency: string;
  status: string;
  payment_date?: string;
  created_at: string;
  [key: string]: any;
}

interface Supplier {
  id: number | string;
  supplier_id: string;
  business_name: string;
  registration_number: string;
  total_lpos_financed: number;
  total_amount_financed: number;
  successful_repayments: number;
  defaulted_repayments: number;
  credit_score: number;
  created_at: string;
  updated_at: string;
  contact_email?: string;
  contact_phone?: string;
  [key: string]: any;
}

interface SupplierProfile extends Supplier {
  address?: string;
  tax_id?: string;
  bank_account?: string;
  bank_name?: string;
  [key: string]: any;
}

interface LPOsResponse {
  lpos: LPO[];
  total: number;
  [key: string]: any;
}

interface SuppliersResponse {
  suppliers: Supplier[];
  total: number;
  [key: string]: any;
}

export default function LPO() {
  const { primaryColor } = useTenantBranding();
  const [activeTab, setActiveTab] = useState<'lpos' | 'repayments' | 'suppliers'>('lpos');
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [selectedLPOId, setSelectedLPOId] = useState<string | null>(null);
  
  // LPOs state
  const [lpos, setLpos] = useState<LPO[]>([]);
  const [lposLoading, setLposLoading] = useState(true);
  
  // Repayments state
  const [repayments, setRepayments] = useState<LPORepayment[]>([]);
  const [repaymentsLoading, setRepaymentsLoading] = useState(true);
  
  // Suppliers state
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [suppliersLoading, setSuppliersLoading] = useState(true);
  
  // Processing state
  const [processingIds, setProcessingIds] = useState<Set<string>>(new Set());
  
  // Supplier registration modal
  const [showRegisterModal, setShowRegisterModal] = useState(false);
  const [registerForm, setRegisterForm] = useState({
    supplier_id: '',
    business_name: '',
    registration_number: '',
  });
  const [registering, setRegistering] = useState(false);
  
  // Supplier profile/view state
  const [selectedSupplierId, setSelectedSupplierId] = useState<string | null>(null);
  const [supplierProfile, setSupplierProfile] = useState<SupplierProfile | null>(null);
  const [supplierLPOs, setSupplierLPOs] = useState<LPO[]>([]);
  const [showSupplierDetails, setShowSupplierDetails] = useState(false);
  const [supplierDetailsLoading, setSupplierDetailsLoading] = useState(false);

  // LPO details and modals state
  // eslint-disable-next-line @typescript-eslint/no-unused-vars, @typescript-eslint/ban-ts-comment
  // @ts-ignore - Kept for future use
  const [selectedLPO, setSelectedLPO] = useState<LPO | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars, @typescript-eslint/ban-ts-comment
  // @ts-ignore - Kept for future use
  const [showVerifyModal, setShowVerifyModal] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars, @typescript-eslint/ban-ts-comment
  // @ts-ignore - Kept for future use
  const [showDisburseModal, setShowDisburseModal] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars, @typescript-eslint/ban-ts-comment
  // @ts-ignore - Kept for future use
  const [showLPODetails, setShowLPODetails] = useState(false);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars, @typescript-eslint/ban-ts-comment
  // @ts-ignore - Kept for future use
  const [lpoDetails, setLpoDetails] = useState<LPO | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-unused-vars, @typescript-eslint/ban-ts-comment
  // @ts-ignore - Kept for future use
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [verifyForm, setVerifyForm] = useState({
    verified_by: 'Admin User',
    is_authentic: true,
  });
  const [disburseForm, setDisburseForm] = useState({
    disbursed_to: '',
  });

  const fetchLPOs = async (setLoading = true) => {
    if (setLoading) {
      setLposLoading(true);
    }
    try {
      const response = await apiClient.get<LPOsResponse>(`/lpo/api/v1/lpo/administration`);
      const data = response.data;
      let lposData: LPO[] = [];
      if (Array.isArray(data)) {
        lposData = data;
      } else if (Array.isArray(data.lpos)) {
        lposData = data.lpos;
      } else if (data.data && Array.isArray(data.data)) {
        lposData = data.data;
      }
      setLpos(lposData);
    } catch (error) {
      console.error('Error fetching LPOs:', error);
      toast.error(error instanceof Error ? error.message : 'Something went wrong. Please try again.');
      if (setLoading) {
        setLpos([]);
      }
    } finally {
      if (setLoading) {
        setLposLoading(false);
      }
    }
  };

  // Fetch LPOs
  useEffect(() => {
    if (activeTab === 'lpos' || activeTab === 'repayments') {
      // Load LPOs for both LPOs tab and Repayments tab (needed for selector)
      fetchLPOs(true);
      if (activeTab === 'lpos') {
        // Refresh every 10 seconds (silently in background)
        const interval = setInterval(() => fetchLPOs(false), 10000);
        return () => clearInterval(interval);
      }
    }
  }, [activeTab]);

  const fetchRepayments = async (setLoading = true) => {
    if (!selectedLPOId) {
      setRepayments([]);
      if (setLoading) {
        setRepaymentsLoading(false);
      }
      return;
    }

    if (setLoading) {
      setRepaymentsLoading(true);
    }
    try {
      const response = await apiClient.get<LPORepayment[] | { repayments: LPORepayment[] }>(`/lpo/api/v1/lpo/${selectedLPOId}/repayments`);
      const data = response.data;
      
      let repaymentsData: LPORepayment[] = [];
      if (Array.isArray(data)) {
        repaymentsData = data;
      } else if (data && typeof data === 'object' && 'repayments' in data && Array.isArray(data.repayments)) {
        repaymentsData = data.repayments;
      } else if (data && typeof data === 'object' && 'data' in data && Array.isArray((data as any).data)) {
        repaymentsData = (data as any).data;
      }
      
      setRepayments(repaymentsData);
    } catch (error) {
      console.error('Error fetching repayments:', error);
      if (setLoading) {
        setRepayments([]);
        toast.error('Failed to fetch repayments');
      }
    } finally {
      if (setLoading) {
        setRepaymentsLoading(false);
      }
    }
  };

  // Fetch repayments for selected LPO
  useEffect(() => {
    if (activeTab === 'repayments' && selectedLPOId) {
      fetchRepayments(true);
      // Refresh every 10 seconds (silently in background)
      const interval = setInterval(() => fetchRepayments(false), 10000);
      return () => clearInterval(interval);
    } else if (activeTab === 'repayments' && !selectedLPOId) {
      setRepayments([]);
      setRepaymentsLoading(false);
    }
  }, [activeTab, selectedLPOId]);

  const fetchSuppliers = async (setLoading = true) => {
    if (setLoading) {
      setSuppliersLoading(true);
    }
    try {
      const response = await apiClient.get<SuppliersResponse>(`/lpo/api/v1/suppliers`);
      const data = response.data;
      
      let suppliersData: Supplier[] = [];
      if (Array.isArray(data)) {
        suppliersData = data;
      } else if (data && typeof data === 'object' && 'suppliers' in data && Array.isArray(data.suppliers)) {
        suppliersData = data.suppliers;
      } else if (data && typeof data === 'object' && 'data' in data && Array.isArray((data as any).data)) {
        suppliersData = (data as any).data;
      }
      
      setSuppliers(suppliersData);
    } catch (error) {
      console.error('Error fetching suppliers:', error);
      toast.error(error instanceof Error ? error.message : 'Something went wrong. Please try again.');
      if (setLoading) {
        setSuppliers([]);
      }
    } finally {
      if (setLoading) {
        setSuppliersLoading(false);
      }
    }
  };

  // Fetch suppliers
  useEffect(() => {
    if (activeTab === 'suppliers') {
      fetchSuppliers(true);
      // Refresh every 10 seconds (silently in background)
      const interval = setInterval(() => fetchSuppliers(false), 10000);
      return () => clearInterval(interval);
    }
  }, [activeTab]);

  const fetchSupplierProfile = async (supplierId: string) => {
    setSupplierDetailsLoading(true);
    try {
      const response = await apiClient.get<SupplierProfile>(`/lpo/api/v1/lpo/supplier/${supplierId}/profile`);
      setSupplierProfile(response.data);
    } catch (error) {
      console.error('Error fetching supplier profile:', error);
      toast.error('Failed to fetch supplier profile');
      setSupplierProfile(null);
    } finally {
      setSupplierDetailsLoading(false);
    }
  };

  const fetchSupplierLPOs = async (supplierId: string) => {
    try {
      const response = await apiClient.get<LPO[] | { lpos: LPO[] }>(`/lpo/api/v1/lpo/supplier/${supplierId}`);
      const data = response.data;
      
      let lposData: LPO[] = [];
      if (Array.isArray(data)) {
        lposData = data;
      } else if (data && typeof data === 'object' && 'lpos' in data && Array.isArray((data as any).lpos)) {
        lposData = (data as any).lpos;
      } else if (data && typeof data === 'object' && 'data' in data && Array.isArray((data as any).data)) {
        lposData = (data as any).data;
      }
      
      setSupplierLPOs(lposData);
    } catch (error) {
      console.error('Error fetching supplier LPOs:', error);
      toast.error('Failed to fetch supplier LPOs');
      setSupplierLPOs([]);
    }
  };

  const handleViewSupplier = async (supplierId: string) => {
    setSelectedSupplierId(supplierId);
    setShowSupplierDetails(true);
    await Promise.all([
      fetchSupplierProfile(supplierId),
      fetchSupplierLPOs(supplierId)
    ]);
  };

  const handleRegisterSupplier = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!registerForm.supplier_id || !registerForm.business_name || !registerForm.registration_number) {
      toast.error('Please fill in all required fields');
      return;
    }

    setRegistering(true);
    try {
      const params = new URLSearchParams({
        supplier_id: registerForm.supplier_id,
        business_name: registerForm.business_name,
        registration_number: registerForm.registration_number,
      });
      await apiClient.post(`/lpo/api/v1/lpo/supplier/register?${params.toString()}`);
      toast.success('Supplier registered successfully');
      setShowRegisterModal(false);
      setRegisterForm({ supplier_id: '', business_name: '', registration_number: '' });
      await fetchSuppliers();
    } catch (error: any) {
      console.error('Error registering supplier:', error);
      const errorMessage = error?.response?.data?.message || error?.message || 'Failed to register supplier';
      toast.error(errorMessage);
    } finally {
      setRegistering(false);
    }
  };

  // Filter LPOs
  const filteredLPOs = useMemo(() => {
    return lpos.filter(lpo => {
      const matchesSearch = !searchTerm || 
        lpo.id?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        lpo.lpo_id?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        lpo.supplier_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        lpo.amount?.includes(searchTerm);
      
      const matchesStatus = statusFilter === 'all' || lpo.status?.toLowerCase() === statusFilter.toLowerCase();
      
      return matchesSearch && matchesStatus;
    });
  }, [lpos, searchTerm, statusFilter]);

  // Filter suppliers
  const filteredSuppliers = useMemo(() => {
    return suppliers.filter(supplier => {
      const matchesSearch = !searchTerm || 
        String(supplier.id || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
        supplier.supplier_id?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        supplier.business_name?.toLowerCase().includes(searchTerm.toLowerCase()) ||
        supplier.registration_number?.toLowerCase().includes(searchTerm.toLowerCase());
      
      return matchesSearch;
    });
  }, [suppliers, searchTerm]);

  // Calculate LPO statistics
  const lpoStats = useMemo(() => {
    const total = filteredLPOs.length;
    const totalAmount = filteredLPOs.reduce((sum, lpo) => sum + parseFloat(lpo.amount || '0'), 0);
    const pending = filteredLPOs.filter(lpo => lpo.status?.toLowerCase() === 'pending').length;
    const approved = filteredLPOs.filter(lpo => lpo.status?.toLowerCase() === 'approved').length;
    const rejected = filteredLPOs.filter(lpo => lpo.status?.toLowerCase() === 'rejected').length;
    
    return { total, totalAmount, pending, approved, rejected };
  }, [filteredLPOs]);

  const getStatusColor = (status: string) => {
    const statusLower = status?.toLowerCase();
    if (statusLower === 'approved') {
      return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300';
    }
    if (statusLower === 'rejected') {
      return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300';
    }
    if (statusLower === 'pending') {
      return 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300';
    }
    return 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300';
  };

  const getStatusIcon = (status: string) => {
    const statusLower = status?.toLowerCase();
    if (statusLower === 'approved') {
      return <CheckCircle className="w-4 h-4" />;
    }
    if (statusLower === 'rejected') {
      return <XCircle className="w-4 h-4" />;
    }
    if (statusLower === 'pending') {
      return <Clock className="w-4 h-4" />;
    }
    return null;
  };

  // Verify LPO
  // eslint-disable-next-line @typescript-eslint/no-unused-vars, @typescript-eslint/ban-ts-comment
  // @ts-ignore - Kept for future use
  const handleVerifyLPO = async (lpoId: string) => {
    if (processingIds.has(lpoId)) return;
    
    setProcessingIds(prev => new Set(prev).add(lpoId));
    
    try {
      await apiClient.post(`/lpo/api/v1/lpo/${lpoId}/verify`, {
        lpo_id: lpoId,
        verified_by: verifyForm.verified_by,
        is_authentic: verifyForm.is_authentic
      });
      toast.success('LPO verified successfully');
      setShowVerifyModal(false);
      setVerifyForm({ verified_by: 'Admin User', is_authentic: true });
      await fetchLPOs();
    } catch (error: any) {
      console.error('Error verifying LPO:', error);
      const errorMessage = error?.response?.data?.message || error?.message || 'Failed to verify LPO';
      toast.error(errorMessage);
    } finally {
      setProcessingIds(prev => {
        const newSet = new Set(prev);
        newSet.delete(lpoId);
        return newSet;
      });
    }
  };

  // Approve LPO (only for verified LPOs)
  const handleApproveLPO = async (lpoId: string) => {
    if (processingIds.has(lpoId)) return;
    
    setProcessingIds(prev => new Set(prev).add(lpoId));
    
    try {
      await apiClient.post(`/lpo/api/v1/lpo/${lpoId}/approve`, {
        lpo_id: lpoId,
        approved_by: 'Admin User'
      });
      toast.success('LPO approved successfully');
      await fetchLPOs();
    } catch (error: any) {
      console.error('Error approving LPO:', error);
      const errorMessage = error?.response?.data?.message || error?.message || 'Failed to approve LPO';
      toast.error(errorMessage);
    } finally {
      setProcessingIds(prev => {
        const newSet = new Set(prev);
        newSet.delete(lpoId);
        return newSet;
      });
    }
  };

  // Disburse LPO (only for approved LPOs)
  // eslint-disable-next-line @typescript-eslint/no-unused-vars, @typescript-eslint/ban-ts-comment
  // @ts-ignore - Kept for future use
  const handleDisburseLPO = async (lpoId: string) => {
    if (processingIds.has(lpoId)) return;
    
    if (!disburseForm.disbursed_to.trim()) {
      toast.error('Please provide a disbursement recipient');
      return;
    }
    
    setProcessingIds(prev => new Set(prev).add(lpoId));
    
    try {
      await apiClient.post(`/api/v1/lpo/${lpoId}/disburse`, {
        lpo_id: lpoId,
        disbursed_to: disburseForm.disbursed_to
      });
      toast.success('LPO disbursed successfully');
      setShowDisburseModal(false);
      setDisburseForm({ disbursed_to: '' });
      await fetchLPOs();
    } catch (error: any) {
      console.error('Error disbursing LPO:', error);
      const errorMessage = error?.response?.data?.message || error?.message || 'Failed to disburse LPO';
      toast.error(errorMessage);
    } finally {
      setProcessingIds(prev => {
        const newSet = new Set(prev);
        newSet.delete(lpoId);
        return newSet;
      });
    }
  };

  // Fetch LPO details
  const fetchLPODetails = async (lpoId: string) => {
    setDetailsLoading(true);
    try {
      const response = await apiClient.get<LPO>(`/api/v1/lpo/${lpoId}`);
      setLpoDetails(response.data);
    } catch (error: any) {
      console.error('Error fetching LPO details:', error);
      const errorMessage = error?.response?.data?.message || error?.message || 'Failed to fetch LPO details';
      toast.error(errorMessage);
      setLpoDetails(null);
    } finally {
      setDetailsLoading(false);
    }
  };

  // Handle view LPO details
  // eslint-disable-next-line @typescript-eslint/no-unused-vars, @typescript-eslint/ban-ts-comment
  // @ts-ignore - Kept for future use
  const handleViewLPODetails = async (lpo: LPO) => {
    setSelectedLPO(lpo);
    setShowLPODetails(true);
    await fetchLPODetails(lpo.lpo_id || lpo.id);
  };

  const handleRejectLPO = async (lpoId: string, reason?: string) => {
    if (processingIds.has(lpoId)) return;
    
    const rejectionReason = reason || prompt('Please provide a reason for rejection:');
    if (!rejectionReason) {
      toast.error('Rejection reason is required');
      return;
    }
    
    setProcessingIds(prev => new Set(prev).add(lpoId));
    
    try {
      await apiClient.post(`/lpo/api/v1/lpo/${lpoId}/reject`, {
        lpo_id: lpoId,
        rejected_by: 'Admin User',
        reason: rejectionReason
      });
      toast.success('LPO rejected successfully');
      await fetchLPOs();
    } catch (error: any) {
      console.error('Error rejecting LPO:', error);
      const errorMessage = error?.response?.data?.message || error?.message || 'Failed to reject LPO';
      toast.error(errorMessage);
    } finally {
      setProcessingIds(prev => {
        const newSet = new Set(prev);
        newSet.delete(lpoId);
        return newSet;
      });
    }
  };

  const handleExportExcel = () => {
    let data: any[] = [];
    if (activeTab === 'lpos') {
      data = filteredLPOs.map(lpo => ({
        'LPO ID': lpo.lpo_id || lpo.id,
        'Supplier': lpo.supplier_name || 'N/A',
        'Amount': `${lpo.currency} ${parseFloat(lpo.amount || '0').toLocaleString()}`,
        'Status': lpo.status,
        'Created': new Date(lpo.created_at).toLocaleDateString(),
      }));
      exportToExcel(data, 'lpos');
    } else if (activeTab === 'suppliers') {
      data = filteredSuppliers.map(supplier => ({
        'Supplier ID': supplier.supplier_id,
        'Business Name': supplier.business_name,
        'Registration Number': supplier.registration_number,
        'Total LPOs Financed': supplier.total_lpos_financed || 0,
        'Total Amount Financed': `₦${(supplier.total_amount_financed || 0).toLocaleString()}`,
        'Successful Repayments': supplier.successful_repayments || 0,
        'Defaulted Repayments': supplier.defaulted_repayments || 0,
        'Credit Score': supplier.credit_score || 0,
        'Created': new Date(supplier.created_at).toLocaleDateString(),
      }));
      exportToExcel(data, 'suppliers');
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-purple-50 dark:from-slate-900 dark:via-slate-900 dark:to-slate-900">
      {/* Header */}
      <div className="border-b border-slate-200 dark:border-slate-800 bg-white/50 dark:bg-slate-900/50 backdrop-blur-sm">
        <div className="container py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
                <FileText className="w-8 h-8" style={{ color: primaryColor }} />
                Local Purchase Orders (LPO)
              </h1>
              <p className="text-slate-600 dark:text-slate-400 mt-1">
                Manage LPOs, repayments, and suppliers
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleExportExcel}
                className="px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 flex items-center gap-2"
                disabled={lposLoading || suppliersLoading}
              >
                <Download className="w-5 h-5" />
                Excel
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="container py-8">
        {/* Tabs */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700 mb-8">
          <div className="flex border-b border-slate-200 dark:border-slate-700">
            <button
              onClick={() => setActiveTab('lpos')}
              className={`px-6 py-4 font-semibold transition-colors ${
                activeTab === 'lpos'
                  ? 'border-b-2 text-slate-900 dark:text-white'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              }`}
              style={activeTab === 'lpos' ? { borderBottomColor: primaryColor } : {}}
            >
              LPOs
            </button>
            <button
              onClick={() => setActiveTab('repayments')}
              className={`px-6 py-4 font-semibold transition-colors ${
                activeTab === 'repayments'
                  ? 'border-b-2 text-slate-900 dark:text-white'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              }`}
              style={activeTab === 'repayments' ? { borderBottomColor: primaryColor } : {}}
            >
              Repayments
            </button>
            <button
              onClick={() => setActiveTab('suppliers')}
              className={`px-6 py-4 font-semibold transition-colors ${
                activeTab === 'suppliers'
                  ? 'border-b-2 text-slate-900 dark:text-white'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              }`}
              style={activeTab === 'suppliers' ? { borderBottomColor: primaryColor } : {}}
            >
              Suppliers
            </button>
          </div>
        </div>

        {/* LPOs Tab */}
        {activeTab === 'lpos' && (
          <>
            {/* Statistics */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
              <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
                <div className="flex items-center justify-between mb-2">
                  <div className="text-sm text-slate-600 dark:text-slate-400">Total LPOs</div>
                  <FileText className="w-5 h-5" style={{ color: primaryColor }} />
                </div>
                <div className="text-3xl font-bold text-slate-900 dark:text-white">
                  {lpoStats.total}
                </div>
              </div>
              <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
                <div className="text-sm text-slate-600 dark:text-slate-400 mb-2">Total Amount</div>
                <div className="text-3xl font-bold text-green-600 dark:text-green-400">
                  ₦{(lpoStats.totalAmount / 1000).toFixed(1)}K
                </div>
              </div>
              <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
                <div className="text-sm text-slate-600 dark:text-slate-400 mb-2">Approved</div>
                <div className="text-3xl font-bold text-green-600 dark:text-green-400">
                  {lpoStats.approved}
                </div>
              </div>
              <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
                <div className="text-sm text-slate-600 dark:text-slate-400 mb-2">Pending</div>
                <div className="text-3xl font-bold text-yellow-600 dark:text-yellow-400">
                  {lpoStats.pending}
                </div>
              </div>
            </div>

            {/* Filters */}
            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700 mb-8">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-slate-400" />
                  <input
                    type="text"
                    placeholder="Search LPOs..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="w-full pl-10 pr-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:outline-none focus:ring-2"
                  />
                </div>
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:outline-none focus:ring-2"
                >
                  <option value="all">All Statuses</option>
                  <option value="pending">Pending</option>
                  <option value="approved">Approved</option>
                  <option value="rejected">Rejected</option>
                </select>
              </div>
            </div>

            {/* LPOs Table */}
            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
              <div className="p-6 border-b border-slate-200 dark:border-slate-700">
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                  LPOs ({filteredLPOs.length})
                </h3>
              </div>

              {lposLoading ? (
                <div className="p-12 text-center">
                  <Activity className="w-12 h-12 text-slate-400 animate-spin mx-auto mb-4" />
                  <p className="text-slate-600 dark:text-slate-400">Loading LPOs...</p>
                </div>
              ) : filteredLPOs.length === 0 ? (
                <div className="p-12 text-center">
                  <FileText className="w-12 h-12 text-slate-400 mx-auto mb-4" />
                  <p className="text-slate-600 dark:text-slate-400">No LPOs found</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-slate-50 dark:bg-slate-700/50 border-b border-slate-200 dark:border-slate-700">
                      <tr>
                        <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">LPO ID</th>
                        <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Supplier</th>
                        <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Amount</th>
                        <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Status</th>
                        <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Created</th>
                        <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                      {filteredLPOs.map((lpo) => {
                        const isPending = lpo.status?.toLowerCase() === 'pending';
                        const isProcessing = processingIds.has(lpo.lpo_id || lpo.id);
                        
                        return (
                          <tr key={lpo.id} className="hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors">
                            <td className="px-6 py-4 font-mono text-sm text-slate-900 dark:text-white">
                              {lpo.lpo_id || lpo.id}
                            </td>
                            <td className="px-6 py-4 text-slate-600 dark:text-slate-400">
                              {lpo.supplier_name || 'N/A'}
                            </td>
                            <td className="px-6 py-4 font-semibold text-slate-900 dark:text-white">
                              {lpo.currency} {parseFloat(lpo.amount || '0').toLocaleString()}
                            </td>
                            <td className="px-6 py-4">
                              <span className={`px-3 py-1 rounded-full text-xs font-semibold capitalize flex items-center gap-1 w-fit ${getStatusColor(lpo.status || '')}`}>
                                {getStatusIcon(lpo.status || '')}
                                {lpo.status || 'Unknown'}
                              </span>
                            </td>
                            <td className="px-6 py-4 text-slate-600 dark:text-slate-400">
                              {new Date(lpo.created_at).toLocaleDateString()}
                            </td>
                            <td className="px-6 py-4">
                              <div className="flex items-center gap-2">
                                {isPending && (
                                  <>
                                    <button
                                      onClick={() => handleApproveLPO(lpo.lpo_id || lpo.id)}
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
                                      onClick={() => handleRejectLPO(lpo.lpo_id || lpo.id)}
                                      disabled={isProcessing}
                                      className="px-3 py-1.5 text-xs font-semibold text-red-600 dark:text-red-400 border border-red-300 dark:border-red-700 rounded-lg hover:bg-red-50 dark:hover:bg-red-900/20 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
                                    >
                                      <XCircle className="w-3 h-3" />
                                      Reject
                                    </button>
                                  </>
                                )}
                                <button
                                  onClick={() => {
                                    setSelectedLPOId(lpo.lpo_id || lpo.id);
                                    setActiveTab('repayments');
                                  }}
                                  className="px-3 py-1.5 text-xs font-semibold border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700"
                                >
                                  View Repayments
                                </button>
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
          </>
        )}

        {/* Repayments Tab */}
        {activeTab === 'repayments' && (
          <>
            {/* LPO Selector */}
            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700 mb-8">
              <div className="flex items-center gap-4">
                <label className="text-sm font-semibold text-slate-900 dark:text-white whitespace-nowrap">
                  Select LPO:
                </label>
                <select
                  value={selectedLPOId || ''}
                  onChange={(e) => setSelectedLPOId(e.target.value || null)}
                  className="flex-1 px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:outline-none focus:ring-2"
                  style={{ '--tw-ring-color': primaryColor } as React.CSSProperties}
                >
                  <option value="">-- Select an LPO --</option>
                  {lpos.map((lpo) => (
                    <option key={lpo.id} value={lpo.lpo_id || lpo.id}>
                      {lpo.lpo_id || lpo.id} - {lpo.supplier_name || 'N/A'} ({lpo.currency} {parseFloat(lpo.amount || '0').toLocaleString()})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {!selectedLPOId ? (
              <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
                <div className="p-12 text-center">
                  <FileText className="w-12 h-12 text-slate-400 mx-auto mb-4" />
                  <p className="text-slate-600 dark:text-slate-400">Please select an LPO to view repayments</p>
                </div>
              </div>
            ) : repaymentsLoading ? (
              <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
                <div className="p-12 text-center">
                  <Activity className="w-12 h-12 text-slate-400 animate-spin mx-auto mb-4" />
                  <p className="text-slate-600 dark:text-slate-400">Loading repayments...</p>
                </div>
              </div>
            ) : repayments.length === 0 ? (
              <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
                <div className="p-12 text-center">
                  <FileText className="w-12 h-12 text-slate-400 mx-auto mb-4" />
                  <p className="text-slate-600 dark:text-slate-400">No repayments found for this LPO</p>
                </div>
              </div>
            ) : (
              <>
                {/* Repayment Statistics */}
                {(() => {
                  const totalAmount = repayments.reduce((sum, r) => sum + parseFloat(r.amount || '0'), 0);
                  const paidAmount = repayments.filter(r => r.status?.toLowerCase() === 'paid' || r.status?.toLowerCase() === 'completed').reduce((sum, r) => sum + parseFloat(r.amount || '0'), 0);
                  const pendingAmount = repayments.filter(r => r.status?.toLowerCase() === 'pending').reduce((sum, r) => sum + parseFloat(r.amount || '0'), 0);
                  const paidCount = repayments.filter(r => r.status?.toLowerCase() === 'paid' || r.status?.toLowerCase() === 'completed').length;
                  
                  return (
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
                        <div className="flex items-center justify-between mb-2">
                          <div className="text-sm text-slate-600 dark:text-slate-400">Total Repayments</div>
                          <DollarSign className="w-5 h-5" style={{ color: primaryColor }} />
                        </div>
                        <div className="text-3xl font-bold text-slate-900 dark:text-white">
                          {repayments.length}
                        </div>
                        <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                          Total: {repayments[0]?.currency || 'NGN'} {totalAmount.toLocaleString()}
                        </div>
                      </div>
                      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
                        <div className="text-sm text-slate-600 dark:text-slate-400 mb-2">Paid Amount</div>
                        <div className="text-3xl font-bold text-green-600 dark:text-green-400">
                          {repayments[0]?.currency || 'NGN'} {(paidAmount / 1000).toFixed(1)}K
                        </div>
                        <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                          {paidCount} completed
                        </div>
                      </div>
                      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
                        <div className="text-sm text-slate-600 dark:text-slate-400 mb-2">Pending Amount</div>
                        <div className="text-3xl font-bold text-yellow-600 dark:text-yellow-400">
                          {repayments[0]?.currency || 'NGN'} {(pendingAmount / 1000).toFixed(1)}K
                        </div>
                        <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                          {repayments.filter(r => r.status?.toLowerCase() === 'pending').length} pending
                        </div>
                      </div>
                      <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
                        <div className="text-sm text-slate-600 dark:text-slate-400 mb-2">Payment Rate</div>
                        <div className="text-3xl font-bold text-green-600 dark:text-green-400">
                          {totalAmount > 0 ? ((paidAmount / totalAmount) * 100).toFixed(1) : '0.0'}%
                        </div>
                        <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                          Completion rate
                        </div>
                      </div>
                    </div>
                  );
                })()}

                {/* Repayments Table */}
                <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
                  <div className="p-6 border-b border-slate-200 dark:border-slate-700">
                    <div className="flex items-center justify-between">
                      <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                        Repayments for LPO: {selectedLPOId} ({repayments.length})
                      </h3>
                      <button
                        onClick={() => {
                          const data = repayments.map(r => ({
                            'Repayment ID': r.id,
                            'LPO ID': r.lpo_id,
                            'Amount': `${r.currency} ${parseFloat(r.amount || '0').toLocaleString()}`,
                            'Status': r.status,
                            'Payment Date': r.payment_date || 'N/A',
                            'Created': r.created_at,
                          }));
                          exportToExcel(data, `lpo-${selectedLPOId}-repayments`);
                        }}
                        className="px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 flex items-center gap-2"
                      >
                        <Download className="w-5 h-5" />
                        Export Excel
                      </button>
                    </div>
                  </div>

                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead className="bg-slate-50 dark:bg-slate-700/50 border-b border-slate-200 dark:border-slate-700">
                        <tr>
                          <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Repayment ID</th>
                          <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Amount</th>
                          <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Status</th>
                          <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Payment Date</th>
                          <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Created</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                        {repayments.map((repayment) => (
                          <tr key={repayment.id} className="hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors">
                            <td className="px-6 py-4 font-mono text-sm text-slate-900 dark:text-white">
                              {repayment.id}
                            </td>
                            <td className="px-6 py-4 font-semibold text-slate-900 dark:text-white">
                              {repayment.currency} {parseFloat(repayment.amount || '0').toLocaleString()}
                            </td>
                            <td className="px-6 py-4">
                              <span className={`px-3 py-1 rounded-full text-xs font-semibold capitalize flex items-center gap-1 w-fit ${getStatusColor(repayment.status || '')}`}>
                                {getStatusIcon(repayment.status || '')}
                                {repayment.status || 'Unknown'}
                              </span>
                            </td>
                            <td className="px-6 py-4 text-slate-600 dark:text-slate-400">
                              {repayment.payment_date ? new Date(repayment.payment_date).toLocaleDateString() : 'N/A'}
                            </td>
                            <td className="px-6 py-4 text-slate-600 dark:text-slate-400">
                              {new Date(repayment.created_at).toLocaleDateString()}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            )}
          </>
        )}

        {/* Suppliers Tab */}
        {activeTab === 'suppliers' && (
          <>
            {/* Statistics */}
            {(() => {
              const totalAmount = suppliers.reduce((sum, s) => sum + (s.total_amount_financed || 0), 0);
              const totalSuccessful = suppliers.reduce((sum, s) => sum + (s.successful_repayments || 0), 0);
              const totalDefaulted = suppliers.reduce((sum, s) => sum + (s.defaulted_repayments || 0), 0);
              const avgCreditScore = suppliers.length > 0 
                ? (suppliers.reduce((sum, s) => sum + (s.credit_score || 0), 0) / suppliers.length).toFixed(1)
                : '0.0';
              
              return (
                <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
                  <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
                    <div className="flex items-center justify-between mb-2">
                      <div className="text-sm text-slate-600 dark:text-slate-400">Total Suppliers</div>
                      <Users className="w-5 h-5" style={{ color: primaryColor }} />
                    </div>
                    <div className="text-3xl font-bold text-slate-900 dark:text-white">
                      {suppliers.length}
                    </div>
                  </div>
                  <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
                    <div className="text-sm text-slate-600 dark:text-slate-400 mb-2">Total Financed</div>
                    <div className="text-3xl font-bold text-green-600 dark:text-green-400">
                      ₦{(totalAmount / 1000).toFixed(1)}K
                    </div>
                    <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                      {suppliers.reduce((sum, s) => sum + (s.total_lpos_financed || 0), 0)} LPOs
                    </div>
                  </div>
                  <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
                    <div className="text-sm text-slate-600 dark:text-slate-400 mb-2">Successful Repayments</div>
                    <div className="text-3xl font-bold text-green-600 dark:text-green-400">
                      {totalSuccessful}
                    </div>
                    <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                      {totalDefaulted} defaulted
                    </div>
                  </div>
                  <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
                    <div className="text-sm text-slate-600 dark:text-slate-400 mb-2">Avg Credit Score</div>
                    <div className="text-3xl font-bold text-blue-600 dark:text-blue-400">
                      {avgCreditScore}
                    </div>
                    <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                      Out of 100
                    </div>
                  </div>
                </div>
              );
            })()}

            {/* Actions and Filters */}
            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700 mb-8">
              <div className="flex items-center gap-4">
                <button
                  onClick={() => setShowRegisterModal(true)}
                  className="px-4 py-2 text-white rounded-lg font-semibold hover:opacity-90 flex items-center gap-2"
                  style={{ backgroundColor: primaryColor }}
                >
                  <Plus className="w-5 h-5" />
                  Register Supplier
                </button>
                <div className="flex-1 relative">
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-slate-400" />
                  <input
                    type="text"
                    placeholder="Search suppliers..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="w-full pl-10 pr-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:outline-none focus:ring-2"
                  />
                </div>
              </div>
            </div>

            {/* Suppliers Table */}
            <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
              <div className="p-6 border-b border-slate-200 dark:border-slate-700">
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                  Suppliers ({filteredSuppliers.length})
                </h3>
              </div>

              {suppliersLoading ? (
                <div className="p-12 text-center">
                  <Activity className="w-12 h-12 text-slate-400 animate-spin mx-auto mb-4" />
                  <p className="text-slate-600 dark:text-slate-400">Loading suppliers...</p>
                </div>
              ) : filteredSuppliers.length === 0 ? (
                <div className="p-12 text-center">
                  <FileText className="w-12 h-12 text-slate-400 mx-auto mb-4" />
                  <p className="text-slate-600 dark:text-slate-400">No suppliers found</p>
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-slate-50 dark:bg-slate-700/50 border-b border-slate-200 dark:border-slate-700">
                      <tr>
                        <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Supplier ID</th>
                        <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Business Name</th>
                        <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Registration Number</th>
                        <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">LPOs Financed</th>
                        <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Amount Financed</th>
                        <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Credit Score</th>
                        <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Repayments</th>
                        <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                      {filteredSuppliers.map((supplier) => (
                        <tr key={supplier.id} className="hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors">
                          <td className="px-6 py-4 font-mono text-sm text-slate-900 dark:text-white">
                            {supplier.supplier_id}
                          </td>
                          <td className="px-6 py-4 font-semibold text-slate-900 dark:text-white">
                            {supplier.business_name}
                          </td>
                          <td className="px-6 py-4 text-slate-600 dark:text-slate-400">
                            {supplier.registration_number}
                          </td>
                          <td className="px-6 py-4 text-slate-600 dark:text-slate-400">
                            {supplier.total_lpos_financed || 0}
                          </td>
                          <td className="px-6 py-4 font-semibold text-slate-900 dark:text-white">
                            ₦{(supplier.total_amount_financed || 0).toLocaleString()}
                          </td>
                          <td className="px-6 py-4">
                            <span className={`px-3 py-1 rounded-full text-xs font-semibold ${
                              (supplier.credit_score || 0) >= 70 
                                ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300'
                                : (supplier.credit_score || 0) >= 50
                                ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300'
                                : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300'
                            }`}>
                              {supplier.credit_score || 0}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-slate-600 dark:text-slate-400">
                            <div className="text-sm">
                              <span className="text-green-600 dark:text-green-400">{supplier.successful_repayments || 0}</span>
                              <span className="text-slate-400 mx-1">/</span>
                              <span className="text-red-600 dark:text-red-400">{supplier.defaulted_repayments || 0}</span>
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <button
                              onClick={() => handleViewSupplier(supplier.supplier_id)}
                              className="px-3 py-1.5 text-xs font-semibold border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700 flex items-center gap-1"
                            >
                              <Eye className="w-3 h-3" />
                              View Details
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Register Supplier Modal */}
            {showRegisterModal && (
              <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
                <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700 w-full max-w-md">
                  <div className="p-6 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between">
                    <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Register New Supplier</h3>
                    <button
                      onClick={() => {
                        setShowRegisterModal(false);
                        setRegisterForm({ supplier_id: '', business_name: '', registration_number: '' });
                      }}
                      className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
                    >
                      <X className="w-5 h-5" />
                    </button>
                  </div>
                  <form onSubmit={handleRegisterSupplier} className="p-6 space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                        Supplier ID <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="text"
                        required
                        value={registerForm.supplier_id}
                        onChange={(e) => setRegisterForm(prev => ({ ...prev, supplier_id: e.target.value }))}
                        className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:outline-none focus:ring-2"
                        placeholder="Enter supplier ID"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                        Business Name <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="text"
                        required
                        value={registerForm.business_name}
                        onChange={(e) => setRegisterForm(prev => ({ ...prev, business_name: e.target.value }))}
                        className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:outline-none focus:ring-2"
                        placeholder="Enter business name"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                        Registration Number <span className="text-red-500">*</span>
                      </label>
                      <input
                        type="text"
                        required
                        value={registerForm.registration_number}
                        onChange={(e) => setRegisterForm(prev => ({ ...prev, registration_number: e.target.value }))}
                        className="w-full px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white focus:outline-none focus:ring-2"
                        placeholder="Enter registration number"
                      />
                    </div>
                    <div className="flex items-center gap-3 pt-4">
                      <button
                        type="submit"
                        disabled={registering}
                        className="flex-1 px-4 py-2 text-white rounded-lg font-semibold hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed"
                        style={{ backgroundColor: primaryColor }}
                      >
                        {registering ? 'Registering...' : 'Register Supplier'}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          setShowRegisterModal(false);
                          setRegisterForm({ supplier_id: '', business_name: '', registration_number: '' });
                        }}
                        className="px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-700"
                      >
                        Cancel
                      </button>
                    </div>
                  </form>
                </div>
              </div>
            )}

            {/* Supplier Details Modal */}
            {showSupplierDetails && (
              <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
                <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700 w-full max-w-4xl max-h-[90vh] overflow-y-auto">
                  <div className="p-6 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between sticky top-0 bg-white dark:bg-slate-800 z-10">
                    <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                      Supplier Details: {selectedSupplierId}
                    </h3>
                    <button
                      onClick={() => {
                        setShowSupplierDetails(false);
                        setSelectedSupplierId(null);
                        setSupplierProfile(null);
                        setSupplierLPOs([]);
                      }}
                      className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
                    >
                      <X className="w-5 h-5" />
                    </button>
                  </div>
                  
                  <div className="p-6 space-y-6">
                    {supplierDetailsLoading ? (
                      <div className="text-center py-12">
                        <Activity className="w-12 h-12 text-slate-400 animate-spin mx-auto mb-4" />
                        <p className="text-slate-600 dark:text-slate-400">Loading supplier details...</p>
                      </div>
                    ) : (
                      <>
                        {/* Supplier Profile */}
                        {supplierProfile && (
                          <div className="space-y-4">
                            <div className="bg-slate-50 dark:bg-slate-900 rounded-lg p-6 border border-slate-200 dark:border-slate-700">
                              <h4 className="text-md font-semibold text-slate-900 dark:text-white mb-4">Profile Information</h4>
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                                <div>
                                  <label className="text-xs text-slate-500 dark:text-slate-400">Business Name</label>
                                  <p className="text-sm font-medium text-slate-900 dark:text-white">{supplierProfile.business_name}</p>
                                </div>
                                <div>
                                  <label className="text-xs text-slate-500 dark:text-slate-400">Supplier ID</label>
                                  <p className="text-sm font-medium text-slate-900 dark:text-white font-mono">{supplierProfile.supplier_id}</p>
                                </div>
                                <div>
                                  <label className="text-xs text-slate-500 dark:text-slate-400">Registration Number</label>
                                  <p className="text-sm font-medium text-slate-900 dark:text-white">{supplierProfile.registration_number}</p>
                                </div>
                                {supplierProfile.contact_email && (
                                  <div>
                                    <label className="text-xs text-slate-500 dark:text-slate-400">Contact Email</label>
                                    <p className="text-sm font-medium text-slate-900 dark:text-white">{supplierProfile.contact_email}</p>
                                  </div>
                                )}
                                {supplierProfile.contact_phone && (
                                  <div>
                                    <label className="text-xs text-slate-500 dark:text-slate-400">Contact Phone</label>
                                    <p className="text-sm font-medium text-slate-900 dark:text-white">{supplierProfile.contact_phone}</p>
                                  </div>
                                )}
                                {supplierProfile.address && (
                                  <div>
                                    <label className="text-xs text-slate-500 dark:text-slate-400">Address</label>
                                    <p className="text-sm font-medium text-slate-900 dark:text-white">{supplierProfile.address}</p>
                                  </div>
                                )}
                                {supplierProfile.tax_id && (
                                  <div>
                                    <label className="text-xs text-slate-500 dark:text-slate-400">Tax ID</label>
                                    <p className="text-sm font-medium text-slate-900 dark:text-white">{supplierProfile.tax_id}</p>
                                  </div>
                                )}
                                {supplierProfile.bank_account && (
                                  <div>
                                    <label className="text-xs text-slate-500 dark:text-slate-400">Bank Account</label>
                                    <p className="text-sm font-medium text-slate-900 dark:text-white">{supplierProfile.bank_account}</p>
                                  </div>
                                )}
                                {supplierProfile.bank_name && (
                                  <div>
                                    <label className="text-xs text-slate-500 dark:text-slate-400">Bank Name</label>
                                    <p className="text-sm font-medium text-slate-900 dark:text-white">{supplierProfile.bank_name}</p>
                                  </div>
                                )}
                              </div>
                            </div>

                            {/* Financial Statistics */}
                            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                              <div className="bg-slate-50 dark:bg-slate-900 rounded-lg p-4 border border-slate-200 dark:border-slate-700">
                                <label className="text-xs text-slate-500 dark:text-slate-400">Total LPOs Financed</label>
                                <p className="text-lg font-bold text-slate-900 dark:text-white">{supplierProfile.total_lpos_financed || 0}</p>
                              </div>
                              <div className="bg-slate-50 dark:bg-slate-900 rounded-lg p-4 border border-slate-200 dark:border-slate-700">
                                <label className="text-xs text-slate-500 dark:text-slate-400">Total Amount Financed</label>
                                <p className="text-lg font-bold text-green-600 dark:text-green-400">₦{(supplierProfile.total_amount_financed || 0).toLocaleString()}</p>
                              </div>
                              <div className="bg-slate-50 dark:bg-slate-900 rounded-lg p-4 border border-slate-200 dark:border-slate-700">
                                <label className="text-xs text-slate-500 dark:text-slate-400">Credit Score</label>
                                <p className={`text-lg font-bold ${
                                  (supplierProfile.credit_score || 0) >= 70 
                                    ? 'text-green-600 dark:text-green-400'
                                    : (supplierProfile.credit_score || 0) >= 50
                                    ? 'text-yellow-600 dark:text-yellow-400'
                                    : 'text-red-600 dark:text-red-400'
                                }`}>
                                  {supplierProfile.credit_score || 0}
                                </p>
                              </div>
                              <div className="bg-slate-50 dark:bg-slate-900 rounded-lg p-4 border border-slate-200 dark:border-slate-700">
                                <label className="text-xs text-slate-500 dark:text-slate-400">Repayment Status</label>
                                <p className="text-lg font-bold text-slate-900 dark:text-white">
                                  <span className="text-green-600 dark:text-green-400">{supplierProfile.successful_repayments || 0}</span>
                                  <span className="text-slate-400 mx-1">/</span>
                                  <span className="text-red-600 dark:text-red-400">{supplierProfile.defaulted_repayments || 0}</span>
                                </p>
                              </div>
                            </div>
                          </div>
                        )}

                        {/* Supplier LPOs */}
                        <div>
                          <h4 className="text-md font-semibold text-slate-900 dark:text-white mb-4">LPOs ({supplierLPOs.length})</h4>
                          {supplierLPOs.length === 0 ? (
                            <div className="text-center py-8 text-slate-600 dark:text-slate-400">
                              No LPOs found for this supplier
                            </div>
                          ) : (
                            <div className="overflow-x-auto">
                              <table className="w-full">
                                <thead className="bg-slate-50 dark:bg-slate-700/50 border-b border-slate-200 dark:border-slate-700">
                                  <tr>
                                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-900 dark:text-white">LPO ID</th>
                                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-900 dark:text-white">Amount</th>
                                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-900 dark:text-white">Status</th>
                                    <th className="px-4 py-3 text-left text-xs font-semibold text-slate-900 dark:text-white">Created</th>
                                  </tr>
                                </thead>
                                <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                                  {supplierLPOs.map((lpo) => (
                                    <tr key={lpo.id} className="hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors">
                                      <td className="px-4 py-3 font-mono text-xs text-slate-900 dark:text-white">
                                        {lpo.lpo_id || lpo.id}
                                      </td>
                                      <td className="px-4 py-3 font-semibold text-xs text-slate-900 dark:text-white">
                                        {lpo.currency} {parseFloat(lpo.amount || '0').toLocaleString()}
                                      </td>
                                      <td className="px-4 py-3">
                                        <span className={`px-2 py-1 rounded-full text-xs font-semibold capitalize ${getStatusColor(lpo.status || '')}`}>
                                          {lpo.status || 'Unknown'}
                                        </span>
                                      </td>
                                      <td className="px-4 py-3 text-xs text-slate-600 dark:text-slate-400">
                                        {new Date(lpo.created_at).toLocaleDateString()}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

