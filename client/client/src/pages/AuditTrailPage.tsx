import { useState, useMemo } from "react";
import DashboardLayout from "@/components/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { trpc } from "@/lib/trpc";
import {
  Download,
  Search,
  Shield,
  AlertTriangle,
  Activity,
  Clock,
  Filter,
  RefreshCw,
} from "lucide-react";
import { useDataExport } from "@/hooks/useDataExport";

const SEVERITY_COLORS: Record<string, string> = {
  critical: "bg-red-500/20 text-red-400 border-red-500/30",
  high: "bg-orange-500/20 text-orange-400 border-orange-500/30",
  medium: "bg-yellow-500/20 text-yellow-400 border-yellow-500/30",
  low: "bg-green-500/20 text-green-400 border-green-500/30",
};

const ACTION_ICONS: Record<string, string> = {
  CREATE: "🆕",
  UPDATE: "✏️",
  DELETE: "🗑️",
  LOGIN: "🔑",
  LOGOUT: "🚪",
  EXPORT: "📤",
  APPROVE: "✅",
  REJECT: "❌",
  ESCALATE: "⬆️",
  READ: "👁️",
};

export default function AuditTrailPage() {
  const [search, setSearch] = useState("");
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [actionFilter, setActionFilter] = useState<string>("all");
  const [page, setPage] = useState(0);
  const limit = 25;

  const {
    data: auditData,
    isLoading,
    refetch,
    // @ts-ignore Sprint 85
  } = trpc.sprint27Export.auditLog.useQuery({
    format: "json",
    severity: severityFilter !== "all" ? severityFilter : undefined,
    category: categoryFilter !== "all" ? categoryFilter : undefined,
    action: actionFilter !== "all" ? actionFilter : undefined,
    limit,
    offset: page * limit,
  });

  // @ts-ignore Sprint 85
  const { data: stats } = trpc.sprint27Export.auditStats.useQuery();
  const { exportCSV } = useDataExport();

  const entries = (auditData as any)?.entries || [];
  const total = auditData?.total || 0;

  const filteredEntries = useMemo(() => {
    if (!search) return entries;
    const q = search.toLowerCase();
    return entries.filter(
      (e: any) =>
        e.description?.toLowerCase().includes(q) ||
        e.resource?.toLowerCase().includes(q) ||
        e.userId?.toLowerCase().includes(q)
    );
  }, [entries, search]);

  const handleExportCsv = () => {
    exportCSV(
      filteredEntries,
      [
        { key: "id", label: "Audit ID" },
        {
          key: "timestamp",
          label: "Timestamp",
          format: (v: unknown) => new Date(v as string).toLocaleString(),
        },
        { key: "userId", label: "User ID" },
        { key: "action", label: "Action" },
        { key: "resource", label: "Resource" },
        { key: "description", label: "Description" },
        { key: "severity", label: "Severity" },
        { key: "category", label: "Category" },
      ],
      "audit-trail-export"
    );
  };

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6 max-w-[1400px] mx-auto">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <Shield className="w-6 h-6 text-emerald-400" /> Audit Trail
            </h1>
            <p className="text-zinc-400 mt-1">
              Track all system actions, changes, and access events
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => refetch()}>
              <RefreshCw className="w-4 h-4 mr-1" /> Refresh
            </Button>
            <Button variant="outline" size="sm" onClick={handleExportCsv}>
              <Download className="w-4 h-4 mr-1" /> Export CSV
            </Button>
          </div>
        </div>

        {/* Stats Cards */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card className="bg-zinc-900/50 border-zinc-800">
              <CardContent className="p-4">
                <div className="text-sm text-zinc-400">Total Events</div>
                <div className="text-2xl font-bold text-white">
                  {stats.total.toLocaleString()}
                </div>
              </CardContent>
            </Card>
            <Card className="bg-zinc-900/50 border-zinc-800">
              <CardContent className="p-4">
                <div className="text-sm text-zinc-400">Last 24h</div>
                <div className="text-2xl font-bold text-emerald-400">
                  {stats.last24h}
                </div>
              </CardContent>
            </Card>
            <Card className="bg-zinc-900/50 border-zinc-800">
              <CardContent className="p-4">
                <div className="text-sm text-zinc-400 flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3" /> Critical
                </div>
                <div className="text-2xl font-bold text-red-400">
                  {stats.bySeverity.critical}
                </div>
              </CardContent>
            </Card>
            <Card className="bg-zinc-900/50 border-zinc-800">
              <CardContent className="p-4">
                <div className="text-sm text-zinc-400 flex items-center gap-1">
                  <Activity className="w-3 h-3" /> High
                </div>
                <div className="text-2xl font-bold text-orange-400">
                  {stats.bySeverity.high}
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Filters */}
        <Card className="bg-zinc-900/50 border-zinc-800">
          <CardContent className="p-4">
            <div className="flex flex-wrap gap-3 items-center">
              <div className="relative flex-1 min-w-[200px]">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
                <Input
                  placeholder="Search audit entries..."
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  className="pl-9 bg-zinc-800 border-zinc-700"
                />
              </div>
              <Select value={severityFilter} onValueChange={setSeverityFilter}>
                <SelectTrigger className="w-[140px] bg-zinc-800 border-zinc-700">
                  <SelectValue placeholder="Severity" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Severity</SelectItem>
                  <SelectItem value="critical">Critical</SelectItem>
                  <SelectItem value="high">High</SelectItem>
                  <SelectItem value="medium">Medium</SelectItem>
                  <SelectItem value="low">Low</SelectItem>
                </SelectContent>
              </Select>
              <Select value={categoryFilter} onValueChange={setCategoryFilter}>
                <SelectTrigger className="w-[140px] bg-zinc-800 border-zinc-700">
                  <SelectValue placeholder="Category" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Categories</SelectItem>
                  <SelectItem value="auth">Auth</SelectItem>
                  <SelectItem value="data">Data</SelectItem>
                  <SelectItem value="financial">Financial</SelectItem>
                  <SelectItem value="compliance">Compliance</SelectItem>
                  <SelectItem value="config">Config</SelectItem>
                  <SelectItem value="system">System</SelectItem>
                </SelectContent>
              </Select>
              <Select value={actionFilter} onValueChange={setActionFilter}>
                <SelectTrigger className="w-[140px] bg-zinc-800 border-zinc-700">
                  <SelectValue placeholder="Action" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Actions</SelectItem>
                  <SelectItem value="CREATE">Create</SelectItem>
                  <SelectItem value="UPDATE">Update</SelectItem>
                  <SelectItem value="DELETE">Delete</SelectItem>
                  <SelectItem value="LOGIN">Login</SelectItem>
                  <SelectItem value="EXPORT">Export</SelectItem>
                  <SelectItem value="APPROVE">Approve</SelectItem>
                  <SelectItem value="REJECT">Reject</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        {/* Audit Log Table */}
        <Card className="bg-zinc-900/50 border-zinc-800">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg flex items-center justify-between">
              <span className="flex items-center gap-2">
                <Clock className="w-5 h-5 text-zinc-400" /> Event Log
              </span>
              <span className="text-sm font-normal text-zinc-500">
                {total} total entries
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="text-center py-8 text-zinc-500">
                Loading audit entries...
              </div>
            ) : filteredEntries.length === 0 ? (
              <div className="text-center py-8 text-zinc-500">
                No audit entries found
              </div>
            ) : (
              <div className="space-y-2">
                {filteredEntries.map((entry: any) => (
                  <div
                    key={entry.id}
                    className="flex items-center gap-3 p-3 rounded-lg bg-zinc-800/50 hover:bg-zinc-800 transition-colors"
                  >
                    <span className="text-lg">
                      {ACTION_ICONS[entry.action] || "📋"}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-white text-sm">
                          {entry.description}
                        </span>
                        <Badge
                          variant="outline"
                          className={SEVERITY_COLORS[entry.severity] || ""}
                        >
                          {entry.severity}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-3 mt-1 text-xs text-zinc-500">
                        <span>{entry.userId || "anonymous"}</span>
                        <span>•</span>
                        <span>{entry.resource}</span>
                        <span>•</span>
                        <span>{entry.category}</span>
                        <span>•</span>
                        <span>
                          {new Date(entry.timestamp).toLocaleString()}
                        </span>
                      </div>
                    </div>
                    <Badge
                      variant="outline"
                      className="text-xs bg-zinc-700/50 border-zinc-600"
                    >
                      {entry.action}
                    </Badge>
                  </div>
                ))}
              </div>
            )}

            {/* Pagination */}
            {total > limit && (
              <div className="flex items-center justify-between mt-4 pt-4 border-t border-zinc-800">
                <span className="text-sm text-zinc-500">
                  Showing {page * limit + 1}–
                  {Math.min((page + 1) * limit, total)} of {total}
                </span>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={page === 0}
                    onClick={() => setPage(p => p - 1)}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={(page + 1) * limit >= total}
                    onClick={() => setPage(p => p + 1)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
