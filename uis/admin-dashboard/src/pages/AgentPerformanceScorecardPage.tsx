// @ts-nocheck
import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Search, TrendingUp, Award, Star } from "lucide-react";

export default function AgentPerformanceScorecardPage() {
  const [search, setSearch] = useState("");
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const { data, isLoading } = trpc.agentPerformanceScorecard.list.useQuery();
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const agents = (data?.agents || []).filter(
    (a: any) => !search || a.name?.toLowerCase().includes(search.toLowerCase())
  );

  const getScoreColor = (score: number) =>
    score >= 80
      ? "text-green-600"
      : score >= 60
        ? "text-yellow-600"
        : "text-red-600";
  const getScoreBg = (score: number) =>
    score >= 80 ? "bg-green-100" : score >= 60 ? "bg-yellow-100" : "bg-red-100";

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <Award className="w-6 h-6" /> Agent Performance Scorecard
        </h1>
        <p className="text-muted-foreground mt-1">
          Track agent KPIs, transaction volumes, and commission performance
        </p>
      </div>
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4 text-center">
            <p className="text-2xl font-bold">
              {data?.summary?.totalAgents || 0}
            </p>
            <p className="text-sm text-muted-foreground">Total Agents</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 text-center">
            <p className="text-2xl font-bold text-green-600">
              {data?.summary?.topPerformers || 0}
            </p>
            <p className="text-sm text-muted-foreground">Top Performers</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 text-center">
            <p className="text-2xl font-bold text-yellow-600">
              {data?.summary?.avgScore || 0}%
            </p>
            <p className="text-sm text-muted-foreground">Avg Score</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4 text-center">
            <p className="text-2xl font-bold">
              ${(data?.summary?.totalCommission || 0).toLocaleString()}
            </p>
            <p className="text-sm text-muted-foreground">Total Commission</p>
          </CardContent>
        </Card>
      </div>
      <div className="flex items-center gap-2">
        <Search className="w-4 h-4" />
        <Input
          placeholder="Search agents..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="max-w-sm"
        />
      </div>
      {isLoading ? (
        <div className="text-center py-8">Loading...</div>
      ) : (
        <div className="grid gap-4">
          {agents.map((agent: any, i: number) => (
            <Card key={i}>
              <CardContent className="flex items-center justify-between py-4">
                <div className="flex items-center gap-4">
                  <div
                    className={`w-12 h-12 rounded-full flex items-center justify-center ${getScoreBg(agent.score)}`}
                  >
                    <span
                      className={`text-lg font-bold ${getScoreColor(agent.score)}`}
                    >
                      {agent.score}
                    </span>
                  </div>
                  <div>
                    <p className="font-medium">{agent.name}</p>
                    <p className="text-sm text-muted-foreground">
                      {agent.territory} • {agent.role}
                    </p>
                    <div className="flex gap-4 mt-1 text-xs text-muted-foreground">
                      <span>
                        <TrendingUp className="w-3 h-3 inline mr-1" />
                        {agent.txnCount} txns
                      </span>
                      <span>
                        <Star className="w-3 h-3 inline mr-1" />$
                        {agent.commission?.toLocaleString()} earned
                      </span>
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="w-32 bg-gray-200 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full ${agent.score >= 80 ? "bg-green-500" : agent.score >= 60 ? "bg-yellow-500" : "bg-red-500"}`}
                      style={{ width: `${agent.score}%` }}
                    />
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    {agent.score >= 80
                      ? "Excellent"
                      : agent.score >= 60
                        ? "Good"
                        : "Needs Improvement"}
                  </p>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
