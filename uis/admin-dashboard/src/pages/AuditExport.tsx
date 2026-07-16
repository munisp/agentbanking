/**
 * Audit Export — Export audit logs, compliance reports, and transaction history
 * Wired to audit.list for log data
 */
import { useState, useMemo } from "react";
import { trpc } from "@/lib/trpc";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Download,
  FileText,
  Search,
  Calendar,
  Filter,
  FileSpreadsheet,
  File,
} from "lucide-react";
import { toast } from "sonner";

export default function AuditExport() {
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [category, setCategory] = useState("all");
  const [search, setSearch] = useState("");

  const logs = trpc.auditLog.list.useQuery({}, { retry: false });

  const filteredLogs = useMemo(() => {
    const items = logs.data ?? [];
    if (!search) return items;
    const q = search.toLowerCase();
    return items.filter(
      (l: any) =>
        l.action?.toLowerCase().includes(q) ||
        l.entityType?.toLowerCase().includes(q) ||
        l.userId?.toString().includes(q)
    );
  }, [logs.data, search]);

  const exportCSV = () => {
    const items = filteredLogs;
    if (!items.length) {
      toast.error("No data to export");
      return;
    }
    const headers = [
      "ID",
      "Action",
      "Entity Type",
      "Entity ID",
      "User ID",
      "IP Address",
      "Created At",
    ];
    const rows = items.map((l: any) =>
      [
        l.id,
        l.action,
        l.entityType,
        l.entityId,
        l.userId,
        l.ipAddress,
        l.createdAt,
      ].join(",")
    );
    const csv = [headers.join(","), ...rows].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `audit-export-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success(`Exported ${items.length} records as CSV`);
  };

  const exportJSON = () => {
    const items = filteredLogs;
    if (!items.length) {
      toast.error("No data to export");
      return;
    }
    const blob = new Blob([JSON.stringify(items, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `audit-export-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast.success(`Exported ${items.length} records as JSON`);
  };

  const EXPORT_TEMPLATES = [
    {
      name: "Transaction Audit Trail",
      description: "All financial transactions with agent, amount, and status",
      icon: <FileSpreadsheet className="w-4 h-4 text-green-400" />,
      count: filteredLogs.length,
    },
    {
      name: "Compliance Report",
      description:
        "Device compliance violations and policy enforcement actions",
      icon: <FileText className="w-4 h-4 text-blue-400" />,
      count: 0,
    },
    {
      name: "Agent Activity Log",
      description: "Login/logout, transaction, and location events per agent",
      icon: <File className="w-4 h-4 text-purple-400" />,
      count: 0,
    },
    {
      name: "Fraud Investigation Pack",
      description: "Flagged transactions with SHAP features and risk scores",
      icon: <FileText className="w-4 h-4 text-red-400" />,
      count: 0,
    },
    {
      name: "Settlement Reconciliation",
      description: "Daily settlement batches with discrepancy analysis",
      icon: <FileSpreadsheet className="w-4 h-4 text-yellow-400" />,
      count: 0,
    },
    {
      name: "KYC Verification Summary",
      description:
        "Agent KYC status, document verification, and approval history",
      icon: <File className="w-4 h-4 text-cyan-400" />,
      count: 0,
    },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-white p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Download className="w-6 h-6 text-blue-400" /> Audit Export Center
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Export audit logs, compliance reports, and transaction history for
            regulatory review
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant="outline"
            className="border-green-600 text-green-400"
            onClick={exportCSV}
          >
            <FileSpreadsheet className="w-3 h-3 mr-1" /> Export CSV
          </Button>
          <Button
            size="sm"
            variant="outline"
            className="border-blue-600 text-blue-400"
            onClick={exportJSON}
          >
            <FileText className="w-3 h-3 mr-1" /> Export JSON
          </Button>
        </div>
      </div>

      {/* Filters */}
      <Card className="bg-slate-900/50 border-slate-700">
        <CardContent className="p-4">
          <div className="flex flex-wrap gap-3 items-end">
            <div className="flex-1 min-w-[200px]">
              <label className="text-xs text-slate-400 mb-1 block">
                Search
              </label>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <Input
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  placeholder="Search logs..."
                  className="pl-9 bg-slate-800 border-slate-700 text-white"
                />
              </div>
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1 block">
                Category
              </label>
              <Select value={category} onValueChange={setCategory}>
                <SelectTrigger className="w-[150px] bg-slate-800 border-slate-700 text-white">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-slate-800 border-slate-700">
                  <SelectItem value="all">All Categories</SelectItem>
                  <SelectItem value="transaction">Transactions</SelectItem>
                  <SelectItem value="auth">Authentication</SelectItem>
                  <SelectItem value="compliance">Compliance</SelectItem>
                  <SelectItem value="admin">Admin Actions</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1 block">From</label>
              <Input
                type="date"
                value={dateFrom}
                onChange={e => setDateFrom(e.target.value)}
                className="bg-slate-800 border-slate-700 text-white w-[140px]"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 mb-1 block">To</label>
              <Input
                type="date"
                value={dateTo}
                onChange={e => setDateTo(e.target.value)}
                className="bg-slate-800 border-slate-700 text-white w-[140px]"
              />
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Export Templates */}
      <div>
        <h2 className="text-sm font-semibold text-slate-400 mb-3">
          Export Templates
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {EXPORT_TEMPLATES.map(t => (
            <Card
              key={t.name}
              className="bg-slate-900/50 border-slate-700 hover:border-blue-600/50 transition-colors cursor-pointer"
              onClick={() => toast.success(`Generating ${t.name}...`)}
            >
              <CardContent className="p-4">
                <div className="flex items-start gap-3">
                  {t.icon}
                  <div className="flex-1">
                    <div className="text-sm text-white font-medium">
                      {t.name}
                    </div>
                    <div className="text-[10px] text-slate-500 mt-0.5">
                      {t.description}
                    </div>
                  </div>
                  <Download className="w-3 h-3 text-slate-600" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Recent Logs Preview */}
      <Card className="bg-slate-900/50 border-slate-700">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm text-white">
            Recent Audit Logs ({filteredLogs.length} records)
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-slate-700 text-slate-500">
                <th className="px-3 py-2 text-left">ID</th>
                <th className="px-3 py-2 text-left">Action</th>
                <th className="px-3 py-2 text-left">Entity</th>
                <th className="px-3 py-2 text-left">User</th>
                <th className="px-3 py-2 text-left">IP</th>
                <th className="px-3 py-2 text-left">Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/50">
              {filteredLogs.slice(0, 20).map((l: any) => (
                <tr key={l.id} className="hover:bg-slate-800/40">
                  <td className="px-3 py-2 font-mono text-slate-400">{l.id}</td>
                  <td className="px-3 py-2 text-white">{l.action}</td>
                  <td className="px-3 py-2 text-slate-300">
                    {l.entityType} #{l.entityId}
                  </td>
                  <td className="px-3 py-2 text-slate-300">
                    {l.userId ?? "system"}
                  </td>
                  <td className="px-3 py-2 font-mono text-slate-500">
                    {l.ipAddress ?? "-"}
                  </td>
                  <td className="px-3 py-2 text-slate-500">
                    {l.createdAt ? new Date(l.createdAt).toLocaleString() : "-"}
                  </td>
                </tr>
              ))}
              {filteredLogs.length === 0 && (
                <tr>
                  <td
                    colSpan={6}
                    className="px-3 py-8 text-center text-slate-600"
                  >
                    {logs.isLoading ? "Loading..." : "No audit logs found"}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
