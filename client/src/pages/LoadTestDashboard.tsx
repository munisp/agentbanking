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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useState, useMemo } from "react";
import { toast } from "sonner";
import { trpc } from "@/lib/trpc";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Activity,
  Zap,
  Clock,
  AlertTriangle,
  BarChart3,
  TrendingUp,
  RefreshCw,
  Server,
  Gauge,
  Target,
  ArrowUpRight,
  ArrowDownRight,
  Play,
  Loader2,
  Settings,
  GitCompareArrows,
  Download,
  Save,
} from "lucide-react";
import { useLocation } from "wouter";

// ─── Inline Chart Components (no external deps) ─────────────────────────────

function BarChartInline({
  data,
  maxValue,
  color = "bg-blue-500",
  labelKey = "label",
  valueKey = "value",
}: {
  data: Array<Record<string, any>>;
  maxValue?: number;
  color?: string;
  labelKey?: string;
  valueKey?: string;
}) {
  const max =
    maxValue ?? Math.max(...data.map((d: any) => d[valueKey] ?? 0), 1);
  return (
    <div className="space-y-1.5">
      {data.map((item, i) => (
        <div key={i} className="flex items-center gap-2 text-xs">
          <span className="w-20 text-right text-muted-foreground truncate">
            {item[labelKey]}
          </span>
          <div className="flex-1 h-5 bg-muted/30 rounded overflow-hidden">
            <div
              className={`h-full ${color} rounded transition-all`}
              style={{ width: `${Math.max(1, (item[valueKey] / max) * 100)}%` }}
            />
          </div>
          <span className="w-16 text-right font-mono">
            {item[valueKey]?.toLocaleString()}
          </span>
        </div>
      ))}
    </div>
  );
}

function SparklineInline({
  data,
  height = 60,
  color = "#3b82f6",
}: {
  data: number[];
  height?: number;
  color?: string;
}) {
  if (data.length === 0) return null;
  const max = Math.max(...data, 1);
  const min = Math.min(...data, 0);
  const range = max - min || 1;
  const w = 100;
  const points = data
    .map((v, i) => {
      const x = (i / Math.max(data.length - 1, 1)) * w;
      const y = height - ((v - min) / range) * (height - 4) - 2;
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg viewBox={`0 0 ${w} ${height}`} className="w-full" style={{ height }}>
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

// ─── Helper Functions ────────────────────────────────────────────────────────

function formatMs(ms: number): string {
  if (ms < 1) return `${(ms * 1000).toFixed(0)}μs`;
  if (ms < 1000) return `${ms.toFixed(0)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

// ─── Main Page ───────────────────────────────────────────────────────────────

export default function LoadTestDashboard() {
  const [selectedRun, setSelectedRun] = useState<string | null>(null);
  const [showRunDialog, setShowRunDialog] = useState(false);
  const [testConfig, setTestConfig] = useState({
    targetRps: 500,
    duration: 60,
    concurrency: 50,
    zipfExponent: 1.07,
    merchantCount: 1000,
  });

  const [showThresholdDialog, setShowThresholdDialog] = useState(false);
  const [thresholdConfig, setThresholdConfig] = useState({
    p99ThresholdMs: 500,
    errorRateThreshold: 5.0,
  });
  const [, navigate] = useLocation();
  const [compareRunA, setCompareRunA] = useState<string | null>(null);

  // S61-1: Load current threshold config
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const p99ThresholdQuery = trpc.runtimeConfigAdmin.get.useQuery({
    key: "loadtest_p99_threshold_ms",
  });
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const errorThresholdQuery = trpc.runtimeConfigAdmin.get.useQuery({
    key: "loadtest_error_rate_threshold",
  });
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const updateConfigMutation = trpc.runtimeConfigAdmin.batchUpdate.useMutation({
    onSuccess: () => {
      toast.success("Threshold configuration saved");
      setShowThresholdDialog(false);
      p99ThresholdQuery.refetch();
      errorThresholdQuery.refetch();
    },
    onError: (err: any) => toast.error(`Failed to save: ${err.message}`),
  });

  // Sync threshold state from server
  const currentP99 = p99ThresholdQuery.data?.value
    ? parseFloat(p99ThresholdQuery.data.value)
    : 500;
  const currentErrorRate = errorThresholdQuery.data?.value
    ? parseFloat(errorThresholdQuery.data.value)
    : 5.0;

  // @ts-ignore Sprint 85
  const runsQuery = trpc.loadTestMetrics.listRuns.useQuery({ limit: 20 });
  // @ts-ignore Sprint 85
  const engineMetricsQuery = trpc.loadTestMetrics.getEngineMetrics.useQuery();
  // @ts-ignore Sprint 85
  const activeTestQuery = trpc.loadTestMetrics.getActiveTest.useQuery(
    undefined,
    {
      refetchInterval: 2000,
    }
  );

  // @ts-ignore Sprint 85
  const runLoadTestMutation = trpc.loadTestMetrics.runLoadTest.useMutation({
    onSuccess: (data: any) => {
      if (data.success) {
        toast.success(`Load test ${data.runId} started! Monitoring...`);
        setShowRunDialog(false);
        // Poll for completion
        const pollInterval = setInterval(() => {
          // @ts-ignore Sprint 85
          activeTestQuery.refetch().then(result => {
            if (!result.data) {
              clearInterval(pollInterval);
              runsQuery.refetch();
              toast.success("Load test completed! Results available.");
            }
          });
        }, 2000);
        // Safety timeout
        setTimeout(() => clearInterval(pollInterval), 600000);
      } else {
        toast.error(data.error ?? "Failed to start load test");
      }
    },
    onError: (err: any) => toast.error(`Error: ${err.message}`),
  });

  const runs = runsQuery.data ?? [];
  const activeRunId = selectedRun ?? runs[0]?.runId ?? null;
  // @ts-ignore Sprint 85
  const detailsQuery = trpc.loadTestMetrics.getRunDetails.useQuery(
    { runId: activeRunId! },
    { enabled: !!activeRunId }
  );

  const run = detailsQuery.data;
  const results = run?.results;
  const engines: any[] = (engineMetricsQuery.data as any)?.engines ?? [];

  // Prepare chart data
  const zipfData = useMemo(
    () =>
      (results?.zipfDistribution ?? []).slice(0, 15).map((d: any) => ({
        label: `#${d.merchantRank}`,
        value: d.requestCount,
        pct: d.percentage,
      })),
    [results]
  );

  const latencyData = useMemo(
    () =>
      (results?.latencyHistogram ?? []).map((d: any) => ({
        label: d.bucket,
        value: d.count,
      })),
    [results]
  );

  const timelineRps = useMemo(
    () => (results?.timeline ?? []).map((t: any) => t.rps),
    [results]
  );

  const timelineLatency = useMemo(
    () => (results?.timeline ?? []).map((t: any) => t.avgLatencyMs),
    [results]
  );

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <BarChart3 className="h-6 w-6" /> Load Test Performance
            </h1>
            <p className="text-muted-foreground">
              Pareto-aware load test results and real-time engine metrics
            </p>
          </div>
          <div className="flex gap-2">
            {/* S61-1: Threshold Settings Button */}
            <Dialog
              open={showThresholdDialog}
              onOpenChange={open => {
                if (open)
                  setThresholdConfig({
                    p99ThresholdMs: currentP99,
                    errorRateThreshold: currentErrorRate,
                  });
                setShowThresholdDialog(open);
              }}
            >
              <DialogTrigger asChild>
                <Button size="sm" variant="outline">
                  <Settings className="h-4 w-4 mr-1" /> Thresholds
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Alert Threshold Configuration</DialogTitle>
                  <DialogDescription>
                    Set thresholds for P99 latency and error rate. Owner
                    notifications will fire when load test results exceed these
                    values.
                  </DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-4">
                  <div>
                    <Label htmlFor="p99Threshold">
                      P99 Latency Threshold (ms)
                    </Label>
                    <Input
                      id="p99Threshold"
                      type="number"
                      min={10}
                      max={30000}
                      value={thresholdConfig.p99ThresholdMs}
                      onChange={(e: any) =>
                        setThresholdConfig(prev => ({
                          ...prev,
                          p99ThresholdMs: parseFloat(e.target.value) || 500,
                        }))
                      }
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      Current: {currentP99}ms. Notifications fire when P99
                      exceeds this value.
                    </p>
                  </div>
                  <div>
                    <Label htmlFor="errorRateThreshold">
                      Error Rate Threshold (%)
                    </Label>
                    <Input
                      id="errorRateThreshold"
                      type="number"
                      min={0.1}
                      max={100}
                      step={0.1}
                      value={thresholdConfig.errorRateThreshold}
                      onChange={(e: any) =>
                        setThresholdConfig(prev => ({
                          ...prev,
                          errorRateThreshold: parseFloat(e.target.value) || 5.0,
                        }))
                      }
                    />
                    <p className="text-xs text-muted-foreground mt-1">
                      Current: {currentErrorRate}%. Notifications fire when
                      error rate exceeds this value.
                    </p>
                  </div>
                  <div className="p-3 bg-muted/30 rounded-lg text-xs text-muted-foreground space-y-1">
                    <p>
                      <strong>P95 Warning:</strong> A warning is also sent when
                      P95 latency exceeds 80% of the P99 threshold (
                      {Math.round(thresholdConfig.p99ThresholdMs * 0.8)}ms).
                    </p>
                    <p>
                      <strong>Severity:</strong> CRITICAL when 2+ thresholds
                      breached, WARNING for single breach.
                    </p>
                  </div>
                </div>
                <DialogFooter>
                  <Button
                    variant="outline"
                    onClick={() => setShowThresholdDialog(false)}
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={() =>
                      updateConfigMutation.mutate({
                        // @ts-ignore Sprint 85
                        updates: [
                          {
                            key: "loadtest_p99_threshold_ms",
                            value: String(thresholdConfig.p99ThresholdMs),
                          },
                          {
                            key: "loadtest_error_rate_threshold",
                            value: String(thresholdConfig.errorRateThreshold),
                          },
                        ],
                      })
                    }
                    disabled={updateConfigMutation.isPending}
                  >
                    {updateConfigMutation.isPending ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-1 animate-spin" />{" "}
                        Saving...
                      </>
                    ) : (
                      <>
                        <Save className="h-4 w-4 mr-1" /> Save Thresholds
                      </>
                    )}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>

            {/* S59-3: Run Load Test Button */}
            <Dialog open={showRunDialog} onOpenChange={setShowRunDialog}>
              <DialogTrigger asChild>
                <Button
                  size="sm"
                  disabled={
                    !!activeTestQuery.data || runLoadTestMutation.isPending
                  }
                >
                  {activeTestQuery.data ? (
                    <>
                      <Loader2 className="h-4 w-4 mr-1 animate-spin" /> Running
                      ({activeTestQuery.data.elapsedSeconds}s)
                    </>
                  ) : (
                    <>
                      <Play className="h-4 w-4 mr-1" /> Run Load Test
                    </>
                  )}
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader>
                  <DialogTitle>Run Pareto Load Test</DialogTitle>
                  <DialogDescription>
                    Configure and execute a Zipf-distributed load test against
                    the settlement engine.
                  </DialogDescription>
                </DialogHeader>
                <div className="grid grid-cols-2 gap-4 py-4">
                  <div>
                    <Label htmlFor="targetRps">Target RPS</Label>
                    <Input
                      id="targetRps"
                      type="number"
                      min={10}
                      max={10000}
                      value={testConfig.targetRps}
                      onChange={(e: any) =>
                        setTestConfig(prev => ({
                          ...prev,
                          targetRps: parseInt(e.target.value) || 500,
                        }))
                      }
                    />
                  </div>
                  <div>
                    <Label htmlFor="duration">Duration (seconds)</Label>
                    <Input
                      id="duration"
                      type="number"
                      min={5}
                      max={300}
                      value={testConfig.duration}
                      onChange={(e: any) =>
                        setTestConfig(prev => ({
                          ...prev,
                          duration: parseInt(e.target.value) || 60,
                        }))
                      }
                    />
                  </div>
                  <div>
                    <Label htmlFor="concurrency">Concurrency</Label>
                    <Input
                      id="concurrency"
                      type="number"
                      min={1}
                      max={200}
                      value={testConfig.concurrency}
                      onChange={(e: any) =>
                        setTestConfig(prev => ({
                          ...prev,
                          concurrency: parseInt(e.target.value) || 50,
                        }))
                      }
                    />
                  </div>
                  <div>
                    <Label htmlFor="zipfExponent">Zipf Exponent (s)</Label>
                    <Input
                      id="zipfExponent"
                      type="number"
                      min={0.5}
                      max={3.0}
                      step={0.01}
                      value={testConfig.zipfExponent}
                      onChange={(e: any) =>
                        setTestConfig(prev => ({
                          ...prev,
                          zipfExponent: parseFloat(e.target.value) || 1.07,
                        }))
                      }
                    />
                  </div>
                  <div>
                    <Label htmlFor="merchantCount">Merchant Count</Label>
                    <Input
                      id="merchantCount"
                      type="number"
                      min={10}
                      max={100000}
                      value={testConfig.merchantCount}
                      onChange={(e: any) =>
                        setTestConfig(prev => ({
                          ...prev,
                          merchantCount: parseInt(e.target.value) || 1000,
                        }))
                      }
                    />
                  </div>
                </div>
                <DialogFooter>
                  <Button
                    variant="outline"
                    onClick={() => setShowRunDialog(false)}
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={() => runLoadTestMutation.mutate(testConfig)}
                    disabled={runLoadTestMutation.isPending}
                  >
                    {runLoadTestMutation.isPending ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-1 animate-spin" />{" "}
                        Starting...
                      </>
                    ) : (
                      <>
                        <Play className="h-4 w-4 mr-1" /> Start Test
                      </>
                    )}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>

            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                runsQuery.refetch();
                engineMetricsQuery.refetch();
                toast.success("Refreshed");
              }}
            >
              <RefreshCw className="h-4 w-4 mr-1" /> Refresh
            </Button>
            {runs.length > 1 && (
              <div className="flex items-center gap-2">
                <Select
                  value={activeRunId ?? ""}
                  onValueChange={setSelectedRun}
                >
                  <SelectTrigger className="w-64">
                    <SelectValue placeholder="Select run" />
                  </SelectTrigger>
                  <SelectContent>
                    {runs.map((r: any) => (
                      <SelectItem key={r.runId} value={r.runId}>
                        {r.runId?.slice(0, 40) ?? r.id}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {/* S61-3: Compare button */}
                {!compareRunA ? (
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setCompareRunA(activeRunId);
                      toast.info(
                        "Run A selected. Now select Run B and click Compare again."
                      );
                    }}
                    disabled={!activeRunId}
                  >
                    <GitCompareArrows className="h-4 w-4 mr-1" /> Compare
                  </Button>
                ) : (
                  <div className="flex items-center gap-1">
                    <Button
                      size="sm"
                      variant="default"
                      onClick={() => {
                        if (compareRunA === activeRunId) {
                          toast.error("Select a different run for comparison");
                          return;
                        }
                        navigate(
                          `/load-test-comparison?a=${compareRunA}&b=${activeRunId}`
                        );
                        setCompareRunA(null);
                      }}
                      disabled={!activeRunId || compareRunA === activeRunId}
                    >
                      <GitCompareArrows className="h-4 w-4 mr-1" /> Compare vs A
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => {
                        setCompareRunA(null);
                        toast.info("Comparison cancelled");
                      }}
                    >
                      Cancel
                    </Button>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Run Summary KPI Cards */}
        {results && (
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
            <Card>
              <CardContent className="pt-4 pb-3">
                <div className="flex items-center gap-1 text-xs text-muted-foreground mb-1">
                  <Target className="h-3 w-3" /> Actual RPS
                </div>
                <div className="text-xl font-bold">
                  {results.actualRps.toLocaleString()}
                </div>
                <p className="text-xs text-muted-foreground">
                  Target: {run?.config.targetRps}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4 pb-3">
                <div className="flex items-center gap-1 text-xs text-muted-foreground mb-1">
                  <Zap className="h-3 w-3" /> Total Requests
                </div>
                <div className="text-xl font-bold">
                  {results.totalRequests.toLocaleString()}
                </div>
                <p className="text-xs text-emerald-400">
                  {results.successfulRequests.toLocaleString()} success
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4 pb-3">
                <div className="flex items-center gap-1 text-xs text-muted-foreground mb-1">
                  <Clock className="h-3 w-3" /> Avg Latency
                </div>
                <div className="text-xl font-bold">
                  {formatMs(results.avgLatencyMs)}
                </div>
                <p className="text-xs text-muted-foreground">
                  P50: {formatMs(results.p50LatencyMs)}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4 pb-3">
                <div className="flex items-center gap-1 text-xs text-muted-foreground mb-1">
                  <Gauge className="h-3 w-3" /> P95 / P99
                </div>
                <div className="text-xl font-bold">
                  {formatMs(results.p95LatencyMs)}
                </div>
                <p className="text-xs text-yellow-400">
                  P99: {formatMs(results.p99LatencyMs)}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4 pb-3">
                <div className="flex items-center gap-1 text-xs text-muted-foreground mb-1">
                  <AlertTriangle className="h-3 w-3" /> Error Rate
                </div>
                <div
                  className={`text-xl font-bold ${results.errorRate > 5 ? "text-red-400" : results.errorRate > 1 ? "text-yellow-400" : "text-emerald-400"}`}
                >
                  {results.errorRate.toFixed(2)}%
                </div>
                <p className="text-xs text-muted-foreground">
                  {results.failedRequests} failed
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4 pb-3">
                <div className="flex items-center gap-1 text-xs text-muted-foreground mb-1">
                  <TrendingUp className="h-3 w-3" /> Throughput
                </div>
                <div className="text-xl font-bold">
                  {results.throughputMbps.toFixed(1)} MB/s
                </div>
                <p className="text-xs text-muted-foreground">
                  {run?.config.concurrency} concurrent
                </p>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Charts Row */}
        {results && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Zipf Distribution */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <BarChart3 className="h-4 w-4" /> Zipf Distribution (Top 15
                  Merchants)
                </CardTitle>
                <CardDescription className="text-xs">
                  Pareto-skewed traffic: top merchants receive disproportionate
                  load (s={run?.config.zipfExponent})
                </CardDescription>
              </CardHeader>
              <CardContent>
                <BarChartInline
                  data={zipfData}
                  labelKey="label"
                  valueKey="value"
                  color="bg-blue-500"
                />
                <p className="text-xs text-muted-foreground mt-2">
                  Top merchant received {zipfData[0]?.pct ?? 0}% of all requests
                </p>
              </CardContent>
            </Card>

            {/* Latency Histogram */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Clock className="h-4 w-4" /> Latency Distribution
                </CardTitle>
                <CardDescription className="text-xs">
                  Request latency histogram across all endpoints
                </CardDescription>
              </CardHeader>
              <CardContent>
                <BarChartInline
                  data={latencyData}
                  labelKey="label"
                  valueKey="value"
                  color="bg-emerald-500"
                />
              </CardContent>
            </Card>
          </div>
        )}

        {/* Timeline Sparklines */}
        {results && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Activity className="h-4 w-4" /> RPS Timeline
                </CardTitle>
                <CardDescription className="text-xs">
                  Requests per second over {run?.config.duration}s test duration
                </CardDescription>
              </CardHeader>
              <CardContent>
                <SparklineInline
                  data={timelineRps}
                  height={80}
                  color="#3b82f6"
                />
                <div className="flex justify-between text-xs text-muted-foreground mt-1">
                  <span>0s</span>
                  <span>Peak: {Math.max(...timelineRps, 0)} RPS</span>
                  <span>{run?.config.duration}s</span>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Gauge className="h-4 w-4" /> Latency Timeline
                </CardTitle>
                <CardDescription className="text-xs">
                  Average latency per second during the test
                </CardDescription>
              </CardHeader>
              <CardContent>
                <SparklineInline
                  data={timelineLatency}
                  height={80}
                  color="#10b981"
                />
                <div className="flex justify-between text-xs text-muted-foreground mt-1">
                  <span>0s</span>
                  <span>Avg: {formatMs(results.avgLatencyMs)}</span>
                  <span>{run?.config.duration}s</span>
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Test Configuration */}
        {run && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Test Configuration</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
                <div>
                  <p className="text-muted-foreground text-xs">Target RPS</p>
                  <p className="font-mono font-medium">
                    {run.config.targetRps}
                  </p>
                </div>
                <div>
                  <p className="text-muted-foreground text-xs">Duration</p>
                  <p className="font-mono font-medium">
                    {run.config.duration}s
                  </p>
                </div>
                <div>
                  <p className="text-muted-foreground text-xs">Concurrency</p>
                  <p className="font-mono font-medium">
                    {run.config.concurrency}
                  </p>
                </div>
                <div>
                  <p className="text-muted-foreground text-xs">Zipf Exponent</p>
                  <p className="font-mono font-medium">
                    {run.config.zipfExponent}
                  </p>
                </div>
                <div>
                  <p className="text-muted-foreground text-xs">Merchants</p>
                  <p className="font-mono font-medium">
                    {run.config.merchantCount.toLocaleString()}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Real-Time Engine Metrics */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Server className="h-5 w-5" /> Real-Time Engine Metrics
            </CardTitle>
            <CardDescription>
              Live OpenTelemetry metrics from settlement, dispute, and
              commission engines
            </CardDescription>
          </CardHeader>
          <CardContent>
            {engines.length === 0 ? (
              <p className="text-muted-foreground text-center py-6">
                No engine metrics recorded yet. Metrics will appear after
                processing operations.
              </p>
            ) : (
              <div className="space-y-4">
                {engines.map((engine: any) => (
                  <div
                    key={engine.name}
                    className="p-4 border border-border/50 rounded-lg space-y-3"
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Badge className="bg-blue-500/20 text-blue-400 font-mono">
                          {engine.name}
                        </Badge>
                        <span className="text-sm text-muted-foreground">
                          {engine.totalOperations.toLocaleString()} operations
                        </span>
                      </div>
                      <div className="flex items-center gap-3 text-xs">
                        <span className="flex items-center gap-1 text-emerald-400">
                          <ArrowUpRight className="h-3 w-3" />
                          {engine.successCount.toLocaleString()} ok
                        </span>
                        {engine.errorCount > 0 && (
                          <span className="flex items-center gap-1 text-red-400">
                            <ArrowDownRight className="h-3 w-3" />
                            {engine.errorCount} errors ({engine.errorRate}%)
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="grid grid-cols-4 gap-4 text-xs">
                      <div>
                        <span className="text-muted-foreground">Avg</span>
                        <p className="font-mono font-medium">
                          {formatMs(engine.avgLatencyMs)}
                        </p>
                      </div>
                      <div>
                        <span className="text-muted-foreground">P50</span>
                        <p className="font-mono font-medium">
                          {formatMs(engine.p50LatencyMs)}
                        </p>
                      </div>
                      <div>
                        <span className="text-muted-foreground">P95</span>
                        <p className="font-mono font-medium text-yellow-400">
                          {formatMs(engine.p95LatencyMs)}
                        </p>
                      </div>
                      <div>
                        <span className="text-muted-foreground">P99</span>
                        <p className="font-mono font-medium text-red-400">
                          {formatMs(engine.p99LatencyMs)}
                        </p>
                      </div>
                    </div>
                    {engine.topOperations?.length > 0 && (
                      <div className="text-xs">
                        <span className="text-muted-foreground">
                          Top operations:{" "}
                        </span>
                        {engine.topOperations
                          .slice(0, 5)
                          .map((op: any, i: number) => (
                            <span key={op.operation}>
                              {i > 0 && " · "}
                              <span className="font-mono">{op.operation}</span>
                              <span className="text-muted-foreground">
                                {" "}
                                ({op.count})
                              </span>
                            </span>
                          ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* No data state */}
        {!results && runs.length === 0 && (
          <Card className="border-dashed">
            <CardContent className="py-12">
              <div className="text-center space-y-3">
                <BarChart3 className="h-12 w-12 text-muted-foreground mx-auto" />
                <h3 className="text-lg font-medium">No Load Test Results</h3>
                <p className="text-sm text-muted-foreground max-w-md mx-auto">
                  Run the Pareto load test script to generate performance data:
                  <code className="block mt-2 p-2 bg-muted rounded text-xs font-mono">
                    node scripts/load-test-pareto.mjs --target-rps 500
                    --duration 60
                  </code>
                </p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardLayout>
  );
}
