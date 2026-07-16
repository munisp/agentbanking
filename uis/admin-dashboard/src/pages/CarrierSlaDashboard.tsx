// CarrierSlaDashboard — Sprint 77
// SLA monitoring: uptime, latency, packet loss per carrier per region
import { useState } from "react";
import { trpc } from "@/lib/trpc";
import DashboardLayout from "@/components/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Activity, CheckCircle, XCircle, Clock } from "lucide-react";

export default function CarrierSlaDashboard() {
  const targets = trpc.carrierSla.getStats.useQuery();
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const violations = trpc.carrierSla.getViolations.useQuery({ hours: 24 });
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const compliance = trpc.carrierSla.getComplianceReport.useQuery({
    period: "weekly",
  });

  return (
    <DashboardLayout>
      <div className="container py-6 space-y-6">
        <div className="flex items-center gap-3">
          <Activity className="h-8 w-8 text-blue-500" />
          <div>
            <h1 className="text-2xl font-bold">Carrier SLA Monitoring</h1>
            <p className="text-muted-foreground">
              Uptime, latency, and packet loss tracking per carrier
            </p>
          </div>
        </div>

        {/* SLA Targets */}
        {targets.data && (
          <Card>
            <CardHeader>
              <CardTitle>SLA Targets</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left p-2">Carrier</th>
                      <th className="text-left p-2">Country</th>
                      <th className="text-right p-2">Uptime Target</th>
                      <th className="text-right p-2">Max Latency</th>
                      <th className="text-right p-2">Max Packet Loss</th>
                      <th className="text-right p-2">Actual Uptime</th>
                      <th className="text-center p-2">Compliant</th>
                    </tr>
                  </thead>
                  <tbody>
                    {targets.data.map((t: any) => (
                      <tr
                        key={t.carrier}
                        className="border-b hover:bg-muted/30"
                      >
                        <td className="p-2 font-medium">{t.carrier}</td>
                        <td className="p-2">{t.country}</td>
                        <td className="p-2 text-right">{t.uptimeTarget}%</td>
                        <td className="p-2 text-right">{t.maxLatencyMs}ms</td>
                        <td className="p-2 text-right">
                          {t.maxPacketLossPct}%
                        </td>
                        <td
                          className="p-2 text-right font-bold"
                          style={{
                            color:
                              t.actualUptime >= t.uptimeTarget
                                ? "#22c55e"
                                : "#ef4444",
                          }}
                        >
                          {t.actualUptime}%
                        </td>
                        <td className="p-2 text-center">
                          {t.compliant ? (
                            <CheckCircle className="h-4 w-4 text-green-500 mx-auto" />
                          ) : (
                            <XCircle className="h-4 w-4 text-red-500 mx-auto" />
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Recent Violations */}
        {violations.data && violations.data.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <XCircle className="h-5 w-5 text-red-500" /> Recent Violations
                (24h)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {violations.data.map((v: any, i: number) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-3 rounded-lg bg-red-500/10"
                  >
                    <div>
                      <p className="font-medium">
                        {v.carrier} — {v.region}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {v.violation}
                      </p>
                    </div>
                    <div className="text-right">
                      <Badge variant="destructive">{v.severity}</Badge>
                      <p className="text-xs text-muted-foreground mt-1">
                        {v.timestamp}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Compliance Report */}
        {compliance.data && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Clock className="h-5 w-5" /> Weekly Compliance Report
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                <div className="text-center p-4 rounded-lg bg-muted/50">
                  <p className="text-3xl font-bold text-green-500">
                    {compliance.data.compliantCarriers}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Compliant Carriers
                  </p>
                </div>
                <div className="text-center p-4 rounded-lg bg-muted/50">
                  <p className="text-3xl font-bold text-red-500">
                    {compliance.data.nonCompliantCarriers}
                  </p>
                  <p className="text-sm text-muted-foreground">Non-Compliant</p>
                </div>
                <div className="text-center p-4 rounded-lg bg-muted/50">
                  <p className="text-3xl font-bold">
                    {compliance.data.overallScore}%
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Overall SLA Score
                  </p>
                </div>
              </div>
              <div className="space-y-2">
                {compliance.data.details.map((d: any, i: number) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-2 rounded bg-muted/30"
                  >
                    <span className="font-medium">{d.carrier}</span>
                    <div className="flex items-center gap-3">
                      <span className="text-sm">Uptime: {d.uptime}%</span>
                      <span className="text-sm">Latency: {d.avgLatency}ms</span>
                      <Badge variant={d.compliant ? "default" : "destructive"}>
                        {d.compliant ? "Pass" : "Fail"}
                      </Badge>
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
