import { trpc } from "@/lib/trpc";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { TrendingUp, Server, HardDrive } from "lucide-react";

export default function CapacityPlanningPage() {
  // @ts-ignore Sprint 85
  const { data } = trpc.capacityPlanning.dashboard.useQuery();

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Capacity Planning</h1>
        <p className="text-muted-foreground">
          Resource forecasting, scaling recommendations, cost projections
        </p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[
          {
            label: "CPU Utilization",
            value: `${data?.utilizationPercent?.cpu ?? 0}%`,
          },
          {
            label: "Memory Utilization",
            value: `${data?.utilizationPercent?.memory ?? 0}%`,
          },
          {
            label: "Storage Utilization",
            value: `${data?.utilizationPercent?.storage ?? 0}%`,
          },
          {
            label: "Network Utilization",
            value: `${data?.utilizationPercent?.network ?? 0}%`,
          },
        ].map((s, i) => (
          <Card key={i}>
            <CardContent className="pt-4">
              <p className="text-2xl font-bold">{s.value}</p>
              <p className="text-xs text-muted-foreground">{s.label}</p>
            </CardContent>
          </Card>
        ))}
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5" /> Growth Forecast
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {data?.growthForecast &&
                Object.entries(data.growthForecast).map(
                  ([key, val]: [string, any]) => (
                    <div key={key} className="p-3 rounded bg-muted/50">
                      <p className="font-medium capitalize">{key}</p>
                      <div className="grid grid-cols-3 gap-2 mt-1 text-sm">
                        <div>
                          <span className="text-muted-foreground">
                            Current:
                          </span>{" "}
                          {val.current?.toLocaleString()}
                        </div>
                        <div>
                          <span className="text-muted-foreground">6mo:</span>{" "}
                          {val.projected6m?.toLocaleString()}
                        </div>
                        <div>
                          <span className="text-muted-foreground">12mo:</span>{" "}
                          {val.projected12m?.toLocaleString()}
                        </div>
                      </div>
                    </div>
                  )
                )}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Scaling Recommendations</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {(data?.scalingRecommendations ?? []).map((r: any, i: number) => (
                <div key={i} className="p-3 rounded bg-muted/50">
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{r.resource}</span>
                    <Badge
                      variant={
                        r.urgency === "high"
                          ? "destructive"
                          : r.urgency === "medium"
                            ? "secondary"
                            : "outline"
                      }
                    >
                      {r.urgency}
                    </Badge>
                  </div>
                  <p className="text-sm text-muted-foreground mt-1">
                    {r.recommendation}
                  </p>
                  <p className="text-xs mt-1">
                    Est. cost: ₦{r.estimatedCost?.toLocaleString()}
                  </p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
