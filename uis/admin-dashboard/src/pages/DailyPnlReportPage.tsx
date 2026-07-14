import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import {
  TrendingUp,
  TrendingDown,
  DollarSign,
  Calendar,
  Download,
} from "lucide-react";

export default function DailyPnlReportPage() {
  const [date, setDate] = useState(new Date().toISOString().split("T")[0]);
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const { data, isLoading } = trpc.dailyPnlReport.getReport.useQuery({ date });
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const exportMut = trpc.dailyPnlReport.export.useMutation({
    onSuccess: () => toast.success("Report exported"),
  });

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <DollarSign className="w-6 h-6" /> Daily P&L Report
          </h1>
          <p className="text-muted-foreground mt-1">
            Daily profit and loss breakdown by product, agent tier, and region
          </p>
        </div>
        <div className="flex gap-2">
          <Input
            type="date"
            value={date}
            onChange={e => setDate(e.target.value)}
            className="w-40"
          />
          <Button
            onClick={() => exportMut.mutate({ date })}
            disabled={exportMut.isPending}
          >
            <Download className="w-4 h-4 mr-1" /> Export
          </Button>
        </div>
      </div>
      <div className="grid grid-cols-4 gap-4">
        <Card className="border-green-200">
          <CardContent className="pt-4 text-center">
            <TrendingUp className="w-5 h-5 mx-auto text-green-600 mb-1" />
            <p className="text-2xl font-bold text-green-600">
              ${(data?.revenue || 0).toLocaleString()}
            </p>
            <p className="text-sm text-muted-foreground">Revenue</p>
          </CardContent>
        </Card>
        <Card className="border-red-200">
          <CardContent className="pt-4 text-center">
            <TrendingDown className="w-5 h-5 mx-auto text-red-600 mb-1" />
            <p className="text-2xl font-bold text-red-600">
              ${(data?.expenses || 0).toLocaleString()}
            </p>
            <p className="text-sm text-muted-foreground">Expenses</p>
          </CardContent>
        </Card>
        <Card className="border-blue-200">
          <CardContent className="pt-4 text-center">
            <DollarSign className="w-5 h-5 mx-auto text-blue-600 mb-1" />
            <p className="text-2xl font-bold text-blue-600">
              ${(data?.commissionPaid || 0).toLocaleString()}
            </p>
            <p className="text-sm text-muted-foreground">Commission Paid</p>
          </CardContent>
        </Card>
        <Card
          className={`border-${(data?.netProfit || 0) >= 0 ? "green" : "red"}-200`}
        >
          <CardContent className="pt-4 text-center">
            <DollarSign className="w-5 h-5 mx-auto mb-1" />
            <p
              className={`text-2xl font-bold ${(data?.netProfit || 0) >= 0 ? "text-green-600" : "text-red-600"}`}
            >
              ${(data?.netProfit || 0).toLocaleString()}
            </p>
            <p className="text-sm text-muted-foreground">Net Profit</p>
          </CardContent>
        </Card>
      </div>
      {isLoading ? (
        <div className="text-center py-8">Loading...</div>
      ) : (
        <>
          <Card>
            <CardContent className="pt-4">
              <h3 className="font-semibold mb-3">Revenue by Product</h3>
              <div className="space-y-2">
                {(data?.byProduct || []).map((p: any, i: number) => (
                  <div key={i} className="flex items-center justify-between">
                    <span className="text-sm">{p.product}</span>
                    <div className="flex items-center gap-2">
                      <div className="w-48 bg-gray-200 rounded h-4">
                        <div
                          className="bg-green-500 rounded h-4"
                          style={{
                            width: `${Math.min(100, (p.revenue / (data?.revenue || 1)) * 100)}%`,
                          }}
                        />
                      </div>
                      <span className="text-sm font-medium w-24 text-right">
                        ${p.revenue?.toLocaleString()}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-4">
              <h3 className="font-semibold mb-3">Commission by Agent Tier</h3>
              <div className="border rounded-lg overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="bg-muted">
                    <tr>
                      <th className="p-3 text-left">Tier</th>
                      <th className="p-3 text-right">Agents</th>
                      <th className="p-3 text-right">Transactions</th>
                      <th className="p-3 text-right">Commission</th>
                      <th className="p-3 text-right">Avg/Agent</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(data?.byTier || []).map((t: any, i: number) => (
                      <tr key={i} className="border-t">
                        <td className="p-3 font-medium">{t.tier}</td>
                        <td className="p-3 text-right">{t.agents}</td>
                        <td className="p-3 text-right">
                          {t.transactions?.toLocaleString()}
                        </td>
                        <td className="p-3 text-right">
                          ${t.commission?.toLocaleString()}
                        </td>
                        <td className="p-3 text-right">
                          ${t.avgPerAgent?.toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
