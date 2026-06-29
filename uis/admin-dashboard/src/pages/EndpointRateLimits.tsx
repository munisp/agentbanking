import { useState } from "react";
import DashboardLayout from "@/components/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { trpc } from "@/lib/trpc";
import { toast } from "sonner";
import { Shield, Plus, Zap, Clock, Settings2 } from "lucide-react";

export default function EndpointRateLimits() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [newEndpoint, setNewEndpoint] = useState("");
  const [newMaxReqs, setNewMaxReqs] = useState("100");
  const [newWindowMs, setNewWindowMs] = useState("60000");

  // @ts-ignore Sprint 85
  const limits = trpc.sprint23.rateLimits.list.useQuery();
  const utils = trpc.useUtils();

  // @ts-ignore Sprint 85
  const setMutation = trpc.sprint23.rateLimits.set.useMutation({
    onSuccess: () => {
      // @ts-ignore Sprint 85
      utils.sprint23.rateLimits.list.invalidate();
      toast.success("Rate limit configured");
      setDialogOpen(false);
      setNewEndpoint("");
      setNewMaxReqs("100");
      setNewWindowMs("60000");
    },
  });

  const formatWindow = (ms: number) => {
    if (ms >= 3600000) return `${ms / 3600000}h`;
    if (ms >= 60000) return `${ms / 60000}m`;
    return `${ms / 1000}s`;
  };

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Shield className="w-6 h-6 text-yellow-400" />
              Endpoint Rate Limits
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Configure per-endpoint rate limiting for API protection
            </p>
          </div>
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button size="sm">
                <Plus className="w-4 h-4 mr-1" /> Add Limit
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Configure Rate Limit</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 pt-2">
                <Input
                  placeholder="Endpoint (e.g., transactions.create)"
                  value={newEndpoint}
                  onChange={e => setNewEndpoint(e.target.value)}
                />
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-xs text-muted-foreground">
                      Max Requests
                    </label>
                    <Input
                      type="number"
                      value={newMaxReqs}
                      onChange={e => setNewMaxReqs(e.target.value)}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground">
                      Window (ms)
                    </label>
                    <Input
                      type="number"
                      value={newWindowMs}
                      onChange={e => setNewWindowMs(e.target.value)}
                    />
                  </div>
                </div>
                <Button
                  className="w-full"
                  onClick={() =>
                    setMutation.mutate({
                      endpoint: newEndpoint,
                      maxRequests: parseInt(newMaxReqs),
                      windowMs: parseInt(newWindowMs),
                    })
                  }
                  disabled={!newEndpoint}
                >
                  Save Rate Limit
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="border-blue-500/30">
            <CardContent className="pt-6 text-center">
              <Settings2 className="w-8 h-8 mx-auto text-blue-400 mb-2" />
              <p className="text-2xl font-bold">{limits.data?.length ?? 0}</p>
              <p className="text-sm text-muted-foreground">
                Configured Endpoints
              </p>
            </CardContent>
          </Card>
          <Card className="border-green-500/30">
            <CardContent className="pt-6 text-center">
              <Zap className="w-8 h-8 mx-auto text-green-400 mb-2" />
              <p className="text-2xl font-bold">
                {limits.data?.reduce(
                  (sum: any, l: any) => sum + l.maxRequests,
                  0
                ) ?? 0}
              </p>
              <p className="text-sm text-muted-foreground">
                Total Capacity (req/window)
              </p>
            </CardContent>
          </Card>
          <Card className="border-purple-500/30">
            <CardContent className="pt-6 text-center">
              <Clock className="w-8 h-8 mx-auto text-purple-400 mb-2" />
              <p className="text-2xl font-bold">
                {limits.data?.reduce(
                  (sum: any, l: any) => sum + l.currentCount,
                  0
                ) ?? 0}
              </p>
              <p className="text-sm text-muted-foreground">Current Usage</p>
            </CardContent>
          </Card>
        </div>

        {/* Rate Limit Table */}
        <Card>
          <CardHeader>
            <CardTitle>Endpoint Configuration</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-2 px-3">Endpoint</th>
                    <th className="text-right py-2 px-3">Max Requests</th>
                    <th className="text-right py-2 px-3">Window</th>
                    <th className="text-right py-2 px-3">Current Count</th>
                    <th className="text-center py-2 px-3">Utilization</th>
                    <th className="text-right py-2 px-3">Last Reset</th>
                  </tr>
                </thead>
                <tbody>
                  {limits.data?.map((limit: any) => {
                    const utilization =
                      limit.maxRequests > 0
                        ? (limit.currentCount / limit.maxRequests) * 100
                        : 0;
                    return (
                      <tr
                        key={limit.endpoint}
                        className="border-b border-border/50 hover:bg-muted/30"
                      >
                        <td className="py-2 px-3 font-mono text-xs">
                          {limit.endpoint}
                        </td>
                        <td className="text-right py-2 px-3">
                          {limit.maxRequests}
                        </td>
                        <td className="text-right py-2 px-3">
                          {formatWindow(limit.windowMs)}
                        </td>
                        <td className="text-right py-2 px-3">
                          {limit.currentCount}
                        </td>
                        <td className="text-center py-2 px-3">
                          <Badge
                            variant={
                              utilization > 80
                                ? "destructive"
                                : utilization > 50
                                  ? "secondary"
                                  : "outline"
                            }
                          >
                            {utilization.toFixed(0)}%
                          </Badge>
                        </td>
                        <td className="text-right py-2 px-3 text-xs text-muted-foreground">
                          {new Date(limit.lastReset).toLocaleTimeString()}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
