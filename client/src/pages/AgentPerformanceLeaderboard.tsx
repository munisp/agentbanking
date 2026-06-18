import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import DashboardLayout from "@/components/DashboardLayout";

const statusColors: Record<string, string> = {};

function formatCurrency(val: unknown): string {
  const n = Number(val ?? 0);
  return new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency: "NGN",
    maximumFractionDigits: 0,
  }).format(n);
}

export default function AgentPerformanceLeaderboard() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const summary = trpc.agentPerformanceLeaderboard.getSummary.useQuery()
    ?.data as Record<string, unknown> | undefined;
  const listQ = trpc.agentPerformanceLeaderboard.list.useQuery({
    limit: 20,
    offset: page * 20,
    search: search || undefined,
  });
  const items = (listQ.data as any)?.items ?? (listQ.data as any)?.data ?? [];
  const total = (listQ.data as any)?.total ?? 0;

  return (
    <DashboardLayout>
      <div className="space-y-6 p-6">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-2xl font-bold">
              Agent Performance Leaderboard
            </h1>
            <p className="text-muted-foreground">
              Agent rankings by transaction volume, revenue, and customer
              satisfaction
            </p>
          </div>
          <div className="flex gap-2 flex-wrap">
            <Button onClick={() => toast.success("Export Rankings initiated")}>
              Export Rankings
            </Button>
            <Button
              variant="outline"
              onClick={() => toast.success("Award Bonus initiated")}
            >
              Award Bonus
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card key="0">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Ranked Agents
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {(summary?.totalAgents ?? 0).toLocaleString()}
              </div>
            </CardContent>
          </Card>
          <Card key="1">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Avg Score
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {(summary?.avgScore ?? 0).toLocaleString()}
              </div>
            </CardContent>
          </Card>
          <Card key="2">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Top Performer
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {(summary?.topPerformer ?? 0).toLocaleString()}
              </div>
            </CardContent>
          </Card>
          <Card key="3">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Total Revenue
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {formatCurrency(summary?.totalRevenue)}
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
            {listQ.isLoading ? (
              <div className="space-y-3">
                {[1, 2, 3, 4, 5].map(i => (
                  <div
                    key={i}
                    className="h-12 bg-muted animate-pulse rounded"
                  />
                ))}
              </div>
            ) : items.length > 0 ? (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-border">
                        <th className="text-left p-3 text-sm font-medium text-muted-foreground">
                          #
                        </th>
                        <th className="text-left p-3 text-sm font-medium text-muted-foreground">
                          Agent Name
                        </th>
                        <th className="text-left p-3 text-sm font-medium text-muted-foreground">
                          Code
                        </th>
                        <th className="text-left p-3 text-sm font-medium text-muted-foreground">
                          Transactions
                        </th>
                        <th className="text-left p-3 text-sm font-medium text-muted-foreground">
                          Revenue
                        </th>
                        <th className="text-left p-3 text-sm font-medium text-muted-foreground">
                          Rating
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((row: any, idx: number) => (
                        <tr
                          key={idx}
                          className="border-b border-border/50 hover:bg-muted/50 transition-colors"
                        >
                          <td className="p-3">{String(row.rank ?? "—")}</td>
                          <td className="p-3">{String(row.fullName ?? "—")}</td>
                          <td className="p-3">
                            {String(row.agentCode ?? "—")}
                          </td>
                          <td className="p-3">
                            {Number(row.txVolume ?? 0).toLocaleString()}
                          </td>
                          <td className="p-3 font-mono">
                            {formatCurrency(row.revenue)}
                          </td>
                          <td className="p-3">
                            {"★".repeat(
                              Math.min(
                                5,
                                Math.max(0, Math.round(Number(row.rating ?? 0)))
                              )
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="flex items-center justify-between mt-4 pt-4 border-t border-border">
                  <p className="text-sm text-muted-foreground">
                    Showing {page * 20 + 1}–{Math.min((page + 1) * 20, total)}{" "}
                    of {total}
                  </p>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage(p => Math.max(0, p - 1))}
                      disabled={page === 0}
                    >
                      Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setPage(p => p + 1)}
                      disabled={(page + 1) * 20 >= total}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              </>
            ) : (
              <div className="text-center py-12 text-muted-foreground">
                <p className="text-lg font-medium">No records found</p>
                <p className="text-sm mt-1">
                  Data will appear here once the system is connected to live
                  services
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
