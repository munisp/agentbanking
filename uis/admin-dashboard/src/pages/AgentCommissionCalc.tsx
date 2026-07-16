import DashboardLayout from "@/components/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { useState } from "react";
import { toast } from "sonner";
import { trpc } from "@/lib/trpc";
import {
  Calculator,
  RefreshCw,
  DollarSign,
  Users,
  Layers,
  TrendingUp,
} from "lucide-react";

export default function AgentCommissionCalc() {
  const [tab, setTab] = useState<"overview" | "calculate" | "tiers">(
    "overview"
  );
  const [agentId, setAgentId] = useState("11");
  const [volume, setVolume] = useState("100000");
  const [txCount, setTxCount] = useState("50");

  const statsQuery = trpc.agentCommissionCalc.getStats.useQuery();
  const tiersQuery = trpc.agentCommissionCalc.listTiers.useQuery();
  const calcMutation = trpc.agentCommissionCalc.calculateCommission.useMutation(
    {
      onSuccess: () => toast.success("Commission calculated"),
      onError: (e: any) => toast.error(e.message),
    }
  );

  const stats = statsQuery.data as any;

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Calculator className="h-6 w-6" /> Agent Commission Calculator
            </h1>
            <p className="text-muted-foreground">
              Calculate and simulate agent commissions across all tiers
            </p>
          </div>
          <div className="flex gap-2">
            {(["overview", "calculate", "tiers"] as const).map((t: any) => (
              <Button
                key={t}
                variant={tab === t ? "default" : "outline"}
                size="sm"
                onClick={() => setTab(t)}
              >
                {t.charAt(0).toUpperCase() + t.slice(1)}
              </Button>
            ))}
            <Button
              size="sm"
              variant="outline"
              onClick={() => {
                statsQuery.refetch();
                tiersQuery.refetch();
                toast.success("Data refreshed");
              }}
            >
              <RefreshCw className="h-4 w-4 mr-1" /> Refresh
            </Button>
          </div>
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground flex items-center gap-1">
                <DollarSign className="h-4 w-4" /> Total Commissions
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                ₦{stats?.totalCommissions?.toLocaleString() ?? "—"}
              </div>
              <p className="text-xs text-muted-foreground">Paid + Pending</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground flex items-center gap-1">
                <TrendingUp className="h-4 w-4" /> Avg Rate
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-500">
                {stats?.avgRate ?? "—"}%
              </div>
              <p className="text-xs text-muted-foreground">Across all tiers</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground flex items-center gap-1">
                <Users className="h-4 w-4" /> Active Agents
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stats?.activeAgents ?? "—"}
              </div>
              <p className="text-xs text-muted-foreground">With payouts</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground flex items-center gap-1">
                <Layers className="h-4 w-4" /> Commission Tiers
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats?.tiers ?? "—"}</div>
              <p className="text-xs text-muted-foreground">
                {stats?.splitRules ?? 0} split rules
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Calculate Tab */}
        {tab === "calculate" && (
          <Card>
            <CardHeader>
              <CardTitle>Commission Simulator</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="text-sm text-muted-foreground">
                    Agent ID
                  </label>
                  <Input
                    value={agentId}
                    onChange={e => setAgentId(e.target.value)}
                    placeholder="Agent ID"
                  />
                </div>
                <div>
                  <label className="text-sm text-muted-foreground">
                    Volume (₦)
                  </label>
                  <Input
                    value={volume}
                    onChange={e => setVolume(e.target.value)}
                    placeholder="Transaction volume"
                  />
                </div>
                <div>
                  <label className="text-sm text-muted-foreground">
                    Transaction Count
                  </label>
                  <Input
                    value={txCount}
                    onChange={e => setTxCount(e.target.value)}
                    placeholder="Number of transactions"
                  />
                </div>
              </div>
              <Button
                onClick={() =>
                  calcMutation.mutate({
                    agentId,
                    volume: Number(volume),
                    transactionCount: Number(txCount),
                  })
                }
                disabled={calcMutation.isPending}
              >
                {calcMutation.isPending
                  ? "Calculating..."
                  : "Calculate Commission"}
              </Button>
              {calcMutation.data && (
                <div className="mt-4 p-4 bg-muted rounded-lg space-y-2">
                  <h3 className="font-semibold">Calculation Result</h3>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                    <div>
                      <span className="text-muted-foreground">Tier:</span>{" "}
                      <strong>{(calcMutation.data as any).tier}</strong>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Rate:</span>{" "}
                      <strong>{(calcMutation.data as any).rate}%</strong>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Commission:</span>{" "}
                      <strong>
                        ₦
                        {(
                          calcMutation.data as any
                        ).commission?.toLocaleString()}
                      </strong>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Bonus:</span>{" "}
                      <strong>
                        ₦{(calcMutation.data as any).bonus?.toLocaleString()}
                      </strong>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Total:</span>{" "}
                      <strong className="text-green-500">
                        ₦{(calcMutation.data as any).total?.toLocaleString()}
                      </strong>
                    </div>
                    <div>
                      <span className="text-muted-foreground">Multiplier:</span>{" "}
                      <strong>{(calcMutation.data as any).multiplier}x</strong>
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Tiers Tab */}
        {tab === "tiers" && (
          <Card>
            <CardHeader>
              <CardTitle>Commission Tiers</CardTitle>
            </CardHeader>
            <CardContent>
              {tiersQuery.isLoading ? (
                <p className="text-muted-foreground">Loading tiers...</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left py-3 px-2">Tier</th>
                        <th className="text-left py-3 px-2">Type</th>
                        <th className="text-left py-3 px-2">Volume Range</th>
                        <th className="text-left py-3 px-2">Rate</th>
                        <th className="text-left py-3 px-2">Flat Fee</th>
                        <th className="text-left py-3 px-2">Bonus</th>
                        <th className="text-left py-3 px-2">Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {((tiersQuery.data as any) ?? []).map((tier: any) => (
                        <tr
                          key={tier.id}
                          className="border-b hover:bg-muted/50"
                        >
                          <td className="py-3 px-2 font-medium">{tier.name}</td>
                          <td className="py-3 px-2">
                            <Badge variant="outline">
                              {tier.transactionType}
                            </Badge>
                          </td>
                          <td className="py-3 px-2">
                            ₦{Number(tier.minVolume).toLocaleString()} — ₦
                            {Number(tier.maxVolume).toLocaleString()}
                          </td>
                          <td className="py-3 px-2 font-mono">{tier.rate}%</td>
                          <td className="py-3 px-2 font-mono">
                            ₦{tier.flatFee}
                          </td>
                          <td className="py-3 px-2 font-mono">
                            {tier.bonusRate}%
                          </td>
                          <td className="py-3 px-2">
                            <Badge
                              variant={
                                tier.isActive ? "default" : "destructive"
                              }
                            >
                              {tier.isActive ? "Active" : "Inactive"}
                            </Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Overview Tab */}
        {tab === "overview" && (
          <Card>
            <CardHeader>
              <CardTitle>Commission Summary</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="space-y-3">
                  <h3 className="font-semibold">Payout Status</h3>
                  <div className="text-sm space-y-1">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">
                        Pending Payouts
                      </span>
                      <span className="font-mono">
                        ₦{stats?.pendingPayouts?.toLocaleString() ?? "—"}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">
                        Paid This Month
                      </span>
                      <span className="font-mono text-green-500">
                        ₦{stats?.paidThisMonth?.toLocaleString() ?? "—"}
                      </span>
                    </div>
                  </div>
                </div>
                <div className="space-y-3">
                  <h3 className="font-semibold">Configuration</h3>
                  <div className="text-sm space-y-1">
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">
                        Active Tiers
                      </span>
                      <span>{stats?.tiers ?? "—"}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Split Rules</span>
                      <span>{stats?.splitRules ?? "—"}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">
                        Last Calculation
                      </span>
                      <span>
                        {stats?.lastCalculation
                          ? new Date(stats.lastCalculation).toLocaleString()
                          : "—"}
                      </span>
                    </div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardLayout>
  );
}
