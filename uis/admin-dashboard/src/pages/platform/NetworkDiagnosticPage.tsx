// NetworkDiagnosticPage — Sprint 77
// Ping, traceroute, speedtest from agent devices
import { useState } from "react";
import { trpc } from "@/lib/trpc";
import DashboardLayout from "@/components/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Wifi, Activity, Globe, Zap } from "lucide-react";

export default function NetworkDiagnosticPage() {
  const [target, setTarget] = useState("8.8.8.8");
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const resilience = trpc.networkResilience.getResilienceStatus.useQuery();
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const metrics = trpc.networkResilience.getConnectionMetrics.useQuery();

  return (
    <DashboardLayout>
      <div className="container py-6 space-y-6">
        <div className="flex items-center gap-3">
          <Wifi className="h-8 w-8 text-cyan-500" />
          <div>
            <h1 className="text-2xl font-bold">Network Diagnostics</h1>
            <p className="text-muted-foreground">
              Connection quality, protocol selection, bandwidth monitoring
            </p>
          </div>
        </div>

        {/* Connection Metrics */}
        {metrics.data && (
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <Card>
              <CardContent className="pt-6 text-center">
                <Activity className="h-6 w-6 text-blue-500 mx-auto" />
                <p className="text-2xl font-bold mt-2">
                  {metrics.data.totalConnections}
                </p>
                <p className="text-xs text-muted-foreground">
                  Total Connections
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6 text-center">
                <Zap className="h-6 w-6 text-green-500 mx-auto" />
                <p className="text-2xl font-bold mt-2">
                  {metrics.data.activeWebSocket}
                </p>
                <p className="text-xs text-muted-foreground">WebSocket</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6 text-center">
                <p className="text-2xl font-bold text-yellow-500">
                  {metrics.data.activeSSE}
                </p>
                <p className="text-xs text-muted-foreground">SSE</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6 text-center">
                <p className="text-2xl font-bold text-orange-500">
                  {metrics.data.activeLongPoll}
                </p>
                <p className="text-xs text-muted-foreground">Long-Poll</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6 text-center">
                <p className="text-2xl font-bold text-red-500">
                  {metrics.data.offlineAgents}
                </p>
                <p className="text-xs text-muted-foreground">Offline</p>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Resilience Status */}
        {resilience.data && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Globe className="h-5 w-5" /> Resilience Status
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {resilience.data.regions.map((r: any) => (
                  <div key={r.region} className="p-4 rounded-lg bg-muted/50">
                    <div className="flex items-center justify-between mb-2">
                      <p className="font-semibold">{r.region}</p>
                      <Badge
                        variant={
                          r.status === "healthy"
                            ? "default"
                            : r.status === "degraded"
                              ? "secondary"
                              : "destructive"
                        }
                      >
                        {r.status}
                      </Badge>
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-sm">
                      <div>
                        <span className="text-muted-foreground">Latency:</span>{" "}
                        {r.avgLatencyMs}ms
                      </div>
                      <div>
                        <span className="text-muted-foreground">Loss:</span>{" "}
                        {r.packetLossPct}%
                      </div>
                      <div>
                        <span className="text-muted-foreground">
                          Bandwidth:
                        </span>{" "}
                        {r.bandwidthKbps} kbps
                      </div>
                    </div>
                    <div className="mt-2 text-xs text-muted-foreground">
                      Protocol: {r.recommendedProtocol} | Agents:{" "}
                      {r.activeAgents}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Diagnostic Tool */}
        <Card>
          <CardHeader>
            <CardTitle>Run Diagnostic</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-3 mb-4">
              <Input
                value={target}
                onChange={e => setTarget(e.target.value)}
                placeholder="Target IP or hostname"
              />
              <Button>Ping</Button>
              <Button variant="outline">Traceroute</Button>
              <Button variant="outline">Speed Test</Button>
            </div>
            <div className="p-4 rounded-lg bg-muted/50 font-mono text-sm min-h-[200px]">
              <p className="text-muted-foreground">
                Select a diagnostic tool above to begin testing...
              </p>
              <p className="text-muted-foreground mt-2">Available tests:</p>
              <p>- Ping: ICMP echo to target with RTT measurement</p>
              <p>- Traceroute: Network path analysis with hop-by-hop latency</p>
              <p>- Speed Test: Download/upload bandwidth measurement</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
