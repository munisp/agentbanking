import DashboardLayout from "@/components/DashboardLayout";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
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
  DialogTrigger,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { useState } from "react";
import { toast } from "sonner";
import { trpc } from "@/lib/trpc";
import {
  Archive,
  Play,
  Calendar,
  Clock,
  Database,
  HardDrive,
  Trash2,
  RefreshCw,
  CheckCircle,
  XCircle,
  Loader2,
  Settings,
  FileArchive,
} from "lucide-react";

const CRON_PRESETS: Record<string, { label: string; cron: string }> = {
  daily_2am: { label: "Daily at 2:00 AM", cron: "0 2 * * *" },
  weekly_sun: { label: "Weekly (Sunday 2:00 AM)", cron: "0 2 * * 0" },
  weekly_sat: { label: "Weekly (Saturday 3:00 AM)", cron: "0 3 * * 6" },
  biweekly: {
    label: "Bi-weekly (1st & 15th at 2:00 AM)",
    cron: "0 2 1,15 * *",
  },
  monthly: { label: "Monthly (1st at 2:00 AM)", cron: "0 2 1 * *" },
};

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${(bytes / Math.pow(k, i)).toFixed(1)} ${sizes[i]}`;
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`;
}

export default function ArchivalAdmin() {
  const utils = trpc.useUtils();
  // @ts-ignore Sprint 85
  const statsQuery = trpc.archivalAdmin.getStats.useQuery();
  // @ts-ignore Sprint 85
  const historyQuery = trpc.archivalAdmin.getHistory.useQuery({ limit: 20 });

  const [triggerOpen, setTriggerOpen] = useState(false);
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [retentionDays, setRetentionDays] = useState(90);
  const [deleteAfterArchive, setDeleteAfterArchive] = useState(false);
  const [selectedTables, setSelectedTables] = useState("all");

  // Schedule state
  const [scheduleEnabled, setScheduleEnabled] = useState(false);
  const [cronPreset, setCronPreset] = useState("weekly_sun");
  const [customCron, setCustomCron] = useState("");
  const [schedRetention, setSchedRetention] = useState(90);
  const [schedDelete, setSchedDelete] = useState(false);

  // @ts-ignore Sprint 85
  const triggerMutation = trpc.archivalAdmin.triggerArchival.useMutation({
    // @ts-ignore Sprint 85
    onSuccess: data => {
      if (data.success) {
        toast.success(`Archival job ${data.jobId} started`);
        setTriggerOpen(false);
        // Poll for completion
        const poll = setInterval(() => {
          // @ts-ignore Sprint 85
          utils.archivalAdmin.getStats.invalidate();
          // @ts-ignore Sprint 85
          utils.archivalAdmin.getHistory.invalidate();
        }, 3000);
        setTimeout(() => clearInterval(poll), 120000);
      } else {
        toast.error(data.error ?? "Failed to start archival job");
      }
    },
    // @ts-ignore Sprint 85
    onError: err => toast.error(`Error: ${err.message}`),
  });

  // @ts-ignore Sprint 85
  const scheduleMutation = trpc.archivalAdmin.updateSchedule.useMutation({
    onSuccess: () => {
      toast.success("Archival schedule updated");
      setScheduleOpen(false);
      // @ts-ignore Sprint 85
      utils.archivalAdmin.getStats.invalidate();
    },
    // @ts-ignore Sprint 85
    onError: err => toast.error(`Error: ${err.message}`),
  });

  const stats = statsQuery.data;
  const schedule = stats?.schedule;
  const currentJob = stats?.currentJob;
  const history = historyQuery.data ?? [];

  // Sync schedule state when data loads
  if (schedule && !scheduleOpen) {
    if (scheduleEnabled !== schedule.enabled)
      setScheduleEnabled(schedule.enabled);
  }

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Archive className="h-6 w-6" /> Cold-Tier Archival
            </h1>
            <p className="text-muted-foreground">
              Archive old settlements and reconciliation data to compressed cold
              storage
            </p>
          </div>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                // @ts-ignore Sprint 85
                utils.archivalAdmin.getStats.invalidate();
                // @ts-ignore Sprint 85
                utils.archivalAdmin.getHistory.invalidate();
                toast.success("Refreshed");
              }}
            >
              <RefreshCw className="h-4 w-4 mr-1" /> Refresh
            </Button>
            <Dialog open={scheduleOpen} onOpenChange={setScheduleOpen}>
              <DialogTrigger asChild>
                <Button size="sm" variant="outline">
                  <Calendar className="h-4 w-4 mr-1" /> Schedule
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Configure Archival Schedule</DialogTitle>
                  <DialogDescription>
                    Set up automatic archival to run on a recurring schedule
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div className="flex items-center justify-between">
                    <Label>Enable Scheduled Archival</Label>
                    <Switch
                      checked={scheduleEnabled}
                      onCheckedChange={setScheduleEnabled}
                    />
                  </div>
                  {scheduleEnabled && (
                    <>
                      <div className="space-y-2">
                        <Label>Schedule Frequency</Label>
                        <Select
                          value={cronPreset}
                          onValueChange={setCronPreset}
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            {Object.entries(CRON_PRESETS).map(
                              ([key, { label }]) => (
                                <SelectItem key={key} value={key}>
                                  {label}
                                </SelectItem>
                              )
                            )}
                            <SelectItem value="custom">
                              Custom Cron Expression
                            </SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      {cronPreset === "custom" && (
                        <div className="space-y-2">
                          <Label>Cron Expression</Label>
                          <Input
                            placeholder="0 2 * * 0"
                            value={customCron}
                            onChange={e => setCustomCron(e.target.value)}
                          />
                          <p className="text-xs text-muted-foreground">
                            Format: minute hour day-of-month month day-of-week
                          </p>
                        </div>
                      )}
                      <div className="space-y-2">
                        <Label>Retention Period (days)</Label>
                        <Input
                          type="number"
                          min={1}
                          max={3650}
                          value={schedRetention}
                          onChange={e =>
                            setSchedRetention(Number(e.target.value))
                          }
                        />
                        <p className="text-xs text-muted-foreground">
                          Records older than this will be archived
                        </p>
                      </div>
                      <div className="flex items-center justify-between">
                        <div>
                          <Label>Delete After Archive</Label>
                          <p className="text-xs text-muted-foreground">
                            Remove archived records from the database
                          </p>
                        </div>
                        <Switch
                          checked={schedDelete}
                          onCheckedChange={setSchedDelete}
                        />
                      </div>
                    </>
                  )}
                </div>
                <DialogFooter>
                  <Button
                    variant="outline"
                    onClick={() => setScheduleOpen(false)}
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={() => {
                      const cron =
                        cronPreset === "custom"
                          ? customCron
                          : (CRON_PRESETS[cronPreset]?.cron ?? "0 2 * * 0");
                      scheduleMutation.mutate({
                        enabled: scheduleEnabled,
                        cronExpression: cron,
                        retentionDays: schedRetention,
                        deleteAfterArchive: schedDelete,
                      });
                    }}
                    disabled={scheduleMutation.isPending}
                  >
                    {scheduleMutation.isPending && (
                      <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                    )}
                    Save Schedule
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
            <Dialog open={triggerOpen} onOpenChange={setTriggerOpen}>
              <DialogTrigger asChild>
                <Button size="sm" disabled={!!currentJob}>
                  <Play className="h-4 w-4 mr-1" /> Run Archival
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Trigger Manual Archival</DialogTitle>
                  <DialogDescription>
                    Archive records older than the specified retention period
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div className="space-y-2">
                    <Label>Retention Period (days)</Label>
                    <Input
                      type="number"
                      min={1}
                      max={3650}
                      value={retentionDays}
                      onChange={e => setRetentionDays(Number(e.target.value))}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Tables to Archive</Label>
                    <Select
                      value={selectedTables}
                      onValueChange={setSelectedTables}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Tables</SelectItem>
                        <SelectItem value="settlements">
                          Settlements Only
                        </SelectItem>
                        <SelectItem value="batches">
                          Reconciliation Batches Only
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex items-center justify-between">
                    <div>
                      <Label>Delete After Archive</Label>
                      <p className="text-xs text-muted-foreground text-red-400">
                        Warning: This permanently removes records from the
                        database
                      </p>
                    </div>
                    <Switch
                      checked={deleteAfterArchive}
                      onCheckedChange={setDeleteAfterArchive}
                    />
                  </div>
                  {stats && (
                    <div className="p-3 bg-muted/50 rounded-lg text-sm space-y-1">
                      <p>
                        <strong>Eligible settlements:</strong>{" "}
                        {stats.eligibleSettlements.toLocaleString()}
                      </p>
                      <p>
                        <strong>Eligible batches:</strong>{" "}
                        {stats.eligibleBatches.toLocaleString()}
                      </p>
                      <p>
                        <strong>Cutoff date:</strong>{" "}
                        {new Date(stats.cutoffDate).toLocaleDateString()}
                      </p>
                    </div>
                  )}
                </div>
                <DialogFooter>
                  <Button
                    variant="outline"
                    onClick={() => setTriggerOpen(false)}
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={() => {
                      triggerMutation.mutate({
                        retentionDays,
                        deleteAfterArchive,
                        tables: [selectedTables as any],
                      });
                    }}
                    disabled={triggerMutation.isPending}
                    variant={deleteAfterArchive ? "destructive" : "default"}
                  >
                    {triggerMutation.isPending && (
                      <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                    )}
                    {deleteAfterArchive ? "Archive & Delete" : "Start Archival"}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground flex items-center gap-1">
                <Database className="h-4 w-4" /> Eligible Settlements
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stats?.eligibleSettlements?.toLocaleString() ?? "—"}
              </div>
              <p className="text-xs text-muted-foreground">
                Older than {stats?.retentionDays ?? 90} days
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground flex items-center gap-1">
                <FileArchive className="h-4 w-4" /> Eligible Batches
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stats?.eligibleBatches?.toLocaleString() ?? "—"}
              </div>
              <p className="text-xs text-muted-foreground">
                Reconciliation batches
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground flex items-center gap-1">
                <Calendar className="h-4 w-4" /> Schedule
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {schedule?.enabled ? (
                  <Badge className="bg-emerald-500/20 text-emerald-400">
                    Active
                  </Badge>
                ) : (
                  <Badge className="bg-yellow-500/20 text-yellow-400">
                    Disabled
                  </Badge>
                )}
              </div>
              <p className="text-xs text-muted-foreground">
                {schedule?.enabled ? schedule.cronExpression : "Not scheduled"}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground flex items-center gap-1">
                <Clock className="h-4 w-4" /> Cutoff Date
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stats?.cutoffDate
                  ? new Date(stats.cutoffDate).toLocaleDateString()
                  : "—"}
              </div>
              <p className="text-xs text-muted-foreground">
                {stats?.retentionDays ?? 90}-day retention
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Current Job Status */}
        {currentJob && (
          <Card className="border-blue-500/30">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Loader2 className="h-5 w-5 text-blue-400 animate-spin" />
                Archival Job Running
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span>
                    Job ID: <span className="font-mono">{currentJob.id}</span>
                  </span>
                  <span>
                    Started: {new Date(currentJob.startedAt).toLocaleString()}
                  </span>
                </div>
                <Progress
                  value={undefined}
                  className="h-2 [&>div]:animate-pulse"
                />
                <p className="text-xs text-muted-foreground">
                  Archiving records older than {currentJob.retentionDays}{" "}
                  days...
                </p>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Schedule Info */}
        {schedule?.enabled && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Settings className="h-5 w-5" /> Active Schedule
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <p className="text-muted-foreground">Cron Expression</p>
                  <p className="font-mono font-medium">
                    {schedule.cronExpression}
                  </p>
                </div>
                <div>
                  <p className="text-muted-foreground">Retention</p>
                  <p className="font-medium">{schedule.retentionDays} days</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Delete After Archive</p>
                  <p className="font-medium">
                    {schedule.deleteAfterArchive ? "Yes" : "No"}
                  </p>
                </div>
                <div>
                  <p className="text-muted-foreground">Next Run</p>
                  <p className="font-medium">
                    {schedule.nextRun
                      ? new Date(schedule.nextRun).toLocaleString()
                      : "—"}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Job History */}
        <Card>
          <CardHeader>
            <CardTitle>Archival Job History</CardTitle>
            <CardDescription>
              Recent archival operations and their results
            </CardDescription>
          </CardHeader>
          <CardContent>
            {history.length === 0 ? (
              <p className="text-muted-foreground text-center py-8">
                No archival jobs have been run yet
              </p>
            ) : (
              <div className="space-y-3">
                {history.map((job: any) => (
                  <div
                    key={job.id}
                    className="p-4 border border-border/50 rounded-lg space-y-2"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {job.status === "completed" ? (
                          <CheckCircle className="h-4 w-4 text-emerald-400" />
                        ) : job.status === "failed" ? (
                          <XCircle className="h-4 w-4 text-red-400" />
                        ) : (
                          <Loader2 className="h-4 w-4 text-blue-400 animate-spin" />
                        )}
                        <span className="font-mono text-sm">{job.id}</span>
                        <Badge
                          className={
                            job.status === "completed"
                              ? "bg-emerald-500/20 text-emerald-400"
                              : job.status === "failed"
                                ? "bg-red-500/20 text-red-400"
                                : "bg-blue-500/20 text-blue-400"
                          }
                        >
                          {job.status}
                        </Badge>
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {new Date(job.startedAt).toLocaleString()}
                      </span>
                    </div>
                    {job.result && (
                      <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-xs">
                        <div>
                          <span className="text-muted-foreground">
                            Archived:
                          </span>{" "}
                          <span className="font-medium">
                            {job.result.totalArchived.toLocaleString()}
                          </span>
                        </div>
                        <div>
                          <span className="text-muted-foreground">
                            Deleted:
                          </span>{" "}
                          <span className="font-medium">
                            {job.result.totalDeleted.toLocaleString()}
                          </span>
                        </div>
                        <div>
                          <span className="text-muted-foreground">
                            Duration:
                          </span>{" "}
                          <span className="font-medium">
                            {formatDuration(job.result.duration)}
                          </span>
                        </div>
                        <div>
                          <span className="text-muted-foreground">By:</span>{" "}
                          <span className="font-medium">{job.triggeredBy}</span>
                        </div>
                        <div>
                          <span className="text-muted-foreground">
                            Retention:
                          </span>{" "}
                          <span className="font-medium">
                            {job.retentionDays}d
                          </span>
                        </div>
                      </div>
                    )}
                    {job.result?.tables?.map((t: any) => (
                      <div
                        key={t.table}
                        className="flex items-center gap-4 text-xs pl-6"
                      >
                        <HardDrive className="h-3 w-3 text-muted-foreground" />
                        <span className="font-mono">{t.table}</span>
                        <span>{t.archivedCount.toLocaleString()} rows</span>
                        <span>{formatBytes(t.archiveSizeBytes)}</span>
                        <span>{t.compressionRatio}x compression</span>
                        <Badge className="text-[10px] bg-muted">
                          {t.format}
                        </Badge>
                      </div>
                    ))}
                    {job.error && (
                      <p className="text-xs text-red-400 pl-6">{job.error}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
