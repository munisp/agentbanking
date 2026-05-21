import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import DashboardLayout from "@/components/DashboardLayout";

const statusColors: Record<string, string> = {
  normal: "bg-emerald-500/20 text-emerald-400",
  suspicious: "bg-orange-500/20 text-orange-400",
  flagged: "bg-red-500/20 text-red-400",
  reviewed: "bg-blue-500/20 text-blue-400",
};

function formatCurrency(val: unknown): string {
  const n = Number(val ?? 0);
  return new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency: "NGN",
    maximumFractionDigits: 0,
  }).format(n);
}

export default function TransactionGraphAnalyzer() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const summary = trpc.transactionGraphAnalyzer.getSummary.useQuery()?.data as
    | Record<string, unknown>
    | undefined;
  const listQ = trpc.transactionGraphAnalyzer.list.useQuery({
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
            <h1 className="text-2xl font-bold">Transaction Graph Analyzer</h1>
            <p className="text-muted-foreground">
              Network analysis of transaction flows, pattern detection, and
              anomaly identification
            </p>
          </div>
          <div className="flex gap-2 flex-wrap">
            <Button onClick={() => toast.success("Analyze Network initiated")}>
              Analyze Network
            </Button>
            <Button
              variant="outline"
              onClick={() => toast.success("Flag Anomaly initiated")}
            >
              Flag Anomaly
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card key="0">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Network Nodes
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {(summary?.totalNodes ?? 0).toLocaleString()}
              </div>
            </CardContent>
          </Card>
          <Card key="1">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Connections
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {(summary?.totalEdges ?? 0).toLocaleString()}
              </div>
            </CardContent>
          </Card>
          <Card key="2">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Anomalies
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {(summary?.anomalies ?? 0).toLocaleString()}
              </div>
            </CardContent>
          </Card>
          <Card key="3">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Clusters
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {(summary?.clusters ?? 0).toLocaleString()}
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
                          ID
                        </th>
                        <th className="text-left p-3 text-sm font-medium text-muted-foreground">
                          Source
                        </th>
                        <th className="text-left p-3 text-sm font-medium text-muted-foreground">
                          Target
                        </th>
                        <th className="text-left p-3 text-sm font-medium text-muted-foreground">
                          Amount
                        </th>
                        <th className="text-left p-3 text-sm font-medium text-muted-foreground">
                          Frequency
                        </th>
                        <th className="text-left p-3 text-sm font-medium text-muted-foreground">
                          Risk
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((row: any, idx: number) => (
                        <tr
                          key={idx}
                          className="border-b border-border/50 hover:bg-muted/50 transition-colors"
                        >
                          <td className="p-3">{String(row.id ?? "—")}</td>
                          <td className="p-3">
                            {String(row.sourceNode ?? "—")}
                          </td>
                          <td className="p-3">
                            {String(row.targetNode ?? "—")}
                          </td>
                          <td className="p-3 font-mono">
                            {formatCurrency(row.amount)}
                          </td>
                          <td className="p-3">
                            {Number(row.frequency ?? 0).toLocaleString()}
                          </td>
                          <td className="p-3">
                            <span
                              className={`px-2 py-1 rounded-full text-xs font-medium ${statusColors[String(row.riskScore)] || "bg-gray-500/20 text-gray-400"}`}
                            >
                              {String(row.riskScore ?? "—")}
                            </span>
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
