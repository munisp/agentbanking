import { trpc } from "@/lib/trpc";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import DashboardLayout from "@/components/DashboardLayout";

export default function ApiVersioningPage() {
  const { data, isLoading } = trpc.apiVersioning.dashboard.useQuery();
  if (isLoading)
    return (
      <DashboardLayout>
        <div className="p-8 text-center animate-pulse">
          Loading API versions...
        </div>
      </DashboardLayout>
    );
  const d = data as any;
  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold">API Versioning</h1>
          <p className="text-muted-foreground">
            Version management, deprecation, and migration guides
          </p>
        </div>
        <div className="grid grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="text-3xl font-bold text-green-500">
                {d?.currentVersion ?? "v3.0"}
              </div>
              <p className="text-sm text-muted-foreground">Current Version</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-3xl font-bold text-red-500">
                {d?.deprecatedVersions?.length ?? 0}
              </div>
              <p className="text-sm text-muted-foreground">Deprecated</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-3xl font-bold">
                {d?.versionUsage?.length ?? 0}
              </div>
              <p className="text-sm text-muted-foreground">Active Versions</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-3xl font-bold text-blue-500">
                {d?.migrationGuides?.length ?? 0}
              </div>
              <p className="text-sm text-muted-foreground">Migration Guides</p>
            </CardContent>
          </Card>
        </div>
        <Card>
          <CardHeader>
            <CardTitle>Version Usage</CardTitle>
          </CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left">
                  <th className="p-3">Version</th>
                  <th className="p-3">Status</th>
                  <th className="p-3">Requests (24h)</th>
                  <th className="p-3">Clients</th>
                  <th className="p-3">Sunset Date</th>
                </tr>
              </thead>
              <tbody>
                {(d?.versionUsage ?? []).map((v: any, i: number) => (
                  <tr key={i} className="border-b hover:bg-muted/50">
                    <td className="p-3 font-mono font-bold">
                      {v.version ?? `v${3 - i}.0`}
                    </td>
                    <td className="p-3">
                      <Badge
                        className={
                          v.status === "current"
                            ? "bg-green-500"
                            : v.status === "deprecated"
                              ? "bg-red-500"
                              : "bg-amber-500"
                        }
                      >
                        {v.status ?? "active"}
                      </Badge>
                    </td>
                    <td className="p-3">
                      {(v.requests ?? 0).toLocaleString()}
                    </td>
                    <td className="p-3">{v.clients ?? 0}</td>
                    <td className="p-3">{v.sunsetDate ?? "N/A"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Changelog</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {(d?.changelog ?? []).map((c: any, i: number) => (
                <div key={i} className="p-3 bg-muted rounded">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant="outline">{c.version ?? "v3.0"}</Badge>
                    <span className="text-xs text-muted-foreground">
                      {c.date ?? "2024-01-15"}
                    </span>
                  </div>
                  <p className="text-sm">
                    {c.description ?? c.change ?? "API update"}
                  </p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
