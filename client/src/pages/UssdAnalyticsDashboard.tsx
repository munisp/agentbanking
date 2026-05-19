// @ts-nocheck
// UssdAnalyticsDashboard — Sprint 77
import { trpc } from "@/lib/trpc";
import DashboardLayout from "@/components/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Phone, TrendingUp, AlertTriangle, BarChart3 } from "lucide-react";

export default function UssdAnalyticsDashboard() {
  const summary = trpc.ussdAnalytics.getSummary.useQuery();

  return (
    <DashboardLayout>
      <div className="container py-6 space-y-6">
        <div className="flex items-center gap-3">
          <Phone className="h-8 w-8 text-purple-500" />
          <div>
            <h1 className="text-2xl font-bold">USSD Analytics</h1>
            <p className="text-muted-foreground">
              Session completion rates, drop-off analysis, carrier performance
            </p>
          </div>
        </div>

        {summary.data && (
          <>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <Card>
                <CardContent className="pt-6 text-center">
                  <TrendingUp className="h-8 w-8 text-blue-500 mx-auto" />
                  <p className="text-3xl font-bold mt-2">
                    {summary.data.totalSessions.toLocaleString()}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Total Sessions
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6 text-center">
                  <p className="text-3xl font-bold text-green-500">
                    {summary.data.completionRate}%
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Completion Rate
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6 text-center">
                  <p className="text-3xl font-bold text-yellow-500">
                    {summary.data.avgDurationMs}ms
                  </p>
                  <p className="text-sm text-muted-foreground">Avg Duration</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6 text-center">
                  <p className="text-3xl font-bold text-blue-500">
                    {summary.data.completedSessions.toLocaleString()}
                  </p>
                  <p className="text-sm text-muted-foreground">Completed</p>
                </CardContent>
              </Card>
            </div>

            {/* Drop-off Points */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <AlertTriangle className="h-5 w-5 text-yellow-500" /> Drop-off
                  Points
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {Object.entries(summary.data.dropOffPoints).map(
                    ([step, count]: any) => (
                      <div
                        key={step}
                        className="flex items-center justify-between p-3 rounded-lg bg-muted/50"
                      >
                        <span className="font-medium">{step}</span>
                        <span className="font-bold text-red-500">{count}</span>
                      </div>
                    )
                  )}
                </div>
              </CardContent>
            </Card>

            {/* By Type */}
            <Card>
              <CardHeader>
                <CardTitle>Sessions by Transaction Type</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {Object.entries(summary.data.completionByType).map(
                    ([type, stats]: any) => (
                      <div
                        key={type}
                        className="flex items-center justify-between p-3 rounded-lg bg-muted/50"
                      >
                        <Badge variant="outline">{type}</Badge>
                        <div className="flex items-center gap-4">
                          <span className="text-sm">
                            {stats.started} started
                          </span>
                          <span className="text-sm text-green-500">
                            {stats.completed} completed
                          </span>
                          <span className="text-sm font-bold">
                            {stats.started > 0
                              ? (
                                  (stats.completed / stats.started) *
                                  100
                                ).toFixed(1)
                              : 0}
                            %
                          </span>
                        </div>
                      </div>
                    )
                  )}
                </div>
              </CardContent>
            </Card>

            {/* Carrier Stats */}
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="h-5 w-5" /> Performance by Carrier
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left p-2">Carrier</th>
                        <th className="text-right p-2">Sessions</th>
                        <th className="text-right p-2">Completed</th>
                        <th className="text-right p-2">Rate</th>
                        <th className="text-right p-2">Avg Duration</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(summary.data.carrierStats).map(
                        ([carrier, stats]: any) => (
                          <tr
                            key={carrier}
                            className="border-b hover:bg-muted/30"
                          >
                            <td className="p-2 font-medium">{carrier}</td>
                            <td className="p-2 text-right">{stats.sessions}</td>
                            <td className="p-2 text-right">
                              {stats.completed}
                            </td>
                            <td className="p-2 text-right">
                              <Badge
                                variant={
                                  stats.completionRate >= 90
                                    ? "default"
                                    : stats.completionRate >= 75
                                      ? "secondary"
                                      : "destructive"
                                }
                              >
                                {stats.completionRate}%
                              </Badge>
                            </td>
                            <td className="p-2 text-right">
                              {stats.avgDurationMs}ms
                            </td>
                          </tr>
                        )
                      )}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </DashboardLayout>
  );
}
