import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import DashboardLayout from "@/components/DashboardLayout";

const statusColors: Record<string, string> = {
  connected: "bg-emerald-500/20 text-emerald-400",
  disconnected: "bg-red-500/20 text-red-400",
  pending: "bg-yellow-500/20 text-yellow-400",
  syncing: "bg-blue-500/20 text-blue-400",
};

export default function IntegrationMarketplacePage() {
  const [search, setSearch] = useState("");
  const { data, isLoading } = trpc.integrationMarketplace.dashboard.useQuery(
    undefined as any
  );
  const d = data as Record<string, unknown> | undefined;
  const listData = (d?.integrations ?? d?.recent ?? []) as Record<
    string,
    unknown
  >[];
  const filtered = listData.filter(
    r =>
      !search || JSON.stringify(r).toLowerCase().includes(search.toLowerCase())
  );

  return (
    <DashboardLayout>
      <div className="space-y-6 p-6">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-2xl font-bold">Integration Marketplace</h1>
            <p className="text-muted-foreground">
              Third-party integration catalog, API connectors, and plugin
              management
            </p>
          </div>
          <div className="flex gap-2 flex-wrap">
            <Button
              onClick={() => toast.success("Browse Marketplace initiated")}
            >
              Browse Marketplace
            </Button>
            <Button
              variant="outline"
              onClick={() => toast.success("Add Custom initiated")}
            >
              Add Custom
            </Button>
          </div>
        </div>

        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="h-24 bg-muted animate-pulse rounded-lg" />
            ))}
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    Total Integrations
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {String(d?.totalIntegrations ?? 0)}
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    Active Connectors
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {String(d?.activeConnectors ?? 0)}
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    Pending Setup
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {String(d?.pendingSetup ?? 0)}
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    API Calls Today
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {String(d?.apiCallsToday ?? 0)}
                  </div>
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader>
                <div className="flex items-center justify-between gap-4">
                  <CardTitle>Records</CardTitle>
                  <Input
                    placeholder="Search..."
                    value={search}
                    onChange={e => setSearch(e.target.value)}
                    className="max-w-xs"
                  />
                </div>
              </CardHeader>
              <CardContent>
                {filtered.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-border">
                          <th className="text-left p-3 text-sm font-medium text-muted-foreground">
                            ID
                          </th>
                          <th className="text-left p-3 text-sm font-medium text-muted-foreground">
                            Integration
                          </th>
                          <th className="text-left p-3 text-sm font-medium text-muted-foreground">
                            Provider
                          </th>
                          <th className="text-left p-3 text-sm font-medium text-muted-foreground">
                            Status
                          </th>
                          <th className="text-left p-3 text-sm font-medium text-muted-foreground">
                            Last Sync
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {filtered.map((r, idx) => (
                          <tr
                            key={idx}
                            className="border-b border-border/50 hover:bg-muted/50 transition-colors"
                          >
                            <td className="p-3">{String(r.id ?? "—")}</td>
                            <td className="p-3">{String(r.name ?? "—")}</td>
                            <td className="p-3">{String(r.provider ?? "—")}</td>
                            <td className="p-3">
                              <span
                                className={`px-2 py-1 rounded-full text-xs font-medium ${statusColors[String(r.status)] || "bg-gray-500/20 text-gray-400"}`}
                              >
                                {String(r.status ?? "—")}
                              </span>
                            </td>
                            <td className="p-3 text-sm text-muted-foreground">
                              {r.lastSync
                                ? new Date(
                                    String(r.lastSync)
                                  ).toLocaleDateString()
                                : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="text-center py-12 text-muted-foreground">
                    <p className="text-lg font-medium">No records found</p>
                    <p className="text-sm mt-1">
                      Data will appear here once connected to live services
                    </p>
                  </div>
                )}
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </DashboardLayout>
  );
}
