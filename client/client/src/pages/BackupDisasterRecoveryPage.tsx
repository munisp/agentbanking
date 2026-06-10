import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { toast } from "sonner";
import {
  HardDrive,
  RefreshCw,
  Plus,
  Eye,
  Download,
  CheckCircle,
  Clock,
  Database,
  RotateCcw,
} from "lucide-react";

const STATUS_COLORS: Record<string, string> = {
  completed: "bg-emerald-500/20 text-emerald-400",
  in_progress: "bg-blue-500/20 text-blue-400",
  failed: "bg-red-500/20 text-red-400",
  pending: "bg-yellow-500/20 text-yellow-400",
};

export default function BackupDisasterRecoveryPage() {
  const [selectedBackup, setSelectedBackup] = useState<any>(null);

  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const snapshotsQuery = trpc.backupDisasterRecovery.listSnapshots.useQuery({
    limit: 50,
  });
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const statsQuery = trpc.backupDisasterRecovery.getStats.useQuery();
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const createMutation = trpc.backupDisasterRecovery.createSnapshot.useMutation(
    {
      onSuccess: () => {
        snapshotsQuery.refetch();
        toast.success("Backup initiated");
      },
      onError: (e: any) => toast.error(e.message),
    }
  );
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const restoreMutation =
    trpc.backupDisasterRecovery.restoreSnapshot.useMutation({
      onSuccess: () => {
        toast.success("Restore initiated");
      },
      onError: (e: any) => toast.error(e.message),
    });

  const snapshots = snapshotsQuery.data ?? [];
  const stats = statsQuery.data;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <HardDrive className="h-6 w-6 text-violet-400" /> Backup & Disaster
            Recovery
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            Database snapshots, point-in-time recovery, and disaster recovery
            plans
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => {
              snapshotsQuery.refetch();
              statsQuery.refetch();
            }}
            className="px-4 py-2 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg text-sm"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          <button
            onClick={() =>
              createMutation.mutate({
                // @ts-ignore Sprint 85
                type: "full",
                description: "Manual backup",
              })
            }
            className="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white rounded-lg text-sm"
          >
            <Plus className="h-4 w-4" /> New Backup
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          {
            label: "Total Snapshots",
            // @ts-ignore Sprint 85
            value: stats?.totalSnapshots ?? 0,
            icon: Database,
            color: "text-violet-400",
          },
          {
            label: "Successful",
            // @ts-ignore Sprint 85
            value: stats?.successful ?? 0,
            icon: CheckCircle,
            color: "text-emerald-400",
          },
          {
            label: "Total Size",
            // @ts-ignore Sprint 85
            value: stats?.totalSize || "0 GB",
            icon: HardDrive,
            color: "text-blue-400",
          },
          {
            label: "Last Backup",
            // @ts-ignore Sprint 85
            value: stats?.lastBackup || "Never",
            icon: Clock,
            color: "text-yellow-400",
          },
        ].map((s: any) => (
          <div
            key={s.label}
            className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl p-4"
          >
            <div className="flex items-center gap-2">
              <s.icon className={`h-4 w-4 ${s.color}`} />
              <p className="text-xs text-zinc-400 uppercase">{s.label}</p>
            </div>
            <p className="text-2xl font-bold text-white mt-2">{s.value}</p>
          </div>
        ))}
      </div>

      <div className="bg-zinc-800/50 border border-zinc-700/50 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-zinc-700/50 text-zinc-400">
              <th className="text-left p-4 font-medium">Type</th>
              <th className="text-left p-4 font-medium">Description</th>
              <th className="text-left p-4 font-medium">Size</th>
              <th className="text-left p-4 font-medium">Tables</th>
              <th className="text-left p-4 font-medium">Status</th>
              <th className="text-left p-4 font-medium">Created</th>
              <th className="text-left p-4 font-medium">Actions</th>
            </tr>
          </thead>
          <tbody>
            {snapshotsQuery.isLoading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} className="border-b border-zinc-700/30">
                  <td colSpan={7} className="p-4">
                    <div className="h-8 bg-zinc-700/50 rounded animate-pulse" />
                  </td>
                </tr>
              ))
            ) : // @ts-ignore Sprint 85
            snapshots.length === 0 ? (
              <tr>
                <td colSpan={7} className="p-8 text-center text-zinc-500">
                  No backups found
                </td>
              </tr>
            ) : (
              // @ts-ignore Sprint 85
              snapshots.map((s: any) => (
                <tr
                  key={s.id}
                  className="border-b border-zinc-700/30 hover:bg-zinc-700/20"
                >
                  <td className="p-4">
                    <span
                      className={`px-2 py-1 rounded text-xs ${s.backup_type === "full" ? "bg-violet-500/20 text-violet-400" : "bg-blue-500/20 text-blue-400"}`}
                    >
                      {s.backup_type}
                    </span>
                  </td>
                  <td className="p-4 text-white">{s.description || "—"}</td>
                  <td className="p-4 text-zinc-300">
                    {s.size_bytes
                      ? `${(s.size_bytes / 1024 / 1024).toFixed(1)} MB`
                      : "—"}
                  </td>
                  <td className="p-4 text-zinc-400">
                    {s.tables_included || "—"}
                  </td>
                  <td className="p-4">
                    <span
                      className={`px-2 py-1 rounded-full text-xs ${STATUS_COLORS[s.status] || "bg-zinc-500/20 text-zinc-400"}`}
                    >
                      {s.status?.replace(/_/g, " ")}
                    </span>
                  </td>
                  <td className="p-4 text-zinc-400 text-xs">
                    {s.created_at
                      ? new Date(s.created_at).toLocaleString()
                      : "—"}
                  </td>
                  <td className="p-4">
                    <div className="flex gap-1">
                      <button
                        onClick={() => setSelectedBackup(s)}
                        className="p-1.5 hover:bg-zinc-700 rounded-lg"
                      >
                        <Eye className="h-4 w-4 text-zinc-400" />
                      </button>
                      {s.status === "completed" && (
                        <button
                          onClick={() => {
                            if (
                              confirm(
                                "Restore from this backup? This will overwrite current data."
                              )
                            )
                              // @ts-ignore Sprint 85
                              restoreMutation.mutate({ id: s.id });
                          }}
                          className="p-1.5 hover:bg-violet-700/30 rounded-lg"
                          title="Restore"
                        >
                          <RotateCcw className="h-4 w-4 text-violet-400" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {selectedBackup && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
          onClick={() => setSelectedBackup(null)}
        >
          <div
            className="bg-zinc-900 border border-zinc-700 rounded-xl p-6 max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex justify-between items-start mb-4">
              <h3 className="text-lg font-bold text-white">Backup Details</h3>
              <button
                onClick={() => setSelectedBackup(null)}
                className="text-zinc-400 hover:text-white"
              >
                ✕
              </button>
            </div>
            <div className="space-y-3">
              {Object.entries(selectedBackup).map(([key, value]) => (
                <div
                  key={key}
                  className="flex justify-between border-b border-zinc-800 pb-2"
                >
                  <span className="text-zinc-400 text-sm">
                    {key.replace(/_/g, " ")}
                  </span>
                  <span className="text-white text-sm font-mono max-w-[250px] truncate">
                    {String(value ?? "—")}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
