import DashboardLayout from "@/components/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useState } from "react";
import { toast } from "sonner";
import { trpc } from "@/lib/trpc";

function StatusBadge({ status }: { status: string }) {
  const variant =
    status === "healthy"
      ? "default"
      : status === "degraded"
        ? "secondary"
        : "destructive";
  return <Badge variant={variant}>{status}</Badge>;
}

export default function PlatformHealthDash() {
  const [tab, setTab] = useState("overview");

  // @ts-ignore Sprint 85: pre-existing type mismatch from router/page interface
  const { data: dashData, refetch: refetchDash } =
    trpc.platformHealth.dashboard.useQuery(undefined, { retry: 1 });

  // @ts-ignore Sprint 85: pre-existing type mismatch from router/page interface
  const { data: serviceData, refetch: refetchServices } =
    trpc.platformHealth.overview.useQuery(undefined, { retry: 1 });

  // @ts-ignore Sprint 85: pre-existing type mismatch from router/page interface
  const { data: queryData } = trpc.platformHealth.queryMetrics.useQuery(
    undefined,
    { retry: 1 }
  );

  // @ts-ignore Sprint 85: pre-existing type mismatch from router/page interface
  const { data: cacheData } = trpc.platformHealth.cacheMetrics.useQuery(
    undefined,
    { retry: 1 }
  );

  const handleRefresh = () => {
    refetchDash();
    refetchServices();
    toast.success("Health data refreshed");
  };

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Platform Health Dashboard</h1>
            <p className="text-muted-foreground">
              Real-time monitoring — cache, queries, services, orphan detection
            </p>
          </div>
          <div className="flex gap-2">
            {["overview", "services", "cache", "queries"].map(t => (
              <Button
                key={t}
                variant={tab === t ? "default" : "outline"}
                size="sm"
                onClick={() => setTab(t)}
              >
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </Button>
            ))}
            <Button size="sm" variant="outline" onClick={handleRefresh}>
              Refresh
            </Button>
          </div>
        </div>

        {tab === "overview" && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm text-muted-foreground">
                    Cache Hit Rate
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold text-green-500">
                    {dashData?.cache?.hitRate != null
                      ? `${(dashData.cache.hitRate * 100).toFixed(1)}%`
                      : "—"}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Redis{" "}
                    {dashData?.cache?.redisConnected
                      ? "connected"
                      : "disconnected"}
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm text-muted-foreground">
                    Total Queries
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {dashData?.queries?.total?.toLocaleString() ?? "0"}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Avg {dashData?.queries?.avgPerRequest ?? 0}/request
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm text-muted-foreground">
                    Slow Queries
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div
                    className={`text-2xl font-bold ${(dashData?.queries?.slowQueries ?? 0) > 0 ? "text-amber-500" : "text-green-500"}`}
                  >
                    {dashData?.queries?.slowQueries ?? 0}
                  </div>
                  <p className="text-xs text-muted-foreground">&gt;500ms</p>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm text-muted-foreground">
                    N+1 Detected
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div
                    className={`text-2xl font-bold ${(dashData?.queries?.nPlusOneDetected ?? 0) > 0 ? "text-red-500" : "text-green-500"}`}
                  >
                    {dashData?.queries?.nPlusOneDetected ?? 0}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    &gt;10 queries/request
                  </p>
                </CardContent>
              </Card>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card>
                <CardHeader>
                  <CardTitle>Database Stats</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span>Users</span>
                      <span className="font-mono">
                        {dashData?.database?.users?.toLocaleString() ?? "—"}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Transactions</span>
                      <span className="font-mono">
                        {dashData?.database?.transactions?.toLocaleString() ??
                          "—"}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Agents</span>
                      <span className="font-mono">
                        {dashData?.database?.agents?.toLocaleString() ?? "—"}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Audit Entries</span>
                      <span className="font-mono">
                        {dashData?.database?.auditEntries?.toLocaleString() ??
                          "—"}
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader>
                  <CardTitle>Platform Coverage</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span>tRPC Routers</span>
                      <span className="font-mono">
                        {dashData?.components?.routersRegistered ?? "—"}/
                        {dashData?.components?.totalRouterFiles ?? "—"}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>PWA Screens</span>
                      <span className="font-mono">
                        {dashData?.components?.pwaRoutes ?? "—"}/
                        {dashData?.components?.pwaScreens ?? "—"}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Flutter Screens</span>
                      <span className="font-mono">
                        {dashData?.components?.flutterRoutes ?? "—"}/
                        {dashData?.components?.flutterScreens ?? "—"}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>React Native Screens</span>
                      <span className="font-mono">
                        {dashData?.components?.rnRoutes ?? "—"}/
                        {dashData?.components?.rnScreens ?? "—"}
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </>
        )}

        {tab === "services" && (
          <Card>
            <CardHeader>
              <CardTitle>Service Health</CardTitle>
            </CardHeader>
            <CardContent>
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-3 px-2">Service</th>
                    <th className="text-left py-3 px-2">Status</th>
                    <th className="text-left py-3 px-2">Latency</th>
                    <th className="text-left py-3 px-2">Last Check</th>
                  </tr>
                </thead>
                <tbody>
                  {(serviceData?.services ?? []).map(
                    (svc: {
                      name: string;
                      status: string;
                      latency?: number;
                      lastChecked: string;
                    }) => (
                      <tr key={svc.name} className="border-b">
                        <td className="py-2 px-2 font-mono">{svc.name}</td>
                        <td className="py-2 px-2">
                          <StatusBadge status={svc.status} />
                        </td>
                        <td className="py-2 px-2">
                          {svc.latency != null ? `${svc.latency}ms` : "—"}
                        </td>
                        <td className="py-2 px-2 text-muted-foreground">
                          {svc.lastChecked
                            ? new Date(svc.lastChecked).toLocaleTimeString()
                            : "—"}
                        </td>
                      </tr>
                    )
                  )}
                  {(!serviceData?.services ||
                    serviceData.services.length === 0) && (
                    <tr>
                      <td
                        colSpan={4}
                        className="py-4 text-center text-muted-foreground"
                      >
                        No service data available
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </CardContent>
          </Card>
        )}

        {tab === "cache" && (
          <Card>
            <CardHeader>
              <CardTitle>Cache Metrics</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <div className="text-muted-foreground">Hits</div>
                  <div className="text-xl font-mono">
                    {cacheData?.hits?.toLocaleString() ?? "0"}
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground">Misses</div>
                  <div className="text-xl font-mono">
                    {cacheData?.misses?.toLocaleString() ?? "0"}
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground">Hit Rate</div>
                  <div className="text-xl font-mono text-green-500">
                    {cacheData?.hitRate != null
                      ? `${(cacheData.hitRate * 100).toFixed(1)}%`
                      : "—"}
                  </div>
                </div>
                <div>
                  <div className="text-muted-foreground">
                    Stampede Prevented
                  </div>
                  <div className="text-xl font-mono">
                    {cacheData?.stampedePrevented ?? "0"}
                  </div>
                </div>
              </div>
              <div className="mt-4 pt-4 border-t text-sm">
                <Badge
                  variant={
                    cacheData?.redisConnected ? "default" : "destructive"
                  }
                >
                  Redis{" "}
                  {cacheData?.redisConnected ? "Connected" : "Disconnected"}
                </Badge>
              </div>
            </CardContent>
          </Card>
        )}

        {tab === "queries" && (
          <div className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Query Performance</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div>
                    <div className="text-muted-foreground">Total Queries</div>
                    <div className="text-xl font-mono">
                      {queryData?.totalQueries?.toLocaleString() ?? "0"}
                    </div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">
                      Slow (&gt;500ms)
                    </div>
                    <div className="text-xl font-mono text-amber-500">
                      {queryData?.totalSlowQueries ?? 0}
                    </div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">N+1 Detected</div>
                    <div className="text-xl font-mono text-red-500">
                      {queryData?.totalNPlusOne ?? 0}
                    </div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Avg/Request</div>
                    <div className="text-xl font-mono">
                      {queryData?.avgQueriesPerRequest?.toFixed(1) ?? "0"}
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>

            {(queryData?.recentSlowQueries?.length ?? 0) > 0 && (
              <Card>
                <CardHeader>
                  <CardTitle>Recent Slow Queries</CardTitle>
                </CardHeader>
                <CardContent>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left py-2 px-2">Path</th>
                        <th className="text-left py-2 px-2">Duration</th>
                        <th className="text-left py-2 px-2">Query</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(
                        queryData?.recentSlowQueries as Array<{
                          path: string;
                          durationMs: number;
                          query: string;
                        }>
                      )?.map(
                        (
                          q: {
                            path: string;
                            durationMs: number;
                            query: string;
                          },
                          i: number
                        ) => (
                          <tr key={i} className="border-b">
                            <td className="py-2 px-2 font-mono">{q.path}</td>
                            <td className="py-2 px-2 text-amber-500">
                              {q.durationMs}ms
                            </td>
                            <td className="py-2 px-2 truncate max-w-xs">
                              {q.query}
                            </td>
                          </tr>
                        )
                      )}
                    </tbody>
                  </table>
                </CardContent>
              </Card>
            )}
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
