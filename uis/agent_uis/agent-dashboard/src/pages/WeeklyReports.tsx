import { useState, useEffect, useCallback } from "react";
import { toast } from "sonner";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
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
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import {
  BarChart3,
  Calendar,
  Clock,
  Download,
  FileText,
  Loader2,
  Mail,
  MailPlus,
  Play,
  Plus,
  Settings,
  Shield,
  Trash2,
  TrendingUp,
  Users,
  Zap,
  AlertTriangle,
  CheckCircle2,
  ArrowUp,
  ArrowDown,
  Minus,
} from "lucide-react";
import { authHeaders } from "../utils/api";

const CORE_BANKING_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

const DAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

// ─── Types ──────────────────────────────────────────────────────────────────

interface TrendDelta {
  current: number;
  previous: number;
  delta: number;
  deltaPercent: number;
  direction: "up" | "down" | "flat";
  isPositive: boolean;
}

// ─── Trend Arrow ─────────────────────────────────────────────────────────────

function TrendArrow({ trend }: { trend?: TrendDelta | null }) {
  if (!trend || trend.direction === "flat") {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
        <Minus className="h-3 w-3" /> 0%
      </span>
    );
  }
  const isUp = trend.direction === "up";
  const color = trend.isPositive ? "text-emerald-400" : "text-red-400";
  const Icon = isUp ? ArrowUp : ArrowDown;
  const sign = trend.delta > 0 ? "+" : "";
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-semibold ${color}`}>
      <Icon className="h-3 w-3" />
      {sign}{trend.deltaPercent}%
    </span>
  );
}

// ─── Score Badge ──────────────────────────────────────────────────────────────

function ScoreBadge({ score }: { score: number }) {
  const color =
    score >= 90
      ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
      : score >= 70
        ? "bg-amber-500/20 text-amber-400 border-amber-500/30"
        : "bg-red-500/20 text-red-400 border-red-500/30";
  const label = score >= 90 ? "Excellent" : score >= 70 ? "Good" : "Needs Attention";
  return (
    <Badge variant="outline" className={color}>
      {label} — {score}/100
    </Badge>
  );
}

// ─── Metric Card ──────────────────────────────────────────────────────────────

function MetricCard({
  label,
  value,
  trend,
  icon: Icon,
}: {
  label: string;
  value: string;
  trend?: TrendDelta | null;
  icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/30">
      <div className="p-2 rounded-md bg-primary/10">
        <Icon className="h-4 w-4 text-primary" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-muted-foreground truncate">{label}</p>
        <p className="text-sm font-semibold">{value}</p>
      </div>
      {trend && <TrendArrow trend={trend} />}
    </div>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function WeeklyReports() {
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);
  const [newRecipientEmail, setNewRecipientEmail] = useState("");
  const [newRecipientName, setNewRecipientName] = useState("");
  const [newRecipientRole, setNewRecipientRole] = useState("admin");

  // Query state
  const [listData, setListData] = useState<any>(null);
  const [listLoading, setListLoading] = useState(false);
  const [latest, setLatest] = useState<any>(null);
  const [schedule, setSchedule] = useState<any>(null);
  const [emailCfg, setEmailCfg] = useState<any>(null);
  const [recipients, setRecipients] = useState<any[]>([]);
  const [detail, setDetail] = useState<any>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // Mutation pending state
  const [generatePending, setGeneratePending] = useState(false);
  const [sendEmailPending, setSendEmailPending] = useState(false);
  const [addRecipientPending, setAddRecipientPending] = useState(false);

  // ── Loaders ──────────────────────────────────────────────────────────────

  const loadList = useCallback(async () => {
    setListLoading(true);
    try {
      const res = await fetch(`${CORE_BANKING_URL}/insights/api/v1/weekly-reports?limit=20&offset=0`, { headers: authHeaders() });
      if (!res.ok) throw new Error();
      setListData(await res.json());
    } catch {
      setListData(null);
    } finally {
      setListLoading(false);
    }
  }, []);

  const loadLatest = useCallback(async () => {
    try {
      const res = await fetch(`${CORE_BANKING_URL}/insights/api/v1/weekly-reports/latest`, { headers: authHeaders() });
      if (!res.ok) throw new Error();
      setLatest(await res.json());
    } catch {
      setLatest(null);
    }
  }, []);

  const loadSchedule = useCallback(async () => {
    try {
      const res = await fetch(`${CORE_BANKING_URL}/insights/api/v1/weekly-reports/schedule`, { headers: authHeaders() });
      if (!res.ok) throw new Error();
      setSchedule(await res.json());
    } catch {
      setSchedule(null);
    }
  }, []);

  const loadEmailConfig = useCallback(async () => {
    try {
      const res = await fetch(`${CORE_BANKING_URL}/insights/api/v1/weekly-reports/email-config`, { headers: authHeaders() });
      if (!res.ok) throw new Error();
      setEmailCfg(await res.json());
    } catch {
      setEmailCfg(null);
    }
  }, []);

  const loadRecipients = useCallback(async () => {
    try {
      const res = await fetch(`${CORE_BANKING_URL}/insights/api/v1/weekly-reports/recipients`, { headers: authHeaders() });
      if (!res.ok) throw new Error();
      const json = await res.json();
      const data = json?.recipients ?? json;
      setRecipients(Array.isArray(data) ? data : []);
    } catch {
      setRecipients([]);
    }
  }, []);

  const loadDetail = useCallback(async (id: string) => {
    setDetailLoading(true);
    try {
      const res = await fetch(`${CORE_BANKING_URL}/insights/api/v1/weekly-reports/${id}`, { headers: authHeaders() });
      if (!res.ok) throw new Error();
      setDetail(await res.json());
    } catch {
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => {
    loadList();
    loadLatest();
    loadSchedule();
    loadEmailConfig();
    loadRecipients();
  }, []);

  useEffect(() => {
    if (selectedReportId) loadDetail(selectedReportId);
  }, [selectedReportId]);

  // ── Mutations ─────────────────────────────────────────────────────────────

  const generate = async (data: { notify: boolean }) => {
    setGeneratePending(true);
    try {
      const res = await fetch(`${CORE_BANKING_URL}/insights/api/v1/weekly-reports/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error("Failed to generate report");
      toast.success("Weekly report generated successfully");
      loadList();
      loadLatest();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setGeneratePending(false);
    }
  };

  const updateSchedule = async (data: any) => {
    try {
      const res = await fetch(`${CORE_BANKING_URL}/insights/api/v1/weekly-reports/schedule`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error("Failed to update schedule");
      toast.success("Schedule updated");
      loadSchedule();
    } catch (e: any) {
      toast.error(e.message);
    }
  };

  const sendEmail = async (data: { reportId: string }) => {
    setSendEmailPending(true);
    try {
      const res = await fetch(`${CORE_BANKING_URL}/insights/api/v1/weekly-reports/send-email`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error("Failed to send email");
      const json = await res.json();
      toast.success(`Email sent to ${json.sent} recipient(s)`);
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setSendEmailPending(false);
    }
  };

  const updateEmailConfig = async (data: any) => {
    try {
      const res = await fetch(`${CORE_BANKING_URL}/insights/api/v1/weekly-reports/email-config`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error("Failed to update email settings");
      toast.success("Email settings updated");
      loadEmailConfig();
    } catch (e: any) {
      toast.error(e.message);
    }
  };

  const addRecipient = async (data: { email: string; name: string; role: string }) => {
    setAddRecipientPending(true);
    try {
      const res = await fetch(`${CORE_BANKING_URL}/insights/api/v1/weekly-reports/recipients`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...authHeaders() },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error("Failed to add recipient");
      toast.success("Recipient added");
      setNewRecipientEmail("");
      setNewRecipientName("");
      loadRecipients();
      loadEmailConfig();
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setAddRecipientPending(false);
    }
  };

  const removeRecipient = async (data: { email: string }) => {
    try {
      const res = await fetch(
        `${CORE_BANKING_URL}/insights/api/v1/weekly-reports/recipients/${encodeURIComponent(data.email)}`,
        { method: "DELETE", headers: authHeaders() }
      );
      if (!res.ok) throw new Error("Failed to remove recipient");
      toast.success("Recipient removed");
      loadRecipients();
      loadEmailConfig();
    } catch (e: any) {
      toast.error(e.message);
    }
  };

  const handlePdfExport = async () => {
    if (!selectedReportId) return;
    try {
      const res = await fetch(
        `${CORE_BANKING_URL}/insights/api/v1/weekly-reports/${selectedReportId}/pdf-html`,
        { headers: authHeaders() }
      );
      if (!res.ok) throw new Error("Failed to generate PDF");
      const json = await res.json();
      const blob = new Blob([json.html], { type: "text/html" });
      const url = URL.createObjectURL(blob);
      const printWindow = window.open(url, "_blank");
      if (printWindow) {
        printWindow.onload = () => printWindow.print();
      }
      toast.success("PDF export opened — use your browser print dialog to save as PDF");
    } catch {
      toast.error("Failed to generate PDF");
    }
  };

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <FileText className="h-6 w-6 text-primary" />
            Weekly Health Reports
          </h1>
          <p className="text-muted-foreground mt-1">
            Automated system health summaries with trend analysis, email delivery, and PDF export
          </p>
        </div>
        <Button onClick={() => generate({ notify: true })} disabled={generatePending}>
          {generatePending ? (
            <Loader2 className="h-4 w-4 animate-spin mr-2" />
          ) : (
            <Play className="h-4 w-4 mr-2" />
          )}
          Generate Now
        </Button>
      </div>

      {/* Latest Report Summary */}
      {latest?.report && (
        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-lg">Latest Report</CardTitle>
                <CardDescription>
                  {latest.report.period.start} → {latest.report.period.end}
                </CardDescription>
              </div>
              <div className="flex items-center gap-2">
                <ScoreBadge score={latest.report.score} />
                {latest.trends && <TrendArrow trend={latest.trends.healthScore} />}
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
              <MetricCard label="Transactions" value={latest.report.metrics.transactions.totalCount.toLocaleString()} trend={latest.trends?.transactionCount} icon={BarChart3} />
              <MetricCard label="Success Rate" value={`${latest.report.metrics.transactions.successRate}%`} trend={latest.trends?.successRate} icon={CheckCircle2} />
              <MetricCard label="Active Users" value={String(latest.report.metrics.userActivity.totalActiveUsers)} trend={latest.trends?.activeUsers} icon={Users} />
              <MetricCard label="p50 Latency" value={`${latest.report.metrics.apiPerformance.p50Ms}ms`} trend={latest.trends?.apiLatencyP50} icon={Zap} />
              <MetricCard label="Error Rate" value={`${latest.report.metrics.errors.errorRate}%`} trend={latest.trends?.errorRate} icon={AlertTriangle} />
              <MetricCard label="Uptime" value={`${latest.report.metrics.system.uptimePercent}%`} trend={latest.trends?.uptimePercent} icon={Shield} />
            </div>
            {latest.report.alerts.length > 0 && (
              <div className="mt-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                <p className="text-sm font-semibold text-red-400 mb-1">{latest.report.alerts.length} Alert(s)</p>
                {latest.report.alerts.slice(0, 3).map((a: string, i: number) => (
                  <p key={i} className="text-xs text-red-300">{a}</p>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Tabs */}
      <Tabs defaultValue="history">
        <TabsList>
          <TabsTrigger value="history"><Calendar className="h-4 w-4 mr-1" /> Report History</TabsTrigger>
          <TabsTrigger value="email"><Mail className="h-4 w-4 mr-1" /> Email Delivery</TabsTrigger>
          <TabsTrigger value="schedule"><Settings className="h-4 w-4 mr-1" /> Schedule</TabsTrigger>
        </TabsList>

        {/* ─── History Tab ──────────────────────────────────────────────── */}
        <TabsContent value="history" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <Card className="lg:col-span-1">
              <CardHeader className="pb-2"><CardTitle className="text-base">Reports</CardTitle></CardHeader>
              <CardContent className="space-y-1 max-h-[500px] overflow-y-auto">
                {listLoading && (
                  <div className="flex justify-center py-8">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                  </div>
                )}
                {listData?.reports?.map((r: any) => (
                  <button
                    key={r.id}
                    onClick={() => setSelectedReportId(r.id)}
                    className={`w-full text-left p-3 rounded-lg transition-colors ${
                      selectedReportId === r.id ? "bg-primary/10 border border-primary/30" : "hover:bg-muted/50"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium">{r.period.start}</span>
                      <ScoreBadge score={r.score} />
                    </div>
                    <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                      <span>{r.txCount.toLocaleString()} tx</span>
                      <span>{r.activeUsers} users</span>
                      <span>{r.errorRate}% errors</span>
                    </div>
                  </button>
                ))}
                {listData?.reports?.length === 0 && (
                  <p className="text-sm text-muted-foreground text-center py-8">
                    No reports yet. Click "Generate Now" to create one.
                  </p>
                )}
              </CardContent>
            </Card>

            <Card className="lg:col-span-2">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">Report Detail</CardTitle>
                  {selectedReportId && (
                    <div className="flex gap-2">
                      <Button size="sm" variant="outline" onClick={handlePdfExport}>
                        <Download className="h-4 w-4 mr-1" /> PDF
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => sendEmail({ reportId: selectedReportId })}
                        disabled={sendEmailPending}
                      >
                        {sendEmailPending ? (
                          <Loader2 className="h-4 w-4 animate-spin mr-1" />
                        ) : (
                          <Mail className="h-4 w-4 mr-1" />
                        )}
                        Email
                      </Button>
                    </div>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                {!selectedReportId && (
                  <p className="text-sm text-muted-foreground text-center py-12">
                    Select a report from the list to view details
                  </p>
                )}
                {detailLoading && (
                  <div className="flex justify-center py-12">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                  </div>
                )}
                {detail && (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm text-muted-foreground">{detail.report.period.start} → {detail.report.period.end}</p>
                        <p className="text-xs text-muted-foreground">Generated: {new Date(detail.report.generatedAt).toLocaleString()}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <ScoreBadge score={detail.report.score} />
                        {detail.trends && <TrendArrow trend={detail.trends.healthScore} />}
                      </div>
                    </div>

                    <Separator />

                    <div className="space-y-3">
                      <h4 className="text-sm font-semibold flex items-center gap-1"><BarChart3 className="h-4 w-4" /> Transactions</h4>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                        <MetricCard label="Count" value={detail.report.metrics.transactions.totalCount.toLocaleString()} trend={detail.trends?.transactionCount} icon={BarChart3} />
                        <MetricCard label="Value" value={`₦${(detail.report.metrics.transactions.totalValue / 1e6).toFixed(1)}M`} trend={detail.trends?.transactionValue} icon={TrendingUp} />
                        <MetricCard label="Success" value={`${detail.report.metrics.transactions.successRate}%`} trend={detail.trends?.successRate} icon={CheckCircle2} />
                      </div>

                      <h4 className="text-sm font-semibold flex items-center gap-1 mt-3"><Users className="h-4 w-4" /> Users</h4>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                        <MetricCard label="Active" value={String(detail.report.metrics.userActivity.totalActiveUsers)} trend={detail.trends?.activeUsers} icon={Users} />
                        <MetricCard label="New" value={String(detail.report.metrics.userActivity.newUsers)} trend={detail.trends?.newUsers} icon={Plus} />
                        <MetricCard label="Sessions" value={String(detail.report.metrics.userActivity.totalSessions)} icon={Clock} />
                      </div>

                      <h4 className="text-sm font-semibold flex items-center gap-1 mt-3"><Zap className="h-4 w-4" /> API Performance</h4>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                        <MetricCard label="p50" value={`${detail.report.metrics.apiPerformance.p50Ms}ms`} trend={detail.trends?.apiLatencyP50} icon={Zap} />
                        <MetricCard label="p99" value={`${detail.report.metrics.apiPerformance.p99Ms}ms`} trend={detail.trends?.apiLatencyP99} icon={Zap} />
                        <MetricCard label="Errors" value={`${detail.report.metrics.errors.errorRate}%`} trend={detail.trends?.errorRate} icon={AlertTriangle} />
                      </div>

                      <h4 className="text-sm font-semibold flex items-center gap-1 mt-3"><Shield className="h-4 w-4" /> Security & System</h4>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                        <MetricCard label="Uptime" value={`${detail.report.metrics.system.uptimePercent}%`} trend={detail.trends?.uptimePercent} icon={Shield} />
                        <MetricCard label="Security Events" value={String(detail.report.metrics.security.suspiciousActivities)} trend={detail.trends?.securityEvents} icon={Shield} />
                        <MetricCard label="DB Latency" value={`${detail.report.metrics.system.dbLatencyAvgMs}ms`} icon={Zap} />
                      </div>
                    </div>

                    {detail.report.alerts.length > 0 && (
                      <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                        <p className="text-sm font-semibold text-red-400 mb-2">Alerts ({detail.report.alerts.length})</p>
                        {detail.report.alerts.map((a: string, i: number) => (
                          <p key={i} className="text-xs text-red-300 flex items-start gap-1 mb-1">
                            <AlertTriangle className="h-3 w-3 mt-0.5 shrink-0" /> {a}
                          </p>
                        ))}
                      </div>
                    )}

                    {detail.report.recommendations.length > 0 && (
                      <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                        <p className="text-sm font-semibold text-emerald-400 mb-2">Recommendations ({detail.report.recommendations.length})</p>
                        {detail.report.recommendations.map((r: string, i: number) => (
                          <p key={i} className="text-xs text-emerald-300 flex items-start gap-1 mb-1">
                            <CheckCircle2 className="h-3 w-3 mt-0.5 shrink-0" /> {r}
                          </p>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* ─── Email Tab ────────────────────────────────────────────────── */}
        <TabsContent value="email" className="space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2"><Mail className="h-4 w-4" /> Email Settings</CardTitle>
                <CardDescription>Configure automatic email delivery of weekly reports</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <Label>Email Delivery Enabled</Label>
                  <Switch checked={emailCfg?.enabled ?? false} onCheckedChange={(checked) => updateEmailConfig({ enabled: checked })} />
                </div>
                <div className="flex items-center justify-between">
                  <Label>Include Full Report</Label>
                  <Switch checked={emailCfg?.includeFullReport ?? true} onCheckedChange={(checked) => updateEmailConfig({ includeFullReport: checked })} />
                </div>
                <div className="flex items-center justify-between">
                  <Label>Include PDF Attachment</Label>
                  <Switch checked={emailCfg?.includePdfAttachment ?? false} onCheckedChange={(checked) => updateEmailConfig({ includePdfAttachment: checked })} />
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2"><MailPlus className="h-4 w-4" /> Distribution List</CardTitle>
                <CardDescription>Manage who receives the weekly report emails</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex gap-2">
                  <Input placeholder="Email" value={newRecipientEmail} onChange={(e) => setNewRecipientEmail(e.target.value)} className="flex-1" />
                  <Input placeholder="Name" value={newRecipientName} onChange={(e) => setNewRecipientName(e.target.value)} className="w-32" />
                  <Select value={newRecipientRole} onValueChange={setNewRecipientRole}>
                    <SelectTrigger className="w-28"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="admin">Admin</SelectItem>
                      <SelectItem value="manager">Manager</SelectItem>
                      <SelectItem value="analyst">Analyst</SelectItem>
                      <SelectItem value="executive">Executive</SelectItem>
                    </SelectContent>
                  </Select>
                  <Button
                    size="icon"
                    onClick={() => {
                      if (newRecipientEmail && newRecipientName) {
                        addRecipient({ email: newRecipientEmail, name: newRecipientName, role: newRecipientRole });
                      }
                    }}
                    disabled={addRecipientPending || !newRecipientEmail}
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>

                <Separator />

                <div className="space-y-2 max-h-[300px] overflow-y-auto">
                  {recipients.map((r: any) => (
                    <div key={r.email} className="flex items-center justify-between p-2 rounded-lg bg-muted/30">
                      <div>
                        <p className="text-sm font-medium">{r.name}</p>
                        <p className="text-xs text-muted-foreground">{r.email}</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs">{r.role}</Badge>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-7 w-7 text-red-400 hover:text-red-300"
                          onClick={() => removeRecipient({ email: r.email })}
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                  ))}
                  {recipients.length === 0 && (
                    <p className="text-sm text-muted-foreground text-center py-4">No recipients configured</p>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* ─── Schedule Tab ─────────────────────────────────────────────── */}
        <TabsContent value="schedule">
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2"><Clock className="h-4 w-4" /> Report Schedule</CardTitle>
              <CardDescription>Configure when weekly reports are automatically generated</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 max-w-lg">
              <div className="flex items-center justify-between">
                <Label>Auto-Generate Enabled</Label>
                <Switch checked={schedule?.enabled ?? true} onCheckedChange={(checked) => updateSchedule({ enabled: checked })} />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Day of Week</Label>
                  <Select value={String(schedule?.dayOfWeek ?? 1)} onValueChange={(v) => updateSchedule({ dayOfWeek: Number(v) })}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {DAYS.map((d, i) => (
                        <SelectItem key={i} value={String(i)}>{d}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Hour (UTC)</Label>
                  <Select value={String(schedule?.hourUtc ?? 8)} onValueChange={(v) => updateSchedule({ hourUtc: Number(v) })}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {Array.from({ length: 24 }, (_, i) => (
                        <SelectItem key={i} value={String(i)}>{String(i).padStart(2, "0")}:00</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <Label>Notify Owner</Label>
                <Switch checked={schedule?.notifyOwner ?? true} onCheckedChange={(checked) => updateSchedule({ notifyOwner: checked })} />
              </div>

              <div className="space-y-2">
                <Label>Retention (weeks)</Label>
                <Select value={String(schedule?.retentionWeeks ?? 52)} onValueChange={(v) => updateSchedule({ retentionWeeks: Number(v) })}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="12">12 weeks (3 months)</SelectItem>
                    <SelectItem value="26">26 weeks (6 months)</SelectItem>
                    <SelectItem value="52">52 weeks (1 year)</SelectItem>
                    <SelectItem value="104">104 weeks (2 years)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="p-3 rounded-lg bg-muted/30 text-sm text-muted-foreground">
                <p>
                  Next report:{" "}
                  <strong>
                    {DAYS[schedule?.dayOfWeek ?? 1]} at{" "}
                    {String(schedule?.hourUtc ?? 8).padStart(2, "0")}:{String(schedule?.minuteUtc ?? 0).padStart(2, "0")} UTC
                  </strong>
                </p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
