// @ts-nocheck
import DashboardLayout from "@/components/DashboardLayout";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import {
    Activity,
    AlertTriangle,
    ArrowUpRight,
    Brain,
    CheckCircle,
    RefreshCw,
    Shield,
    TrendingDown,
    Users,
} from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

// NOTE: The predictive churn backend is not reachable from this dashboard
// (the tRPC client in @/lib/trpc is a migration stub and no REST endpoint
// for churn analytics exists). This page fails loud: it renders an explicit
// unavailable state instead of fabricated "0%" KPIs or fake success toasts.
const CHURN_UNAVAILABLE_MESSAGE =
  "Churn analytics are currently unavailable — the predictive churn service is not connected.";

export default function PredictiveAgentChurn() {
  const [selectedRisk, setSelectedRisk] = useState<string>("all");

  const unavailableError = new Error(CHURN_UNAVAILABLE_MESSAGE);
  const summary = {
    data: null,
    isLoading: false,
    error: unavailableError,
    refetch: () => {},
  };
  const atRisk = {
    data: null,
    isLoading: false,
    error: unavailableError,
    refetch: () => {},
  };
  const unavailable = true;

  const riskColors: Record<string, string> = {
    critical: "bg-red-100 text-red-800",
    high: "bg-orange-100 text-orange-800",
    medium: "bg-amber-100 text-amber-800",
    low: "bg-green-100 text-green-800",
  };

  const filteredAgents = (atRisk.data?.agents || []).filter(
    (a: any) => selectedRisk === "all" || a.riskLevel === selectedRisk
  );

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Brain className="h-6 w-6 text-purple-600" />
              Predictive Agent Churn
            </h1>
            <p className="text-muted-foreground">
              AI-powered churn prediction and intervention
            </p>
          </div>
          <Button
            onClick={() => toast.error(CHURN_UNAVAILABLE_MESSAGE)}
            disabled={summary.isLoading}
          >
            <RefreshCw
              className={`h-4 w-4 mr-2 ${summary.isLoading ? "animate-spin" : ""}`}
            />
            Run Churn Analysis
          </Button>
        </div>

        <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          {CHURN_UNAVAILABLE_MESSAGE}
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground flex items-center gap-2">
                <TrendingDown className="h-4 w-4" /> Churn Rate
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold text-red-600">
                {summary.data?.churnRate != null
                  ? `${summary.data.churnRate}%`
                  : "—"}
              </p>
              <p className="text-xs text-muted-foreground">
                Predicted 30-day churn
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground flex items-center gap-2">
                <Shield className="h-4 w-4" /> Retention
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold text-green-600">
                {summary.data?.retentionRate != null
                  ? `${summary.data.retentionRate}%`
                  : "—"}
              </p>
              <p className="text-xs text-muted-foreground">
                Expected retention rate
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground flex items-center gap-2">
                <AlertTriangle className="h-4 w-4" /> At-Risk Agents
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold text-amber-600">
                {summary.data?.atRiskCount ?? "—"}
              </p>
              <p className="text-xs text-muted-foreground">
                Require intervention
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground flex items-center gap-2">
                <Activity className="h-4 w-4" /> Model Accuracy
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">
                {summary.data?.modelAccuracy != null
                  ? `${summary.data.modelAccuracy}%`
                  : "—"}
              </p>
              <p className="text-xs text-muted-foreground">
                Prediction confidence
              </p>
            </CardContent>
          </Card>
        </div>

        {/* Risk Filter */}
        <div className="flex gap-2">
          {["all", "critical", "high", "medium", "low"].map(risk => (
            <Button
              key={risk}
              variant={selectedRisk === risk ? "default" : "outline"}
              size="sm"
              onClick={() => setSelectedRisk(risk)}
            >
              {risk.charAt(0).toUpperCase() + risk.slice(1)}
            </Button>
          ))}
        </div>

        {/* At-Risk Agents Table */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Users className="h-5 w-5" /> At-Risk Agents
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Agent</TableHead>
                  <TableHead>Churn Risk</TableHead>
                  <TableHead>Risk Level</TableHead>
                  <TableHead>Key Factors</TableHead>
                  <TableHead>Recommended Action</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredAgents.map((agent: any) => (
                  <TableRow key={agent.id}>
                    <TableCell>
                      <div>
                        <p className="font-medium">{agent.name}</p>
                        <p className="text-xs text-muted-foreground">
                          {agent.code}
                        </p>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <div className="w-16 bg-muted rounded-full h-2">
                          <div
                            className={`h-full rounded-full ${
                              agent.churnRisk >= 70
                                ? "bg-red-500"
                                : agent.churnRisk >= 50
                                  ? "bg-orange-500"
                                  : agent.churnRisk >= 30
                                    ? "bg-amber-500"
                                    : "bg-green-500"
                            }`}
                            style={{ width: `${agent.churnRisk}%` }}
                          />
                        </div>
                        <span className="text-sm font-medium">
                          {agent.churnRisk}%
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge className={riskColors[agent.riskLevel] || ""}>
                        {agent.riskLevel}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {agent.factors?.slice(0, 2).map((f: any, i: number) => (
                          <Badge key={i} variant="outline" className="text-xs">
                            {f}
                          </Badge>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground max-w-[200px] truncate">
                      {agent.recommendedAction}
                    </TableCell>
                    <TableCell>
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={unavailable}
                        title={
                          unavailable ? CHURN_UNAVAILABLE_MESSAGE : undefined
                        }
                      >
                        <ArrowUpRight className="h-3 w-3 mr-1" /> Send
                        Intervention
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
                {filteredAgents.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center py-8">
                      {atRisk.isLoading ? (
                        "Loading at-risk agents..."
                      ) : (
                        <span className="text-muted-foreground">
                          {CHURN_UNAVAILABLE_MESSAGE}
                        </span>
                      )}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* Intervention Templates */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CheckCircle className="h-5 w-5" /> Intervention Templates
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {[
                {
                  title: "Re-engagement Call",
                  description: "Schedule a call to understand challenges",
                  trigger: "Activity drop > 30%",
                },
                {
                  title: "Float Support",
                  description: "Offer additional float or credit line",
                  trigger: "Float issues detected",
                },
                {
                  title: "Training Refresh",
                  description: "Invite to refresher training session",
                  trigger: "Error rate increase",
                },
              ].map((template, i) => (
                <div key={i} className="border rounded-lg p-4">
                  <h3 className="font-semibold">{template.title}</h3>
                  <p className="text-sm text-muted-foreground mt-1">
                    {template.description}
                  </p>
                  <p className="text-xs text-primary mt-2">
                    Trigger: {template.trigger}
                  </p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
