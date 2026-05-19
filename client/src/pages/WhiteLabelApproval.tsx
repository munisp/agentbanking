import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { toast } from "sonner";
import { CheckCircle } from "lucide-react";

export default function WhiteLabelApproval() {
  const [search, setSearch] = useState("");
  const statsQuery = trpc.whiteLabelApproval.getStats.useQuery();
  const stats = statsQuery.data;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <CheckCircle className="h-6 w-6 text-emerald-400" />
            Approval Workflow
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            Review and approve partner applications with SLA tracking
          </p>
        </div>
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Search..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-white placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
          />
          <button
            onClick={() => {
              statsQuery.refetch();
              toast.success("Data refreshed");
            }}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg text-sm font-medium"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats &&
          Object.entries(stats).map(([key, value]) => (
            <div
              key={key}
              className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl p-4"
            >
              <p className="text-xs text-zinc-400 uppercase tracking-wider">
                {key.replace(/([A-Z])/g, " $1").trim()}
              </p>
              <p className="text-xl font-bold text-white mt-1">
                {typeof value === "number"
                  ? value.toLocaleString()
                  : String(value)}
              </p>
            </div>
          ))}
      </div>

      {/* Main Content Area */}
      <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-white mb-4">
          Approval Workflow Dashboard
        </h2>
        {statsQuery.isLoading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4, 5].map(i => (
              <div
                key={i}
                className="h-12 bg-zinc-700/50 rounded-lg animate-pulse"
              />
            ))}
          </div>
        ) : (
          <div className="space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="bg-zinc-900/50 rounded-lg p-4 border border-zinc-700/30">
                <h3 className="text-sm font-medium text-zinc-300 mb-2">
                  Quick Actions
                </h3>
                <div className="space-y-2">
                  <button
                    onClick={() => toast.success("Action executed")}
                    className="w-full text-left px-3 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-sm text-zinc-300"
                  >
                    Create New Record
                  </button>
                  <button
                    onClick={() => toast.success("Export started")}
                    className="w-full text-left px-3 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-sm text-zinc-300"
                  >
                    Export Data
                  </button>
                  <button
                    onClick={() => toast.success("Report generated")}
                    className="w-full text-left px-3 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-sm text-zinc-300"
                  >
                    Generate Report
                  </button>
                </div>
              </div>
              <div className="bg-zinc-900/50 rounded-lg p-4 border border-zinc-700/30">
                <h3 className="text-sm font-medium text-zinc-300 mb-2">
                  Recent Activity
                </h3>
                <div className="space-y-2">
                  {[1, 2, 3].map(i => (
                    <div
                      key={i}
                      className="flex items-center justify-between px-3 py-2 bg-zinc-800 rounded-lg"
                    >
                      <span className="text-sm text-zinc-300">
                        Activity {i}
                      </span>
                      <span className="text-xs text-zinc-500">{i}h ago</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
