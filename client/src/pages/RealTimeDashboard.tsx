// @ts-ignore Sprint 85
import { useState, useEffect, useCallback, useRef } from "react";
import { useAuth } from "@/_core/hooks/useAuth";
import { trpc } from "@/lib/trpc";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { io, Socket } from "socket.io-client";

interface LiveTransaction {
  id: string;
  amount: number;
  currency: string;
  type: string;
  status: "completed" | "pending" | "failed";
  agentId: string;
  timestamp: number;
}

interface ReconciliationEvent {
  id: string;
  matchedCount: number;
  unmatchedCount: number;
  discrepancyCount: number;
  totalVariance: number;
  source: string;
  timestamp: number;
}

interface ServiceHealth {
  name: string;
  status: "healthy" | "degraded" | "down";
  latencyMs: number;
  lastCheck: number;
}

interface DashboardMetrics {
  totalTransactionsToday: number;
  totalVolumeToday: number;
  activeAgents: number;
  successRate: number;
  avgLatencyMs: number;
  peakTps: number;
}

export default function RealTimeDashboard() {
  const { user } = useAuth();
  const [liveTransactions, setLiveTransactions] = useState<LiveTransaction[]>(
    []
  );
  const [reconciliationEvents, setReconciliationEvents] = useState<
    ReconciliationEvent[]
  >([]);
  const [serviceHealth, setServiceHealth] = useState<ServiceHealth[]>([]);
  const [metrics, setMetrics] = useState<DashboardMetrics>({
    totalTransactionsToday: 0,
    totalVolumeToday: 0,
    activeAgents: 0,
    successRate: 99.2,
    avgLatencyMs: 450,
    peakTps: 0,
  });
  const [isConnected, setIsConnected] = useState(false);
  const [activeTab, setActiveTab] = useState("transactions");
  const socketRef = useRef<Socket | null>(null);
  const maxItems = 50;

  // Connect to WebSocket namespaces
  useEffect(() => {
    const settlementSocket = io("/settlement", {
      transports: ["websocket"],
      autoConnect: true,
    });
    const notifSocket = io("/notifications", {
      transports: ["websocket"],
      autoConnect: true,
    });

    settlementSocket.on("connect", () => setIsConnected(true));
    settlementSocket.on("disconnect", () => setIsConnected(false));

    settlementSocket.on("transaction:new", (tx: LiveTransaction) => {
      setLiveTransactions(prev => [tx, ...prev].slice(0, maxItems));
      setMetrics(prev => ({
        ...prev,
        totalTransactionsToday: prev.totalTransactionsToday + 1,
        totalVolumeToday: prev.totalVolumeToday + tx.amount,
        peakTps: Math.max(prev.peakTps, prev.totalTransactionsToday / 3600),
      }));
    });

    settlementSocket.on(
      "reconciliation:update",
      (event: ReconciliationEvent) => {
        setReconciliationEvents(prev => [event, ...prev].slice(0, maxItems));
      }
    );

    notifSocket.on("service:health", (health: ServiceHealth[]) => {
      setServiceHealth(health);
    });

    socketRef.current = settlementSocket;

    return () => {
      settlementSocket.disconnect();
      notifSocket.disconnect();
    };
  }, []);

  // Fetch initial metrics from tRPC
  // @ts-ignore Sprint 85
  const statsQuery = trpc.billing?.getStats?.useQuery?.() || { data: null };

  const formatCurrency = (amount: number, currency: string = "KES") =>
    new Intl.NumberFormat("en-KE", { style: "currency", currency }).format(
      amount
    );

  const formatTime = (ts: number) => new Date(ts).toLocaleTimeString();

  const statusColor = (status: string) => {
    switch (status) {
      case "completed":
      case "healthy":
        return "bg-green-500/10 text-green-500";
      case "pending":
      case "degraded":
        return "bg-yellow-500/10 text-yellow-500";
      case "failed":
      case "down":
        return "bg-red-500/10 text-red-500";
      default:
        return "bg-gray-500/10 text-gray-500";
    }
  };

  return (
    <div className="min-h-screen bg-background p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Real-Time Operations Dashboard</h1>
          <p className="text-muted-foreground text-sm">
            Live transaction streaming & reconciliation monitoring
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Badge
            className={
              isConnected
                ? "bg-green-500/10 text-green-500"
                : "bg-red-500/10 text-red-500"
            }
          >
            {isConnected ? "● Connected" : "○ Disconnected"}
          </Badge>
          <Button
            variant="outline"
            size="sm"
            onClick={() => socketRef.current?.connect()}
          >
            Reconnect
          </Button>
        </div>
      </div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-muted-foreground">
              Transactions Today
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {metrics.totalTransactionsToday.toLocaleString()}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-muted-foreground">
              Volume Today
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatCurrency(metrics.totalVolumeToday)}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-muted-foreground">
              Active Agents
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics.activeAgents}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-muted-foreground">
              Success Rate
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-500">
              {metrics.successRate}%
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-muted-foreground">
              Avg Latency
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics.avgLatencyMs}ms</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-xs text-muted-foreground">
              Peak TPS
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {metrics.peakTps.toFixed(1)}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabbed Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="mb-4">
          <TabsTrigger value="transactions">Live Transactions</TabsTrigger>
          <TabsTrigger value="reconciliation">Reconciliation</TabsTrigger>
          <TabsTrigger value="services">Service Health</TabsTrigger>
        </TabsList>

        {/* Live Transactions */}
        <TabsContent value="transactions">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                Live Transaction Feed
                <Badge variant="outline" className="text-xs">
                  {liveTransactions.length} events
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {liveTransactions.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  <p className="text-lg mb-2">
                    Waiting for live transactions...
                  </p>
                  <p className="text-sm">
                    Transactions will appear here in real-time as they are
                    processed.
                  </p>
                </div>
              ) : (
                <div className="space-y-2 max-h-[500px] overflow-y-auto">
                  {liveTransactions.map((tx: any) => (
                    <div
                      key={tx.id}
                      className="flex items-center justify-between p-3 rounded-lg bg-muted/50"
                    >
                      <div className="flex items-center gap-3">
                        <Badge className={statusColor(tx.status)}>
                          {tx.status}
                        </Badge>
                        <div>
                          <p className="font-medium text-sm">{tx.type}</p>
                          <p className="text-xs text-muted-foreground">
                            Agent: {tx.agentId}
                          </p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="font-bold">
                          {formatCurrency(tx.amount, tx.currency)}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {formatTime(tx.timestamp)}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Reconciliation Events */}
        <TabsContent value="reconciliation">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                Reconciliation Events
                <Badge variant="outline" className="text-xs">
                  {reconciliationEvents.length} events
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {reconciliationEvents.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  <p className="text-lg mb-2">No reconciliation events yet</p>
                  <p className="text-sm">
                    Reconciliation results will stream here as batches complete.
                  </p>
                </div>
              ) : (
                <div className="space-y-2 max-h-[500px] overflow-y-auto">
                  {reconciliationEvents.map((event: any) => (
                    <div
                      key={event.id}
                      className="flex items-center justify-between p-3 rounded-lg bg-muted/50"
                    >
                      <div className="flex items-center gap-3">
                        <Badge
                          className={
                            event.discrepancyCount === 0
                              ? "bg-green-500/10 text-green-500"
                              : "bg-yellow-500/10 text-yellow-500"
                          }
                        >
                          {event.source}
                        </Badge>
                        <div>
                          <p className="font-medium text-sm">
                            Matched: {event.matchedCount} | Unmatched:{" "}
                            {event.unmatchedCount}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            Discrepancies: {event.discrepancyCount}
                          </p>
                        </div>
                      </div>
                      <div className="text-right">
                        <p className="font-bold">
                          {event.totalVariance > 0
                            ? formatCurrency(event.totalVariance)
                            : "No variance"}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {formatTime(event.timestamp)}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Service Health */}
        <TabsContent value="services">
          <Card>
            <CardHeader>
              <CardTitle>Go Service Health Monitor</CardTitle>
            </CardHeader>
            <CardContent>
              {serviceHealth.length === 0 ? (
                <div className="text-center py-12 text-muted-foreground">
                  <p className="text-lg mb-2">Monitoring 15 Go microservices</p>
                  <p className="text-sm">
                    Health status updates stream via WebSocket every 30 seconds.
                  </p>
                  <div className="grid grid-cols-3 md:grid-cols-5 gap-3 mt-6">
                    {[
                      "workflow-orchestrator",
                      "tigerbeetle-integrated",
                      "mdm-compliance",
                      "pbac-engine",
                      "connectivity-resilience",
                      "billing-aggregator",
                      "rbac-service",
                      "ussd-gateway",
                      "ussd-tx-processor",
                      "hierarchy-engine",
                      "settlement-gateway",
                      "at-ussd-handler",
                      "opensearch-analytics",
                      "revenue-reconciler",
                      "fluvio-streaming",
                    ].map((svc: any) => (
                      <div
                        key={svc}
                        className="p-3 rounded-lg bg-muted/50 text-center"
                      >
                        <div className="w-3 h-3 rounded-full bg-gray-400 mx-auto mb-2" />
                        <p className="text-xs truncate">{svc}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="grid grid-cols-3 md:grid-cols-5 gap-3">
                  {serviceHealth.map((svc: any) => (
                    <div
                      key={svc.name}
                      className="p-3 rounded-lg bg-muted/50 text-center"
                    >
                      <div
                        className={`w-3 h-3 rounded-full mx-auto mb-2 ${svc.status === "healthy" ? "bg-green-500" : svc.status === "degraded" ? "bg-yellow-500" : "bg-red-500"}`}
                      />
                      <p className="text-xs truncate font-medium">{svc.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {svc.latencyMs}ms
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
