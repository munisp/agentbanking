import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { developerPlatformService } from "@/services/developerPlatform";
import type { PlatformOverview } from "@/types/developerPlatform";
import { AlertCircle } from "lucide-react";
import { useEffect, useState } from "react";

export default function AnalyticsDashboard() {
  const [overview, setOverview] = useState<PlatformOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    developerPlatformService
      .getPlatformOverview({ period: "month" })
      .then((data) => {
        if (cancelled) return;
        setOverview(data);
        setLoading(false);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setOverview(null);
        setError(
          err instanceof Error
            ? err.message
            : "Failed to load platform analytics.",
        );
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) return <div className="p-6">Loading analytics...</div>;
  if (error)
    return (
      <div className="p-6">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </div>
    );
  if (!overview?.metrics)
    return <div className="p-6">No analytics data available.</div>;

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-3xl font-bold mb-4">Platform Analytics</h1>
      <Card>
        <CardHeader>
          <CardTitle>API Usage (30 days)</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
            <div>
              Total API Calls:{" "}
              {overview?.metrics.total_api_calls?.toLocaleString() ?? 0}
            </div>
            <div>
              Successful Calls:{" "}
              {overview?.metrics.successful_calls?.toLocaleString() ?? 0}
            </div>
            <div>
              Failed Calls:{" "}
              {overview?.metrics.failed_calls?.toLocaleString() ?? 0}
            </div>
            <div>
              Avg Latency: {overview?.metrics.average_latency_ms ?? 0} ms
            </div>
            <div>Uptime: {overview?.metrics.uptime_percentage ?? 0}%</div>
            <div>
              Active Developers: {overview?.metrics.active_developers ?? 0}
            </div>
            <div>New Developers: {overview?.metrics.new_developers ?? 0}</div>
            <div>Active Apps: {overview?.metrics.active_apps ?? 0}</div>
            <div>New Apps: {overview?.metrics.new_apps ?? 0}</div>
            <div>
              Total Installations: {overview?.metrics.total_installations ?? 0}
            </div>
            <div>
              New Installations: {overview?.metrics.new_installations ?? 0}
            </div>
            <div>GMV: ₦{(overview?.metrics.gmv ?? 0) / 100}</div>
            <div>
              Platform Revenue: ₦
              {(overview?.metrics.platform_revenue ?? 0) / 100}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
