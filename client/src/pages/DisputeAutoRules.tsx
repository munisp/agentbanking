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
  Scale,
  Plus,
  Gavel,
  RefreshCw,
  AlertTriangle,
  FileSearch,
  ArrowUpRight,
} from "lucide-react";

const actionLabels: Record<
  string,
  { label: string; color: string; icon: any }
> = {
  auto_refund: {
    label: "Auto Refund",
    color: "text-green-400",
    icon: RefreshCw,
  },
  auto_reject: {
    label: "Auto Reject",
    color: "text-red-400",
    icon: AlertTriangle,
  },
  escalate_to_supervisor: {
    label: "Escalate",
    color: "text-yellow-400",
    icon: ArrowUpRight,
  },
  request_evidence: {
    label: "Request Evidence",
    color: "text-blue-400",
    icon: FileSearch,
  },
};

export default function DisputeAutoRules() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newField, setNewField] = useState("amount");
  const [newOperator, setNewOperator] = useState<
    "eq" | "gt" | "lt" | "contains"
  >("lt");
  const [newValue, setNewValue] = useState("");
  const [newAction, setNewAction] = useState<
    | "auto_refund"
    | "auto_reject"
    | "escalate_to_supervisor"
    | "request_evidence"
  >("auto_refund");
  const [newMaxAmount, setNewMaxAmount] = useState("50000");

  // @ts-ignore Sprint 85
  const rules = trpc.sprint23.disputeAutoRules.list.useQuery();
  const utils = trpc.useUtils();

  // @ts-ignore Sprint 85
  const createMutation = trpc.sprint23.disputeAutoRules.create.useMutation({
    onSuccess: () => {
      // @ts-ignore Sprint 85
      utils.sprint23.disputeAutoRules.list.invalidate();
      toast.success("Rule created");
      setDialogOpen(false);
      setNewName("");
      setNewValue("");
    },
  });

  // Test evaluation
  const [testAmount, setTestAmount] = useState("3000");
  const [testReason, setTestReason] = useState("duplicate charge");
  // @ts-ignore Sprint 85
  const testResult = trpc.sprint23.disputeAutoRules.evaluate.useQuery(
    {
      amount: parseFloat(testAmount) || 0,
      reason: testReason,
      category: "transaction",
    },
    { enabled: !!testAmount && !!testReason }
  );

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Scale className="w-6 h-6 text-purple-400" />
              Dispute Auto-Resolution Rules
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Configure automated rules for transaction dispute resolution
            </p>
          </div>
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button size="sm">
                <Plus className="w-4 h-4 mr-1" /> Add Rule
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create Auto-Resolution Rule</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 pt-2">
                <Input
                  placeholder="Rule name"
                  value={newName}
                  onChange={e => setNewName(e.target.value)}
                />
                <div className="grid grid-cols-3 gap-2">
                  <Select value={newField} onValueChange={setNewField}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="amount">Amount</SelectItem>
                      <SelectItem value="reason">Reason</SelectItem>
                      <SelectItem value="category">Category</SelectItem>
                    </SelectContent>
                  </Select>
                  <Select
                    value={newOperator}
                    onValueChange={v => setNewOperator(v as any)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="eq">Equals</SelectItem>
                      <SelectItem value="gt">Greater than</SelectItem>
                      <SelectItem value="lt">Less than</SelectItem>
                      <SelectItem value="contains">Contains</SelectItem>
                    </SelectContent>
                  </Select>
                  <Input
                    placeholder="Value"
                    value={newValue}
                    onChange={e => setNewValue(e.target.value)}
                  />
                </div>
                <Select
                  value={newAction}
                  onValueChange={v => setNewAction(v as any)}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="auto_refund">Auto Refund</SelectItem>
                    <SelectItem value="auto_reject">Auto Reject</SelectItem>
                    <SelectItem value="escalate_to_supervisor">
                      Escalate to Supervisor
                    </SelectItem>
                    <SelectItem value="request_evidence">
                      Request Evidence
                    </SelectItem>
                  </SelectContent>
                </Select>
                <Input
                  type="number"
                  placeholder="Max amount for auto-resolve"
                  value={newMaxAmount}
                  onChange={e => setNewMaxAmount(e.target.value)}
                />
                <Button
                  className="w-full"
                  onClick={() =>
                    createMutation.mutate({
                      name: newName,
                      condition: {
                        field: newField,
                        operator: newOperator,
                        value:
                          newField === "amount"
                            ? parseFloat(newValue)
                            : newValue,
                      },
                      action: newAction,
                      maxAmount: parseFloat(newMaxAmount),
                      enabled: true,
                    })
                  }
                  disabled={!newName || !newValue}
                >
                  Create Rule
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>

        {/* Rules Table */}
        <Card>
          <CardHeader>
            <CardTitle>Active Rules ({rules.data?.length ?? 0})</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border">
                    <th className="text-left py-2 px-3">Rule Name</th>
                    <th className="text-left py-2 px-3">Condition</th>
                    <th className="text-center py-2 px-3">Action</th>
                    <th className="text-right py-2 px-3">Max Amount</th>
                    <th className="text-center py-2 px-3">Resolutions</th>
                    <th className="text-center py-2 px-3">Enabled</th>
                  </tr>
                </thead>
                <tbody>
                  {rules.data?.map((rule: any) => {
                    const actionInfo = actionLabels[rule.action];
                    const Icon = actionInfo?.icon;
                    return (
                      <tr
                        key={rule.id}
                        className="border-b border-border/50 hover:bg-muted/30"
                      >
                        <td className="py-2 px-3 font-medium">{rule.name}</td>
                        <td className="py-2 px-3 text-xs font-mono">
                          {rule.condition.field} {rule.condition.operator}{" "}
                          {String(rule.condition.value)}
                        </td>
                        <td className="text-center py-2 px-3">
                          <div
                            className={`flex items-center justify-center gap-1 ${actionInfo?.color}`}
                          >
                            {Icon && <Icon className="w-3 h-3" />}
                            <span className="text-xs">{actionInfo?.label}</span>
                          </div>
                        </td>
                        <td className="text-right py-2 px-3">
                          {rule.maxAmount === Infinity
                            ? "Unlimited"
                            : `₦${rule.maxAmount.toLocaleString()}`}
                        </td>
                        <td className="text-center py-2 px-3">
                          <Badge variant="outline">
                            {rule.resolutionCount}
                          </Badge>
                        </td>
                        <td className="text-center py-2 px-3">
                          <Switch checked={rule.enabled} disabled />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        {/* Test Evaluation */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Gavel className="w-5 h-5" /> Test Rule Evaluation
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Input
                type="number"
                placeholder="Dispute amount"
                value={testAmount}
                onChange={e => setTestAmount(e.target.value)}
              />
              <Input
                placeholder="Dispute reason"
                value={testReason}
                onChange={e => setTestReason(e.target.value)}
              />
              <div className="p-2 rounded-lg bg-muted/30 text-sm">
                {testResult.data ? (
                  <div className={actionLabels[testResult.data.action]?.color}>
                    <strong>
                      {actionLabels[testResult.data.action]?.label}
                    </strong>
                    <span className="text-muted-foreground ml-2">
                      via: {testResult.data.rule.name}
                    </span>
                  </div>
                ) : (
                  <span className="text-muted-foreground">
                    No matching rule — manual review required
                  </span>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
