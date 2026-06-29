import { toast } from 'sonner';
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Pagination,
    PaginationContent,
    PaginationItem,
    PaginationNext,
    PaginationPrevious,
} from "@/components/ui/pagination";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import {
    Calendar,
    ClipboardList,
    Download,
    Search,
    Shield,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useTenantBranding } from "../../../contexts/TenantBrandingContext";
import { auditService } from "../../../services/audit";
import type { AuditLog as ApiAuditLog } from "../../../types/audit";

const PAGE_SIZE = 25;

interface AuditLog {
  id: string;
  timestamp: Date;
  adminId: string;
  adminName: string;
  adminEmail: string;
  action: string;
  resource: string;
  resourceId?: string;
  details: string;
  ipAddress?: string;
  userAgent?: string;
  status: "success" | "failure";
  metadata?: Record<string, any>;
  tenantId: string;
}

export default function AuditLogs() {
  const { primaryColor, secondaryColor } = useTenantBranding();
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [auditLogsLoading, setAuditLogsLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");
  const [filterAction, setFilterAction] = useState<string>("all");
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [filterDateRange, setFilterDateRange] = useState<string>("all");
  const [currentPage, setCurrentPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);

  const totalPages = Math.ceil(totalCount / PAGE_SIZE);
  const hasNextPage = totalCount > 0
    ? currentPage < totalPages
    : auditLogs.length === PAGE_SIZE;
  const hasPrevPage = currentPage > 1;

  // Fetch audit logs from API
  const fetchAuditLogs = async (page: number, setLoading = true) => {
    if (setLoading) {
      setAuditLogsLoading(true);
    }
    try {
      const response = await auditService.getAuditLogs({ page, limit: PAGE_SIZE });
      const apiLogs = response.data;
      setTotalCount(response.total);

      // Transform API logs to match component interface
      const transformedLogs: AuditLog[] = apiLogs.map((log: ApiAuditLog) => {
        // Extract email from event_data if available
        const email = log.event_data?.email || "N/A";
        const actorName = email.split("@")[0] || "Unknown";

        // Determine details based on event type
        let details = "";
        if (log.event_type === "TRANSFER" && log.event_data) {
          details = `Transfer ${log.event_data.amount} from ${log.event_data.payer} to ${log.event_data.payee}`;
        } else if (log.event_type === "LOGIN" && log.event_data) {
          details = `Login from ${email}`;
        } else {
          details = JSON.stringify(log.event_data);
        }

        return {
          id: log.id,
          timestamp: new Date(log.timestamp),
          adminId: log.actor_id,
          adminName: actorName,
          adminEmail: email,
          action: log.event_type,
          resource: log.event_type,
          resourceId: log.id,
          details: details,
          ipAddress: undefined,
          userAgent: undefined,
          status: "success" as const,
          metadata: log.event_data,
          tenantId: log.tenant_id,
        };
      });

      setAuditLogs(transformedLogs);
    } catch (error) {
      console.error("Error fetching audit logs:", error);
      toast.error(error instanceof Error ? error.message : 'Something went wrong. Please try again.');
      if (setLoading) {
        setAuditLogs([]);
      }
    } finally {
      if (setLoading) {
        setAuditLogsLoading(false);
      }
    }
  };

  useEffect(() => {
    fetchAuditLogs(currentPage, true);
    const interval = setInterval(() => fetchAuditLogs(currentPage, false), 30000);
    return () => clearInterval(interval);
  }, [currentPage]);

  const handleFilterChange = (setter: (v: string) => void) => (value: string) => {
    setter(value);
    setCurrentPage(1);
  };

  const filteredLogs = useMemo(() => {
    return auditLogs.filter((log) => {
      const matchesSearch =
        log.adminName.toLowerCase().includes(searchTerm.toLowerCase()) ||
        log.adminEmail.toLowerCase().includes(searchTerm.toLowerCase()) ||
        log.action.toLowerCase().includes(searchTerm.toLowerCase()) ||
        log.resource.toLowerCase().includes(searchTerm.toLowerCase()) ||
        log.details.toLowerCase().includes(searchTerm.toLowerCase());

      const matchesAction =
        filterAction === "all" || log.action === filterAction;
      const matchesStatus =
        filterStatus === "all" || log.status === filterStatus;

      let matchesDate = true;
      if (filterDateRange !== "all") {
        const now = new Date();
        const logDate = new Date(log.timestamp);
        const diffMs = now.getTime() - logDate.getTime();
        const diffHours = diffMs / (1000 * 60 * 60);
        const diffDays = diffMs / (1000 * 60 * 60 * 24);

        switch (filterDateRange) {
          case "1h":
            matchesDate = diffHours <= 1;
            break;
          case "24h":
            matchesDate = diffHours <= 24;
            break;
          case "7d":
            matchesDate = diffDays <= 7;
            break;
          case "30d":
            matchesDate = diffDays <= 30;
            break;
        }
      }

      return matchesSearch && matchesAction && matchesStatus && matchesDate;
    });
  }, [auditLogs, searchTerm, filterAction, filterStatus, filterDateRange]);

  const getActionBadge = (action: string) => {
    const actionColors: Record<string, string> = {
      CREATE: "bg-green-600 hover:bg-green-700",
      UPDATE: "bg-blue-600 hover:bg-blue-700",
      DELETE: "bg-red-600 hover:bg-red-700",
      VIEW: "bg-gray-600 hover:bg-gray-700",
      LOGIN: "bg-purple-600 hover:bg-purple-700",
      LOGOUT: "bg-orange-600 hover:bg-orange-700",
      EXPORT: "bg-indigo-600 hover:bg-indigo-700",
    };

    const color = actionColors[action] || "bg-slate-600 hover:bg-slate-700";
    return <Badge className={color}>{action}</Badge>;
  };

  const stats = {
    total: auditLogs.length,
    today: auditLogs.filter((log) => {
      const today = new Date();
      const logDate = new Date(log.timestamp);
      return today.toDateString() === logDate.toDateString();
    }).length,
    success: auditLogs.filter((log) => log.status === "success").length,
    failures: auditLogs.filter((log) => log.status === "failure").length,
  };

  const uniqueActions = useMemo(() => {
    return Array.from(new Set(auditLogs.map((log) => log.action))).sort();
  }, [auditLogs]);

  const handleExport = () => {
    // TODO: Implement export functionality
    const csv = [
      [
        "Timestamp",
        "Admin",
        "Email",
        "Action",
        "Resource",
        "Details",
        "Status",
        "IP Address",
      ].join(","),
      ...filteredLogs.map((log) =>
        [
          log.timestamp.toISOString(),
          log.adminName,
          log.adminEmail,
          log.action,
          log.resource,
          `"${log.details}"`,
          log.status,
          log.ipAddress || "",
        ].join(","),
      ),
    ].join("\n");

    const blob = new Blob([csv], { type: "text/csv" });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `audit-logs-${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  return (
    <div
      className="min-h-screen dark:from-slate-900 dark:to-slate-800"
      style={{
        background: `linear-gradient(to bottom right, ${primaryColor}15, ${secondaryColor}15)`,
      }}
    >
      {/* Header */}
      <div className="bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700">
        <div className="container py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <ClipboardList
                className="w-8 h-8"
                style={{ color: primaryColor }}
              />
              <div>
                <h1 className="text-3xl font-bold text-slate-900 dark:text-white">
                  Audit Logs
                </h1>
                <p className="text-slate-600 dark:text-slate-400 mt-1">
                  Track and monitor all admin activities in the system
                </p>
              </div>
            </div>
            <Button
              onClick={handleExport}
              variant="outline"
              className="border-slate-300 dark:border-slate-600"
            >
              <Download className="w-4 h-4 mr-2" />
              Export
            </Button>
          </div>
        </div>
      </div>

      <div className="container py-8 space-y-6">
        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-600 dark:text-slate-400 font-medium">
                  Total Logs
                </p>
                <p className="text-3xl font-bold text-slate-900 dark:text-white mt-2">
                  {stats.total}
                </p>
              </div>
              <ClipboardList
                className="w-12 h-12 opacity-20"
                style={{ color: primaryColor }}
              />
            </div>
          </div>

          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-600 dark:text-slate-400 font-medium">
                  Today
                </p>
                <p className="text-3xl font-bold text-slate-900 dark:text-white mt-2">
                  {stats.today}
                </p>
              </div>
              <Calendar className="w-12 h-12 text-blue-600 opacity-20" />
            </div>
          </div>

          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-600 dark:text-slate-400 font-medium">
                  Successful
                </p>
                <p className="text-3xl font-bold text-green-600 mt-2">
                  {stats.success}
                </p>
              </div>
              <Shield className="w-12 h-12 text-green-600 opacity-20" />
            </div>
          </div>

          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-slate-600 dark:text-slate-400 font-medium">
                  Failures
                </p>
                <p className="text-3xl font-bold text-red-600 mt-2">
                  {stats.failures}
                </p>
              </div>
              <Shield className="w-12 h-12 text-red-600 opacity-20" />
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
          <div className="flex flex-wrap items-center gap-4">
            <div className="flex-1 min-w-[200px]">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-slate-400" />
                <Input
                  type="text"
                  placeholder="Search logs..."
                  value={searchTerm}
                  onChange={(e) => { setSearchTerm(e.target.value); setCurrentPage(1); }}
                  className="pl-10"
                />
              </div>
            </div>

            <Select value={filterAction} onValueChange={handleFilterChange(setFilterAction)}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Filter by action" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Actions</SelectItem>
                {uniqueActions.map((action) => (
                  <SelectItem key={action} value={action}>
                    {action}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            <Select value={filterStatus} onValueChange={handleFilterChange(setFilterStatus)}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Filter by status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Status</SelectItem>
                <SelectItem value="success">Success</SelectItem>
                <SelectItem value="failure">Failure</SelectItem>
              </SelectContent>
            </Select>

            <Select value={filterDateRange} onValueChange={handleFilterChange(setFilterDateRange)}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Date range" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Time</SelectItem>
                <SelectItem value="1h">Last Hour</SelectItem>
                <SelectItem value="24h">Last 24 Hours</SelectItem>
                <SelectItem value="7d">Last 7 Days</SelectItem>
                <SelectItem value="30d">Last 30 Days</SelectItem>
              </SelectContent>
            </Select>

            <div className="text-sm text-slate-600 dark:text-slate-400">
              Showing {filteredLogs.length} of {totalCount} logs
            </div>
          </div>
        </div>

        {/* Audit Logs Table */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700 overflow-hidden" id="audit-table">
          {auditLogsLoading ? (
            <div className="p-12 text-center">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-slate-900 dark:border-slate-100"></div>
              <p className="mt-4 text-slate-600 dark:text-slate-400">
                Loading audit logs...
              </p>
            </div>
          ) : filteredLogs.length === 0 ? (
            <div className="p-12 text-center">
              <ClipboardList className="w-16 h-16 mx-auto text-slate-400 mb-4" />
              <p className="text-slate-600 dark:text-slate-400">
                No audit logs found
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-50 dark:bg-slate-700 border-b border-slate-200 dark:border-slate-600">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                      Timestamp
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                      Admin
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                      Action
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                      Resource
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                      Details
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                      Tenant ID
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-semibold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                      IP Address
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                  {filteredLogs.map((log) => (
                    <tr
                      key={log.id}
                      className="hover:bg-slate-50 dark:hover:bg-slate-700/50"
                    >
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-slate-900 dark:text-white">
                          {log.timestamp.toLocaleString()}
                        </div>
                        <div className="text-xs text-slate-500 dark:text-slate-400">
                          {Math.round(
                            (Date.now() - log.timestamp.getTime()) /
                              (1000 * 60),
                          )}
                          m ago
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div>
                          <p className="font-semibold text-slate-900 dark:text-white">
                            {log.adminName}
                          </p>
                          <p className="text-sm text-slate-600 dark:text-slate-400">
                            {log.adminEmail}
                          </p>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        {getActionBadge(log.action)}
                      </td>
                      <td className="px-6 py-4">
                        <div>
                          <p className="text-sm font-medium text-slate-900 dark:text-white">
                            {log.resource}
                          </p>
                          {log.resourceId && (
                            <p className="text-xs text-slate-500 dark:text-slate-400">
                              ID: {log.resourceId}
                            </p>
                          )}
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <p
                          className="text-sm text-slate-900 dark:text-white max-w-md truncate"
                          title={log.details}
                        >
                          {log.details}
                        </p>
                      </td>
                      <td className="px-6 py-4">
                        {log.status === "success" ? (
                          <Badge className="bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300">
                            Success
                          </Badge>
                        ) : (
                          <Badge className="bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300">
                            Failure
                          </Badge>
                        )}
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-600 dark:text-slate-400">
                        <span className="font-mono text-xs">
                          {log.tenantId}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-600 dark:text-slate-400">
                        {log.ipAddress || "N/A"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        {/* Pagination */}
        {(hasPrevPage || hasNextPage) && (
          <div className="flex items-center justify-between mt-4">
            <p className="text-sm text-slate-600 dark:text-slate-400">
              Page {currentPage}{totalPages > 1 ? ` of ${totalPages}` : ""}
            </p>
            <Pagination>
              <PaginationContent>
                <PaginationItem>
                  <PaginationPrevious
                    onClick={(e) => {
                      e.preventDefault();
                      if (hasPrevPage) setCurrentPage((p) => p - 1);
                    }}
                    className={!hasPrevPage ? "pointer-events-none opacity-50" : "cursor-pointer"}
                  />
                </PaginationItem>
                <PaginationItem>
                  <PaginationNext
                    onClick={(e) => {
                      e.preventDefault();
                      if (hasNextPage) setCurrentPage((p) => p + 1);
                    }}
                    className={!hasNextPage ? "pointer-events-none opacity-50" : "cursor-pointer"}
                  />
                </PaginationItem>
              </PaginationContent>
            </Pagination>
          </div>
        )}
      </div>
    </div>
  );
}
