import DashboardLayout from "@/components/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useState, useCallback, useMemo } from "react";
import { toast } from "sonner";
import { trpc } from "@/lib/trpc";
import {
  useSettlementProgressSocket,
  type BatchProgressEvent,
} from "@/hooks/useSocket";
import {
  RefreshCw,
  Layers,
  CheckCircle,
  Clock,
  DollarSign,
  Activity,
  Zap,
  AlertTriangle,
} from "lucide-react";

const STATUS_COLORS: Record<string, string> = {
  completed: "bg-emerald-500/20 text-emerald-400",
  processing: "bg-blue-500/20 text-blue-400",
  pending: "bg-yellow-500/20 text-yellow-400",
  failed: "bg-red-500/20 text-red-400",
};

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
}

function formatRate(rate: number): string {
  if (rate >= 1000) return `${(rate / 1000).toFixed(1)}K/s`;
  return `${rate}/s`;
}

// ─── Progress Bar Component ──────────────────────────────────────────────────

function BatchProgressBar({ event }: { event: BatchProgressEvent }) {
  const isCompleted = event.type === "batch.completed";
  const isFailed = event.type === "batch.failed";
  const isStarted = event.type === "batch.started";

  const statusColor = isFailed
    ? "text-red-400"
    : isCompleted
      ? "text-emerald-400"
      : "text-blue-400";

  const statusLabel = isFailed
    ? "Failed"
    : isCompleted
      ? "Completed"
      : isStarted
        ? "Starting..."
        : "Processing";

  const progressValue = event.percentage;
  const elapsed = Math.round((event.updatedAt - event.startedAt) / 1000);

  return (
    <div className="p-4 border border-border/50 rounded-lg bg-card/50 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {isFailed ? (
            <AlertTriangle className="h-4 w-4 text-red-400" />
          ) : isCompleted ? (
            <CheckCircle className="h-4 w-4 text-emerald-400" />
          ) : (
            <Activity className="h-4 w-4 text-blue-400 animate-pulse" />
          )}
          <span className="font-mono text-sm font-medium">{event.batchId}</span>
          <Badge
            className={`text-xs ${isFailed ? "bg-red-500/20 text-red-400" : isCompleted ? "bg-emerald-500/20 text-emerald-400" : "bg-blue-500/20 text-blue-400"}`}
          >
            {statusLabel}
          </Badge>
        </div>
        <span className={`text-sm font-bold ${statusColor}`}>
          {event.percentage}%
        </span>
      </div>

      {/* Progress bar */}
      <div className="relative">
        <Progress
          value={progressValue}
          className={`h-3 ${isFailed ? "[&>div]:bg-red-500" : isCompleted ? "[&>div]:bg-emerald-500" : "[&>div]:bg-blue-500"}`}
        />
      </div>

      {/* Stats row */}
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>
          {event.processed.toLocaleString()} / {event.total.toLocaleString()}{" "}
          items
        </span>
        <div className="flex items-center gap-4">
          {event.rate > 0 && (
            <span className="flex items-center gap-1">
              <Zap className="h-3 w-3" /> {formatRate(event.rate)}
            </span>
          )}
          {event.errors > 0 && (
            <span className="text-red-400 flex items-center gap-1">
              <AlertTriangle className="h-3 w-3" /> {event.errors} errors
            </span>
          )}
          {!isCompleted && !isFailed && event.estimatedSecondsRemaining > 0 && (
            <span>ETA: {formatDuration(event.estimatedSecondsRemaining)}</span>
          )}
          <span>Elapsed: {formatDuration(elapsed)}</span>
        </div>
      </div>
    </div>
  );
}

// ─── Main Page ───────────────────────────────────────────────────────────────

export default function SettlementBatchProcessor() {
  const [statusFilter, setStatusFilter] = useState("all");
  const [activeProgressEvents, setActiveProgressEvents] = useState<
    Map<string, BatchProgressEvent>
  >(new Map());

  // @ts-ignore Sprint 85
  const statsQuery = trpc.settlementBatchProcessor.getStats.useQuery();
  // @ts-ignore Sprint 85
  const batchesQuery = trpc.settlementBatchProcessor.listBatches.useQuery({
    status: statusFilter as any,
    limit: 50,
    offset: 0,
  });
  const stats = statsQuery.data as any;
  const batches = (batchesQuery.data as any)?.batches ?? [];

  // Socket.IO progress handler
  const handleProgress = useCallback(
    (event: BatchProgressEvent) => {
      setActiveProgressEvents(prev => {
        const next = new Map(prev);
        if (event.type === "batch.completed" || event.type === "batch.failed") {
          // Keep completed/failed for 10 seconds then remove
          next.set(event.batchId, event);
          setTimeout(() => {
            setActiveProgressEvents(p => {
              const updated = new Map(p);
              updated.delete(event.batchId);
              return updated;
            });
          }, 10000);
        } else {
          next.set(event.batchId, event);
        }
        return next;
      });

      // Toast notifications for key events
      if (event.type === "batch.started") {
        toast.info(
          `Settlement batch ${event.batchId} started (${event.total.toLocaleString()} items)`
        );
      } else if (event.type === "batch.completed") {
        toast.success(
          `Batch ${event.batchId} completed: ${event.processed.toLocaleString()} items processed`
        );
        // Refresh data
        statsQuery.refetch();
        batchesQuery.refetch();
      } else if (event.type === "batch.failed") {
        toast.error(`Batch ${event.batchId} failed at ${event.percentage}%`);
      }
    },
    [statsQuery, batchesQuery]
  );

  useSettlementProgressSocket(handleProgress);

  const progressEvents = useMemo(
    () =>
      Array.from(activeProgressEvents.values()).sort(
        (a: any, b: any) => b.updatedAt - a.updatedAt
      ),
    [activeProgressEvents]
  );

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Layers className="h-6 w-6" /> Settlement Batch Processor
            </h1>
            <p className="text-muted-foreground">
              Monitor and manage settlement batch processing with real-time
              progress
            </p>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              statsQuery.refetch();
              batchesQuery.refetch();
              toast.success("Data refreshed");
            }}
          >
            <RefreshCw className="h-4 w-4 mr-1" /> Refresh
          </Button>
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground flex items-center gap-1">
                <Layers className="h-4 w-4" /> Total Batches
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stats?.totalBatches ?? "—"}
              </div>
              <p className="text-xs text-muted-foreground">
                {stats?.totalSettlements ?? 0} settlements
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground flex items-center gap-1">
                <CheckCircle className="h-4 w-4" /> Settled
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-500">
                {stats?.settled ?? "—"}
              </div>
              <p className="text-xs text-muted-foreground">
                Reconciliation: {stats?.reconciliationRate ?? 0}%
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground flex items-center gap-1">
                <Clock className="h-4 w-4" /> Processing
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-blue-500">
                {stats?.processing ?? "—"}
              </div>
              <p className="text-xs text-muted-foreground">
                {stats?.pending ?? 0} pending
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground flex items-center gap-1">
                <DollarSign className="h-4 w-4" /> Total Volume
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                ₦{stats?.totalVolume?.toLocaleString() ?? "—"}
              </div>
              <p className="text-xs text-muted-foreground">
                Avg batch: ₦{stats?.avgBatchSize?.toLocaleString() ?? 0}
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Real-Time Progress Section */}
        {progressEvents.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Activity className="h-5 w-5 text-blue-400 animate-pulse" />
                Live Batch Progress
                <Badge className="bg-blue-500/20 text-blue-400 text-xs ml-2">
                  {
                    progressEvents.filter(
                      (e: any) =>
                        e.type === "batch.progress" ||
                        e.type === "batch.started"
                    ).length
                  }{" "}
                  active
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {progressEvents.map((event: any) => (
                <BatchProgressBar key={event.batchId} event={event} />
              ))}
            </CardContent>
          </Card>
        )}

        {/* No active batches indicator */}
        {progressEvents.length === 0 && (
          <Card className="border-dashed">
            <CardContent className="py-6">
              <div className="flex items-center justify-center gap-3 text-muted-foreground">
                <Activity className="h-5 w-5" />
                <span className="text-sm">
                  No active batch processing. Progress bars will appear here
                  when batches are running.
                </span>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Batch Table */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Settlement Batches</CardTitle>
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-40">
                  <SelectValue placeholder="Filter" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  <SelectItem value="pending">Pending</SelectItem>
                  <SelectItem value="processing">Processing</SelectItem>
                  <SelectItem value="completed">Completed</SelectItem>
                  <SelectItem value="failed">Failed</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </CardHeader>
          <CardContent>
            {batchesQuery.isLoading ? (
              <p className="text-muted-foreground">Loading...</p>
            ) : batches.length === 0 ? (
              <p className="text-muted-foreground text-center py-8">
                No batches found
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-3 px-2">Batch Ref</th>
                      <th className="text-left py-3 px-2">Merchant</th>
                      <th className="text-left py-3 px-2">Amount</th>
                      <th className="text-left py-3 px-2">Status</th>
                      <th className="text-left py-3 px-2">Created</th>
                    </tr>
                  </thead>
                  <tbody>
                    {batches.map((b: any) => (
                      <tr key={b.id} className="border-b hover:bg-muted/50">
                        <td className="py-3 px-2 font-mono text-xs">
                          {b.ref ?? b.batchRef ?? `BATCH-${b.id}`}
                        </td>
                        <td className="py-3 px-2">
                          {b.merchantName ?? `Merchant-${b.merchantId}`}
                        </td>
                        <td className="py-3 px-2 font-mono">
                          ₦
                          {Number(
                            b.amount ?? b.totalAmount ?? 0
                          ).toLocaleString()}
                        </td>
                        <td className="py-3 px-2">
                          <Badge className={STATUS_COLORS[b.status] ?? ""}>
                            {b.status}
                          </Badge>
                        </td>
                        <td className="py-3 px-2 text-muted-foreground">
                          {b.createdAt
                            ? new Date(b.createdAt).toLocaleDateString()
                            : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
