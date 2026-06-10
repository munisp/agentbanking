import { trpc } from "@/lib/trpc";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function ResilienceMonitor() {
  const probeQ = trpc.resilience.probe.useQuery(undefined, {
    retry: false,
    refetchInterval: 15000,
  });
  const queueQ = trpc.resilience.queueCount.useQuery(undefined, {
    retry: false,
    refetchInterval: 15000,
  });

  return (
    <div className="min-h-screen bg-gray-950 text-white p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Resilience & USSD Monitor</h1>
            <p className="text-gray-400 text-sm">
              Offline-first resilience, USSD encoding, and carrier detection
            </p>
          </div>
          <a href="/" className="text-sm text-gray-400 hover:text-white">
            ← Back
          </a>
        </div>

        <div className="grid grid-cols-4 gap-4">
          {[
            {
              label: "Network Quality",
              value: probeQ.data?.quality || "Unknown",
              color:
                probeQ.data?.quality === "good"
                  ? "text-green-400"
                  : "text-amber-400",
            },
            {
              label: "Latency",
              value: probeQ.data?.latency_ms
                ? `${probeQ.data.latency_ms}ms`
                : "—",
              color: "text-white",
            },
            {
              label: "Queue Depth",
              value: String(queueQ.data?.pending ?? 0),
              color: "text-white",
            },
            {
              label: "Timestamp",
              value: probeQ.data?.timestamp
                ? new Date(probeQ.data.timestamp).toLocaleTimeString()
                : "—",
              color: "text-white",
            },
          ].map((kpi, i) => (
            <Card key={i} className="bg-gray-900 border-gray-800">
              <CardContent className="pt-4">
                <div className="text-xs text-gray-400">{kpi.label}</div>
                <div className={`text-xl font-bold ${kpi.color}`}>
                  {kpi.value}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        <Card className="bg-gray-900 border-gray-800">
          <CardHeader>
            <CardTitle className="text-white">USSD Fallback Status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {[
                { label: "USSD Gateway", value: "Connected", ok: true },
                { label: "SMS Fallback", value: "Ready", ok: true },
                {
                  label: "Offline Queue",
                  value: `${queueQ.data?.pending ?? 0} pending`,
                  ok: (queueQ.data?.pending ?? 0) < 100,
                },
                { label: "Auto-Retry", value: "Enabled", ok: true },
              ].map((item, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between p-3 bg-gray-800 rounded"
                >
                  <span className="text-sm text-gray-300">{item.label}</span>
                  <Badge className={item.ok ? "bg-green-600" : "bg-amber-600"}>
                    {item.value}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
