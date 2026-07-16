import { trpc } from "@/lib/trpc";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Activity, AlertTriangle, CheckCircle, XCircle } from "lucide-react";

export default function PipelineMonitoringPage() {
  // @ts-ignore Sprint 85
  const { data } = trpc.pipelineMonitoring.dashboard.useQuery();
  // @ts-ignore Sprint 85
  const { data: alerts } = trpc.pipelineMonitoring.activeAlerts.useQuery({
    limit: 20,
  });

  const statusIcon = (s: string) =>
    s === "healthy" ? (
      <CheckCircle className="w-4 h-4 text-green-500" />
    ) : s === "degraded" ? (
      <AlertTriangle className="w-4 h-4 text-yellow-500" />
    ) : (
      <XCircle className="w-4 h-4 text-red-500" />
    );

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Pipeline Monitoring & Alerting</h1>
        <p className="text-muted-foreground">
          NiFi, dbt, and Airflow health tracking
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[
          { label: "Health Score", value: `${data?.healthScore ?? 0}%` },
          { label: "Active Alerts", value: data?.activeAlerts ?? 0 },
          { label: "Resolved Today", value: data?.resolvedToday ?? 0 },
          { label: "SLA Breaches", value: data?.slaBreaches ?? 0 },
        ].map((s, i) => (
          <Card key={i}>
            <CardContent className="pt-4">
              <p className="text-2xl font-bold">{s.value}</p>
              <p className="text-xs text-muted-foreground">{s.label}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Services</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {(data?.services ?? []).map((p: any, i: number) => (
              <div key={i} className="p-4 rounded bg-muted/50">
                <div className="flex items-center gap-2 mb-2">
                  {statusIcon(p.status)}
                  <span className="font-medium">{p.name}</span>
                </div>
                <div className="space-y-1 text-sm">
                  <div className="flex justify-between">
                    <span>Status</span>
                    <Badge
                      variant={
                        p.status === "healthy" ? "default" : "destructive"
                      }
                    >
                      {p.status}
                    </Badge>
                  </div>
                  <div className="flex justify-between">
                    <span>Uptime</span>
                    <span>{p.uptime}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Latency</span>
                    <span>{p.latencyMs}ms</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Version</span>
                    <span>{p.version}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5" /> Active Alerts (
            {alerts?.alerts?.length ?? 0})
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {(alerts?.alerts ?? []).map((a: any, i: number) => (
              <div
                key={i}
                className="flex items-center justify-between p-3 rounded bg-muted/50"
              >
                <div className="flex items-center gap-3">
                  {a.severity === "critical" ? (
                    <XCircle className="w-5 h-5 text-red-500" />
                  ) : (
                    <AlertTriangle className="w-5 h-5 text-yellow-500" />
                  )}
                  <div>
                    <p className="font-medium">{a.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {a.pipeline} — {a.message}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <Badge
                    variant={
                      a.severity === "critical" ? "destructive" : "secondary"
                    }
                  >
                    {a.severity}
                  </Badge>
                  <p className="text-xs text-muted-foreground mt-1">
                    {new Date(a.timestamp).toLocaleString()}
                  </p>
                </div>
              </div>
            ))}
            {(alerts?.alerts?.length ?? 0) === 0 && (
              <p className="text-center text-muted-foreground py-4">
                No active alerts
              </p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
