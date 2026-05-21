import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import DashboardLayout from "@/components/DashboardLayout";

const statusColors: Record<string, string> = {
  'ok': 'bg-emerald-500/20 text-emerald-400',
  'error': 'bg-red-500/20 text-red-400',
  'slow': 'bg-yellow-500/20 text-yellow-400'
};

function formatCurrency(val: unknown): string {
  const n = Number(val ?? 0);
  return new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN", maximumFractionDigits: 0 }).format(n);
}

export default function DistributedTracingDash() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const summary = trpc.distributedTracingDash.getSummary.useQuery()?.data as Record<string, unknown> | undefined;
  const listQ = trpc.distributedTracingDash.list.useQuery({ limit: 20, offset: page * 20, search: search || undefined });
  const items = (listQ.data as any)?.items ?? (listQ.data as any)?.data ?? [];
  const total = (listQ.data as any)?.total ?? 0;

  return (
    <DashboardLayout>
      <div className="space-y-6 p-6">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-2xl font-bold">Distributed Tracing</h1>
            <p className="text-muted-foreground">End-to-end request tracing, latency analysis, and service dependency mapping</p>
          </div>
          <div className="flex gap-2 flex-wrap">
        <Button onClick={() => toast.success("Search Traces initiated")}>Search Traces</Button>
        <Button variant="outline" onClick={() => toast.success("Analyze Bottleneck initiated")}>Analyze Bottleneck</Button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card key="0">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Total Traces</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{(summary?.totalTraces ?? 0).toLocaleString()}</div>
          </CardContent>
        </Card>
        <Card key="1">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Avg Latency</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{(summary?.avgLatency ?? 0).toLocaleString()}</div>
          </CardContent>
        </Card>
        <Card key="2">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">P99 Latency</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{(summary?.p99Latency ?? 0).toLocaleString()}</div>
          </CardContent>
        </Card>
        <Card key="3">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">Error Traces</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{(summary?.errorTraces ?? 0).toLocaleString()}</div>
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
                onChange={(e) => setSearch(e.target.value)}
                className="max-w-xs"
              />
            </div>
          </CardHeader>
          <CardContent>
            {listQ.isLoading ? (
              <div className="space-y-3">
                {[1,2,3,4,5].map(i => <div key={i} className="h-12 bg-muted animate-pulse rounded" />)}
              </div>
            ) : items.length > 0 ? (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-border">
            <th className="text-left p-3 text-sm font-medium text-muted-foreground">Trace ID</th>
            <th className="text-left p-3 text-sm font-medium text-muted-foreground">Service</th>
            <th className="text-left p-3 text-sm font-medium text-muted-foreground">Operation</th>
            <th className="text-left p-3 text-sm font-medium text-muted-foreground">Duration (ms)</th>
            <th className="text-left p-3 text-sm font-medium text-muted-foreground">Spans</th>
            <th className="text-left p-3 text-sm font-medium text-muted-foreground">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((row: any, idx: number) => (
                        <tr key={idx} className="border-b border-border/50 hover:bg-muted/50 transition-colors">
              <td className="p-3">{String(row.id ?? '—')}</td>
              <td className="p-3">{String(row.service ?? '—')}</td>
              <td className="p-3">{String(row.operation ?? '—')}</td>
              <td className="p-3">{Number(row.duration ?? 0).toLocaleString()}</td>
              <td className="p-3">{Number(row.spans ?? 0).toLocaleString()}</td>
              <td className="p-3"><span className={`px-2 py-1 rounded-full text-xs font-medium ${statusColors[String(row.status)] || 'bg-gray-500/20 text-gray-400'}`}>{String(row.status ?? '—')}</span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="flex items-center justify-between mt-4 pt-4 border-t border-border">
                  <p className="text-sm text-muted-foreground">
                    Showing {page * 20 + 1}–{Math.min((page + 1) * 20, total)} of {total}
                  </p>
                  <div className="flex gap-2">
                    <Button variant="outline" size="sm" onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}>Previous</Button>
                    <Button variant="outline" size="sm" onClick={() => setPage(p => p + 1)} disabled={(page + 1) * 20 >= total}>Next</Button>
                  </div>
                </div>
              </>
            ) : (
              <div className="text-center py-12 text-muted-foreground">
                <p className="text-lg font-medium">No records found</p>
                <p className="text-sm mt-1">Data will appear here once the system is connected to live services</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
