// @ts-nocheck
import { useState } from "react";
import DashboardLayout from "@/components/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { trpc } from "@/lib/trpc";
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Brain,
  Zap,
  Clock,
  TrendingUp,
  Bell,
  Shield,
} from "lucide-react";

export default function AIMonitoringDashboard() {
  const [tab, setTab] = useState("overview");
  const dashboard = trpc.aiMonitoring.dashboard.useQuery(undefined, {
    refetchInterval: 5000,
  });
  const fraudFeed = trpc.aiMonitoring.liveFraudFeed.useQuery(
    { limit: 20, minRiskLevel: "medium" },
    { refetchInterval: 3000 }
  );
  const drift = trpc.aiMonitoring.driftAnalysis.useQuery(undefined, {
    refetchInterval: 30000,
  });
  const alerts = trpc.aiMonitoring.alerts.useQuery(
    { includeAcknowledged: false },
    { refetchInterval: 10000 }
  );
  const serviceHealth = trpc.aiMonitoring.serviceHealth.useQuery(undefined, {
    refetchInterval: 15000,
  });
  const throughput = trpc.aiMonitoring.throughputTimeSeries.useQuery(
    { intervalMinutes: 5, periods: 12 },
    { refetchInterval: 10000 }
  );
  const ackMut = trpc.aiMonitoring.acknowledgeAlert.useMutation({
    onSuccess: () => alerts.refetch(),
  });

  const stats = dashboard.data?.overview;

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Activity className="h-7 w-7 text-green-500" /> AI/ML Real-time
              Monitoring
            </h1>
            <p className="text-muted-foreground mt-1">
              Live model performance, fraud detection feed, and service health
            </p>
          </div>
          <div className="flex items-center gap-2">
            {alerts.data && alerts.data.total > 0 && (
              <Badge variant="destructive">
                <Bell className="h-3 w-3 mr-1" />
                {alerts.data.total} Active Alerts
              </Badge>
            )}
            <Badge variant="default">
              <Zap className="h-3 w-3 mr-1" />
              Live
            </Badge>
          </div>
        </div>

        {/* KPI Cards */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
            <Card>
              <CardContent className="pt-4 text-center">
                <p className="text-2xl font-bold">
                  {stats.totalInferences.toLocaleString()}
                </p>
                <p className="text-xs text-muted-foreground">
                  Total Inferences
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4 text-center">
                <p className="text-2xl font-bold text-green-500">
                  {stats.successRate}%
                </p>
                <p className="text-xs text-muted-foreground">Success Rate</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4 text-center">
                <p className="text-2xl font-bold">{stats.avgLatencyMs}ms</p>
                <p className="text-xs text-muted-foreground">Avg Latency</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4 text-center">
                <p className="text-2xl font-bold">{stats.p99LatencyMs}ms</p>
                <p className="text-xs text-muted-foreground">P99 Latency</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4 text-center">
                <p className="text-2xl font-bold">
                  {stats.throughputPerMin}/min
                </p>
                <p className="text-xs text-muted-foreground">Throughput</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4 text-center">
                <p className="text-2xl font-bold">{stats.activeModels}</p>
                <p className="text-xs text-muted-foreground">Active Models</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4 text-center">
                <p className="text-2xl font-bold text-red-500">
                  {stats.flaggedTransactions}
                </p>
                <p className="text-xs text-muted-foreground">Flagged</p>
              </CardContent>
            </Card>
          </div>
        )}

        <Tabs value={tab} onValueChange={setTab}>
          <TabsList>
            <TabsTrigger value="overview">Model Performance</TabsTrigger>
            <TabsTrigger value="fraud">Live Fraud Feed</TabsTrigger>
            <TabsTrigger value="drift">Drift Detection</TabsTrigger>
            <TabsTrigger value="services">Service Health</TabsTrigger>
            <TabsTrigger value="alerts">Alerts</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-4">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left">
                    <th className="p-2">Model</th>
                    <th className="p-2">Version</th>
                    <th className="p-2">Inferences</th>
                    <th className="p-2">Success</th>
                    <th className="p-2">Avg Latency</th>
                    <th className="p-2">P95</th>
                    <th className="p-2">P99</th>
                    <th className="p-2">Low</th>
                    <th className="p-2">Med</th>
                    <th className="p-2">High</th>
                    <th className="p-2">Critical</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.data?.modelMetrics.map(m => (
                    <tr key={m.modelName} className="border-b">
                      <td className="p-2 font-medium">{m.modelName}</td>
                      <td className="p-2">
                        <Badge variant="outline">{m.modelVersion}</Badge>
                      </td>
                      <td className="p-2">
                        {m.totalInferences.toLocaleString()}
                      </td>
                      <td className="p-2">
                        <span
                          className={
                            m.successRate > 99
                              ? "text-green-500"
                              : m.successRate > 95
                                ? "text-yellow-500"
                                : "text-red-500"
                          }
                        >
                          {m.successRate}%
                        </span>
                      </td>
                      <td className="p-2">{m.avgLatencyMs}ms</td>
                      <td className="p-2">{m.p95LatencyMs}ms</td>
                      <td className="p-2">{m.p99LatencyMs}ms</td>
                      <td className="p-2 text-green-500">
                        {m.riskDistribution.low}
                      </td>
                      <td className="p-2 text-yellow-500">
                        {m.riskDistribution.medium}
                      </td>
                      <td className="p-2 text-orange-500">
                        {m.riskDistribution.high}
                      </td>
                      <td className="p-2 text-red-500">
                        {m.riskDistribution.critical}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {throughput.data && (
              <Card>
                <CardHeader>
                  <CardTitle className="text-sm">
                    Throughput Timeline (5-min intervals)
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex items-end gap-1 h-32">
                    {throughput.data.series.map((s, i) => (
                      <div
                        key={i}
                        className="flex-1 flex flex-col items-center gap-1"
                      >
                        <div
                          className="w-full bg-primary/20 rounded-t relative"
                          style={{
                            height: `${Math.max(4, (s.inferences / Math.max(...throughput.data!.series.map(x => x.inferences || 1))) * 100)}%`,
                          }}
                        >
                          <div
                            className="absolute bottom-0 w-full bg-primary rounded-t"
                            style={{
                              height: `${Math.max(4, ((s.inferences - s.errorCount) / Math.max(...throughput.data!.series.map(x => x.inferences || 1))) * 100)}%`,
                            }}
                          />
                        </div>
                        <span className="text-[9px] text-muted-foreground">
                          {new Date(s.timestamp).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </TabsContent>

          <TabsContent value="fraud" className="space-y-4">
            <div className="flex items-center gap-2 mb-2">
              <Shield className="h-5 w-5 text-red-500" />
              <h3 className="font-semibold">Live Fraud Detection Feed</h3>
              <Badge variant="secondary">
                {fraudFeed.data?.highRiskCount ?? 0} high/critical
              </Badge>
            </div>
            <div className="space-y-2 max-h-[500px] overflow-y-auto">
              {fraudFeed.data?.events.map(e => (
                <Card
                  key={e.id}
                  className={
                    e.riskLevel === "critical"
                      ? "border-red-500/50"
                      : e.riskLevel === "high"
                        ? "border-orange-500/50"
                        : ""
                  }
                >
                  <CardContent className="pt-3 pb-3 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      {e.riskLevel === "critical" ? (
                        <AlertTriangle className="h-5 w-5 text-red-500" />
                      ) : e.riskLevel === "high" ? (
                        <AlertTriangle className="h-5 w-5 text-orange-500" />
                      ) : (
                        <Clock className="h-5 w-5 text-yellow-500" />
                      )}
                      <div>
                        <p className="text-sm font-medium">
                          {e.id} — {e.modelName}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Score: {(e.prediction * 100).toFixed(1)}% ·{" "}
                          {e.latencyMs}ms ·{" "}
                          {new Date(e.timestamp).toLocaleTimeString()}
                        </p>
                      </div>
                    </div>
                    <Badge
                      variant={
                        e.riskLevel === "critical"
                          ? "destructive"
                          : e.riskLevel === "high"
                            ? "secondary"
                            : "outline"
                      }
                    >
                      {e.riskLevel}
                    </Badge>
                  </CardContent>
                </Card>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="drift" className="space-y-4">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold flex items-center gap-2">
                <TrendingUp className="h-5 w-5" /> Feature Drift Analysis
              </h3>
              <Badge
                variant={
                  drift.data?.driftedCount === 0 ? "default" : "destructive"
                }
              >
                {drift.data?.driftedCount ?? 0} drifted features
              </Badge>
            </div>
            {drift.data && (
              <>
                <Card>
                  <CardContent className="pt-4">
                    <p className="text-sm font-medium">
                      Overall Drift Score:{" "}
                      <span
                        className={
                          drift.data.overallDriftScore > 0.1
                            ? "text-red-500"
                            : "text-green-500"
                        }
                      >
                        {drift.data.overallDriftScore}
                      </span>
                    </p>
                    <p className="text-sm text-muted-foreground mt-1">
                      {drift.data.recommendation}
                    </p>
                  </CardContent>
                </Card>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b text-left">
                        <th className="p-2">Feature</th>
                        <th className="p-2">Baseline Mean</th>
                        <th className="p-2">Current Mean</th>
                        <th className="p-2">PSI Score</th>
                        <th className="p-2">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {drift.data.features.map(f => (
                        <tr key={f.feature} className="border-b">
                          <td className="p-2 font-medium">{f.feature}</td>
                          <td className="p-2">{f.baselineMean}</td>
                          <td className="p-2">{f.currentMean}</td>
                          <td className="p-2">
                            <span
                              className={
                                f.psiScore > 0.1 ? "text-red-500 font-bold" : ""
                              }
                            >
                              {f.psiScore}
                            </span>
                          </td>
                          <td className="p-2">
                            {f.driftDetected ? (
                              <Badge variant="destructive">Drift</Badge>
                            ) : (
                              <Badge variant="default">Stable</Badge>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </TabsContent>

          <TabsContent value="services" className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {serviceHealth.data?.services.map(s => (
                <Card key={s.name}>
                  <CardContent className="pt-4 flex items-center justify-between">
                    <div>
                      <p className="font-medium">{s.name}</p>
                      <p className="text-xs text-muted-foreground">
                        v{s.version} · {s.latencyMs}ms · {s.uptime} uptime
                      </p>
                      {"note" in s && s.note && (
                        <p className="text-xs text-yellow-500 mt-1">
                          {s.note as string}
                        </p>
                      )}
                    </div>
                    <Badge
                      variant={
                        s.status === "healthy"
                          ? "default"
                          : s.status === "degraded"
                            ? "secondary"
                            : "destructive"
                      }
                    >
                      {s.status === "healthy" ? (
                        <CheckCircle className="h-3 w-3 mr-1" />
                      ) : (
                        <XCircle className="h-3 w-3 mr-1" />
                      )}
                      {s.status}
                    </Badge>
                  </CardContent>
                </Card>
              ))}
            </div>
          </TabsContent>

          <TabsContent value="alerts" className="space-y-4">
            {alerts.data?.alerts.map(a => (
              <Card
                key={a.id}
                className={
                  a.severity === "critical"
                    ? "border-red-500/50"
                    : a.severity === "warning"
                      ? "border-yellow-500/50"
                      : ""
                }
              >
                <CardContent className="pt-4 flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={
                          a.severity === "critical"
                            ? "destructive"
                            : a.severity === "warning"
                              ? "secondary"
                              : "outline"
                        }
                      >
                        {a.severity}
                      </Badge>
                      <p className="font-medium">{a.modelName}</p>
                    </div>
                    <p className="text-sm text-muted-foreground mt-1">
                      {a.message}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {a.metric}: {a.currentValue} (threshold: {a.threshold})
                    </p>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => ackMut.mutate({ alertId: a.id })}
                  >
                    Acknowledge
                  </Button>
                </CardContent>
              </Card>
            ))}
            {alerts.data?.total === 0 && (
              <p className="text-center text-muted-foreground py-8">
                No active alerts
              </p>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </DashboardLayout>
  );
}
