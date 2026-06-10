// ConnectionQualityPage — Sprint 77
// Real-time connection quality monitoring per agent/region
import { trpc } from "@/lib/trpc";
import DashboardLayout from "@/components/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Signal, Gauge, Waves } from "lucide-react";

export default function ConnectionQualityPage() {
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const metrics = trpc.networkResilience.getConnectionMetrics.useQuery();
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const config = trpc.networkResilience.getBandwidthConfig.useQuery();

  return (
    <DashboardLayout>
      <div className="container py-6 space-y-6">
        <div className="flex items-center gap-3">
          <Signal className="h-8 w-8 text-teal-500" />
          <div>
            <h1 className="text-2xl font-bold">Connection Quality Monitor</h1>
            <p className="text-muted-foreground">
              Real-time RTT, jitter, and packet loss tracking
            </p>
          </div>
        </div>

        {metrics.data && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <Card>
                <CardContent className="pt-6 text-center">
                  <Gauge className="h-6 w-6 text-blue-500 mx-auto" />
                  <p className="text-2xl font-bold mt-2">
                    {metrics.data.avgLatencyMs}ms
                  </p>
                  <p className="text-xs text-muted-foreground">Avg Latency</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6 text-center">
                  <Waves className="h-6 w-6 text-purple-500 mx-auto" />
                  <p className="text-2xl font-bold mt-2">
                    {metrics.data.jitterMs}ms
                  </p>
                  <p className="text-xs text-muted-foreground">Jitter</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6 text-center">
                  <p className="text-2xl font-bold text-red-500">
                    {metrics.data.packetLossPct}%
                  </p>
                  <p className="text-xs text-muted-foreground">Packet Loss</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6 text-center">
                  <p className="text-2xl font-bold text-green-500">
                    {metrics.data.bandwidthKbps} kbps
                  </p>
                  <p className="text-xs text-muted-foreground">Bandwidth</p>
                </CardContent>
              </Card>
            </div>

            {/* Per-Agent Connection Quality */}
            <Card>
              <CardHeader>
                <CardTitle>Agent Connections</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {(metrics.data.agents || []).map((a: any, i: number) => (
                    <div
                      key={i}
                      className="flex items-center justify-between p-3 rounded-lg bg-muted/50"
                    >
                      <div>
                        <p className="font-medium">{a.agentId}</p>
                        <p className="text-xs text-muted-foreground">
                          {a.region} — {a.carrier}
                        </p>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-sm">{a.latencyMs}ms</span>
                        <span className="text-sm">{a.bandwidthKbps} kbps</span>
                        <Badge
                          variant={
                            a.protocol === "websocket"
                              ? "default"
                              : a.protocol === "sse"
                                ? "secondary"
                                : "destructive"
                          }
                        >
                          {a.protocol}
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </>
        )}

        {/* Bandwidth Config */}
        {config.data && (
          <Card>
            <CardHeader>
              <CardTitle>Adaptive Bandwidth Configuration</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-3 rounded bg-muted/50">
                  <p className="text-xs text-muted-foreground">
                    Adaptive Bandwidth
                  </p>
                  <Badge
                    variant={
                      config.data.adaptiveBandwidth ? "default" : "outline"
                    }
                  >
                    {config.data.adaptiveBandwidth ? "Enabled" : "Disabled"}
                  </Badge>
                </div>
                <div className="p-3 rounded bg-muted/50">
                  <p className="text-xs text-muted-foreground">Compression</p>
                  <Badge
                    variant={
                      config.data.compressionEnabled ? "default" : "outline"
                    }
                  >
                    {config.data.compressionEnabled ? "Enabled" : "Disabled"}
                  </Badge>
                </div>
                <div className="p-3 rounded bg-muted/50">
                  <p className="text-xs text-muted-foreground">
                    Low BW Threshold
                  </p>
                  <p className="font-bold">
                    {config.data.lowBandwidthThresholdKbps} kbps
                  </p>
                </div>
                <div className="p-3 rounded bg-muted/50">
                  <p className="text-xs text-muted-foreground">Max Payload</p>
                  <p className="font-bold">
                    {(config.data.maxPayloadBytes / 1024).toFixed(0)} KB
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardLayout>
  );
}
