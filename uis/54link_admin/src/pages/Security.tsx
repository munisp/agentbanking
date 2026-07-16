import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
// ...existing code...
import type { SecurityScan } from "@/types/developerPlatform";
import { AlertCircle } from "lucide-react";
import { useEffect, useState } from "react";

export default function SecurityDashboard() {
  const [scans, setScans] = useState<SecurityScan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadScans();
  }, []); // Fixed: removed undefined 'filters' and 'page'

  const loadScans = async () => {
    try {
      setLoading(true);
      setError(null);
      // Use mock data for now
      setTimeout(() => {
        setScans([
          {
            scan_id: "scan-1",
            app_id: "mock-app-1",
            app_name: "Mock App 1",
            scan_type: "static",
            status: "completed",
            severity: "low",
            vulnerabilities_found: 0,
            critical: 0,
            high: 0,
            medium: 0,
            low: 0,
            started_at: new Date().toISOString(),
            completed_at: new Date().toISOString(),
          },
        ]);
        setLoading(false);
      }, 500);
      // Uncomment when ready to use real API:
      // const response = await developerPlatformService.listSecurityScans();
      // setScans(response.scans);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to load security scans";
      setError(message);
      setLoading(false);
    }
  };

  if (loading) return <div className="p-6">Loading security scans...</div>;
  if (error)
    return (
      <div className="p-6">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
        <Button onClick={loadScans} className="mt-4">
          Retry
        </Button>
      </div>
    );

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-3xl font-bold mb-4">Security Scans</h1>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {scans.map((scan) => (
          <Card key={scan.scan_id}>
            <CardHeader>
              <CardTitle>{scan.app_name}</CardTitle>
              <div className="flex gap-2 mt-2">
                <Badge variant="secondary">{scan.scan_type}</Badge>
                <Badge variant="outline">{scan.status}</Badge>
                <Badge
                  variant={
                    scan.severity === "critical" ? "destructive" : "default"
                  }
                >
                  {scan.severity}
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <div className="text-sm text-muted-foreground mb-2">
                Vulnerabilities: {scan.vulnerabilities_found}
              </div>
              <div className="text-sm">
                Started: {new Date(scan.started_at).toLocaleString()}
              </div>
              <div className="text-sm">
                Completed:{" "}
                {scan.completed_at
                  ? new Date(scan.completed_at).toLocaleString()
                  : "-"}
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
