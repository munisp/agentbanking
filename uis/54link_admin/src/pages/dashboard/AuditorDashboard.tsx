import { toast } from 'sonner';
import {
    AlertTriangle,
    // CheckCircle,
    Clock,
    Download,
    FileSearch,
    Shield,
} from "lucide-react";
import { useEffect, useState } from "react";
import { auditService } from "../../services/audit";
import type { AuditLog } from "../../types/audit";

export default function AuditorDashboard() {
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAuditLogs = async () => {
      try {
        setLoading(true);
        const logs = await auditService.getAuditLogs();
        setAuditLogs(logs.data ?? []);
      } catch (error) {
        console.error("Failed to fetch audit logs:", error);
        toast.error(error instanceof Error ? error.message : 'Something went wrong. Please try again.');
      } finally {
        setLoading(false);
      }
    };

    fetchAuditLogs();
    // Refresh every 30 seconds
    const interval = setInterval(fetchAuditLogs, 30000);
    return () => clearInterval(interval);
  }, []);

  // Calculate statistics from real data
  const stats = {
    total: auditLogs.length,
    last30Days: auditLogs.filter((log) => {
      const thirtyDaysAgo = new Date();
      thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30);
      return new Date(log.timestamp) >= thirtyDaysAgo;
    }).length,
    flaggedEvents: auditLogs.filter(
      (log) => log.event_type === "DELETE" || log.event_type === "WITHDRAWAL",
    ).length,
  };

  // Format timestamp
  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffHours / 24);

    if (diffHours < 1) {
      const diffMins = Math.floor(diffMs / (1000 * 60));
      return `${diffMins} minute${diffMins !== 1 ? "s" : ""} ago`;
    } else if (diffHours < 24) {
      return `${diffHours} hour${diffHours !== 1 ? "s" : ""} ago`;
    } else if (diffDays === 1) {
      return "Yesterday";
    } else {
      return date.toLocaleDateString();
    }
  };

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-6">Auditor Dashboard</h1>
      <p className="text-muted-foreground mb-8">
        Welcome, Auditor! Access audit trails, compliance reports, and system
        logs.
      </p>

      {/* Audit Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Audit Logs</p>
              <p className="text-2xl font-bold mt-2">
                {loading ? "..." : stats.last30Days.toLocaleString()}
              </p>
              <p className="text-xs text-blue-600 mt-1">Last 30 days</p>
            </div>
            <FileSearch className="h-8 w-8 text-blue-500" />
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Compliance Score</p>
              <p className="text-2xl font-bold mt-2">96%</p>
              <p className="text-xs text-green-600 mt-1">Above target</p>
            </div>
            <Shield className="h-8 w-8 text-green-500" />
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Flagged Events</p>
              <p className="text-2xl font-bold mt-2">
                {loading ? "..." : stats.flaggedEvents}
              </p>
              <p className="text-xs text-orange-600 mt-1">Need review</p>
            </div>
            <AlertTriangle className="h-8 w-8 text-orange-500" />
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Reports Generated</p>
              <p className="text-2xl font-bold mt-2">42</p>
              <p className="text-xs text-purple-600 mt-1">This month</p>
            </div>
            <Download className="h-8 w-8 text-purple-500" />
          </div>
        </div>
      </div>

      {/* Audit Details */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div className="bg-card border rounded-lg p-6">
          <h3 className="font-semibold mb-4">Recent Audit Events</h3>
          <div className="space-y-3">
            {loading ? (
              <div className="p-3 text-center text-muted-foreground">
                Loading...
              </div>
            ) : auditLogs.length === 0 ? (
              <div className="p-3 text-center text-muted-foreground">
                No recent events
              </div>
            ) : (
              auditLogs.slice(0, 3).map((log) => (
                <div key={log.id} className="p-3 border rounded">
                  <div className="flex justify-between items-start mb-2">
                    <p className="text-sm font-medium">{log.event_type}</p>
                    <Clock className="h-4 w-4 text-muted-foreground" />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    User:{" "}
                    {log.event_data?.email || log.actor_id.substring(0, 8)}
                  </p>
                  {log.event_type === "TRANSFER" && log.event_data && (
                    <p className="text-xs text-muted-foreground">
                      Action: Transfer {log.event_data.amount} from{" "}
                      {log.event_data.payer} to {log.event_data.payee}
                    </p>
                  )}
                  {log.event_type === "LOGIN" && log.event_data && (
                    <p className="text-xs text-muted-foreground">
                      Action: Login from {log.event_data.email}
                    </p>
                  )}
                  <p className="text-xs text-muted-foreground mt-1">
                    {formatTimestamp(log.timestamp)}
                  </p>
                </div>
              ))
            )}
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <h3 className="font-semibold mb-4">Compliance Reports</h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center p-3 border rounded hover:bg-accent cursor-pointer">
              <div>
                <p className="text-sm font-medium">
                  AML Transaction Monitoring
                </p>
                <p className="text-xs text-muted-foreground">
                  Monthly report - January 2024
                </p>
              </div>
              <Download className="h-4 w-4 text-blue-500" />
            </div>
            <div className="flex justify-between items-center p-3 border rounded hover:bg-accent cursor-pointer">
              <div>
                <p className="text-sm font-medium">KYC Compliance Summary</p>
                <p className="text-xs text-muted-foreground">
                  Quarterly report - Q4 2023
                </p>
              </div>
              <Download className="h-4 w-4 text-blue-500" />
            </div>
            <div className="flex justify-between items-center p-3 border rounded hover:bg-accent cursor-pointer">
              <div>
                <p className="text-sm font-medium">Security Audit Log</p>
                <p className="text-xs text-muted-foreground">
                  Weekly digest - Week 4
                </p>
              </div>
              <Download className="h-4 w-4 text-blue-500" />
            </div>
          </div>
        </div>
      </div>

      {/* System Activity */}
      <div className="bg-card border rounded-lg p-6">
        <h3 className="font-semibold mb-4">System Access Log</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                <th className="text-left py-2 px-3">Timestamp</th>
                <th className="text-left py-2 px-3">User</th>
                <th className="text-left py-2 px-3">Action</th>
                <th className="text-left py-2 px-3">Details</th>
                <th className="text-left py-2 px-3">Tenant ID</th>
                <th className="text-left py-2 px-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td
                    colSpan={6}
                    className="py-4 text-center text-muted-foreground"
                  >
                    Loading access logs...
                  </td>
                </tr>
              ) : auditLogs.length === 0 ? (
                <tr>
                  <td
                    colSpan={6}
                    className="py-4 text-center text-muted-foreground"
                  >
                    No access logs found
                  </td>
                </tr>
              ) : (
                auditLogs.slice(0, 10).map((log) => (
                  <tr key={log.id} className="border-b hover:bg-accent">
                    <td className="py-2 px-3 text-muted-foreground">
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td className="py-2 px-3">
                      {log.event_data?.email ||
                        log.actor_id.substring(0, 8) + "..."}
                    </td>
                    <td className="py-2 px-3">{log.event_type}</td>
                    <td className="py-2 px-3 text-muted-foreground">
                      {log.event_type === "TRANSFER" && log.event_data
                        ? `${log.event_data.amount}`
                        : log.event_type === "LOGIN"
                          ? "Login"
                          : "-"}
                    </td>
                    <td className="py-2 px-3">
                      <span className="font-mono text-xs text-muted-foreground">
                        {log.tenant_id}
                      </span>
                    </td>
                    <td className="py-2 px-3">
                      <span className="text-xs px-2 py-1 bg-green-100 text-green-700 rounded">
                        Success
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
