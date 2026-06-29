import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

const statusVariant: Record<string, string> = {
  low_risk: "default",
  medium_risk: "secondary",
  high_risk: "destructive",
  very_high_risk: "destructive",
};

export default function AiCreditScoringPage() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const limit = 20;

  const statsQuery = {data: null};
  const listQuery = {data: null};
  const analyticsQuery = {data: null};
  const healthQuery = {data: null};

  const stats: any = statsQuery.data;
  const items: any[] = [];
  const total = 0;

  return (
    <>
      <div className="space-y-6 p-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">AI Credit Scoring</h1>
            <p className="text-muted-foreground">ML-powered credit scoring using transaction history and alternative data</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm">Score Customer</Button>
            <Button variant="outline" size="sm">Retrain Model</Button>
            <Button variant="outline" size="sm">View Metrics</Button>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium text-muted-foreground">Customers Scored</CardTitle></CardHeader>
            <CardContent><div className="text-2xl font-bold">{String(stats?.totalScored ?? "—")}</div></CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium text-muted-foreground">Avg Score</CardTitle></CardHeader>
            <CardContent><div className="text-2xl font-bold">{String(stats?.avgScore ?? "—")}</div></CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium text-muted-foreground">Approval Rate</CardTitle></CardHeader>
            <CardContent><div className="text-2xl font-bold">{String(stats?.approvalRate ?? "—")}</div></CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2"><CardTitle className="text-sm font-medium text-muted-foreground">Model AUC</CardTitle></CardHeader>
            <CardContent><div className="text-2xl font-bold">{String(stats?.modelAuc ?? "—")}</div></CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium">Records</CardTitle>
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
