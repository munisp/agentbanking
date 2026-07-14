import { useState } from "react";
import { toast } from "sonner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const statusColors: Record<string, string> = {
  settled: "bg-emerald-500/20 text-emerald-400",
  pending: "bg-yellow-500/20 text-yellow-400",
  failed: "bg-red-500/20 text-red-400",
  netting: "bg-blue-500/20 text-blue-400",
};

function formatCurrency(val: unknown): string {
  const n = Number(val ?? 0);
  return new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN", maximumFractionDigits: 0 }).format(n);
}

export default function SettlementNettingEngine() {
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
            <h1 className="text-2xl font-bold">Settlement Netting</h1>
            <p className="text-muted-foreground">Bilateral netting, settlement batches, and reconciliation management</p>
          </div>
          <div className="flex gap-2 flex-wrap">
            <Button onClick={() => toast.success("Run Netting initiated")}>Run Netting</Button>
            <Button variant="outline" onClick={() => toast.success("Reconcile initiated")}>Reconcile</Button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium text-muted-foreground">Settlement Batches</CardTitle></CardHeader>
            <CardContent><div className="text-2xl font-bold">{((summary.data as any)?.totalBatches ?? 0).toLocaleString()}</div></CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium text-muted-foreground">Net Settled</CardTitle></CardHeader>
            <CardContent><div className="text-2xl font-bold">{formatCurrency((summary.data as any)?.netSettled)}</div></CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium text-muted-foreground">Pending</CardTitle></CardHeader>
            <CardContent><div className="text-2xl font-bold">{formatCurrency((summary.data as any)?.pendingSettlement)}</div></CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium text-muted-foreground">Netting Savings</CardTitle></CardHeader>
            <CardContent><div className="text-2xl font-bold">{formatCurrency((summary.data as any)?.savingsFromNetting)}</div></CardContent>
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
