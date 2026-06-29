import { useState } from "react";
import { toast } from "sonner";
import {
  Banknote,
  Search,
  RefreshCw,
  Plus,
  Eye,
  CheckCircle,
  XCircle,
  Clock,
  TrendingUp,
} from "lucide-react";

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-500/20 text-yellow-400",
  approved: "bg-emerald-500/20 text-emerald-400",
  disbursed: "bg-blue-500/20 text-blue-400",
  repaying: "bg-purple-500/20 text-purple-400",
  completed: "bg-zinc-500/20 text-zinc-400",
  defaulted: "bg-red-500/20 text-red-400",
  rejected: "bg-red-500/20 text-red-400",
};

export default function AgentLoanFacilityPage() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedLoan, setSelectedLoan] = useState<any>(null);
  const [showApply, setShowApply] = useState(false);
  const [applyForm, setApplyForm] = useState({
    agent_id: "",
    principal_amount: "",
    tenure_months: "6",
    purpose: "",
  });

  const loansQuery = {data: [], isLoading: false, refetch: () => {}};
  const statsQuery = {data: null, isLoading: false, refetch: () => {}};
  const applyMutation = {mutate: () => toast.success("Feature coming soon"), isPending: false};
  const approveMutation = {mutate: () => toast.success("Feature coming soon"), isPending: false};
  const rejectMutation = {mutate: () => toast.success("Feature coming soon"), isPending: false};

  const loans: any[] = [];
  const stats: any = statsQuery.data;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Banknote className="h-6 w-6 text-emerald-400" /> Agent Loan Facility
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            Loan applications, credit scoring, disbursement, and repayment tracking
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => { loansQuery.refetch(); statsQuery.refetch(); }}
            className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg text-sm"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          <button
            onClick={() => setShowApply(true)}
            className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm"
          >
            <Plus className="h-4 w-4" /> New Application
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        {[
          { label: "Total Loans", value: stats?.totalLoans ?? 0, icon: Banknote, color: "text-emerald-400" },
          { label: "Total Disbursed", value: `₦${((stats?.totalDisbursed ?? 0) / 1000000).toFixed(1)}M`, icon: TrendingUp, color: "text-blue-400" },
          { label: "Pending", value: stats?.pending ?? 0, icon: Clock, color: "text-yellow-400" },
          { label: "Active", value: stats?.active ?? 0, icon: CheckCircle, color: "text-purple-400" },
          { label: "Defaulted", value: stats?.defaulted ?? 0, icon: XCircle, color: "text-red-400" },
        ].map((s: any) => (
          <div key={s.label} className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl p-4">
            <div className="flex items-center gap-2">
              <s.icon className={`h-4 w-4 ${s.color}`} />
              <p className="text-xs text-zinc-400 uppercase">{s.label}</p>
            </div>
            <p className="text-2xl font-bold text-white mt-2">{s.value}</p>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
          <input
            type="text"
            placeholder="Search loans..."
            value={search}
            onChange={(e: any) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e: any) => setStatusFilter(e.target.value)}
          className="px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white"
        >
          <option value="all">All Statuses</option>
          {Object.keys(STATUS_COLORS).map((s: any) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
      </div>

      <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-700/50 text-zinc-400">
              <th className="text-left p-4 font-medium">Agent ID</th>
              <th className="text-left p-4 font-medium">Principal</th>
              <th className="text-left p-4 font-medium">Interest Rate</th>
              <th className="text-left p-4 font-medium">Tenure</th>
              <th className="text-left p-4 font-medium">Status</th>
              <th className="text-left p-4 font-medium">Purpose</th>
              <th className="text-left p-4 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td colSpan={7} className="p-8 text-center text-zinc-500">No loans found</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}
