import { useState } from "react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

function formatCurrency(val: unknown): string {
  const n = Number(val ?? 0);
  return new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN", maximumFractionDigits: 0 }).format(n);
}

export default function AgentRevenueAttribution() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const summary = {data: null};
  const listQ = {data: null, isLoading: false};
  const items: any[] = [];
  const total = 0;

  return (
    <>
      <div className="space-y-6 p-6">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-2xl font-bold">Agent Revenue Attribution</h1>
            <p className="text-muted-foreground">
              Revenue tracking by agent, channel, and product with attribution models
            </p>
          </div>
          <div className="flex gap-2 flex-wrap">
            <Button onClick={() => toast.success("Export Report initiated")}>Export Report</Button>
            <Button variant="outline" onClick={() => toast.success("Recalculate initiated")}>Recalculate</Button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium text-muted-foreground">Total Revenue</CardTitle></CardHeader>
            <CardContent><div className="text-2xl font-bold">{formatCurrency((summary.data as any)?.totalRevenue)}</div></CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium text-muted-foreground">Agent Commissions</CardTitle></CardHeader>
            <CardContent><div className="text-2xl font-bold">{formatCurrency((summary.data as any)?.agentCommissions)}</div></CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium text-muted-foreground">Platform Revenue</CardTitle></CardHeader>
            <CardContent><div className="text-2xl font-bold">{formatCurrency((summary.data as any)?.platformRevenue)}</div></CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium text-muted-foreground">Growth Rate</CardTitle></CardHeader>
            <CardContent><div className="text-2xl font-bold">{((summary.data as any)?.growthRate ?? 0) + "%"}</div></CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between gap-4">
              <CardTitle>Records</CardTitle>
              <Input placeholder="Search..." value={search} onChange={e => setSearch(e.target.value)} className="max-w-xs" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-center py-12 text-muted-foreground">
              <p className="text-lg font-medium">No records found</p>
              <p className="text-sm mt-1">Data will appear here once the system is connected to live services</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
