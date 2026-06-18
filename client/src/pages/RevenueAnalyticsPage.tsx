import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import DashboardLayout from "@/components/DashboardLayout";

const statusColors: Record<string, string> = {};

export default function RevenueAnalyticsPage() {
  const [search, setSearch] = useState("");
  // @ts-ignore — Sprint 85: strict-mode suppression
  const { data, isLoading } = trpc.revenueAnalytics.dashboard.useQuery();
  const d = data as Record<string, unknown> | undefined;
  const listData = (d?.revenueBreakdown ?? d?.recent ?? []) as Record<
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
            <h1 className="text-2xl font-bold">Revenue Analytics</h1>
            <p className="text-muted-foreground">
              Revenue tracking, trend analysis, and financial performance
              dashboards
            </p>
          </div>
          <div className="flex gap-2 flex-wrap">
            <Button onClick={() => toast.success("Generate Report initiated")}>
              Generate Report
            </Button>
            <Button
              variant="outline"
              onClick={() => toast.success("Export CSV initiated")}
            >
              Export CSV
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
                    Total Revenue
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {String(d?.totalRevenue ?? 0)}
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    Monthly Growth
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {String(d?.monthlyGrowth ?? 0) + "%"}
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    Avg Per Agent
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {String(d?.avgRevenuePerAgent ?? 0)}
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    Top Source
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {String(d?.topRevenueSource ?? 0)}
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
                            Source
                          </th>
                          <th className="text-left p-3 text-sm font-medium text-muted-foreground">
                            Category
                          </th>
                          <th className="text-left p-3 text-sm font-medium text-muted-foreground">
                            Amount
                          </th>
                          <th className="text-left p-3 text-sm font-medium text-muted-foreground">
                            Period
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
                            <td className="p-3">{String(r.source ?? "—")}</td>
                            <td className="p-3">{String(r.category ?? "—")}</td>
                            <td className="p-3 font-mono">
                              {new Intl.NumberFormat("en-NG", {
                                style: "currency",
                                currency: "NGN",
                                maximumFractionDigits: 0,
                              }).format(Number(r.amount ?? 0))}
                            </td>
                            <td className="p-3">{String(r.period ?? "—")}</td>
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
