import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import DashboardLayout from "@/components/DashboardLayout";

export default function AgentScorecardPage() {
  const [agentId, setAgentId] = useState("");
  // @ts-ignore Sprint 85
  const { data, isLoading } = trpc.agentScorecard.dashboard.useQuery();
  // @ts-ignore Sprint 85
  const agentScore = trpc.agentScorecard.getAgentScore.useQuery(
    { agentId: agentId || "AGT-001" },
    { enabled: !!agentId }
  );

  if (isLoading)
    return (
      <DashboardLayout>
        <div className="p-8 text-center animate-pulse">
          Loading scorecards...
        </div>
      </DashboardLayout>
    );
  const d = data as any;
  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Agent Scorecard</h1>
          <p className="text-muted-foreground">
            Performance tracking and incentive management
          </p>
        </div>
        <div className="grid grid-cols-3 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="text-3xl font-bold">{d?.totalAgents ?? 0}</div>
              <p className="text-sm text-muted-foreground">Total Agents</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-3xl font-bold text-green-500">
                {d?.avgScore ?? 0}%
              </div>
              <p className="text-sm text-muted-foreground">Average Score</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-3xl font-bold text-amber-500">
                {d?.incentives?.length ?? 0}
              </div>
              <p className="text-sm text-muted-foreground">Active Incentives</p>
            </CardContent>
          </Card>
        </div>
        <Card>
          <CardHeader>
            <CardTitle>Leaderboard</CardTitle>
          </CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left">
                  <th className="p-3">#</th>
                  <th className="p-3">Agent</th>
                  <th className="p-3">Score</th>
                  <th className="p-3">Transactions</th>
                  <th className="p-3">Revenue</th>
                  <th className="p-3">Tier</th>
                </tr>
              </thead>
              <tbody>
                {(d?.leaderboard ?? []).map((a: any, i: number) => (
                  <tr key={i} className="border-b hover:bg-muted/50">
                    <td className="p-3 font-bold">{i + 1}</td>
                    <td className="p-3 font-medium">
                      {a.name ?? a.agentId ?? `Agent ${i + 1}`}
                    </td>
                    <td className="p-3">
                      <Badge
                        className={
                          a.score >= 80
                            ? "bg-green-500"
                            : a.score >= 60
                              ? "bg-amber-500"
                              : "bg-red-500"
                        }
                      >
                        {a.score ?? 0}%
                      </Badge>
                    </td>
                    <td className="p-3">
                      {(a.transactions ?? 0).toLocaleString()}
                    </td>
                    <td className="p-3">
                      ₦{(a.revenue ?? 0).toLocaleString()}
                    </td>
                    <td className="p-3">
                      <Badge variant="outline">{a.tier ?? "Bronze"}</Badge>
                    </td>
                  </tr>
                ))}
                {(!d?.leaderboard || d.leaderboard.length === 0) && (
                  <tr>
                    <td
                      colSpan={6}
                      className="p-8 text-center text-muted-foreground"
                    >
                      No leaderboard data
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Agent Lookup</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-2 mb-4">
              <Input
                placeholder="Enter Agent ID (e.g. AGT-001)"
                value={agentId}
                onChange={e => setAgentId(e.target.value)}
              />
              <Button onClick={() => setAgentId(agentId)}>Search</Button>
            </div>
            {agentScore.data && (
              <pre className="text-xs bg-muted p-4 rounded overflow-auto max-h-60">
                {JSON.stringify(agentScore.data, null, 2)}
              </pre>
            )}
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Performance Metrics</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              {(d?.metrics ?? []).map((m: any, i: number) => (
                <div
                  key={i}
                  className="flex items-center justify-between p-3 bg-muted rounded"
                >
                  <span className="font-medium">
                    {m.name ?? m.metric ?? `Metric ${i + 1}`}
                  </span>
                  <span className="text-lg font-bold">
                    {m.value ?? 0}
                    {m.unit ?? ""}
                  </span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
