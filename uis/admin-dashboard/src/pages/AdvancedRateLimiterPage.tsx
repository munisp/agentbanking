import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import DashboardLayout from "@/components/DashboardLayout";

export default function AdvancedRateLimiterPage() {
  const { data, isLoading, refetch } =
    trpc.advancedRateLimiter.dashboard.useQuery();
  const toggleRule = trpc.advancedRateLimiter.toggleRule.useMutation({
    onSuccess: () => {
      refetch();
      toast("Rule toggled");
    },
  });
  const blocked = trpc.advancedRateLimiter.getBlockedIps.useQuery();

  if (isLoading)
    return (
      <DashboardLayout>
        <div className="p-8 text-center animate-pulse">
          Loading rate limiter...
        </div>
      </DashboardLayout>
    );
  const d = data as any;
  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Advanced Rate Limiter</h1>
            <p className="text-muted-foreground">
              IP-based rate limiting with algorithm selection
            </p>
          </div>
          <Button variant="outline" onClick={() => refetch()}>
            Refresh
          </Button>
        </div>
        <div className="grid grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="text-3xl font-bold">{d?.totalRules ?? 0}</div>
              <p className="text-sm text-muted-foreground">Total Rules</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-3xl font-bold text-green-500">
                {d?.algorithms?.length ?? 0}
              </div>
              <p className="text-sm text-muted-foreground">Algorithms</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-3xl font-bold text-red-500">
                {(blocked.data as any)?.length ?? 0}
              </div>
              <p className="text-sm text-muted-foreground">Blocked IPs</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-3xl font-bold text-amber-500">
                {d?.topBlocked?.length ?? 0}
              </div>
              <p className="text-sm text-muted-foreground">Top Offenders</p>
            </CardContent>
          </Card>
        </div>
        <Card>
          <CardHeader>
            <CardTitle>Rate Limit Rules</CardTitle>
          </CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left">
                  <th className="p-3">Rule</th>
                  <th className="p-3">Algorithm</th>
                  <th className="p-3">Window</th>
                  <th className="p-3">Max Requests</th>
                  <th className="p-3">Status</th>
                  <th className="p-3">Action</th>
                </tr>
              </thead>
              <tbody>
                {(d?.rules ?? []).map((r: any, i: number) => (
                  <tr key={i} className="border-b hover:bg-muted/50">
                    <td className="p-3 font-medium">
                      {r.name ?? `Rule ${i + 1}`}
                    </td>
                    <td className="p-3">
                      <Badge variant="outline">
                        {r.algorithm ?? "sliding-window"}
                      </Badge>
                    </td>
                    <td className="p-3">
                      {r.windowMs ? `${r.windowMs / 1000}s` : "60s"}
                    </td>
                    <td className="p-3">{r.maxRequests ?? 100}</td>
                    <td className="p-3">
                      <Badge
                        className={
                          r.enabled !== false ? "bg-green-500" : "bg-gray-400"
                        }
                      >
                        {r.enabled !== false ? "Active" : "Disabled"}
                      </Badge>
                    </td>
                    <td className="p-3">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          toggleRule.mutate({
                            ruleId: r.id ?? `rule-${i}`,
                            enabled: r.enabled === false,
                          })
                        }
                      >
                        {r.enabled !== false ? "Disable" : "Enable"}
                      </Button>
                    </td>
                  </tr>
                ))}
                {(!d?.rules || d.rules.length === 0) && (
                  <tr>
                    <td
                      colSpan={6}
                      className="p-8 text-center text-muted-foreground"
                    >
                      No rules configured
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Blocked IPs</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-2">
              {((blocked.data as any) ?? [])
                .slice(0, 20)
                .map((ip: any, i: number) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-2 bg-muted rounded"
                  >
                    <span className="font-mono text-sm">{ip.ip ?? ip}</span>
                    <Badge variant="destructive">{ip.count ?? 0} hits</Badge>
                  </div>
                ))}
              {(!blocked.data || (blocked.data as any).length === 0) && (
                <p className="text-muted-foreground col-span-2 text-center py-4">
                  No blocked IPs
                </p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
