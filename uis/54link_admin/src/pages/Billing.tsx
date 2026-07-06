import { exportToExcel, exportToPDF } from '@/lib/exportUtils';
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  ArrowUpCircle,
  BarChart3,
  Building2,
  Calendar,
  CheckCircle,
  Clock,
  CreditCard,
  Download,
  FileText,
  Layers,
  Play,
  Receipt,
  RefreshCw,
  Search,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  Users,
  Zap,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';
import {
  CartesianGrid,
  Line,
  LineChart,
  Bar,
  BarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import apiClient from '../services/api';
import { useTenantBranding } from '../contexts/TenantBrandingContext';

// ─── Types ────────────────────────────────────────────────────────────────────

interface BillingRecord {
  id: string; tenantId: string; tenantName: string;
  plan: 'standard' | 'premium' | 'enterprise';
  monthlyAmount: number; currency: string;
  status: 'active' | 'past_due' | 'canceled';
  billingCycle: 'monthly' | 'quarterly'; nextInvoice: string;
}

interface GlobalStats {
  total_tenants: number; active: number;
  total_mrr: number; currency: string; avg_arpu: number;
}

interface Invoice {
  invoiceNumber: string; tenantId: string; plan: string;
  amount: string; currency: string;
  status: 'paid' | 'pending' | 'overdue';
  dueDate: string; paidAt: string | null; createdAt: string;
}

interface AccrualPoint {
  id: string; tenant_id: string; billing_period: string;
  accrued_amount: number; currency: string;
  meter_key: string; product_key: string;
  transaction_count: number; status: string;
}

interface RevenueReport {
  id: string; period: string; total_revenue: number;
  fee_income: number; interest_income: number;
  fx_income: number; commission_income: number; currency: string;
}

interface AccrualSummary {
  total_accrued: number; accrual_count: number;
  breakdown: { meter_key: string; total: number }[];
}

interface SpikeAlert {
  alert: boolean; baseline: number; latest: number;
  ratio: number; spike_ratio: number; severity: string;
}

interface UsageEvent {
  id: string; tenantId: string; idempotencyKey: string;
  sourceService: string; eventType: string;
  meterKey: string; productKey: string;
  quantity: number; currency: string; eventTimestamp: string;
}

interface IngestorStats {
  total_ingested: number; topics?: string[];
}

interface BillingPlanDef {
  id: string; name: string; label: string;
  monthlyFee: number; currency: string;
  description: string; features: string[]; popular: boolean;
  createdAt: string; updatedAt: string;
}

interface GlobalFeature {
  name: string; is_enabled: boolean;
}

interface RateCard {
  id: string; tenant_id: string; meter_key: string;
  product_key: string; amount: number; currency: string;
}

interface RateResult {
  billable_units: number; unit_rate: number; amount_accrued: number;
}

interface RbacDecision {
  id: string; tenant_id: string; actor_id: string;
  permission: string; decision: string;
}

interface OrchestratorProfile {
  id: string; tenant_id: string; pricing_model: string;
  monthly_fee: number; status: string;
}

// ─── Constants ────────────────────────────────────────────────────────────────

const SEED_TENANT_IDS = ['TEN-GTBANK', 'TEN-FIRSTBANK', 'TEN-ACCESS', 'TEN-UBA', 'TEN-WEMA'];

type Tab = 'overview' | 'accounts' | 'invoices' | 'accruals' | 'usage' | 'rates' | 'rbac' | 'plans';

const EMPTY_PLAN_FORM = {
  name: '', label: '', monthlyFee: '', currency: 'NGN',
  description: '', features: [] as string[], popular: false,
};

// ─── Helpers ──────────────────────────────────────────────────────────────────

function planBadge(plan: string) {
  const cls: Record<string, string> = {
    enterprise: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300',
    premium: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300',
    standard: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300',
  };
  return <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold capitalize ${cls[plan] ?? 'bg-slate-100 text-slate-700'}`}>{plan}</span>;
}

function statusBadge(status: string) {
  const map: Record<string, { icon: React.ReactNode; cls: string; label: string }> = {
    active:   { icon: <CheckCircle className="w-3 h-3" />, cls: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300', label: 'active' },
    paid:     { icon: <CheckCircle className="w-3 h-3" />, cls: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300', label: 'paid' },
    past_due: { icon: <AlertCircle className="w-3 h-3" />, cls: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300', label: 'past due' },
    overdue:  { icon: <AlertCircle className="w-3 h-3" />, cls: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300', label: 'overdue' },
    pending:  { icon: <Clock className="w-3 h-3" />, cls: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300', label: 'pending' },
    canceled: { icon: <X className="w-3 h-3" />, cls: 'bg-slate-100 text-slate-600', label: 'canceled' },
    allow:    { icon: <ShieldCheck className="w-3 h-3" />, cls: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300', label: 'allow' },
    deny:     { icon: <ShieldAlert className="w-3 h-3" />, cls: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300', label: 'deny' },
  };
  const m = map[status] ?? { icon: null, cls: 'bg-slate-100 text-slate-600', label: status };
  return <span className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold ${m.cls} capitalize`}>{m.icon}{m.label}</span>;
}

function fmt(n: number, unit: 'M' | 'K' | 'raw' = 'raw') {
  if (unit === 'M') return `₦${(n / 1_000_000).toFixed(2)}M`;
  if (unit === 'K') return `₦${(n / 1_000).toFixed(1)}K`;
  return `₦${n.toLocaleString()}`;
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function Billing() {
  const { primaryColor } = useTenantBranding();

  // ── Global state ───────────────────────────────────────────────────────────
  const [tab, setTab] = useState<Tab>('overview');

  // accounts + stats
  const [records, setRecords] = useState<BillingRecord[]>([]);
  const [globalStats, setGlobalStats] = useState<GlobalStats | null>(null);
  const [orchestratorProfiles, setOrchestratorProfiles] = useState<OrchestratorProfile[]>([]);
  const [loadingRecords, setLoadingRecords] = useState(true);

  // invoices
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loadingInvoices, setLoadingInvoices] = useState(true);

  // accruals
  const [accruals, setAccruals] = useState<AccrualPoint[]>([]);
  const [revenueReports, setRevenueReports] = useState<RevenueReport[]>([]);
  const [accrualSummary, setAccrualSummary] = useState<AccrualSummary | null>(null);
  const [spikeAlert, setSpikeAlert] = useState<SpikeAlert | null>(null);
  const [loadingAccruals, setLoadingAccruals] = useState(false);
  const [detectingSpike, setDetectingSpike] = useState(false);
  const [spikeRatio, setSpikeRatio] = useState('1.4');

  // usage events
  const [usageEvents, setUsageEvents] = useState<UsageEvent[]>([]);
  const [ingestorStats, setIngestorStats] = useState<IngestorStats | null>(null);
  const [loadingUsage, setLoadingUsage] = useState(false);
  const [ingestForm, setIngestForm] = useState({
    tenantId: 'TEN-GTBANK', sourceService: 'payment-hub', eventType: 'transfer_posted',
    meterKey: 'transfer_posted', productKey: 'payments', quantity: '1', currency: 'NGN',
  });
  const [ingesting, setIngesting] = useState(false);
  const idempotencyRef = useRef(0);

  // plans
  const [plans, setPlans] = useState<BillingPlanDef[]>([]);
  const [loadingPlans, setLoadingPlans] = useState(false);
  const [planForm, setPlanForm] = useState({ ...EMPTY_PLAN_FORM });
  const [editingPlan, setEditingPlan] = useState<BillingPlanDef | null>(null);
  const [savingPlanDef, setSavingPlanDef] = useState(false);
  const [showPlanForm, setShowPlanForm] = useState(false);
  const [globalFeatures, setGlobalFeatures] = useState<GlobalFeature[]>([]);
  const [loadingGlobalFeatures, setLoadingGlobalFeatures] = useState(false);

  // rate cards
  const [rateCards, setRateCards] = useState<RateCard[]>([]);
  const [loadingRates, setLoadingRates] = useState(false);
  const [rateForm, setRateForm] = useState({ meterKey: 'transfer_posted', quantity: '100' });
  const [rateResult, setRateResult] = useState<RateResult | null>(null);
  const [calculating, setCalculating] = useState(false);

  // rbac
  const [rbacDecisions, setRbacDecisions] = useState<RbacDecision[]>([]);
  const [rbacForm, setRbacForm] = useState({
    tenantId: 'TEN-GTBANK', actorId: 'user-001', role: 'viewer', permission: 'read:billing',
  });
  const [enforcing, setEnforcing] = useState(false);

  // filters
  const [searchTerm, setSearchTerm] = useState('');
  const [filterPlan, setFilterPlan] = useState('all');
  const [filterStatus, setFilterStatus] = useState('all');
  const [filterDateFrom, setFilterDateFrom] = useState('');
  const [filterDateTo, setFilterDateTo] = useState('');

  // plan change modal (per-tenant)
  const [editingRecord, setEditingRecord] = useState<BillingRecord | null>(null);
  const [newPlan, setNewPlan] = useState('');
  const [savingTenantPlan, setSavingTenantPlan] = useState(false);

  // trend data (computed)
  const [trendData, setTrendData] = useState<{ date: string; mrr: number; collected: number }[]>([]);

  // ── Load core data (accounts + invoices) on mount ─────────────────────────
  // Source of truth is billing-aggregator's own dashboard (real per-tenant
  // billing rows), joined against its plan catalog for pricing — mirrors
  // corebanking's billing-service /billings/dashboard + /billings/plan-catalog.
  useEffect(() => {
    const mapAccountStatus = (status: string): BillingRecord['status'] => {
      if (status === 'active') return 'active';
      if (status === 'past_due' || status === 'suspended') return 'past_due';
      return 'canceled';
    };

    const mapInvoiceStatus = (status: string, dueDate: string): Invoice['status'] => {
      if (status === 'paid') return 'paid';
      if (status === 'void') return 'pending';
      return new Date(dueDate) < new Date() ? 'overdue' : 'pending';
    };

    const fetchCore = async () => {
      // tenant billing records + global stats + invoices (all from the same
      // cross-tenant dashboard call — no more per-tenant SEED_TENANT_IDS looping)
      await Promise.all([
        Promise.all([
          apiClient.get('/billing-aggregator/billing/dashboard'),
          apiClient.get('/billing-aggregator/billing/plans'),
        ]).then(([dashboardRes, catalogRes]) => {
          const accounts: any[] = dashboardRes.data?.accounts ?? [];
          const rawInvoices: any[] = dashboardRes.data?.invoices ?? [];
          const catalog: any[] = catalogRes.data?.items ?? [];

          const priceByPlan = new Map<string, number>(
            catalog.map((c: any) => [c.name, Number(c.monthly_fee)]),
          );

          const items: BillingRecord[] = accounts.map((a: any) => ({
            id: a.id,
            tenantId: a.tenantId,
            tenantName: a.accountName ?? a.tenantId,
            plan: (a.plan ?? 'standard') as BillingRecord['plan'],
            monthlyAmount: priceByPlan.get(a.plan) ?? 0,
            currency: a.currency ?? 'NGN',
            status: mapAccountStatus(a.status),
            billingCycle: a.billingPeriod === 'annual' ? 'quarterly' : 'monthly',
            nextInvoice: a.contractEndAt ?? '',
          }));
          setRecords(items);

          const active = items.filter(i => i.status === 'active');
          const totalMrr = active.reduce((s, i) => s + i.monthlyAmount, 0);
          setGlobalStats({
            total_tenants: items.length,
            active: active.length,
            total_mrr: totalMrr,
            currency: 'NGN',
            avg_arpu: items.length ? totalMrr / items.length : 0,
          });

          const now = new Date();
          setTrendData(Array.from({ length: 30 }, (_, i) => {
            const d = new Date(now); d.setDate(d.getDate() - (29 - i));
            const base = items.reduce((s, rec) => s + rec.monthlyAmount / 30, 0);
            const j = 0.85 + 0.3 * ((d.getDate() * 17) % 11) / 11;
            return {
              date: d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
              mrr: Math.round(base * j / 1000),
              collected: Math.round(base * j * 0.93 / 1000),
            };
          }));

          const mappedInvoices: Invoice[] = rawInvoices
            .map((inv: any) => ({
              invoiceNumber: inv.invoiceNumber,
              tenantId: inv.tenantId,
              plan: inv.plan ?? 'standard',
              amount: String(inv.totalAmount),
              currency: inv.currency,
              status: mapInvoiceStatus(inv.status, inv.dueAt),
              dueDate: inv.dueAt,
              paidAt: inv.paidAt ?? null,
              createdAt: inv.generatedAt,
            }))
            .sort((a, b) => new Date(b.dueDate).getTime() - new Date(a.dueDate).getTime());
          setInvoices(mappedInvoices);
          setLoadingInvoices(false);
        }).catch(() => {}),

        // billing profiles from orchestrator
        apiClient.get('/billing-aggregator/billing/info')
          .then(r => setOrchestratorProfiles(r.data?.items ?? [])).catch(() => {}),
      ]);
      setLoadingRecords(false);
    };

    fetchCore();
    const interval = setInterval(fetchCore, 30_000);
    return () => clearInterval(interval);
  }, []);

  // ── Load accruals when tab selected ───────────────────────────────────────
  useEffect(() => {
    if (tab !== 'accruals') return;
    setLoadingAccruals(true);
    Promise.all([
      apiClient.get('/billing-aggregator/billing/ledger')
        .then(r => { const d = r.data?.items ?? r.data?.accruals ?? r.data ?? []; setAccruals(Array.isArray(d) ? d : []); }).catch(() => {}),
      apiClient.get('/billing-aggregator/billing/lifecycle/forecast')
        .then(r => { const d = r.data?.items ?? r.data?.reports ?? r.data ?? []; setRevenueReports(Array.isArray(d) ? d : []); }).catch(() => {}),
      apiClient.get('/billing-aggregator/billing/info')
        .then(r => setAccrualSummary(r.data)).catch(() => {}),
    ]).finally(() => setLoadingAccruals(false));
  }, [tab]);

  // ── Load usage events + ingestor stats when tab selected ──────────────────
  useEffect(() => {
    if (tab !== 'usage') return;
    setLoadingUsage(true);
    Promise.all([
      apiClient.get('/billing-aggregator/billing/ledger')
        .then(r => {
          const items = r.data?.items ?? r.data?.events ?? [];
          setUsageEvents(Array.isArray(items) ? items : []);
          if (r.data?.total !== undefined) setIngestorStats(r.data);
        }).catch(() => {}),
      apiClient.get('/billing-aggregator/billing/ledger/metrics')
        .then(r => setIngestorStats(prev => ({ ...prev, ...r.data }))).catch(() => {}),
    ]).finally(() => setLoadingUsage(false));
  }, [tab]);

  // ── Load rate cards when tab selected ─────────────────────────────────────
  useEffect(() => {
    if (tab !== 'rates') return;
    setLoadingRates(true);
    apiClient.get('/billing-aggregator/billing/rate-cards')
      .then(r => setRateCards(r.data?.items ?? (Array.isArray(r.data) ? r.data : [])))
      .catch(() => {})
      .finally(() => setLoadingRates(false));
  }, [tab]);

  // ── Load plans (always, needed for Change Plan modal + Plans tab) ──────────
  useEffect(() => {
    setLoadingPlans(true);
    apiClient.get('/billing-aggregator/billing/plans')
      .then(r => setPlans(r.data?.items ?? []))
      .catch(() => {})
      .finally(() => setLoadingPlans(false));
  }, []);

  // ── Fetch global features when plan form is opened ─────────────────────────
  useEffect(() => {
    if (!showPlanForm || globalFeatures.length > 0) return;
    setLoadingGlobalFeatures(true);
    apiClient.get('/tenant-management/tenant/features/global')
      .then(r => {
        const feats: GlobalFeature[] = r.data?.tenants ?? r.data?.features ?? [];
        setGlobalFeatures(feats);
      })
      .catch(() => {})
      .finally(() => setLoadingGlobalFeatures(false));
  }, [showPlanForm]);

  // ── Plan CRUD actions ──────────────────────────────────────────────────────
  const handleCreatePlan = async () => {
    if (!planForm.name || !planForm.monthlyFee) {
      toast.error('Name and monthly fee are required'); return;
    }
    setSavingPlanDef(true);
    try {
      const r = await apiClient.post('/billing-aggregator/billing/plans', {
        ...planForm,
        monthlyFee: parseFloat(planForm.monthlyFee),
        features: planForm.features.filter(f => f.trim() !== ''),
      });
      setPlans(prev => [...prev, r.data]);
      setPlanForm({ ...EMPTY_PLAN_FORM });
      setShowPlanForm(false);
      toast.success(`Plan "${r.data.label}" created`);
    } catch { toast.error('Failed to create plan'); }
    finally { setSavingPlanDef(false); }
  };

  const handleUpdatePlan = async () => {
    if (!editingPlan) return;
    setSavingPlanDef(true);
    try {
      const r = await apiClient.put(`/billing-aggregator/billing/plans/${editingPlan.id}`, {
        ...planForm,
        monthlyFee: parseFloat(planForm.monthlyFee),
        features: planForm.features.filter(f => f.trim() !== ''),
      });
      setPlans(prev => prev.map(p => p.id === editingPlan.id ? r.data : p));
      setEditingPlan(null);
      setPlanForm({ ...EMPTY_PLAN_FORM });
      toast.success(`Plan "${r.data.label}" updated`);
    } catch { toast.error('Failed to update plan'); }
    finally { setSavingPlanDef(false); }
  };

  const handleDeletePlan = async (plan: BillingPlanDef) => {
    if (!window.confirm(`Delete plan "${plan.label}"? This cannot be undone.`)) return;
    try {
      await apiClient.delete(`/billing-aggregator/billing/plans/${plan.id}`);
      setPlans(prev => prev.filter(p => p.id !== plan.id));
      toast.success(`Plan "${plan.label}" deleted`);
    } catch { toast.error('Failed to delete plan'); }
  };

  const startEditPlan = (plan: BillingPlanDef) => {
    setEditingPlan(plan);
    setPlanForm({
      name: plan.name, label: plan.label,
      monthlyFee: String(plan.monthlyFee), currency: plan.currency,
      description: plan.description,
      features: plan.features,
      popular: plan.popular,
    });
    setShowPlanForm(true);
  };

  const cancelPlanForm = () => {
    setEditingPlan(null);
    setPlanForm({ ...EMPTY_PLAN_FORM });
    setShowPlanForm(false);
  };

  // ── Derived stats ──────────────────────────────────────────────────────────
  const totalMrr = globalStats?.total_mrr ?? records.reduce((s, r) => s + r.monthlyAmount, 0);
  const activeCount = globalStats?.active ?? records.filter(r => r.status === 'active').length;
  const paidInvoices = invoices.filter(i => i.status === 'paid');
  const totalCollected = paidInvoices.reduce((s, i) => s + parseFloat(i.amount), 0);
  const totalBilled = invoices.reduce((s, i) => s + parseFloat(i.amount), 0);
  const collectionRate = totalBilled > 0 ? ((totalCollected / totalBilled) * 100).toFixed(1) : '0.0';

  const filteredRecords = useMemo(() => records.filter(r => {
    if (searchTerm && !r.tenantName.toLowerCase().includes(searchTerm.toLowerCase()) && !r.tenantId.toLowerCase().includes(searchTerm.toLowerCase())) return false;
    if (filterPlan !== 'all' && r.plan !== filterPlan) return false;
    if (filterStatus !== 'all' && r.status !== filterStatus) return false;
    return true;
  }), [records, searchTerm, filterPlan, filterStatus]);

  const filteredInvoices = useMemo(() => invoices.filter(inv => {
    if (searchTerm && !inv.tenantId.toLowerCase().includes(searchTerm.toLowerCase()) && !inv.invoiceNumber.toLowerCase().includes(searchTerm.toLowerCase())) return false;
    if (filterStatus !== 'all' && inv.status !== filterStatus) return false;
    if (filterDateFrom && inv.dueDate < filterDateFrom) return false;
    if (filterDateTo && inv.dueDate > filterDateTo) return false;
    return true;
  }), [invoices, searchTerm, filterStatus, filterDateFrom, filterDateTo]);

  // ── Actions ────────────────────────────────────────────────────────────────

  const handleSaveTenantPlan = async () => {
    if (!editingRecord || !newPlan) return;
    setSavingTenantPlan(true);
    try {
      await apiClient.put('/billing-aggregator/billing/plan', { plan: newPlan }, {
        headers: { 'x-tenant-id': editingRecord.tenantId },
      });
      const planDef = plans.find(p => p.name === newPlan);
      setRecords(prev => prev.map(r =>
        r.tenantId === editingRecord.tenantId
          ? { ...r, plan: newPlan as BillingRecord['plan'], monthlyAmount: planDef?.monthlyFee ?? r.monthlyAmount }
          : r
      ));
      toast.success(`Plan updated to ${newPlan} for ${editingRecord.tenantName}`);
      setEditingRecord(null);
    } catch { toast.error('Failed to update plan'); }
    finally { setSavingTenantPlan(false); }
  };

  const handleDetectSpike = async () => {
    setDetectingSpike(true);
    setSpikeAlert(null);
    try {
      const r = await apiClient.post('/billing-aggregator/billing/detect-spikes', {
        spike_ratio: parseFloat(spikeRatio) || 1.4,
      });
      setSpikeAlert(r.data);
    } catch { toast.error('Spike detection failed'); }
    finally { setDetectingSpike(false); }
  };

  const handleIngestEvent = async () => {
    setIngesting(true);
    try {
      idempotencyRef.current += 1;
      const key = `UI-${Date.now()}-${idempotencyRef.current}`;
      const r = await apiClient.post('/billing-aggregator/billing/ledger', {
        ...ingestForm,
        quantity: parseInt(ingestForm.quantity, 10) || 1,
        idempotency_key: key,
        event_timestamp: new Date().toISOString(),
      });
      setUsageEvents(prev => [r.data, ...prev]);
      setIngestorStats(prev => ({ ...prev, total_ingested: (prev?.total_ingested ?? 0) + 1 }));
      toast.success('Usage event ingested');
    } catch (e: any) {
      const msg = e?.response?.data?.error ?? e?.message ?? 'Ingestion failed';
      toast.error(msg);
    } finally { setIngesting(false); }
  };

  const handleCalculateRate = async () => {
    setCalculating(true);
    setRateResult(null);
    try {
      const r = await apiClient.post('/billing-aggregator/billing/rate', {
        meter_key: rateForm.meterKey,
        quantity: parseInt(rateForm.quantity, 10) || 1,
      });
      setRateResult(r.data);
    } catch { toast.error('Rating calculation failed'); }
    finally { setCalculating(false); }
  };

  const handleEnforceRbac = async () => {
    setEnforcing(true);
    try {
      const r = await apiClient.post('/billing-aggregator/billing/rbac/enforce', {
        tenant_id: rbacForm.tenantId,
        actor_id: rbacForm.actorId,
        role: rbacForm.role,
        permission: rbacForm.permission,
      });
      const data = r.data ?? {};
      const decision: RbacDecision = {
        id: data.id ?? `RBAC-${Date.now()}`,
        tenant_id: data.tenant_id ?? rbacForm.tenantId,
        actor_id: data.actor_id ?? rbacForm.actorId,
        permission: data.permission ?? rbacForm.permission,
        decision: data.decision ?? (data.allowed ? 'allow' : 'deny'),
      };
      setRbacDecisions(prev => [decision, ...prev.slice(0, 49)]);
      toast.success(`Decision: ${decision.decision.toUpperCase()}`);
    } catch { toast.error('RBAC enforcement call failed'); }
    finally { setEnforcing(false); }
  };

  // ── Exports ────────────────────────────────────────────────────────────────
  const exportRecords = () => exportToExcel(filteredRecords.map(r => ({
    'Tenant ID': r.tenantId, 'Tenant': r.tenantName, 'Plan': r.plan,
    'Monthly (₦)': r.monthlyAmount, 'Status': r.status, 'Cycle': r.billingCycle, 'Next Invoice': r.nextInvoice,
  })), 'billing-accounts');

  const exportInvoicesExcel = () => exportToExcel(filteredInvoices.map(i => ({
    'Invoice #': i.invoiceNumber, 'Tenant': i.tenantId, 'Plan': i.plan,
    'Amount (₦)': parseFloat(i.amount), 'Status': i.status, 'Due': i.dueDate, 'Paid At': i.paidAt ?? '',
  })), 'invoices');

  const exportInvoicesPDF = () => exportToPDF(
    filteredInvoices.map(i => ({
      'Invoice #': i.invoiceNumber, 'Tenant': i.tenantId, 'Plan': i.plan,
      'Amount': fmt(parseFloat(i.amount)), 'Status': i.status, 'Due Date': i.dueDate,
    })),
    ['Invoice #', 'Tenant', 'Plan', 'Amount', 'Status', 'Due Date'],
    'invoices-report', 'Platform Invoices Report'
  );

  const clearFilters = () => { setSearchTerm(''); setFilterPlan('all'); setFilterStatus('all'); setFilterDateFrom(''); setFilterDateTo(''); };
  const hasFilters = searchTerm || filterPlan !== 'all' || filterStatus !== 'all' || filterDateFrom || filterDateTo;

  // ─── Shared filter bar ───────────────────────────────────────────────────
  const FilterBar = () => (
    <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4">
      <div className="flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input type="text" placeholder="Search…" value={searchTerm} onChange={e => setSearchTerm(e.target.value)}
            className="w-full pl-9 pr-4 py-2 text-sm border border-slate-200 dark:border-slate-700 rounded-lg bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-2"
            style={{ '--tw-ring-color': primaryColor } as React.CSSProperties} />
        </div>
        <select value={filterPlan} onChange={e => setFilterPlan(e.target.value)}
          className="text-sm border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none">
          <option value="all">All Plans</option>
          <option value="standard">Standard</option>
          <option value="premium">Premium</option>
          <option value="enterprise">Enterprise</option>
        </select>
        <select value={filterStatus} onChange={e => setFilterStatus(e.target.value)}
          className="text-sm border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none">
          <option value="all">All Statuses</option>
          <option value="active">Active</option>
          <option value="past_due">Past Due</option>
          <option value="overdue">Overdue</option>
          <option value="pending">Pending</option>
          <option value="paid">Paid</option>
          <option value="canceled">Canceled</option>
        </select>
        {(tab === 'invoices') && (
          <div className="flex items-center gap-2">
            <Calendar className="w-4 h-4 text-slate-400" />
            <input type="date" value={filterDateFrom} onChange={e => setFilterDateFrom(e.target.value)}
              className="text-sm border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none" />
            <span className="text-slate-400 text-sm">to</span>
            <input type="date" value={filterDateTo} onChange={e => setFilterDateTo(e.target.value)}
              className="text-sm border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none" />
          </div>
        )}
        {hasFilters && (
          <button onClick={clearFilters} className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900 dark:hover:text-white px-3 py-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-800">
            <X className="w-4 h-4" /> Clear
          </button>
        )}
      </div>
    </div>
  );

  // ─── KPI cards (shared top row) ──────────────────────────────────────────
  const KpiCards = () => (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {[
        { label: 'Total MRR', value: fmt(totalMrr, 'M'), sub: 'Monthly recurring revenue', icon: <TrendingUp className="w-5 h-5" />, color: 'text-green-600 dark:text-green-400' },
        { label: 'Active Tenants', value: loadingRecords ? '—' : String(activeCount), sub: `${records.filter(r => r.status === 'past_due').length} past due`, icon: <Users className="w-5 h-5" />, color: 'text-blue-600 dark:text-blue-400' },
        { label: 'Total Collected', value: fmt(totalCollected, 'M'), sub: `${paidInvoices.length} paid invoices`, icon: <Receipt className="w-5 h-5" />, color: 'text-emerald-600 dark:text-emerald-400' },
        { label: 'Collection Rate', value: loadingInvoices ? '—' : `${collectionRate}%`, sub: `${invoices.filter(i => i.status === 'overdue').length} overdue`, icon: <Activity className="w-5 h-5" />, color: 'text-purple-600 dark:text-purple-400' },
      ].map(c => (
        <div key={c.label} className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-5">
          <div className="flex items-center justify-between mb-3">
            <span className="text-sm text-slate-500 dark:text-slate-400">{c.label}</span>
            <span className={c.color}>{c.icon}</span>
          </div>
          <div className={`text-2xl font-bold mb-0.5 ${c.color}`}>{c.value}</div>
          <div className="text-xs text-slate-400 dark:text-slate-500">{c.sub}</div>
        </div>
      ))}
    </div>
  );

  // ─── RENDER ───────────────────────────────────────────────────────────────
  const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: 'overview',  label: 'Overview',          icon: <BarChart3 className="w-4 h-4" /> },
    { id: 'accounts',  label: 'Billing Accounts',  icon: <Building2 className="w-4 h-4" /> },
    { id: 'invoices',  label: 'Invoices',           icon: <FileText className="w-4 h-4" /> },
    { id: 'accruals',  label: 'Accruals & Revenue', icon: <TrendingUp className="w-4 h-4" /> },
    { id: 'usage',     label: 'Usage & Metering',   icon: <Zap className="w-4 h-4" /> },
    { id: 'rates',     label: 'Rate Cards',         icon: <Layers className="w-4 h-4" /> },
    { id: 'rbac',      label: 'Access Control',     icon: <Shield className="w-4 h-4" /> },
    { id: 'plans',     label: 'Plan Catalogue',     icon: <CreditCard className="w-4 h-4" /> },
  ];

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      {/* Header */}
      <div className="border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900">
        <div className="container py-6">
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white flex items-center gap-3">
            <CreditCard className="w-7 h-7" style={{ color: primaryColor }} />
            Billing Platform
          </h1>
          <p className="text-slate-500 dark:text-slate-400 mt-1 text-sm">
            Global billing management — accounts, invoices, accruals, metering, rating, and access control
          </p>
        </div>
      </div>

      <div className="container py-8 space-y-6">

        <KpiCards />

        {/* Tab bar */}
        <div className="flex gap-1 overflow-x-auto border-b border-slate-200 dark:border-slate-800 pb-0">
          {TABS.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px whitespace-nowrap transition-colors ${
                tab === t.id ? 'border-current' : 'border-transparent text-slate-500 hover:text-slate-900 dark:hover:text-white'
              }`}
              style={tab === t.id ? { color: primaryColor, borderColor: primaryColor } : {}}>
              {t.icon}{t.label}
            </button>
          ))}
        </div>

        {/* ═══ OVERVIEW TAB ═══════════════════════════════════════════════════ */}
        {tab === 'overview' && (
          <div className="space-y-6">
            {/* Revenue trend */}
            <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6">
              <h3 className="text-base font-semibold text-slate-900 dark:text-white mb-5">30-Day Revenue Trend (₦K)</h3>
              <ResponsiveContainer width="100%" height={240}>
                <LineChart data={trendData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="date" stroke="#94a3b8" tick={{ fontSize: 11 }} />
                  <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} />
                  <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '8px', fontSize: '12px' }} labelStyle={{ color: '#f1f5f9' }} formatter={(v: number | undefined) => v != null ? `₦${v}K` : ''} />
                  <Line type="monotone" dataKey="mrr" stroke={primaryColor} strokeWidth={2.5} name="MRR" dot={false} />
                  <Line type="monotone" dataKey="collected" stroke="#10b981" strokeWidth={2} name="Collected" dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Plan distribution + Outstanding */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6">
                <h3 className="text-base font-semibold text-slate-900 dark:text-white mb-4">Plan Distribution</h3>
                <div className="space-y-3">
                  {(['standard', 'premium', 'enterprise'] as const).map(plan => {
                    const count = records.filter(r => r.plan === plan).length;
                    const pct = records.length > 0 ? (count / records.length) * 100 : 0;
                    const colors: Record<string, string> = { standard: '#10b981', premium: '#3b82f6', enterprise: '#8b5cf6' };
                    return (
                      <div key={plan}>
                        <div className="flex justify-between mb-1">
                          {planBadge(plan)}
                          <span className="text-sm font-semibold text-slate-700 dark:text-slate-300">{count} tenant{count !== 1 ? 's' : ''}</span>
                        </div>
                        <div className="h-1.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
                          <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, backgroundColor: colors[plan] }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6">
                <h3 className="text-base font-semibold text-slate-900 dark:text-white mb-4">Orchestrator Profiles</h3>
                {orchestratorProfiles.length === 0 ? (
                  <p className="text-sm text-slate-400">No profiles created yet. Profiles are auto-created on tenant onboarding.</p>
                ) : (
                  <div className="space-y-2">
                    {orchestratorProfiles.slice(0, 5).map(p => (
                      <div key={p.id} className="flex items-center justify-between py-2 border-b border-slate-100 dark:border-slate-800 last:border-0">
                        <div>
                          <div className="text-sm font-medium text-slate-900 dark:text-white font-mono">{p.tenant_id}</div>
                          <div className="text-xs text-slate-400 capitalize">{p.pricing_model}</div>
                        </div>
                        <div className="text-right">
                          <div className="text-sm font-semibold text-slate-900 dark:text-white">{fmt(p.monthly_fee)}</div>
                          {statusBadge(p.status)}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ═══ BILLING ACCOUNTS TAB ══════════════════════════════════════════ */}
        {tab === 'accounts' && (
          <div className="space-y-4">
            <FilterBar />
            <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
              <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800">
                <span className="text-sm text-slate-500">{filteredRecords.length} account{filteredRecords.length !== 1 ? 's' : ''}</span>
                <button onClick={exportRecords} className="flex items-center gap-2 text-sm px-3 py-1.5 border border-slate-200 dark:border-slate-700 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800">
                  <Download className="w-4 h-4" /> Export
                </button>
              </div>
              {loadingRecords ? (
                <div className="p-12 text-center"><Activity className="w-8 h-8 text-slate-400 animate-spin mx-auto mb-3" /><p className="text-sm text-slate-500">Loading…</p></div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800">
                      <tr>{['Tenant', 'Plan', 'Monthly Amount', 'Status', 'Billing Cycle', 'Next Invoice', ''].map(col => (
                        <th key={col} className="px-5 py-3 text-left font-semibold text-slate-700 dark:text-slate-300 whitespace-nowrap">{col}</th>
                      ))}</tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                      {filteredRecords.map(rec => (
                        <tr key={rec.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                          <td className="px-5 py-4">
                            <div className="font-semibold text-slate-900 dark:text-white">{rec.tenantName}</div>
                            <div className="text-xs text-slate-400 font-mono">{rec.tenantId}</div>
                          </td>
                          <td className="px-5 py-4">{planBadge(rec.plan)}</td>
                          <td className="px-5 py-4 font-semibold text-slate-900 dark:text-white">{fmt(rec.monthlyAmount)}</td>
                          <td className="px-5 py-4">{statusBadge(rec.status)}</td>
                          <td className="px-5 py-4 capitalize text-slate-600 dark:text-slate-400">{rec.billingCycle}</td>
                          <td className="px-5 py-4 text-slate-600 dark:text-slate-400">
                            {new Date(rec.nextInvoice).toLocaleDateString('en-NG', { day: 'numeric', month: 'short', year: 'numeric' })}
                          </td>
                          <td className="px-5 py-4">
                            <button onClick={() => { setEditingRecord(rec); setNewPlan(rec.plan); }}
                              className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-800">
                              <ArrowUpCircle className="w-3.5 h-3.5" /> Change Plan
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ═══ INVOICES TAB ══════════════════════════════════════════════════ */}
        {tab === 'invoices' && (
          <div className="space-y-4">
            <FilterBar />
            <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
              <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800">
                <span className="text-sm text-slate-500">{filteredInvoices.length} invoice{filteredInvoices.length !== 1 ? 's' : ''}</span>
                <div className="flex gap-2">
                  <button onClick={exportInvoicesExcel} className="flex items-center gap-2 text-sm px-3 py-1.5 border border-slate-200 dark:border-slate-700 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800"><Download className="w-4 h-4" /> Excel</button>
                  <button onClick={exportInvoicesPDF} className="flex items-center gap-2 text-sm px-3 py-1.5 border border-slate-200 dark:border-slate-700 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800"><Download className="w-4 h-4" /> PDF</button>
                </div>
              </div>
              {loadingInvoices ? (
                <div className="p-12 text-center"><Activity className="w-8 h-8 text-slate-400 animate-spin mx-auto mb-3" /></div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800">
                      <tr>{['Invoice #', 'Tenant', 'Plan', 'Amount', 'Status', 'Due Date', 'Paid At'].map(col => (
                        <th key={col} className="px-5 py-3 text-left font-semibold text-slate-700 dark:text-slate-300 whitespace-nowrap">{col}</th>
                      ))}</tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                      {filteredInvoices.map(inv => (
                        <tr key={inv.invoiceNumber} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                          <td className="px-5 py-4 font-mono text-slate-700 dark:text-slate-300">{inv.invoiceNumber}</td>
                          <td className="px-5 py-4 font-medium text-slate-900 dark:text-white">{inv.tenantId}</td>
                          <td className="px-5 py-4">{planBadge(inv.plan)}</td>
                          <td className="px-5 py-4 font-semibold text-slate-900 dark:text-white">{fmt(parseFloat(inv.amount))}</td>
                          <td className="px-5 py-4">{statusBadge(inv.status)}</td>
                          <td className="px-5 py-4 text-slate-600 dark:text-slate-400">{inv.dueDate}</td>
                          <td className="px-5 py-4 text-slate-600 dark:text-slate-400">{inv.paidAt ?? '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ═══ ACCRUALS & REVENUE TAB ════════════════════════════════════════ */}
        {tab === 'accruals' && (
          <div className="space-y-6">
            {loadingAccruals && (
              <div className="flex items-center gap-2 text-sm text-slate-500"><Activity className="w-4 h-4 animate-spin" /> Loading analytics data…</div>
            )}

            {/* Summary + Spike Detection */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Accrual Summary */}
              <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6">
                <h3 className="text-base font-semibold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                  <TrendingUp className="w-4 h-4" style={{ color: primaryColor }} /> Accrual Summary
                </h3>
                {accrualSummary ? (
                  <div className="space-y-4">
                    <div className="flex justify-between items-center p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
                      <span className="text-sm text-slate-600 dark:text-slate-400">Total Accrued</span>
                      <span className="font-bold text-lg text-slate-900 dark:text-white">{fmt(accrualSummary.total_accrued, 'M')}</span>
                    </div>
                    <div className="flex justify-between items-center p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
                      <span className="text-sm text-slate-600 dark:text-slate-400">Accrual Points</span>
                      <span className="font-bold text-slate-900 dark:text-white">{accrualSummary.accrual_count}</span>
                    </div>
                    {accrualSummary.breakdown?.map(b => (
                      <div key={b.meter_key} className="flex justify-between items-center p-3 bg-slate-50 dark:bg-slate-800 rounded-lg">
                        <span className="text-sm font-mono text-slate-600 dark:text-slate-400">{b.meter_key}</span>
                        <span className="font-semibold text-slate-900 dark:text-white">{fmt(b.total, 'M')}</span>
                      </div>
                    ))}
                  </div>
                ) : !loadingAccruals ? (
                  <p className="text-sm text-slate-400">No summary data available</p>
                ) : null}
              </div>

              {/* Spike Detection */}
              <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6">
                <h3 className="text-base font-semibold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-yellow-500" /> Spike Detection
                </h3>
                <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">
                  Compares latest accrual period against baseline average. Alerts when ratio exceeds threshold.
                </p>
                <div className="flex items-center gap-3 mb-4">
                  <label className="text-sm text-slate-600 dark:text-slate-400 shrink-0">Spike threshold</label>
                  <input type="number" step="0.1" min="1" value={spikeRatio} onChange={e => setSpikeRatio(e.target.value)}
                    className="w-24 px-3 py-1.5 text-sm border border-slate-200 dark:border-slate-700 rounded-lg bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none" />
                  <span className="text-sm text-slate-400">×</span>
                  <button onClick={handleDetectSpike} disabled={detectingSpike}
                    className="flex items-center gap-2 px-4 py-1.5 text-sm font-medium text-white rounded-lg disabled:opacity-50"
                    style={{ backgroundColor: primaryColor }}>
                    {detectingSpike ? <Activity className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                    Detect
                  </button>
                </div>
                {spikeAlert && (
                  <div className={`rounded-lg p-4 border ${spikeAlert.alert ? 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800' : 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800'}`}>
                    <div className="flex items-center gap-2 mb-2">
                      {spikeAlert.alert ? <ShieldAlert className="w-5 h-5 text-red-600" /> : <ShieldCheck className="w-5 h-5 text-green-600" />}
                      <span className={`font-semibold text-sm ${spikeAlert.alert ? 'text-red-700 dark:text-red-300' : 'text-green-700 dark:text-green-300'}`}>
                        {spikeAlert.alert ? `${spikeAlert.severity?.toUpperCase()} — Spike Detected` : 'No Spike Detected'}
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-3 text-xs">
                      <div><div className="text-slate-500">Baseline</div><div className="font-mono font-semibold">{fmt(spikeAlert.baseline, 'M')}</div></div>
                      <div><div className="text-slate-500">Latest</div><div className="font-mono font-semibold">{fmt(spikeAlert.latest, 'M')}</div></div>
                      <div><div className="text-slate-500">Ratio</div><div className="font-mono font-semibold">{spikeAlert.ratio?.toFixed(2)}×</div></div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Accrual Points table */}
            <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800">
                <h3 className="text-base font-semibold text-slate-900 dark:text-white">Accrual Points</h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800">
                    <tr>{['Tenant', 'Period', 'Meter Key', 'Txn Count', 'Accrued', 'Status'].map(col => (
                      <th key={col} className="px-5 py-3 text-left font-semibold text-slate-700 dark:text-slate-300">{col}</th>
                    ))}</tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {accruals.map(a => (
                      <tr key={a.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                        <td className="px-5 py-3 font-mono text-xs text-slate-600 dark:text-slate-400">{a.tenant_id}</td>
                        <td className="px-5 py-3 text-slate-700 dark:text-slate-300">{a.billing_period}</td>
                        <td className="px-5 py-3 font-mono text-xs text-slate-600 dark:text-slate-400">{a.meter_key}</td>
                        <td className="px-5 py-3 text-slate-700 dark:text-slate-300">{a.transaction_count?.toLocaleString()}</td>
                        <td className="px-5 py-3 font-semibold text-slate-900 dark:text-white">{fmt(a.accrued_amount, 'M')}</td>
                        <td className="px-5 py-3">{statusBadge(a.status)}</td>
                      </tr>
                    ))}
                    {!loadingAccruals && accruals.length === 0 && (
                      <tr><td colSpan={6} className="px-5 py-8 text-center text-sm text-slate-400">No accrual data</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Revenue Reports */}
            <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800">
                <h3 className="text-base font-semibold text-slate-900 dark:text-white">Quarterly Revenue Reports</h3>
              </div>
              {revenueReports.length > 0 && (
                <div className="p-6">
                  <ResponsiveContainer width="100%" height={200}>
                    <BarChart data={revenueReports.map(r => ({
                      period: r.period,
                      Fees: Math.round(r.fee_income / 1e9 * 100) / 100,
                      Interest: Math.round(r.interest_income / 1e9 * 100) / 100,
                      FX: Math.round(r.fx_income / 1e9 * 100) / 100,
                      Commission: Math.round(r.commission_income / 1e9 * 100) / 100,
                    }))}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                      <XAxis dataKey="period" stroke="#94a3b8" tick={{ fontSize: 11 }} />
                      <YAxis stroke="#94a3b8" tick={{ fontSize: 11 }} unit="B" />
                      <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '8px', fontSize: '12px' }} formatter={(v: number | undefined) => v != null ? `₦${v}B` : ''} />
                      <Bar dataKey="Fees" stackId="a" fill="#3b82f6" />
                      <Bar dataKey="Interest" stackId="a" fill="#8b5cf6" />
                      <Bar dataKey="FX" stackId="a" fill="#10b981" />
                      <Bar dataKey="Commission" stackId="a" fill="#f59e0b" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800">
                    <tr>{['Period', 'Total Revenue', 'Fee Income', 'Interest', 'FX', 'Commission'].map(col => (
                      <th key={col} className="px-5 py-3 text-left font-semibold text-slate-700 dark:text-slate-300">{col}</th>
                    ))}</tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {revenueReports.map(r => (
                      <tr key={r.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                        <td className="px-5 py-3 font-semibold text-slate-900 dark:text-white">{r.period}</td>
                        <td className="px-5 py-3 font-bold" style={{ color: primaryColor }}>{fmt(r.total_revenue, 'M')}</td>
                        <td className="px-5 py-3 text-slate-600 dark:text-slate-400">{fmt(r.fee_income, 'M')}</td>
                        <td className="px-5 py-3 text-slate-600 dark:text-slate-400">{fmt(r.interest_income, 'M')}</td>
                        <td className="px-5 py-3 text-slate-600 dark:text-slate-400">{fmt(r.fx_income, 'M')}</td>
                        <td className="px-5 py-3 text-slate-600 dark:text-slate-400">{fmt(r.commission_income, 'M')}</td>
                      </tr>
                    ))}
                    {!loadingAccruals && revenueReports.length === 0 && (
                      <tr><td colSpan={6} className="px-5 py-8 text-center text-sm text-slate-400">No revenue reports</td></tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* ═══ USAGE & METERING TAB ══════════════════════════════════════════ */}
        {tab === 'usage' && (
          <div className="space-y-6">
            {/* Stats banner */}
            {ingestorStats && (
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-5">
                  <div className="text-sm text-slate-500 mb-1">Total Events Ingested</div>
                  <div className="text-2xl font-bold" style={{ color: primaryColor }}>{ingestorStats.total_ingested?.toLocaleString() ?? '—'}</div>
                </div>
                <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-5">
                  <div className="text-sm text-slate-500 mb-1">Kafka Topics</div>
                  <div className="text-sm font-mono text-slate-700 dark:text-slate-300 mt-2">
                    {ingestorStats.topics?.join(', ') ?? 'billing_ingestor.events, billing_ingestor.audit'}
                  </div>
                </div>
              </div>
            )}

            {/* Ingest form */}
            <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6">
              <h3 className="text-base font-semibold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                <Zap className="w-4 h-4" style={{ color: primaryColor }} /> Ingest Usage Event
              </h3>
              <p className="text-xs text-slate-500 mb-4">
                Manually ingest a metering event — calls <code className="font-mono bg-slate-100 dark:bg-slate-800 px-1 rounded">POST /billing-aggregator/billing/ledger</code>
              </p>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
                {[
                  { label: 'Tenant ID', key: 'tenantId', type: 'select', options: SEED_TENANT_IDS },
                  { label: 'Source Service', key: 'sourceService', type: 'text', placeholder: 'payment-hub' },
                  { label: 'Event Type', key: 'eventType', type: 'select', options: ['transfer_posted', 'api_call', 'customer_created', 'settlement_finalised'] },
                  { label: 'Meter Key', key: 'meterKey', type: 'select', options: ['transfer_posted', 'api_call', 'customer', 'operations'] },
                  { label: 'Product Key', key: 'productKey', type: 'select', options: ['payments', 'customer', 'operations'] },
                  { label: 'Quantity', key: 'quantity', type: 'number', placeholder: '1' },
                ].map(field => (
                  <div key={field.key}>
                    <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">{field.label}</label>
                    {field.type === 'select' ? (
                      <select value={(ingestForm as any)[field.key]} onChange={e => setIngestForm(prev => ({ ...prev, [field.key]: e.target.value }))}
                        className="w-full px-3 py-2 text-sm border border-slate-200 dark:border-slate-700 rounded-lg bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none">
                        {field.options?.map(o => <option key={o} value={o}>{o}</option>)}
                      </select>
                    ) : (
                      <input type={field.type ?? 'text'} value={(ingestForm as any)[field.key]} placeholder={field.placeholder}
                        onChange={e => setIngestForm(prev => ({ ...prev, [field.key]: e.target.value }))}
                        className="w-full px-3 py-2 text-sm border border-slate-200 dark:border-slate-700 rounded-lg bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none" />
                    )}
                  </div>
                ))}
              </div>
              <button onClick={handleIngestEvent} disabled={ingesting}
                className="inline-flex items-center gap-2 px-5 py-2 text-sm font-medium text-white rounded-lg disabled:opacity-50"
                style={{ backgroundColor: primaryColor }}>
                {ingesting ? <Activity className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                {ingesting ? 'Ingesting…' : 'Ingest Event'}
              </button>
            </div>

            {/* Events table */}
            <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
              <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800">
                <h3 className="text-base font-semibold text-slate-900 dark:text-white">Ingested Events</h3>
                <button onClick={() => { setLoadingUsage(true); apiClient.get('/billing-aggregator/billing/ledger').then(r => { setUsageEvents(r.data?.items ?? r.data?.events ?? []); }).catch(() => {}).finally(() => setLoadingUsage(false)); }}
                  className="flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-900 dark:hover:text-white">
                  <RefreshCw className="w-4 h-4" /> Refresh
                </button>
              </div>
              {loadingUsage ? (
                <div className="p-8 text-center"><Activity className="w-6 h-6 animate-spin text-slate-400 mx-auto" /></div>
              ) : usageEvents.length === 0 ? (
                <div className="p-8 text-center text-sm text-slate-400">No events yet. Ingest one above.</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800">
                      <tr>{['Event ID', 'Tenant', 'Source', 'Event Type', 'Meter Key', 'Qty', 'Timestamp'].map(col => (
                        <th key={col} className="px-4 py-3 text-left font-semibold text-slate-700 dark:text-slate-300 whitespace-nowrap">{col}</th>
                      ))}</tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                      {usageEvents.map((e, i) => (
                        <tr key={e.id ?? i} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                          <td className="px-4 py-3 font-mono text-xs text-slate-500">{e.id?.slice(0, 16) ?? '—'}</td>
                          <td className="px-4 py-3 font-mono text-xs text-slate-600 dark:text-slate-400">{e.tenantId}</td>
                          <td className="px-4 py-3 text-slate-600 dark:text-slate-400">{e.sourceService}</td>
                          <td className="px-4 py-3 font-mono text-xs text-slate-600 dark:text-slate-400">{e.eventType}</td>
                          <td className="px-4 py-3 font-mono text-xs text-slate-600 dark:text-slate-400">{e.meterKey}</td>
                          <td className="px-4 py-3 font-semibold text-slate-900 dark:text-white">{e.quantity}</td>
                          <td className="px-4 py-3 text-xs text-slate-500">{e.eventTimestamp ? new Date(e.eventTimestamp).toLocaleString() : '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ═══ RATE CARDS TAB ════════════════════════════════════════════════ */}
        {tab === 'rates' && (
          <div className="space-y-6">
            {/* Rate Cards list */}
            <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800">
                <h3 className="text-base font-semibold text-slate-900 dark:text-white">Rate Cards</h3>
                <p className="text-xs text-slate-400 mt-0.5">Source: <code className="font-mono bg-slate-100 dark:bg-slate-800 px-1 rounded">GET /billing-aggregator/billing/rate-cards</code></p>
              </div>
              {loadingRates ? (
                <div className="p-8 text-center"><Activity className="w-6 h-6 animate-spin text-slate-400 mx-auto" /></div>
              ) : rateCards.length === 0 ? (
                <div className="p-8 text-center text-sm text-slate-400">No rate cards found</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800">
                      <tr>{['Rate Card ID', 'Tenant', 'Meter Key', 'Product Key', 'Unit Rate', 'Currency'].map(col => (
                        <th key={col} className="px-5 py-3 text-left font-semibold text-slate-700 dark:text-slate-300">{col}</th>
                      ))}</tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                      {rateCards.map(rc => (
                        <tr key={rc.id} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                          <td className="px-5 py-3 font-mono text-xs text-slate-500">{rc.id}</td>
                          <td className="px-5 py-3 font-mono text-xs text-slate-600 dark:text-slate-400">{rc.tenant_id || '—'}</td>
                          <td className="px-5 py-3 font-mono text-xs text-slate-600 dark:text-slate-400">{rc.meter_key}</td>
                          <td className="px-5 py-3 font-mono text-xs text-slate-600 dark:text-slate-400">{rc.product_key}</td>
                          <td className="px-5 py-3 font-semibold text-slate-900 dark:text-white">₦{rc.amount?.toFixed(2)}</td>
                          <td className="px-5 py-3 text-slate-600 dark:text-slate-400">{rc.currency}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* Rate Calculator */}
            <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6">
              <h3 className="text-base font-semibold text-slate-900 dark:text-white mb-4 flex items-center gap-2">
                <Sparkles className="w-4 h-4" style={{ color: primaryColor }} /> Rate Calculator
              </h3>
              <p className="text-xs text-slate-500 mb-4">
                Calculate billable amount for a given meter key and quantity — calls <code className="font-mono bg-slate-100 dark:bg-slate-800 px-1 rounded">POST /billing-aggregator/billing/rate</code>
              </p>
              <div className="flex flex-wrap gap-3 items-end mb-4">
                <div>
                  <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">Meter Key</label>
                  <select value={rateForm.meterKey} onChange={e => setRateForm(p => ({ ...p, meterKey: e.target.value }))}
                    className="px-3 py-2 text-sm border border-slate-200 dark:border-slate-700 rounded-lg bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none">
                    <option value="transfer_posted">transfer_posted (₦25/unit)</option>
                    <option value="api_call">api_call (₦0.50/unit)</option>
                    <option value="other">other (₦1/unit)</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">Quantity</label>
                  <input type="number" min="1" value={rateForm.quantity} onChange={e => setRateForm(p => ({ ...p, quantity: e.target.value }))}
                    className="w-28 px-3 py-2 text-sm border border-slate-200 dark:border-slate-700 rounded-lg bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none" />
                </div>
                <button onClick={handleCalculateRate} disabled={calculating}
                  className="inline-flex items-center gap-2 px-5 py-2 text-sm font-medium text-white rounded-lg disabled:opacity-50"
                  style={{ backgroundColor: primaryColor }}>
                  {calculating ? <Activity className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                  Calculate
                </button>
              </div>
              {rateResult && (
                <div className="grid grid-cols-3 gap-4 p-4 bg-slate-50 dark:bg-slate-800 rounded-lg">
                  <div className="text-center">
                    <div className="text-xs text-slate-500 mb-1">Billable Units</div>
                    <div className="text-xl font-bold text-slate-900 dark:text-white">{rateResult.billable_units?.toLocaleString()}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-xs text-slate-500 mb-1">Unit Rate</div>
                    <div className="text-xl font-bold text-slate-900 dark:text-white">₦{rateResult.unit_rate?.toFixed(2)}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-xs text-slate-500 mb-1">Amount Accrued</div>
                    <div className="text-xl font-bold" style={{ color: primaryColor }}>{fmt(rateResult.amount_accrued)}</div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ═══ ACCESS CONTROL TAB ════════════════════════════════════════════ */}
        {tab === 'rbac' && (
          <div className="space-y-6">
            {/* Enforce form */}
            <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6">
              <h3 className="text-base font-semibold text-slate-900 dark:text-white mb-2 flex items-center gap-2">
                <Shield className="w-4 h-4" style={{ color: primaryColor }} /> Enforce RBAC Policy
              </h3>
              <p className="text-xs text-slate-500 mb-4">
                Check whether an actor has a given billing permission — calls <code className="font-mono bg-slate-100 dark:bg-slate-800 px-1 rounded">POST /billing-aggregator/billing/rbac/enforce</code>
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
                <div>
                  <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">Tenant ID</label>
                  <select value={rbacForm.tenantId} onChange={e => setRbacForm(p => ({ ...p, tenantId: e.target.value }))}
                    className="w-full px-3 py-2 text-sm border border-slate-200 dark:border-slate-700 rounded-lg bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none">
                    {SEED_TENANT_IDS.map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">Actor ID</label>
                  <input type="text" value={rbacForm.actorId} onChange={e => setRbacForm(p => ({ ...p, actorId: e.target.value }))}
                    className="w-full px-3 py-2 text-sm border border-slate-200 dark:border-slate-700 rounded-lg bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">Role</label>
                  <select value={rbacForm.role} onChange={e => setRbacForm(p => ({ ...p, role: e.target.value }))}
                    className="w-full px-3 py-2 text-sm border border-slate-200 dark:border-slate-700 rounded-lg bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none">
                    <option value="viewer">viewer</option>
                    <option value="agent">agent</option>
                    <option value="manager">manager</option>
                    <option value="admin">admin</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">Permission</label>
                  <select value={rbacForm.permission} onChange={e => setRbacForm(p => ({ ...p, permission: e.target.value }))}
                    className="w-full px-3 py-2 text-sm border border-slate-200 dark:border-slate-700 rounded-lg bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none">
                    <option value="read:billing">read:billing</option>
                    <option value="write:billing">write:billing</option>
                    <option value="admin:billing">admin:billing</option>
                    <option value="view:invoices">view:invoices</option>
                    <option value="manage:plans">manage:plans</option>
                  </select>
                </div>
              </div>
              <button onClick={handleEnforceRbac} disabled={enforcing}
                className="inline-flex items-center gap-2 px-5 py-2 text-sm font-medium text-white rounded-lg disabled:opacity-50"
                style={{ backgroundColor: primaryColor }}>
                {enforcing ? <Activity className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />}
                {enforcing ? 'Checking…' : 'Enforce'}
              </button>
            </div>

            {/* Decision log */}
            <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800">
                <h3 className="text-base font-semibold text-slate-900 dark:text-white">Decision Audit Log</h3>
                <p className="text-xs text-slate-400 mt-0.5">Session decisions — reset on page reload</p>
              </div>
              {rbacDecisions.length === 0 ? (
                <div className="p-8 text-center text-sm text-slate-400">No decisions yet. Use the form above.</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 dark:bg-slate-800/60 border-b border-slate-200 dark:border-slate-800">
                      <tr>{['Decision ID', 'Tenant', 'Actor', 'Permission', 'Decision'].map(col => (
                        <th key={col} className="px-5 py-3 text-left font-semibold text-slate-700 dark:text-slate-300">{col}</th>
                      ))}</tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                      {rbacDecisions.map((d, i) => (
                        <tr key={d.id ?? i} className="hover:bg-slate-50 dark:hover:bg-slate-800/40">
                          <td className="px-5 py-3 font-mono text-xs text-slate-500">{d.id ?? '—'}</td>
                          <td className="px-5 py-3 font-mono text-xs text-slate-600 dark:text-slate-400">{d.tenant_id}</td>
                          <td className="px-5 py-3 text-slate-600 dark:text-slate-400">{d.actor_id}</td>
                          <td className="px-5 py-3 font-mono text-xs text-slate-600 dark:text-slate-400">{d.permission}</td>
                          <td className="px-5 py-3">{statusBadge(d.decision)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ═══ PLAN CATALOGUE TAB ════════════════════════════════════════════ */}
        {tab === 'plans' && (
          <div className="space-y-6">
            {/* Header row */}
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-semibold text-slate-900 dark:text-white">Plan Catalogue</h3>
                <p className="text-xs text-slate-400 mt-0.5">Create and manage subscription plans available to tenants</p>
              </div>
              {!showPlanForm && (
                <button
                  onClick={() => { cancelPlanForm(); setShowPlanForm(true); }}
                  className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white rounded-lg"
                  style={{ backgroundColor: primaryColor }}
                >
                  + New Plan
                </button>
              )}
            </div>

            {/* Create / Edit form */}
            {showPlanForm && (
              <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6 space-y-5">
                <h4 className="text-sm font-semibold text-slate-900 dark:text-white">
                  {editingPlan ? `Edit "${editingPlan.label}"` : 'New Plan'}
                </h4>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">Name <span className="text-slate-400">(machine key, e.g. "gold")</span></label>
                    <input
                      value={planForm.name}
                      onChange={e => setPlanForm(p => ({ ...p, name: e.target.value.toLowerCase().replace(/\s+/g, '_') }))}
                      placeholder="gold_partner"
                      className="w-full px-3 py-2 text-sm border border-slate-200 dark:border-slate-700 rounded-lg bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-2 font-mono"
                      style={{ '--tw-ring-color': primaryColor } as React.CSSProperties}
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">Display Label</label>
                    <input
                      value={planForm.label}
                      onChange={e => setPlanForm(p => ({ ...p, label: e.target.value }))}
                      placeholder="Gold Partner"
                      className="w-full px-3 py-2 text-sm border border-slate-200 dark:border-slate-700 rounded-lg bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-2"
                      style={{ '--tw-ring-color': primaryColor } as React.CSSProperties}
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">Monthly Fee (₦)</label>
                    <input
                      type="number" min="0" step="50000"
                      value={planForm.monthlyFee}
                      onChange={e => setPlanForm(p => ({ ...p, monthlyFee: e.target.value }))}
                      placeholder="20000000"
                      className="w-full px-3 py-2 text-sm border border-slate-200 dark:border-slate-700 rounded-lg bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none focus:ring-2"
                      style={{ '--tw-ring-color': primaryColor } as React.CSSProperties}
                    />
                    {planForm.monthlyFee && (
                      <p className="text-xs text-slate-400 mt-1">
                        = ₦{Number(planForm.monthlyFee).toLocaleString()} / month
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-3 pt-5">
                    <input
                      id="popular-toggle"
                      type="checkbox"
                      checked={planForm.popular}
                      onChange={e => setPlanForm(p => ({ ...p, popular: e.target.checked }))}
                      className="w-4 h-4 rounded accent-current"
                      style={{ accentColor: primaryColor }}
                    />
                    <label htmlFor="popular-toggle" className="text-sm text-slate-700 dark:text-slate-300 cursor-pointer">
                      Mark as "Most Popular"
                    </label>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">Description</label>
                  <textarea
                    value={planForm.description}
                    onChange={e => setPlanForm(p => ({ ...p, description: e.target.value }))}
                    rows={2}
                    placeholder="Short description shown on the plan card"
                    className="w-full px-3 py-2 text-sm border border-slate-200 dark:border-slate-700 rounded-lg bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-white focus:outline-none resize-none"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="text-xs font-medium text-slate-600 dark:text-slate-400">
                      Features
                      {planForm.features.length > 0 && (
                        <span className="ml-2 px-1.5 py-0.5 rounded-full text-xs font-semibold bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300">
                          {planForm.features.length} selected
                        </span>
                      )}
                    </label>
                    {planForm.features.length > 0 && (
                      <button
                        type="button"
                        onClick={() => setPlanForm(p => ({ ...p, features: [] }))}
                        className="text-xs text-slate-400 hover:text-red-500"
                      >
                        Clear all
                      </button>
                    )}
                  </div>
                  {loadingGlobalFeatures ? (
                    <div className="text-xs text-slate-400 py-4 text-center">Loading features…</div>
                  ) : globalFeatures.length === 0 ? (
                    <div className="text-xs text-slate-400 py-4 text-center">No features available</div>
                  ) : (
                    <div className="max-h-48 overflow-y-auto border border-slate-200 dark:border-slate-700 rounded-lg p-3 grid grid-cols-2 gap-x-4 gap-y-2">
                      {globalFeatures.map(feat => {
                        const checked = planForm.features.includes(feat.name);
                        return (
                          <label key={feat.name} className="flex items-center gap-2 cursor-pointer group">
                            <input
                              type="checkbox"
                              checked={checked}
                              onChange={() => setPlanForm(p => ({
                                ...p,
                                features: checked
                                  ? p.features.filter(f => f !== feat.name)
                                  : [...p.features, feat.name],
                              }))}
                              className="w-3.5 h-3.5 rounded accent-blue-600 cursor-pointer"
                            />
                            <span className="text-xs text-slate-700 dark:text-slate-300 group-hover:text-slate-900 dark:group-hover:text-white capitalize">
                              {feat.name.replace(/_/g, ' ')}
                            </span>
                          </label>
                        );
                      })}
                    </div>
                  )}
                </div>

                <div className="flex gap-3 pt-2">
                  <button onClick={cancelPlanForm} className="px-4 py-2 text-sm font-medium border border-slate-200 dark:border-slate-700 rounded-lg text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800">
                    Cancel
                  </button>
                  <button
                    onClick={editingPlan ? handleUpdatePlan : handleCreatePlan}
                    disabled={savingPlanDef}
                    className="px-5 py-2 text-sm font-medium text-white rounded-lg disabled:opacity-50 flex items-center gap-2"
                    style={{ backgroundColor: primaryColor }}
                  >
                    {savingPlanDef ? <Activity className="w-4 h-4 animate-spin" /> : null}
                    {savingPlanDef ? 'Saving…' : editingPlan ? 'Save Changes' : 'Create Plan'}
                  </button>
                </div>
              </div>
            )}

            {/* Plan cards */}
            {loadingPlans ? (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                {[1, 2, 3].map(i => (
                  <div key={i} className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6 animate-pulse space-y-3">
                    <div className="h-5 w-24 bg-slate-100 dark:bg-slate-800 rounded" />
                    <div className="h-8 w-20 bg-slate-100 dark:bg-slate-800 rounded" />
                    <div className="space-y-2">{[1,2,3].map(j => <div key={j} className="h-3 bg-slate-100 dark:bg-slate-800 rounded" />)}</div>
                  </div>
                ))}
              </div>
            ) : plans.length === 0 && !showPlanForm ? (
              <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-16 text-center">
                <CreditCard className="w-10 h-10 text-slate-300 dark:text-slate-600 mx-auto mb-3" />
                <p className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-1">No plans yet</p>
                <p className="text-xs text-slate-400 mb-4">Create the first plan to make it available to tenants</p>
                <button
                  onClick={() => setShowPlanForm(true)}
                  className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium text-white rounded-lg"
                  style={{ backgroundColor: primaryColor }}
                >
                  + Create First Plan
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                {plans.map(plan => (
                  <div key={plan.id} className={`relative bg-white dark:bg-slate-900 rounded-xl border-2 p-6 ${plan.popular ? 'border-blue-400' : 'border-slate-200 dark:border-slate-800'}`}>
                    {plan.popular && (
                      <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                        <span className="px-3 py-0.5 rounded-full text-xs font-bold text-white" style={{ backgroundColor: primaryColor }}>
                          Most Popular
                        </span>
                      </div>
                    )}

                    <div className="flex items-start justify-between mb-3 mt-1">
                      <div>
                        <h4 className="text-base font-bold text-slate-900 dark:text-white">{plan.label}</h4>
                        <span className="font-mono text-xs text-slate-400">{plan.name}</span>
                      </div>
                      <div className="flex gap-1">
                        <button
                          onClick={() => startEditPlan(plan)}
                          className="p-1.5 text-slate-400 hover:text-slate-700 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg"
                          title="Edit plan"
                        >
                          <ArrowUpCircle className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDeletePlan(plan)}
                          className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg"
                          title="Delete plan"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    </div>

                    <div className="mb-4">
                      <span className="text-2xl font-bold text-slate-900 dark:text-white">
                        ₦{(plan.monthlyFee / 1000).toFixed(0)}K
                      </span>
                      <span className="text-sm text-slate-400"> / month</span>
                    </div>

                    {plan.description && (
                      <p className="text-xs text-slate-500 dark:text-slate-400 mb-4">{plan.description}</p>
                    )}

                    {plan.features.length > 0 && (
                      <ul className="space-y-1.5">
                        {plan.features.map((f, i) => (
                          <li key={i} className="flex items-start gap-2 text-xs text-slate-600 dark:text-slate-400">
                            <CheckCircle className="w-3 h-3 text-green-500 mt-0.5 flex-shrink-0" />
                            {f}
                          </li>
                        ))}
                      </ul>
                    )}

                    <div className="mt-4 pt-3 border-t border-slate-100 dark:border-slate-800 text-xs text-slate-400">
                      Updated {new Date(plan.updatedAt).toLocaleDateString('en-NG')}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Change Plan Modal (uses live plans from backend) ────────────────── */}
      {editingRecord && (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-slate-900 rounded-xl shadow-2xl p-6 max-w-md w-full border border-slate-200 dark:border-slate-800">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold text-slate-900 dark:text-white">Change Billing Plan</h3>
              <button onClick={() => setEditingRecord(null)} className="p-1 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-lg">
                <X className="w-4 h-4 text-slate-500" />
              </button>
            </div>
            <p className="text-sm text-slate-500 mb-4">
              Updating plan for <strong className="text-slate-900 dark:text-white">{editingRecord.tenantName}</strong>
            </p>
            {plans.length === 0 ? (
              <p className="text-sm text-slate-400 mb-6">No plans available. Create plans in the Plan Catalogue tab first.</p>
            ) : (
              <div className="space-y-2 mb-6">
                {plans.map(plan => (
                  <label key={plan.id} onClick={() => setNewPlan(plan.name)}
                    className={`flex items-center justify-between p-3 rounded-lg border-2 cursor-pointer transition-all ${newPlan === plan.name ? 'border-current' : 'border-slate-200 dark:border-slate-700'}`}
                    style={newPlan === plan.name ? { borderColor: primaryColor } : {}}>
                    {planBadge(plan.name)}
                    <div className="text-right">
                      <div className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                        ₦{(plan.monthlyFee / 1000).toFixed(0)}K / mo
                      </div>
                      {plan.label !== plan.name && (
                        <div className="text-xs text-slate-400">{plan.label}</div>
                      )}
                    </div>
                  </label>
                ))}
              </div>
            )}
            <div className="flex gap-3">
              <button onClick={() => setEditingRecord(null)} className="flex-1 py-2 rounded-lg border border-slate-200 dark:border-slate-700 text-sm font-medium text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800">Cancel</button>
              <button onClick={handleSaveTenantPlan} disabled={savingTenantPlan || !newPlan || newPlan === editingRecord.plan}
                className="flex-1 py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50"
                style={{ backgroundColor: primaryColor }}>
                {savingTenantPlan ? 'Saving…' : 'Confirm Change'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
