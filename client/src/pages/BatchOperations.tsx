import { useState } from "react";
import DashboardLayout from "@/components/DashboardLayout";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { trpc } from "@/lib/trpc";
import {
  Layers,
  CheckCircle2,
  XCircle,
  Users,
  Wallet,
  MessageSquare,
  FileCheck,
  Loader2,
} from "lucide-react";

type OpType = "kyc" | "wallet" | "sms" | "agent";

export default function BatchOperations() {
  const [activeOp, setActiveOp] = useState<OpType>("kyc");
  const [ids, setIds] = useState("");
  const [action, setAction] = useState("");
  const [reason, setReason] = useState("");
  const [smsMessage, setSmsMessage] = useState("");
  const [lastResult, setLastResult] = useState<any>(null);

  // @ts-ignore Sprint 85
  const kycMut = trpc.production.batchOps.bulkKycAction.useMutation({
    onSuccess: (d: any) => {
      setLastResult(d);
      toast.success(`KYC ${d.action}: ${d.succeeded}/${d.total} succeeded`);
    },
    onError: () => toast.error("Batch KYC operation failed"),
  });
  // @ts-ignore Sprint 85
  const walletMut = trpc.production.batchOps.bulkWalletAction.useMutation({
    onSuccess: (d: any) => {
      setLastResult(d);
      toast.success(`Wallet ${d.action}: ${d.succeeded}/${d.total} succeeded`);
    },
    onError: () => toast.error("Batch wallet operation failed"),
  });
  // @ts-ignore Sprint 85
  const smsMut = trpc.production.batchOps.bulkSms.useMutation({
    onSuccess: (d: any) => {
      setLastResult(d);
      toast.success(`SMS sent: ${d.sent}/${d.total}`);
    },
    onError: () => toast.error("Batch SMS failed"),
  });
  // @ts-ignore Sprint 85
  const agentMut = trpc.production.batchOps.bulkAgentAction.useMutation({
    onSuccess: (d: any) => {
      setLastResult(d);
      toast.success(`Agent ${d.action}: ${d.succeeded}/${d.total} succeeded`);
    },
    onError: () => toast.error("Batch agent operation failed"),
  });

  const isPending =
    kycMut.isPending ||
    walletMut.isPending ||
    smsMut.isPending ||
    agentMut.isPending;

  function execute() {
    const idList = ids
      .split(/[\n,]+/)
      .map(s => s.trim())
      .filter(Boolean);
    if (idList.length === 0) {
      toast.error("Enter at least one ID");
      return;
    }

    if (activeOp === "kyc") {
      if (!action) {
        toast.error("Select an action");
        return;
      }
      kycMut.mutate({
        action: action as "approve" | "reject",
        ids: idList,
        reason: reason || undefined,
      });
    } else if (activeOp === "wallet") {
      if (!action) {
        toast.error("Select an action");
        return;
      }
      walletMut.mutate({
        action: action as any,
        walletIds: idList,
        reason: reason || undefined,
      });
    } else if (activeOp === "sms") {
      if (!smsMessage) {
        toast.error("Enter a message");
        return;
      }
      smsMut.mutate({ phones: idList, message: smsMessage });
    } else if (activeOp === "agent") {
      if (!action) {
        toast.error("Select an action");
        return;
      }
      agentMut.mutate({
        action: action as any,
        agentIds: idList.map(Number).filter(n => !isNaN(n)),
        reason: reason || undefined,
      });
    }
  }

  const OPS: {
    key: OpType;
    label: string;
    icon: React.ReactNode;
    actions: string[];
  }[] = [
    {
      key: "kyc",
      label: "KYC Batch",
      icon: <FileCheck className="w-4 h-4" />,
      actions: ["approve", "reject"],
    },
    {
      key: "wallet",
      label: "Wallet Batch",
      icon: <Wallet className="w-4 h-4" />,
      actions: ["freeze", "unfreeze", "credit", "debit"],
    },
    {
      key: "sms",
      label: "Bulk SMS",
      icon: <MessageSquare className="w-4 h-4" />,
      actions: [],
    },
    {
      key: "agent",
      label: "Agent Batch",
      icon: <Users className="w-4 h-4" />,
      actions: ["suspend", "activate", "promote", "demote"],
    },
  ];

  const currentOp = OPS.find(o => o.key === activeOp)!;

  return (
    <DashboardLayout>
      <div className="container max-w-4xl py-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Layers className="w-6 h-6" /> Batch Operations
          </h1>
          <p className="text-muted-foreground mt-1">
            Execute bulk actions across multiple entities at once
          </p>
        </div>

        <div className="flex gap-2">
          {OPS.map(op => (
            <Button
              key={op.key}
              variant={activeOp === op.key ? "default" : "outline"}
              size="sm"
              onClick={() => {
                setActiveOp(op.key);
                setAction("");
                setLastResult(null);
              }}
            >
              {op.icon} <span className="ml-1">{op.label}</span>
            </Button>
          ))}
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              {currentOp.icon} {currentOp.label}
            </CardTitle>
            <CardDescription>
              Enter IDs (one per line or comma-separated) and select an action
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Textarea
              placeholder={
                activeOp === "sms"
                  ? "Enter phone numbers (one per line)"
                  : "Enter IDs (one per line or comma-separated)"
              }
              value={ids}
              onChange={e => setIds(e.target.value)}
              rows={5}
              className="font-mono text-sm"
            />
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Badge variant="outline">
                {ids.split(/[\n,]+/).filter(s => s.trim()).length} items
              </Badge>
            </div>

            {currentOp.actions.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {currentOp.actions.map(a => (
                  <Button
                    key={a}
                    variant={action === a ? "default" : "outline"}
                    size="sm"
                    onClick={() => setAction(a)}
                    className="capitalize"
                  >
                    {a}
                  </Button>
                ))}
              </div>
            )}

            {activeOp === "sms" && (
              <div>
                <label className="text-sm font-medium mb-1 block">
                  Message (max 160 chars)
                </label>
                <Input
                  value={smsMessage}
                  onChange={e => setSmsMessage(e.target.value)}
                  maxLength={160}
                  placeholder="Enter SMS message..."
                />
                <span className="text-xs text-muted-foreground">
                  {smsMessage.length}/160
                </span>
              </div>
            )}

            {(activeOp === "kyc" ||
              activeOp === "wallet" ||
              activeOp === "agent") && (
              <Input
                placeholder="Reason (optional)"
                value={reason}
                onChange={e => setReason(e.target.value)}
              />
            )}

            <Button onClick={execute} disabled={isPending} className="w-full">
              {isPending ? (
                <>
                  <Loader2 className="w-4 h-4 mr-1 animate-spin" />{" "}
                  Processing...
                </>
              ) : (
                <>Execute Batch Operation</>
              )}
            </Button>
          </CardContent>
        </Card>

        {lastResult && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Result</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <div className="text-2xl font-bold">
                    {lastResult.total ?? lastResult.sent ?? 0}
                  </div>
                  <div className="text-xs text-muted-foreground">Total</div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-green-600">
                    {lastResult.succeeded ?? lastResult.sent ?? 0}
                  </div>
                  <div className="text-xs text-muted-foreground flex items-center justify-center gap-1">
                    <CheckCircle2 className="w-3 h-3" /> Succeeded
                  </div>
                </div>
                <div>
                  <div className="text-2xl font-bold text-red-600">
                    {lastResult.failed ?? 0}
                  </div>
                  <div className="text-xs text-muted-foreground flex items-center justify-center gap-1">
                    <XCircle className="w-3 h-3" /> Failed
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </DashboardLayout>
  );
}
