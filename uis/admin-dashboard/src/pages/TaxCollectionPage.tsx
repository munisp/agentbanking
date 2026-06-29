import { useState } from "react";
import DashboardLayout from "@/components/DashboardLayout";
import { trpc } from "@/lib/trpc";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Receipt, Building2, FileText, BarChart3 } from "lucide-react";

export default function TaxCollectionPage() {
  const [tab, setTab] = useState<"payments" | "types" | "agents">("payments");
  // @ts-ignore Sprint 85
  const payments = trpc.taxCollection.history.useQuery({ limit: 20 });
  // @ts-ignore Sprint 85
  const taxTypes = trpc.taxCollection.taxTypes.useQuery();
  // @ts-ignore Sprint 85
  const agentPerformance = trpc.taxCollection.history.useQuery({ limit: 20 });
  // @ts-ignore Sprint 85
  const analytics = trpc.taxCollection.analytics.useQuery();

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Tax Collection</h1>
          <p className="text-muted-foreground">
            State and federal tax payments — PAYE, WHT, VAT, company income tax
            via agents
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">
                Total Collected
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">
                NGN {(analytics.data?.totalVolume ?? 0).toLocaleString()}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">
                Transactions
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">
                {(analytics.data?.totalPayments ?? 0).toLocaleString()}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">
                Commission
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">
                NGN {(analytics.data?.totalCommission ?? 0).toLocaleString()}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">
                Success Rate
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">
                {analytics.data?.successRate ?? 0}
              </p>
            </CardContent>
          </Card>
        </div>

        <div className="flex gap-2">
          <Button
            variant={tab === "payments" ? "default" : "outline"}
            onClick={() => setTab("payments")}
          >
            <Receipt className="h-4 w-4 mr-1" />
            Payments
          </Button>
          <Button
            variant={tab === "types" ? "default" : "outline"}
            onClick={() => setTab("types")}
          >
            <FileText className="h-4 w-4 mr-1" />
            Tax Types
          </Button>
          <Button
            variant={tab === "agents" ? "default" : "outline"}
            onClick={() => setTab("agents")}
          >
            <Building2 className="h-4 w-4 mr-1" />
            Agent Performance
          </Button>
        </div>

        {tab === "payments" && (
          <Card>
            <CardHeader>
              <CardTitle>Recent Tax Payments</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left p-2">Ref</th>
                      <th className="text-left p-2">Taxpayer</th>
                      <th className="text-left p-2">TIN</th>
                      <th className="text-left p-2">Tax Type</th>
                      <th className="text-right p-2">Amount</th>
                      <th className="text-left p-2">Period</th>
                      <th className="text-left p-2">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {payments.data?.payments?.map((p: any) => (
                      <tr key={p.id} className="border-b">
                        <td className="p-2 font-mono text-xs">{p.reference}</td>
                        <td className="p-2">{p.taxpayerName}</td>
                        <td className="p-2 font-mono text-xs">{p.tin}</td>
                        <td className="p-2">
                          <Badge>{p.taxType}</Badge>
                        </td>
                        <td className="p-2 text-right font-bold">
                          NGN {p.amount?.toLocaleString()}
                        </td>
                        <td className="p-2 text-xs">{p.period}</td>
                        <td className="p-2">
                          <Badge
                            variant={
                              p.status === "remitted"
                                ? "default"
                                : p.status === "collected"
                                  ? "secondary"
                                  : "destructive"
                            }
                          >
                            {p.status}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}

        {tab === "types" && (
          <Card>
            <CardHeader>
              <CardTitle>Tax Types</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {taxTypes.data?.taxTypes?.map((t: any) => (
                  <div key={t.id} className="border rounded p-3">
                    <p className="font-bold">{t.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {t.code} &bull; {t.jurisdiction}
                    </p>
                    <div className="flex items-center justify-between mt-2">
                      <span className="text-xs">Rate: {t.rate}%</span>
                      <Badge variant={t.active ? "default" : "secondary"}>
                        {t.active ? "Active" : "Inactive"}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {tab === "agents" && (
          <Card>
            <CardHeader>
              <CardTitle>Agent Tax Collection Performance</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left p-2">Agent</th>
                      <th className="text-left p-2">State</th>
                      <th className="text-right p-2">Collected</th>
                      <th className="text-right p-2">Transactions</th>
                      <th className="text-right p-2">Commission</th>
                      <th className="text-left p-2">Rating</th>
                    </tr>
                  </thead>
                  <tbody>
                    {agentPerformance.data?.payments?.map((a: any) => (
                      <tr key={a.id} className="border-b">
                        <td className="p-2">{a.agentName}</td>
                        <td className="p-2">{a.state}</td>
                        <td className="p-2 text-right font-bold">
                          NGN {a.totalCollected?.toLocaleString()}
                        </td>
                        <td className="p-2 text-right">{a.transactionCount}</td>
                        <td className="p-2 text-right">
                          NGN {a.commission?.toLocaleString()}
                        </td>
                        <td className="p-2">
                          <Badge
                            variant={a.rating >= 4 ? "default" : "secondary"}
                          >
                            {a.rating}/5
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardLayout>
  );
}
