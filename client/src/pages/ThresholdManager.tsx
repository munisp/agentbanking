import { useState } from "react";
import DashboardLayout from "@/components/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { trpc } from "@/lib/trpc";
import { toast } from "sonner";
import {
  Gauge,
  Plus,
  Trash2,
  AlertTriangle,
  CheckCircle,
  Activity,
} from "lucide-react";

export default function ThresholdManager() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [newLabel, setNewLabel] = useState("");
  const [newMetricKey, setNewMetricKey] = useState("");
  const [newOperator, setNewOperator] = useState<
    "gt" | "lt" | "gte" | "lte" | "eq"
  >("gt");
  const [newValue, setNewValue] = useState("");
  const [newSeverity, setNewSeverity] = useState<
    "critical" | "warning" | "info"
  >("warning");

  // @ts-ignore Sprint 85
  const thresholds = trpc.sprint23.thresholds.list.useQuery();
  // @ts-ignore Sprint 85
  const evaluation = trpc.sprint23.thresholds.evaluate.useQuery();
  const utils = trpc.useUtils();

  // @ts-ignore Sprint 85
  const createMutation = trpc.sprint23.thresholds.create.useMutation({
    onSuccess: () => {
      // @ts-ignore Sprint 85
      utils.sprint23.thresholds.list.invalidate();
      toast.success("Threshold created");
      setDialogOpen(false);
      setNewLabel("");
      setNewMetricKey("");
      setNewValue("");
    },
  });

  // @ts-ignore Sprint 85
  const updateMutation = trpc.sprint23.thresholds.update.useMutation({
    onSuccess: () => {
      // @ts-ignore Sprint 85
      utils.sprint23.thresholds.list.invalidate();
      toast.success("Threshold updated");
    },
  });

  // @ts-ignore Sprint 85
  const deleteMutation = trpc.sprint23.thresholds.delete.useMutation({
    onSuccess: () => {
      // @ts-ignore Sprint 85
      utils.sprint23.thresholds.list.invalidate();
      toast.success("Threshold deleted");
    },
  });

  const severityColor = (s: string) => {
    if (s === "critical") return "destructive";
    if (s === "warning") return "secondary";
    return "outline";
  };

  const operatorLabel: Record<string, string> = {
    gt: ">",
    lt: "<",
    gte: ">=",
    lte: "<=",
    eq: "=",
  };

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Gauge className="w-6 h-6 text-orange-400" />
              Threshold Manager
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Configure custom alert thresholds for system metrics
            </p>
          </div>
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button size="sm">
                <Plus className="w-4 h-4 mr-1" /> Add Threshold
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create New Threshold</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 pt-2">
                <Input
                  placeholder="Label (e.g., CPU > 90%)"
                  value={newLabel}
                  onChange={e => setNewLabel(e.target.value)}
                />
                <Input
                  placeholder="Metric Key (e.g., system.cpuAvgPercent)"
                  value={newMetricKey}
                  onChange={e => setNewMetricKey(e.target.value)}
                />
                <div className="grid grid-cols-2 gap-2">
                  <Select
                    value={newOperator}
                    onValueChange={v => setNewOperator(v as any)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="gt">Greater than (&gt;)</SelectItem>
                      <SelectItem value="lt">Less than (&lt;)</SelectItem>
                      <SelectItem value="gte">
                        Greater or equal (&gt;=)
                      </SelectItem>
                      <SelectItem value="lte">Less or equal (&lt;=)</SelectItem>
                      <SelectItem value="eq">Equal (=)</SelectItem>
                    </SelectContent>
                  </Select>
                  <Input
                    type="number"
                    placeholder="Value"
                    value={newValue}
                    onChange={e => setNewValue(e.target.value)}
                  />
                </div>
                <Select
                  value={newSeverity}
                  onValueChange={v => setNewSeverity(v as any)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="critical">Critical</SelectItem>
                    <SelectItem value="warning">Warning</SelectItem>
                    <SelectItem value="info">Info</SelectItem>
                  </SelectContent>
                </Select>
                <Button
                  className="w-full"
                  onClick={() =>
                    createMutation.mutate({
                      metricKey: newMetricKey,
                      label: newLabel,
                      operator: newOperator,
                      value: parseFloat(newValue),
                      severity: newSeverity,
                      enabled: true,
                    })
                  }
                  disabled={!newLabel || !newMetricKey || !newValue}
                >
                  Create Threshold
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>

        {/* Evaluation Summary */}
        {evaluation.data && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card className="border-green-500/30">
              <CardContent className="pt-6 text-center">
                <CheckCircle className="w-8 h-8 mx-auto text-green-400 mb-2" />
                <p className="text-2xl font-bold">
                  {evaluation.data.filter((e: any) => !e.triggered).length}
                </p>
                <p className="text-sm text-muted-foreground">Within Limits</p>
              </CardContent>
            </Card>
            <Card className="border-red-500/30">
              <CardContent className="pt-6 text-center">
                <AlertTriangle className="w-8 h-8 mx-auto text-red-400 mb-2" />
                <p className="text-2xl font-bold">
                  {evaluation.data.filter((e: any) => e.triggered).length}
                </p>
                <p className="text-sm text-muted-foreground">Breached</p>
              </CardContent>
            </Card>
            <Card className="border-blue-500/30">
              <CardContent className="pt-6 text-center">
                <Activity className="w-8 h-8 mx-auto text-blue-400 mb-2" />
                <p className="text-2xl font-bold">
                  {thresholds.data?.length ?? 0}
                </p>
                <p className="text-sm text-muted-foreground">
                  Total Thresholds
                </p>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Threshold List */}
        <Card>
          <CardHeader>
            <CardTitle>Configured Thresholds</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-2 px-3">Label</th>
                    <th className="text-left py-2 px-3">Metric</th>
                    <th className="text-center py-2 px-3">Condition</th>
                    <th className="text-center py-2 px-3">Severity</th>
                    <th className="text-center py-2 px-3">Triggers</th>
                    <th className="text-center py-2 px-3">Enabled</th>
                    <th className="text-center py-2 px-3">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {thresholds.data?.map((th: any) => (
                    <tr
                      key={th.id}
                      className="border-b border-border/50 hover:bg-muted/30"
                    >
                      <td className="py-2 px-3 font-medium">{th.label}</td>
                      <td className="py-2 px-3 font-mono text-xs text-muted-foreground">
                        {th.metricKey}
                      </td>
                      <td className="text-center py-2 px-3">
                        {operatorLabel[th.operator]} {th.value}
                      </td>
                      <td className="text-center py-2 px-3">
                        <Badge variant={severityColor(th.severity) as any}>
                          {th.severity}
                        </Badge>
                      </td>
                      <td className="text-center py-2 px-3">
                        {th.triggerCount}
                      </td>
                      <td className="text-center py-2 px-3">
                        <Switch
                          checked={th.enabled}
                          onCheckedChange={enabled =>
                            updateMutation.mutate({ id: th.id, enabled })
                          }
                        />
                      </td>
                      <td className="text-center py-2 px-3">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => deleteMutation.mutate({ id: th.id })}
                        >
                          <Trash2 className="w-4 h-4 text-red-400" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
