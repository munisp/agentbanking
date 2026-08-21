/**
 * WeeklyReports — Automated weekly report generation, scheduling, and email distribution
 */
import { useState } from "react";
import DashboardLayout from "@/components/DashboardLayout";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
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
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";
import { trpc } from "@/lib/trpc";
import {
  FileText,
  Calendar,
  Clock,
  Download,
  Mail,
  MailPlus,
  Trash2,
  Play,
  TrendingUp,
  TrendingDown,
  Minus,
  BarChart3,
  Users,
  Zap,
  Shield,
  AlertTriangle,
  CheckCircle2,
  Plus,
  ArrowUp,
  ArrowDown,
  FileDown,
} from "lucide-react";

// @ts-ignore Sprint 85
const DAYS = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
];

function TrendArrow({ trend }: { trend: "up" | "down" | "flat" }) {
  if (trend === "up")
    return <TrendingUp className="h-4 w-4 text-emerald-400" />;
  if (trend === "down")
    return <TrendingDown className="h-4 w-4 text-red-400" />;
  return <Minus className="h-4 w-4 text-muted-foreground" />;
}

function ScoreBadge({ score }: { score: number }) {
  const color =
    score >= 80
      ? "bg-emerald-500/20 text-emerald-400"
      : score >= 60
        ? "bg-yellow-500/20 text-yellow-400"
        : "bg-red-500/20 text-red-400";
  return <Badge className={color}>Score: {score}/100</Badge>;
}

function MetricCard({
  label,
  value,
  trend,
  icon: Icon,
}: {
  label: string;
  value: string;
  trend?: "up" | "down" | "flat";
  icon: any;
}) {
  return (
    <div className="flex items-center gap-3 p-3 rounded-lg bg-muted/30">
      <Icon className="h-5 w-5 text-muted-foreground" />
      <div className="flex-1 min-w-0">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-sm font-semibold truncate">{value}</p>
      </div>
      {trend && <TrendArrow trend={trend} />}
    </div>
  );
}

export default function WeeklyReports() {
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);
  const [newRecipientEmail, setNewRecipientEmail] = useState("");
  const [newRecipientName, setNewRecipientName] = useState("");
  const [newRecipientRole, setNewRecipientRole] = useState<
    "admin" | "manager" | "analyst" | "executive"
  >("admin");

  const { data: listData, isLoading: listLoading } =
    trpc.weeklyReports.list.useQuery({ limit: 52 }) as any;
  const { data: detail } = trpc.weeklyReports.get.useQuery(
    { reportId: selectedReportId! },
    { enabled: !!selectedReportId }
  ) as any;
  const { data: emailCfg } = trpc.weeklyReports.getEmailConfig.useQuery() as any;
  const { data: schedule } =
    trpc.weeklyReports.getReportSchedule.useQuery() as any;
  const { data: recipients } = trpc.weeklyReports.listRecipients.useQuery() as any;

  const generateNow = trpc.weeklyReports.generateNow.useMutation({
    onSuccess: data => {
      toast.success(
        `Report generated! Score: ${data.report.score}/100 · Sent to ${data.emailsSent} recipients`
      );
      setSelectedReportId(data.report.id);
    },
    onError: err => toast.error(err.message),
  }) as any;

  const updateEmailConfigM = trpc.weeklyReports.updateEmailConfig.useMutation({
    onSuccess: () => toast.success("Email config updated"),
  }) as any;

  const updateScheduleM = trpc.weeklyReports.updateSchedule.useMutation({
    onSuccess: () => toast.success("Schedule updated"),
  }) as any;

  const addRecipientM = trpc.weeklyReports.addRecipient.useMutation({
    onSuccess: () => {
      toast.success("Recipient added");
      setNewRecipientEmail("");
      setNewRecipientName("");
    },
    onError: err => toast.error(err.message),
  }) as any;

  const removeRecipientM = trpc.weeklyReports.removeRecipient.useMutation({
    onSuccess: () => toast.success("Recipient removed"),
  }) as any;

  const reports = listData?.reports ?? [];

  // PDF Export handler
  const handlePdfExport = () => {
    if (!detail?.report) return;
    const report = detail.report;
    const printWindow = window.open("", "_blank");
    if (!printWindow) {
      toast.error("Popup blocked — allow popups for PDF export");
      return;
    }
    const html = `
      <!DOCTYPE html>
      <html>
      <head>
        <title>Weekly Report — ${report.period.start}</title>
        <style>
          body { font-family: Inter, sans-serif; margin: 40px; color: #1a1a2e; }
          h1 { color: #6366f1; border-bottom: 2px solid #6366f1; padding-bottom: 8px; }
          h2 { color: #374151; margin-top: 24px; }
          .metric { display: inline-block; margin: 8px 16px 8px 0; padding: 12px; background: #f3f4f6; border-radius: 8px; }
          .metric-label { font-size: 12px; color: #6b7280; }
          .metric-value { font-size: 18px; font-weight: 700; }
          .score { display: inline-block; padding: 4px 12px; border-radius: 9999px; font-weight: 700; }
          .score-high { background: #d1fae5; color: #065f46; }
          .score-mid { background: #fef3c7; color: #92400e; }
          .score-low { background: #fee2e2; color: #991b1b; }
          .alert { padding: 8px 12px; background: #fee2e2; border-radius: 6px; margin: 4px 0; font-size: 13px; }
          .rec { padding: 8px 12px; background: #d1fae5; border-radius: 6px; margin: 4px 0; font-size: 13px; }
          table { border-collapse: collapse; width: 100%; margin-top: 12px; }
          td, th { border: 1px solid #e5e7eb; padding: 6px 10px; font-size: 13px; text-align: left; }
          th { background: #f9fafb; }
          .footer { margin-top: 32px; font-size: 11px; color: #9ca3af; }
        </style>
      </head>
      <body>
        <h1>54agent Weekly Report</h1>
        <p><strong>Period:</strong> ${report.period.start} → ${report.period.end}</p>
        <p><strong>Generated:</strong> ${new Date(report.generatedAt).toLocaleString()}</p>
        <p><span class="score ${report.score >= 80 ? "score-high" : report.score >= 60 ? "score-mid" : "score-low"}">Health Score: ${report.score}/100</span></p>

        <h2>Transactions</h2>
        <div class="metric"><div class="metric-label">Count</div><div class="metric-value">${report.metrics.transactions.totalCount.toLocaleString()}</div></div>
        <div class="metric"><div class="metric-label">Value</div><div class="metric-value">₦${(report.metrics.transactions.totalValue / 1e6).toFixed(1)}M</div></div>
        <div class="metric"><div class="metric-label">Success Rate</div><div class="metric-value">${report.metrics.transactions.successRate}%</div></div>

        <h2>Users</h2>
        <div class="metric"><div class="metric-label">Active Users</div><div class="metric-value">${report.metrics.userActivity.totalActiveUsers}</div></div>
        <div class="metric"><div class="metric-label">New Users</div><div class="metric-value">${report.metrics.userActivity.newUsers}</div></div>
        <div class="metric"><div class="metric-label">Sessions</div><div class="metric-value">${report.metrics.userActivity.totalSessions}</div></div>

        <h2>API Performance</h2>
        <div class="metric"><div class="metric-label">p50 Latency</div><div class="metric-value">${report.metrics.apiPerformance.p50Ms}ms</div></div>
        <div class="metric"><div class="metric-label">p99 Latency</div><div class="metric-value">${report.metrics.apiPerformance.p99Ms}ms</div></div>
        <div class="metric"><div class="metric-label">Error Rate</div><div class="metric-value">${report.metrics.errors.errorRate}%</div></div>

        <h2>System & Security</h2>
        <div class="metric"><div class="metric-label">Uptime</div><div class="metric-value">${report.metrics.system.uptimePercent}%</div></div>
        <div class="metric"><div class="metric-label">Security Events</div><div class="metric-value">${report.metrics.security.suspiciousActivities}</div></div>
        <div class="metric"><div class="metric-label">DB Latency</div><div class="metric-value">${report.metrics.system.dbLatencyAvgMs}ms</div></div>

        ${
          report.alerts.length > 0
            ? `<h2>Alerts</h2>${report.alerts.map((a: any) => `<div class="alert">⚠ ${a}</div>`).join("")}`
            : ""
        }
        ${
          report.recommendations.length > 0
            ? `<h2>Recommendations</h2>${report.recommendations.map((r: any) => `<div class="rec">✓ ${r}</div>`).join("")}`
            : ""
        }

        <div class="footer">
          Generated by 54agent Platform · Weekly Report ${report.id} · ${new Date().toISOString()}
        </div>
      </body>
      </html>
    `;
    printWindow.document.write(html);
    printWindow.document.close();
    setTimeout(() => printWindow.print(), 500);
    toast.success("PDF export opened — use browser Print → Save as PDF");
  };

  return (
    <DashboardLayout>
      <div className="p-6 max-w-7xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <FileText className="h-6 w-6" /> Weekly Reports
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Automated weekly health reports with email distribution
            </p>
          </div>
          <div className="flex items-center gap-2">
            {selectedReportId && detail?.report && (
              <Button variant="outline" onClick={handlePdfExport}>
                <FileDown className="h-4 w-4 mr-2" />
                Export PDF
              </Button>
            )}
            <Button
              onClick={() => generateNow.mutate()}
              disabled={generateNow.isPending}
            >
              <Play className="h-4 w-4 mr-2" />
              {generateNow.isPending ? "Generating..." : "Generate Now"}
            </Button>
          </div>
        </div>

        <Tabs defaultValue="reports">
          <TabsList>
            <TabsTrigger value="reports">Reports</TabsTrigger>
            <TabsTrigger value="email">Email Settings</TabsTrigger>
            <TabsTrigger value="schedule">Schedule</TabsTrigger>
          </TabsList>

          {/* ─── Reports Tab ──────────────────────────────────────────────── */}
          <TabsContent value="reports" className="space-y-4">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {/* Report List */}
              <Card className="lg:col-span-1">
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Calendar className="h-4 w-4" /> Report History
                  </CardTitle>
                  <CardDescription>
                    {listData?.total ?? 0} reports generated
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-2 max-h-[600px] overflow-y-auto">
                  {listLoading ? (
                    <p className="text-sm text-muted-foreground">Loading...</p>
                  ) : reports.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      No reports yet. Click "Generate Now" to create one.
                    </p>
                  ) : (
                    reports.map((r: any) => (
                      <div
                        key={r.id}
                        className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                          selectedReportId === r.id
                            ? "border-primary bg-primary/5"
                            : "border-border hover:bg-muted/50"
                        }`}
                        onClick={() => setSelectedReportId(r.id)}
                      >
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium">
                            Week of {r.period.start}
                          </span>
                          <ScoreBadge score={r.score} />
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                          {r.metrics.transactions.totalCount.toLocaleString()}{" "}
                          txns ·{" "}
                          {r.metrics.userActivity.totalActiveUsers} users
                        </p>
                      </div>
                    ))
                  )}
                </CardContent>
              </Card>

              {/* Report Detail */}
              <Card className="lg:col-span-2">
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <BarChart3 className="h-4 w-4" /> Report Details
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {!selectedReportId ? (
                    <p className="text-sm text-muted-foreground py-8 text-center">
                      Select a report from the list to view details
                    </p>
                  ) : !detail?.report ? (
                    <p className="text-sm text-muted-foreground py-8 text-center">
                      Loading report...
                    </p>
                  ) : (
                    <div className="space-y-4">
                    {/* Score + Period */}
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="text-sm text-muted-foreground">
                          {detail.report.period.start} →{" "}
                          {detail.report.period.end}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Generated:{" "}
                          {new Date(detail.report.generatedAt).toLocaleString()}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <ScoreBadge score={detail.report.score} />
                        {detail.trends && (
                          <TrendArrow trend={detail.trends.healthScore} />
                        )}
                      </div>
                    </div>

                    <Separator />

                    {/* Metrics Grid with Trends */}
                    <div className="space-y-3">
                      <h4 className="text-sm font-semibold flex items-center gap-1">
                        <BarChart3 className="h-4 w-4" /> Transactions
                      </h4>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                        <MetricCard
                          label="Count"
                          value={detail.report.metrics.transactions.totalCount.toLocaleString()}
                          trend={detail.trends?.transactionCount}
                          icon={BarChart3}
                        />
                        <MetricCard
                          label="Value"
                          value={`₦${(detail.report.metrics.transactions.totalValue / 1e6).toFixed(1)}M`}
                          trend={detail.trends?.transactionValue}
                          icon={TrendingUp}
                        />
                        <MetricCard
                          label="Success"
                          value={`${detail.report.metrics.transactions.successRate}%`}
                          trend={detail.trends?.successRate}
                          icon={CheckCircle2}
                        />
                      </div>

                      <h4 className="text-sm font-semibold flex items-center gap-1 mt-3">
                        <Users className="h-4 w-4" /> Users
                      </h4>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                        <MetricCard
                          label="Active"
                          value={String(
                            detail.report.metrics.userActivity.totalActiveUsers
                          )}
                          trend={detail.trends?.activeUsers}
                          icon={Users}
                        />
                        <MetricCard
                          label="New"
                          value={String(
                            detail.report.metrics.userActivity.newUsers
                          )}
                          trend={detail.trends?.newUsers}
                          icon={Plus}
                        />
                        <MetricCard
                          label="Sessions"
                          value={String(
                            detail.report.metrics.userActivity.totalSessions
                          )}
                          icon={Clock}
                        />
                      </div>

                      <h4 className="text-sm font-semibold flex items-center gap-1 mt-3">
                        <Zap className="h-4 w-4" /> API Performance
                      </h4>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                        <MetricCard
                          label="p50"
                          value={`${detail.report.metrics.apiPerformance.p50Ms}ms`}
                          trend={detail.trends?.apiLatencyP50}
                          icon={Zap}
                        />
                        <MetricCard
                          label="p99"
                          value={`${detail.report.metrics.apiPerformance.p99Ms}ms`}
                          trend={detail.trends?.apiLatencyP99}
                          icon={Zap}
                        />
                        <MetricCard
                          label="Errors"
                          value={`${detail.report.metrics.errors.errorRate}%`}
                          trend={detail.trends?.errorRate}
                          icon={AlertTriangle}
                        />
                      </div>

                      <h4 className="text-sm font-semibold flex items-center gap-1 mt-3">
                        <Shield className="h-4 w-4" /> Security & System
                      </h4>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                        <MetricCard
                          label="Uptime"
                          value={`${detail.report.metrics.system.uptimePercent}%`}
                          trend={detail.trends?.uptimePercent}
                          icon={Shield}
                        />
                        <MetricCard
                          label="Security Events"
                          value={String(
                            detail.report.metrics.security.suspiciousActivities
                          )}
                          trend={detail.trends?.securityEvents}
                          icon={Shield}
                        />
                        <MetricCard
                          label="DB Latency"
                          value={`${detail.report.metrics.system.dbLatencyAvgMs}ms`}
                          icon={Zap}
                        />
                      </div>
                    </div>

                    {/* Alerts */}
                    {detail.report.alerts.length > 0 && (
                      <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20">
                        <p className="text-sm font-semibold text-red-400 mb-2">
                          Alerts ({detail.report.alerts.length})
                        </p>
                        {detail.report.alerts.map((a: any, i: any) => (
                          <p
                            key={i}
                            className="text-xs text-red-300 flex items-start gap-1 mb-1"
                          >
                            <AlertTriangle className="h-3 w-3 mt-0.5 shrink-0" />{" "}
                            {a}
                          </p>
                        ))}
                      </div>
                    )}

                    {/* Recommendations */}
                    {detail.report.recommendations.length > 0 && (
                      <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                        <p className="text-sm font-semibold text-emerald-400 mb-2">
                          Recommendations (
                          {detail.report.recommendations.length})
                        </p>
                        {detail.report.recommendations.map((r: any, i: any) => (
                          <p
                            key={i}
                            className="text-xs text-emerald-300 flex items-start gap-1 mb-1"
                          >
                            <CheckCircle2 className="h-3 w-3 mt-0.5 shrink-0" />{" "}
                            {r}
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
            {/* Email Settings */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Mail className="h-4 w-4" /> Email Settings
                </CardTitle>
                <CardDescription>
                  Configure automatic email delivery of weekly reports
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <Label>Email Delivery Enabled</Label>
                  <Switch
                    checked={emailCfg?.enabled ?? false}
                    onCheckedChange={checked =>
                      updateEmailConfigM.mutate({ enabled: checked })
                    }
                  />
                </div>
                <div className="flex items-center justify-between">
                  <Label>Include Full Report</Label>
                  <Switch
                    checked={emailCfg?.includeFullReport ?? true}
                    onCheckedChange={checked =>
                      updateEmailConfigM.mutate({ includeFullReport: checked })
                    }
                  />
                </div>
                <div className="flex items-center justify-between">
                  <Label>Include PDF Attachment</Label>
                  <Switch
                    checked={emailCfg?.includePdfAttachment ?? false}
                    onCheckedChange={checked =>
                      updateEmailConfigM.mutate({
                        includePdfAttachment: checked,
                      })
                    }
                  />
                </div>
              </CardContent>
            </Card>

            {/* Distribution List */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <MailPlus className="h-4 w-4" /> Distribution List
                </CardTitle>
                <CardDescription>
                  Manage who receives the weekly report emails
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Add Recipient Form */}
                <div className="flex gap-2">
                  <Input
                    placeholder="Email"
                    value={newRecipientEmail}
                    onChange={e => setNewRecipientEmail(e.target.value)}
                    className="flex-1"
                  />
                  <Input
                    placeholder="Name"
                    value={newRecipientName}
                    onChange={e => setNewRecipientName(e.target.value)}
                    className="w-32"
                  />
                  <Select
                    value={newRecipientRole}
                    onValueChange={setNewRecipientRole}
                  >
                    <SelectTrigger className="w-28">
                      <SelectValue />
                    </SelectTrigger>
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
                        addRecipientM.mutate({
                          email: newRecipientEmail,
                          name: newRecipientName,
                          role: newRecipientRole,
                        });
                      }
                    }}
                    disabled={addRecipientM.isPending || !newRecipientEmail}
                  >
                    <Plus className="h-4 w-4" />
                  </Button>
                </div>

                <Separator />

                {/* Recipient List */}
                <div className="space-y-2 max-h-[300px] overflow-y-auto">
                  {recipients?.map((r: any) => (
                    <div
                      key={r.email}
                      className="flex items-center justify-between p-2 rounded-lg bg-muted/30"
                    >
                      <div>
                        <p className="text-sm font-medium">{r.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {r.email}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant="outline" className="text-xs">
                          {r.role}
                        </Badge>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-7 w-7 text-red-400 hover:text-red-300"
                          onClick={() =>
                            removeRecipientM.mutate({ email: r.email })
                          }
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                  ))}
                  {(!recipients || recipients.length === 0) && (
                    <p className="text-sm text-muted-foreground text-center py-4">
                      No recipients configured
                    </p>
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
              <CardTitle className="text-base flex items-center gap-2">
                <Clock className="h-4 w-4" /> Report Schedule
              </CardTitle>
              <CardDescription>
                Configure when weekly reports are automatically generated
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4 max-w-lg">
              <div className="flex items-center justify-between">
                <Label>Auto-Generate Enabled</Label>
                <Switch
                  checked={schedule?.enabled ?? true}
                  onCheckedChange={checked =>
                    updateScheduleM.mutate({ enabled: checked })
                  }
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Day of Week</Label>
                  <Select
                    value={String(schedule?.dayOfWeek ?? 1)}
                    onValueChange={v =>
                      updateScheduleM.mutate({ dayOfWeek: Number(v) })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {DAYS.map((d, i) => (
                        <SelectItem key={i} value={String(i)}>
                          {d}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label>Hour (UTC)</Label>
                  <Select
                    value={String(schedule?.hourUtc ?? 8)}
                    onValueChange={v =>
                      updateScheduleM.mutate({ hourUtc: Number(v) })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {Array.from({ length: 24 }, (_, i) => (
                        <SelectItem key={i} value={String(i)}>
                          {String(i).padStart(2, "0")}:00
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <Label>Notify Owner</Label>
                <Switch
                  checked={schedule?.notifyOwner ?? true}
                  onCheckedChange={checked =>
                    updateScheduleM.mutate({ notifyOwner: checked })
                  }
                />
              </div>

              <div className="space-y-2">
                <Label>Retention (weeks)</Label>
                <Select
                  value={String(schedule?.retentionWeeks ?? 52)}
                  onValueChange={v =>
                    updateScheduleM.mutate({ retentionWeeks: Number(v) })
                  }
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
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
                    {String(schedule?.hourUtc ?? 8).padStart(2, "0")}:
                    {String(schedule?.minuteUtc ?? 0).padStart(2, "0")} UTC
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
