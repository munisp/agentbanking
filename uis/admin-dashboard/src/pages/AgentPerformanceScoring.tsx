import { useState, useMemo } from "react";
import DashboardLayout from "@/components/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Trophy,
  Star,
  TrendingUp,
  Users,
  Target,
  Award,
  Medal,
} from "lucide-react";

// No live scoring API is wired to this page yet — render an honest empty
// state instead of fabricated agent rows.
const mockAgents: any[] = [];

const tierColors: Record<string, string> = {
  platinum: "text-purple-400",
  gold: "text-yellow-400",
  silver: "text-gray-300",
  bronze: "text-orange-400",
};

const tierBg: Record<string, string> = {
  platinum: "border-purple-500/30",
  gold: "border-yellow-500/30",
  silver: "border-gray-500/30",
  bronze: "border-orange-500/30",
};

export default function AgentPerformanceScoring() {
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);

  const selected = useMemo(
    () => mockAgents.find((a: any) => a.agentId === selectedAgent),
    [selectedAgent]
  );

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Trophy className="w-6 h-6 text-yellow-400" />
            Agent Performance Scoring
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            KPI-based scoring dashboard for agent performance evaluation
          </p>
        </div>

        {/* Tier Summary */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {(["platinum", "gold", "silver", "bronze"] as const).map(
            (tier: any) => (
              <Card key={tier} className={tierBg[tier]}>
                <CardContent className="pt-4 text-center">
                  <Medal
                    className={`w-6 h-6 mx-auto mb-1 ${tierColors[tier]}`}
                  />
                  <p className="text-xl font-bold">
                    {mockAgents.filter((a: any) => a.tier === tier).length}
                  </p>
                  <p className="text-xs text-muted-foreground capitalize">
                    {tier} Agents
                  </p>
                </CardContent>
              </Card>
            )
          )}
        </div>

        {/* Leaderboard */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Award className="w-5 h-5" /> Agent Leaderboard
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {mockAgents.length === 0 && (
                <p className="py-8 text-center text-sm text-muted-foreground">
                  No performance data available.
                </p>
              )}
              {mockAgents.map((agent, idx) => (
                <div
                  key={agent.agentId}
                  className={`flex items-center gap-4 p-3 rounded-lg cursor-pointer transition-colors ${
                    selectedAgent === agent.agentId
                      ? "bg-muted"
                      : "hover:bg-muted/50"
                  }`}
                  onClick={() =>
                    setSelectedAgent(
                      agent.agentId === selectedAgent ? null : agent.agentId
                    )
                  }
                >
                  <div className="text-2xl font-bold text-muted-foreground w-8 text-center">
                    #{idx + 1}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{agent.name}</span>
                      <Badge variant="outline" className="text-xs">
                        {agent.agentCode}
                      </Badge>
                      <Badge
                        className={`text-xs capitalize ${tierColors[agent.tier]}`}
                        variant="outline"
                      >
                        {agent.tier}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <Progress
                        value={agent.overallScore}
                        className="h-2 flex-1"
                      />
                      <span className="text-sm font-mono">
                        {agent.overallScore.toFixed(1)}
                      </span>
                    </div>
                  </div>
                  <div className="text-right">
                    <div
                      className={`flex items-center gap-1 text-xs ${
                        agent.trend === "improving"
                          ? "text-green-400"
                          : agent.trend === "declining"
                            ? "text-red-400"
                            : "text-gray-400"
                      }`}
                    >
                      {agent.trend === "improving" ? (
                        <TrendingUp className="w-3 h-3" />
                      ) : agent.trend === "declining" ? (
                        <TrendingUp className="w-3 h-3 rotate-180" />
                      ) : null}
                      {agent.trend}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Selected Agent Detail */}
        {selected && (
          <Card>
            <CardHeader>
              <CardTitle>KPI Breakdown — {selected.name}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {Object.entries(selected.breakdown).map(([key, kpi]: [string, any]) => (
                  <div key={key} className="p-3 rounded-lg bg-muted/30">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium capitalize">
                        {key.replace(/([A-Z])/g, " $1").trim()}
                      </span>
                      <span className="text-xs text-muted-foreground">
                        Weight: {(kpi.weight * 100).toFixed(0)}%
                      </span>
                    </div>
                    <Progress value={kpi.score} className="h-2 mb-1" />
                    <div className="flex justify-between text-xs text-muted-foreground">
                      <span>Score: {kpi.score.toFixed(1)}</span>
                      <span>
                        Raw:{" "}
                        {typeof kpi.raw === "number"
                          ? kpi.raw.toLocaleString()
                          : kpi.raw}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardLayout>
  );
}
