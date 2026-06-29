// @ts-nocheck
/**
 * Sprint 92 — Ransomware & Security Alert Dashboard
 *
 * Visual indicator and notification system for administrators to monitor
 * ransomware mitigation triggers, bulk operation limit breaches, file
 * integrity violations, and data exfiltration attempts in real-time.
 */
import { useState, useEffect, useCallback } from "react";
import { trpc } from "@/lib/trpc";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import {
  ShieldAlert,
  AlertTriangle,
  Shield,
  Eye,
  CheckCircle2,
  XCircle,
  Clock,
  Skull,
  FileWarning,
  Database,
  Globe,
  Lock,
  RefreshCw,
  Loader2,
  Bell,
  BellRing,
  Search,
} from "lucide-react";

function timeAgo(ts: number): string {
  const diff = Date.now() - ts;
  if (diff < 60000) return "just now";
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
  return `${Math.floor(diff / 86400000)}d ago`;
}

const severityConfig: Record<
  string,
  { color: string; bgColor: string; icon: React.ReactNode; pulse: boolean }
> = {
  critical: {
    color: "text-red-600",
    bgColor: "bg-red-500/10 border-red-500/30",
    icon: <Skull className="h-4 w-4" />,
    pulse: true,
  },
  high: {
    color: "text-orange-600",
    bgColor: "bg-orange-500/10 border-orange-500/30",
    icon: <AlertTriangle className="h-4 w-4" />,
    pulse: true,
  },
  medium: {
    color: "text-yellow-600",
    bgColor: "bg-yellow-500/10 border-yellow-500/30",
    icon: <ShieldAlert className="h-4 w-4" />,
    pulse: false,
  },
  low: {
    color: "text-blue-600",
    bgColor: "bg-blue-500/10 border-blue-500/30",
    icon: <Shield className="h-4 w-4" />,
    pulse: false,
  },
};

const categoryConfig: Record<string, { icon: React.ReactNode; label: string }> =
  {
    ransomware: { icon: <Skull className="h-4 w-4" />, label: "Ransomware" },
    bulk_operation: {
      icon: <Database className="h-4 w-4" />,
      label: "Bulk Operation",
    },
    file_integrity: {
      icon: <FileWarning className="h-4 w-4" />,
      label: "File Integrity",
    },
    exfiltration: {
      icon: <Globe className="h-4 w-4" />,
      label: "Exfiltration",
    },
    brute_force: { icon: <Lock className="h-4 w-4" />, label: "Brute Force" },
    canary_trigger: {
      icon: <Search className="h-4 w-4" />,
      label: "Canary Trigger",
    },
  };

const statusConfig: Record<string, { color: string; label: string }> = {
  active: {
    color: "bg-red-500/10 text-red-600 border-red-500/20",
    label: "Active",
  },
  acknowledged: {
    color: "bg-yellow-500/10 text-yellow-600 border-yellow-500/20",
    label: "Acknowledged",
  },
  investigating: {
    color: "bg-blue-500/10 text-blue-600 border-blue-500/20",
    label: "Investigating",
  },
  resolved: {
    color: "bg-green-500/10 text-green-600 border-green-500/20",
    label: "Resolved",
  },
  false_positive: {
    color: "bg-gray-500/10 text-gray-600 border-gray-500/20",
    label: "False Positive",
  },
};

export default function RansomwareAlertDashboard() {
  const [categoryFilter, setCategoryFilter] = useState("all");
  const [severityFilter, setSeverityFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedAlert, setSelectedAlert] = useState<any>(null);
  const [actionDialog, setActionDialog] = useState<{
    type: "acknowledge" | "investigate" | "resolve";
    alertId: string;
  } | null>(null);
  const [actionNote, setActionNote] = useState("");
  const [resolution, setResolution] = useState<"resolved" | "false_positive">(
    "resolved"
  );

  const stats = trpc.ransomwareAlerts.getStats.useQuery();
  const alerts = trpc.ransomwareAlerts.getAlerts.useQuery({
    category: categoryFilter as any,
    severity: severityFilter as any,
    status: statusFilter as any,
  });

  const acknowledgeMut = trpc.ransomwareAlerts.acknowledge.useMutation({
    onSuccess: () => {
      toast.success("Alert acknowledged: The alert has been acknowledged.");
      alerts.refetch();
      stats.refetch();
      setActionDialog(null);
      setActionNote("");
    },
  });

  const investigateMut = trpc.ransomwareAlerts.investigate.useMutation({
    onSuccess: () => {
      toast.success(
        "Investigation started: The alert is now under investigation."
      );
      alerts.refetch();
      stats.refetch();
      setActionDialog(null);
      setActionNote("");
    },
  });

  const resolveMut = trpc.ransomwareAlerts.resolve.useMutation({
    onSuccess: () => {
      toast.success("Alert resolved: The alert has been resolved.");
      alerts.refetch();
      stats.refetch();
      setActionDialog(null);
      setActionNote("");
    },
  });

  // Auto-refresh every 15 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      stats.refetch();
      alerts.refetch();
    }, 15000);
    return () => clearInterval(interval);
  }, []);

  // Sound notification for new critical alerts
  useEffect(() => {
    const criticalActive = stats.data?.recentCritical?.length ?? 0;
    if (criticalActive > 0) {
      // Browser notification
      if ("Notification" in window && Notification.permission === "granted") {
        new Notification("CRITICAL Security Alert", {
          body: `${criticalActive} critical alert(s) require immediate attention`,
          icon: "/favicon.ico",
        });
      }
    }
  }, [stats.data?.recentCritical?.length]);

  const handleAction = useCallback(() => {
    if (!actionDialog) return;
    const { type, alertId } = actionDialog;
    if (type === "acknowledge") {
      acknowledgeMut.mutate({ alertId, note: actionNote || undefined });
    } else if (type === "investigate") {
      investigateMut.mutate({ alertId, note: actionNote || undefined });
    } else if (type === "resolve") {
      resolveMut.mutate({
        alertId,
        resolution,
        note: actionNote || "Resolved",
      });
    }
  }, [actionDialog, actionNote, resolution]);

  return (
    <div className="space-y-6">
      {/* Header with live indicator */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <ShieldAlert className="h-6 w-6 text-red-500" />
            Security Alert Center
          </h1>
          <p className="text-muted-foreground mt-1">
            Real-time monitoring of ransomware, bulk operations, and security
            threats
          </p>
        </div>
        <div className="flex items-center gap-3">
          {(stats.data?.activeCount ?? 0) > 0 && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-red-500/10 border border-red-500/30">
              <span className="relative flex h-2.5 w-2.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-red-500"></span>
              </span>
              <span className="text-sm font-semibold text-red-600">
                {stats.data?.activeCount} Active Alert
                {(stats.data?.activeCount ?? 0) !== 1 ? "s" : ""}
              </span>
            </div>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              stats.refetch();
              alerts.refetch();
            }}
          >
            <RefreshCw className="h-4 w-4 mr-1" /> Refresh
          </Button>
        </div>
      </div>

      {/* Severity Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {(["critical", "high", "medium", "low"] as const).map((sev: any) => {
          const sc = severityConfig[sev];
          const count = stats.data?.bySeverity[sev] ?? 0;
          return (
            <Card
              key={sev}
              className={`${sc.bgColor} border cursor-pointer transition-all hover:scale-[1.02]`}
              onClick={() => setSeverityFilter(sev)}
            >
              <CardContent className="pt-4 pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className={sc.color}>{sc.icon}</span>
                    <span
                      className={`text-sm font-medium capitalize ${sc.color}`}
                    >
                      {sev}
                    </span>
                  </div>
                  {sc.pulse && count > 0 && (
                    <span className="relative flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
                    </span>
                  )}
                </div>
                <div className={`text-3xl font-bold mt-2 ${sc.color}`}>
                  {count}
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Category Breakdown */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <Bell className="h-4 w-4" /> Alert Categories
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            {Object.entries(categoryConfig).map(([cat, cfg]) => {
              const count = stats.data?.byCategory[cat] ?? 0;
              return (
                <button
                  key={cat}
                  onClick={() => setCategoryFilter(cat)}
                  className={`flex items-center gap-2 p-3 rounded-lg border transition-all hover:bg-muted/50 ${
                    categoryFilter === cat
                      ? "bg-primary/10 border-primary/30"
                      : ""
                  }`}
                >
                  <span className="text-muted-foreground">{cfg.icon}</span>
                  <div className="text-left">
                    <p className="text-xs text-muted-foreground">{cfg.label}</p>
                    <p className="text-lg font-bold">{count}</p>
                  </div>
                </button>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <Select value={categoryFilter} onValueChange={setCategoryFilter}>
          <SelectTrigger className="w-[160px]">
            <SelectValue placeholder="Category" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Categories</SelectItem>
            <SelectItem value="ransomware">Ransomware</SelectItem>
            <SelectItem value="bulk_operation">Bulk Operation</SelectItem>
            <SelectItem value="file_integrity">File Integrity</SelectItem>
            <SelectItem value="exfiltration">Exfiltration</SelectItem>
            <SelectItem value="brute_force">Brute Force</SelectItem>
            <SelectItem value="canary_trigger">Canary Trigger</SelectItem>
          </SelectContent>
        </Select>
        <Select value={severityFilter} onValueChange={setSeverityFilter}>
          <SelectTrigger className="w-[140px]">
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
        <Select value={statusFilter} onValueChange={setStatusFilter}>
          <SelectTrigger className="w-[150px]">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Status</SelectItem>
            <SelectItem value="active">Active</SelectItem>
            <SelectItem value="acknowledged">Acknowledged</SelectItem>
            <SelectItem value="investigating">Investigating</SelectItem>
            <SelectItem value="resolved">Resolved</SelectItem>
            <SelectItem value="false_positive">False Positive</SelectItem>
          </SelectContent>
        </Select>
        {(categoryFilter !== "all" ||
          severityFilter !== "all" ||
          statusFilter !== "all") && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              setCategoryFilter("all");
              setSeverityFilter("all");
              setStatusFilter("all");
            }}
          >
            Clear filters
          </Button>
        )}
      </div>

      {/* Alert List */}
      <div className="space-y-3">
        {alerts.data?.items.map((alert: any) => {
          const sev = severityConfig[alert.severity] ?? severityConfig.low;
          const cat = categoryConfig[alert.category] ?? {
            icon: <Shield className="h-4 w-4" />,
            label: alert.category,
          };
          const st = statusConfig[alert.status] ?? statusConfig.active;

          return (
            <Card
              key={alert.id}
              className={`${sev.bgColor} border transition-all hover:shadow-md cursor-pointer`}
              onClick={() => setSelectedAlert(alert)}
            >
              <CardContent className="pt-4 pb-3">
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <span className={sev.color}>{sev.icon}</span>
                      <Badge
                        variant="outline"
                        className={`${sev.color} capitalize text-xs`}
                      >
                        {alert.severity}
                      </Badge>
                      <Badge variant="outline" className="text-xs gap-1">
                        {cat.icon} {cat.label}
                      </Badge>
                      <Badge
                        variant="outline"
                        className={`${st.color} text-xs`}
                      >
                        {st.label}
                      </Badge>
                    </div>
                    <h3 className="font-semibold text-sm mt-1">
                      {alert.title}
                    </h3>
                    <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                      {alert.description}
                    </p>
                    <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />{" "}
                        {timeAgo(alert.triggeredAt)}
                      </span>
                      {alert.sourceIp && (
                        <span className="flex items-center gap-1">
                          <Globe className="h-3 w-3" /> {alert.sourceIp}
                        </span>
                      )}
                      {alert.userName && (
                        <span className="flex items-center gap-1">
                          <Eye className="h-3 w-3" /> {alert.userName}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-col gap-1 shrink-0">
                    {alert.status === "active" && (
                      <>
                        <Button
                          size="sm"
                          variant="outline"
                          className="text-xs h-7"
                          onClick={e => {
                            e.stopPropagation();
                            setActionDialog({
                              type: "acknowledge",
                              alertId: alert.id,
                            });
                          }}
                        >
                          Acknowledge
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          className="text-xs h-7"
                          onClick={e => {
                            e.stopPropagation();
                            setActionDialog({
                              type: "investigate",
                              alertId: alert.id,
                            });
                          }}
                        >
                          Investigate
                        </Button>
                      </>
                    )}
                    {(alert.status === "acknowledged" ||
                      alert.status === "investigating") && (
                      <Button
                        size="sm"
                        variant="outline"
                        className="text-xs h-7"
                        onClick={e => {
                          e.stopPropagation();
                          setActionDialog({
                            type: "resolve",
                            alertId: alert.id,
                          });
                        }}
                      >
                        Resolve
                      </Button>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}

        {(!alerts.data?.items || alerts.data.items.length === 0) && (
          <Card>
            <CardContent className="py-12 text-center">
              <Shield className="h-12 w-12 mx-auto text-green-500 mb-3" />
              <p className="text-lg font-semibold">No alerts found</p>
              <p className="text-sm text-muted-foreground mt-1">
                All systems are operating normally
              </p>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Alert Detail Dialog */}
      <Dialog
        open={!!selectedAlert}
        onOpenChange={() => setSelectedAlert(null)}
      >
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          {selectedAlert && (
            <>
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  {severityConfig[selectedAlert.severity]?.icon}
                  {selectedAlert.title}
                </DialogTitle>
                <DialogDescription>
                  {selectedAlert.description}
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 mt-4">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <p className="text-muted-foreground">Category</p>
                    <p className="font-medium capitalize">
                      {selectedAlert.category.replace(/_/g, " ")}
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Severity</p>
                    <p
                      className={`font-medium capitalize ${severityConfig[selectedAlert.severity]?.color}`}
                    >
                      {selectedAlert.severity}
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Source</p>
                    <p className="font-medium">{selectedAlert.source}</p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Source IP</p>
                    <p className="font-medium font-mono">
                      {selectedAlert.sourceIp ?? "N/A"}
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">User</p>
                    <p className="font-medium">
                      {selectedAlert.userName ?? "N/A"}
                    </p>
                  </div>
                  <div>
                    <p className="text-muted-foreground">Triggered</p>
                    <p className="font-medium">
                      {new Date(selectedAlert.triggeredAt).toLocaleString()}
                    </p>
                  </div>
                </div>

                {selectedAlert.metadata &&
                  Object.keys(selectedAlert.metadata).length > 0 && (
                    <div>
                      <p className="text-sm font-semibold mb-2">
                        Technical Details
                      </p>
                      <div className="bg-muted/50 rounded-lg p-3 text-xs font-mono space-y-1">
                        {Object.entries(selectedAlert.metadata).map(
                          ([k, v]) => (
                            <div key={k} className="flex gap-2">
                              <span className="text-muted-foreground">
                                {k}:
                              </span>
                              <span>{String(v)}</span>
                            </div>
                          )
                        )}
                      </div>
                    </div>
                  )}

                {selectedAlert.actionsTaken?.length > 0 && (
                  <div>
                    <p className="text-sm font-semibold mb-2">Actions Taken</p>
                    <ul className="space-y-1">
                      {selectedAlert.actionsTaken.map(
                        (action: string, i: number) => (
                          <li
                            key={i}
                            className="flex items-start gap-2 text-sm"
                          >
                            <CheckCircle2 className="h-4 w-4 text-green-500 mt-0.5 shrink-0" />
                            {action}
                          </li>
                        )
                      )}
                    </ul>
                  </div>
                )}
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>

      {/* Action Dialog */}
      <Dialog
        open={!!actionDialog}
        onOpenChange={() => {
          setActionDialog(null);
          setActionNote("");
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {actionDialog?.type === "acknowledge" && "Acknowledge Alert"}
              {actionDialog?.type === "investigate" && "Start Investigation"}
              {actionDialog?.type === "resolve" && "Resolve Alert"}
            </DialogTitle>
            <DialogDescription>
              {actionDialog?.type === "acknowledge" &&
                "Confirm you have seen this alert and are aware of the threat."}
              {actionDialog?.type === "investigate" &&
                "Mark this alert as under active investigation."}
              {actionDialog?.type === "resolve" &&
                "Close this alert with a resolution."}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 mt-2">
            {actionDialog?.type === "resolve" && (
              <Select
                value={resolution}
                onValueChange={(v: any) => setResolution(v)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="resolved">
                    Resolved (Threat mitigated)
                  </SelectItem>
                  <SelectItem value="false_positive">False Positive</SelectItem>
                </SelectContent>
              </Select>
            )}
            <Textarea
              placeholder="Add a note (optional)..."
              value={actionNote}
              onChange={e => setActionNote(e.target.value)}
              rows={3}
            />
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setActionDialog(null);
                setActionNote("");
              }}
            >
              Cancel
            </Button>
            <Button
              onClick={handleAction}
              disabled={
                acknowledgeMut.isPending ||
                investigateMut.isPending ||
                resolveMut.isPending
              }
            >
              {(acknowledgeMut.isPending ||
                investigateMut.isPending ||
                resolveMut.isPending) && (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              )}
              Confirm
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
