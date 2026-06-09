import { useState, useMemo } from "react";
import DashboardLayout from "@/components/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { trpc } from "@/lib/trpc";

/**
 * Admin Device Analytics Dashboard
 *
 * Shows:
 * - Problematic devices (consistently failing liveness checks)
 * - Success rates per device model
 * - Active cooldowns (locked-out users)
 * - Threshold override controls
 */
export default function AdminLivenessDeviceAnalytics() {
  const [search, setSearch] = useState("");
  const [minAttempts, setMinAttempts] = useState(5);
  const [maxSuccessRate, setMaxSuccessRate] = useState(0.5);

  // Fetch data from KYC router
  const deviceHistories = trpc.kyc.adminDeviceHistories.useQuery();
  const problematicDevices = trpc.kyc.adminProblematicDevices.useQuery({
    minAttempts,
    maxSuccessRate,
  });
  const cooldowns = trpc.kyc.adminGetCooldowns.useQuery();
  const clearCooldownMutation = trpc.kyc.adminClearCooldown.useMutation({
    onSuccess: () => {
      toast.success("Cooldown cleared successfully");
      cooldowns.refetch();
    },
    onError: (e: any) => toast.error(e.message),
  });

  // Aggregate stats
  const stats = useMemo(() => {
    const devices = deviceHistories.data?.devices || [];
    const totalDevices = devices.length;
    const totalAttempts = devices.reduce(
      (sum, d) => sum + (d.attempts?.length || 0),
      0
    );
    const avgSuccessRate =
      totalDevices > 0
        ? devices.reduce((sum, d) => sum + (d.successRate || 0), 0) /
          totalDevices
        : 0;
    const problematicCount = (problematicDevices.data?.devices || []).length;
    const activeLockouts = (cooldowns.data?.cooldowns || []).filter(
      c => c.lockedUntil
    ).length;

    return {
      totalDevices,
      totalAttempts,
      avgSuccessRate,
      problematicCount,
      activeLockouts,
    };
  }, [deviceHistories.data, problematicDevices.data, cooldowns.data]);

  // Filter devices by search
  const filteredDevices = useMemo(() => {
    const devices = deviceHistories.data?.devices || [];
    if (!search) return devices;
    const q = search.toLowerCase();
    return devices.filter(
      (d: any) =>
        (d.deviceModel || "").toLowerCase().includes(q) ||
        (d.fingerprint || "").toLowerCase().includes(q) ||
        (d.osVersion || "").toLowerCase().includes(q)
    );
  }, [deviceHistories.data, search]);

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Liveness Device Analytics</h1>
            <p className="text-muted-foreground">
              Monitor device performance, identify problematic hardware, and
              manage lockouts
            </p>
          </div>
          <div className="flex gap-2">
            <Input
              placeholder="Search devices..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-64"
            />
            <Button
              onClick={() => {
                deviceHistories.refetch();
                problematicDevices.refetch();
                cooldowns.refetch();
                toast.info("Refreshing data...");
              }}
              variant="outline"
            >
              Refresh
            </Button>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Total Devices
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.totalDevices}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Total Attempts
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.totalAttempts}</div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Avg Success Rate
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {(stats.avgSuccessRate * 100).toFixed(1)}%
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Problematic Devices
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-red-500">
                {stats.problematicCount}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Active Lockouts
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-amber-500">
                {stats.activeLockouts}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Active Cooldowns / Lockouts */}
        {(cooldowns.data?.cooldowns || []).length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                Active Lockouts
                <Badge variant="destructive">
                  {(cooldowns.data?.cooldowns || []).length}
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-2 px-3">User ID</th>
                      <th className="text-left py-2 px-3">Failures</th>
                      <th className="text-left py-2 px-3">Locked Until</th>
                      <th className="text-left py-2 px-3">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(cooldowns.data?.cooldowns || []).map(
                      (c: any, i: number) => (
                        <tr key={i} className="border-b hover:bg-muted/50">
                          <td className="py-2 px-3 font-mono text-xs">
                            {c.userId}
                          </td>
                          <td className="py-2 px-3">
                            <Badge variant="destructive">{c.failures}</Badge>
                          </td>
                          <td className="py-2 px-3 text-xs">
                            {c.lockedUntil
                              ? new Date(c.lockedUntil).toLocaleString()
                              : "—"}
                          </td>
                          <td className="py-2 px-3">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() =>
                                clearCooldownMutation.mutate({
                                  userId: c.userId,
                                })
                              }
                              disabled={clearCooldownMutation.isPending}
                            >
                              Clear Lockout
                            </Button>
                          </td>
                        </tr>
                      )
                    )}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Problematic Devices */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                Problematic Devices
                <Badge variant="secondary">
                  {(problematicDevices.data?.devices || []).length}
                </Badge>
              </CardTitle>
              <div className="flex gap-2 items-center text-sm">
                <label className="text-muted-foreground">Min attempts:</label>
                <Input
                  type="number"
                  value={minAttempts}
                  onChange={e => setMinAttempts(Number(e.target.value))}
                  className="w-16 h-8"
                />
                <label className="text-muted-foreground">Max success:</label>
                <Input
                  type="number"
                  step="0.1"
                  value={maxSuccessRate}
                  onChange={e => setMaxSuccessRate(Number(e.target.value))}
                  className="w-16 h-8"
                />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {(problematicDevices.data?.devices || []).length === 0 ? (
              <p className="text-muted-foreground text-center py-8">
                No problematic devices found with current filters.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-2 px-3">Device</th>
                      <th className="text-left py-2 px-3">Fingerprint</th>
                      <th className="text-left py-2 px-3">Attempts</th>
                      <th className="text-left py-2 px-3">Success Rate</th>
                      <th className="text-left py-2 px-3">Avg Score</th>
                      <th className="text-left py-2 px-3">Recommendation</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(problematicDevices.data?.devices || []).map(
                      (d: any, i: number) => (
                        <tr key={i} className="border-b hover:bg-muted/50">
                          <td className="py-2 px-3 font-medium">
                            {d.deviceModel || "Unknown"}
                          </td>
                          <td className="py-2 px-3 font-mono text-xs">
                            {(d.fingerprint || "").slice(0, 12)}...
                          </td>
                          <td className="py-2 px-3">{d.totalAttempts}</td>
                          <td className="py-2 px-3">
                            <Badge
                              variant={
                                d.successRate < 0.3
                                  ? "destructive"
                                  : "secondary"
                              }
                            >
                              {(d.successRate * 100).toFixed(0)}%
                            </Badge>
                          </td>
                          <td className="py-2 px-3">
                            {(d.avgScore || 0).toFixed(2)}
                          </td>
                          <td className="py-2 px-3">
                            <Badge variant="outline">
                              {d.successRate < 0.2
                                ? "Force Passive"
                                : "Relax Thresholds"}
                            </Badge>
                          </td>
                        </tr>
                      )
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        {/* All Device Histories */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              All Device Histories
              <Badge variant="secondary">{filteredDevices.length}</Badge>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {filteredDevices.length === 0 ? (
              <p className="text-muted-foreground text-center py-8">
                No device histories recorded yet.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b">
                      <th className="text-left py-2 px-3">Device Model</th>
                      <th className="text-left py-2 px-3">OS</th>
                      <th className="text-left py-2 px-3">Camera</th>
                      <th className="text-left py-2 px-3">Attempts</th>
                      <th className="text-left py-2 px-3">Success Rate</th>
                      <th className="text-left py-2 px-3">Avg Score</th>
                      <th className="text-left py-2 px-3">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredDevices.slice(0, 50).map((d: any, i: number) => (
                      <tr key={i} className="border-b hover:bg-muted/50">
                        <td className="py-2 px-3 font-medium">
                          {d.deviceModel || "Unknown"}
                        </td>
                        <td className="py-2 px-3 text-xs">
                          {d.osVersion || "—"}
                        </td>
                        <td className="py-2 px-3 text-xs">
                          {d.cameraWidth && d.cameraHeight
                            ? `${d.cameraWidth}×${d.cameraHeight}`
                            : "—"}
                        </td>
                        <td className="py-2 px-3">{d.attempts?.length || 0}</td>
                        <td className="py-2 px-3">
                          <div className="flex items-center gap-2">
                            <div className="w-16 h-2 bg-muted rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full ${
                                  (d.successRate || 0) > 0.7
                                    ? "bg-green-500"
                                    : (d.successRate || 0) > 0.4
                                      ? "bg-amber-500"
                                      : "bg-red-500"
                                }`}
                                style={{
                                  width: `${(d.successRate || 0) * 100}%`,
                                }}
                              />
                            </div>
                            <span className="text-xs">
                              {((d.successRate || 0) * 100).toFixed(0)}%
                            </span>
                          </div>
                        </td>
                        <td className="py-2 px-3">
                          {(d.avgScore || 0).toFixed(2)}
                        </td>
                        <td className="py-2 px-3">
                          <Badge
                            variant={
                              (d.successRate || 0) > 0.7
                                ? "default"
                                : (d.successRate || 0) > 0.4
                                  ? "secondary"
                                  : "destructive"
                            }
                          >
                            {(d.successRate || 0) > 0.7
                              ? "Healthy"
                              : (d.successRate || 0) > 0.4
                                ? "Marginal"
                                : "Failing"}
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
      </div>
    </DashboardLayout>
  );
}
