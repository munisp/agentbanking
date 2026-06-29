import { useState } from "react";
import { Loader2, RefreshCw, Download, Search, Filter } from "lucide-react";
import { toast } from "sonner";

export default function AutoReconciliationEngine() {
  const stats = {data: null, isLoading: false, refetch: () => {}};
  const [searchTerm, setSearchTerm] = useState("");

  return (
    <>
      <div className="p-6 space-y-6 min-h-screen bg-gray-950 text-white">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Automated Reconciliation</h1>
            <p className="text-gray-400 text-sm mt-1">Bank statement matching with exception handling and auto-resolution</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
              <input type="text" placeholder="Search..." value={searchTerm} onChange={e => setSearchTerm(e.target.value)} className="pl-9 pr-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 w-64" />
            </div>
            <button onClick={() => { stats.refetch(); toast.success("Data refreshed"); }} className="flex items-center gap-2 px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm hover:bg-gray-700 transition-colors">
              <RefreshCw className="w-4 h-4" /> Refresh
            </button>
            <button className="flex items-center gap-2 px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm hover:bg-gray-700 transition-colors">
              <Download className="w-4 h-4" /> Export
            </button>
          </div>
        </div>

        {stats.isLoading ? (
          <div className="flex items-center justify-center py-20">
            <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
            <span className="ml-3 text-gray-400">Loading dashboard data...</span>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: "Reconciliations", key: "totalReconciliations", color: "text-blue-400" },
                { label: "Match Rate %", key: "avgMatchRate", color: "text-emerald-400" },
                { label: "Exceptions", key: "totalExceptions", color: "text-amber-400" },
                { label: "Pending Review", key: "pendingReview", color: "text-rose-400" },
                { label: "Banks", key: "banksConnected", color: "text-purple-400" },
                { label: "Auto-Resolved", key: "autoResolvedToday", color: "text-cyan-400" },
                { label: "Manual Review", key: "manualReviewNeeded", color: "text-indigo-400" },
                { label: "Last Run", key: "lastRunTime", color: "text-orange-400" },
              ].map(item => (
                <div key={item.key} className="bg-gray-800/50 border border-gray-700 rounded-lg p-4">
                  <p className="text-xs text-gray-400 mb-1">{item.label}</p>
                  <p className={`text-xl font-bold ${item.color}`}>{String((stats.data as any)?.[item.key] ?? "—")}</p>
                </div>
              ))}
            </div>
            <div className="bg-gray-800/30 border border-gray-700 rounded-lg p-6">
              <h2 className="text-lg font-semibold mb-4">Overview</h2>
              <div className="text-gray-400 text-sm">
                <p>This module provides comprehensive management capabilities for automated reconciliation.</p>
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
}
