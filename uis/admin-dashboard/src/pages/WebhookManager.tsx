// SECURITY: SQL template literals in this file are for display/mock purposes only. All actual DB queries use parameterized Drizzle ORM.
import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { useAuth } from "@/_core/hooks/useAuth";
import { getLoginUrl } from "@/const";
import DashboardLayout from "@/components/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Checkbox } from "@/components/ui/checkbox";
import { toast } from "sonner";
import {
  Plus,
  RefreshCw,
  Trash2,
  Eye,
  EyeOff,
  Copy,
  Zap,
  RotateCcw,
} from "lucide-react";

const ALL_EVENTS = [
  "transaction.completed",
  "transaction.failed",
  "transaction.reversed",
  "float.low",
  "float.topup.approved",
  "float.topup.rejected",
  "kyc.approved",
  "kyc.rejected",
  "kyc.document_uploaded",
  "dispute.raised",
  "dispute.resolved",
  "agent.activated",
  "agent.suspended",
  "agent.deactivated",
  "fraud.alert",
  "settlement.completed",
  "commission.payout.approved",
  "commission.payout.completed",
];

export default function WebhookManager() {
  const { user, loading, isAuthenticated } = useAuth();
  const [showCreate, setShowCreate] = useState(false);
  const [showSecret, setShowSecret] = useState<{
    id: number;
    secret: string;
  } | null>(null);
  const [selectedEndpoint, setSelectedEndpoint] = useState<number | null>(null);
  const [deliveryPage, setDeliveryPage] = useState(1);
  const [form, setForm] = useState({
    name: "",
    url: "",
    events: [] as string[],
  });

  const utils = trpc.useUtils();
  const { data: endpoints = [], isLoading } = trpc.webhooks.list.useQuery();
  const { data: stats } = trpc.webhooks.stats.useQuery();
  const { data: deliveries } = trpc.webhooks.deliveries.useQuery(
    { endpointId: selectedEndpoint!, page: deliveryPage, limit: 15 },
    { enabled: !!selectedEndpoint }
  );

  const createMutation = trpc.webhooks.create.useMutation({
    onSuccess: data => {
      setShowCreate(false);
      setShowSecret({ id: data.id, secret: data.secret });
      setForm({ name: "", url: "", events: [] });
      utils.webhooks.list.invalidate();
      toast.success("Webhook endpoint created");
    },
    onError: e => toast.error(e.message),
  });

  const deleteMutation = trpc.webhooks.delete.useMutation({
    onSuccess: () => {
      utils.webhooks.list.invalidate();
      toast.success("Endpoint deleted");
    },
    onError: e => toast.error(e.message),
  });

  const rotateMutation = trpc.webhooks.rotateSecret.useMutation({
    onSuccess: data => {
      setShowSecret({ id: -1, secret: data.secret });
      toast.success("Secret rotated");
    },
    onError: e => toast.error(e.message),
  });

  const pingMutation = trpc.webhooks.ping.useMutation({
    onSuccess: data => {
      if (data.success) toast.success(`Ping successful (${data.statusCode})`);
      else toast.error(`Ping failed: ${data.error ?? data.statusCode}`);
    },
    onError: e => toast.error(e.message),
  });

  const retryMutation = trpc.webhooks.retryDelivery.useMutation({
    onSuccess: () => {
      utils.webhooks.deliveries.invalidate();
      toast.success("Delivery queued for retry");
    },
    onError: e => toast.error(e.message),
  });

  const toggleEvent = (ev: string) => {
    setForm(f => ({
      ...f,
      events: f.events.includes(ev)
        ? f.events.filter((e: any) => e !== ev)
        : [...f.events, ev],
    }));
  };

  if (loading)
    return (
      <div className="flex items-center justify-center h-screen">
        Loading...
      </div>
    );
  if (!isAuthenticated) {
    window.location.href = getLoginUrl();
    return null;
  }

  const statusColor = (s: string) =>
    s === "delivered"
      ? "bg-green-100 text-green-800"
      : s === "failed"
        ? "bg-red-100 text-red-800"
        : s === "retrying"
          ? "bg-yellow-100 text-yellow-800"
          : "bg-gray-100 text-gray-700";

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">
              Webhook Manager
            </h1>
            <p className="text-muted-foreground text-sm">
              Manage outbound webhook endpoints and delivery history
            </p>
          </div>
          <Button onClick={() => setShowCreate(true)}>
            <Plus className="w-4 h-4 mr-2" /> Add Endpoint
          </Button>
        </div>

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {[
              { label: "Total (24h)", value: stats.total },
              {
                label: "Delivered",
                value: stats.delivered,
                color: "text-green-600",
              },
              { label: "Failed", value: stats.failed, color: "text-red-600" },
              {
                label: "Retrying",
                value: stats.retrying,
                color: "text-yellow-600",
              },
              {
                label: "Success Rate",
                value: `${stats.successRate}%`,
                color:
                  stats.successRate >= 95 ? "text-green-600" : "text-red-600",
              },
            ].map((s: any) => (
              <Card key={s.label}>
                <CardContent className="pt-4">
                  <p className="text-xs text-muted-foreground">{s.label}</p>
                  <p className={`text-2xl font-bold ${s.color ?? ""}`}>
                    {s.value}
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Endpoints list */}
          <Card>
            <CardHeader>
              <CardTitle>Endpoints ({endpoints.length})</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {isLoading && (
                <p className="text-sm text-muted-foreground">Loading...</p>
              )}
              {endpoints.map((ep: any) => (
                <div
                  key={ep.id}
                  className={`border rounded-lg p-3 cursor-pointer transition-colors ${selectedEndpoint === ep.id ? "border-primary bg-primary/5" : "hover:border-muted-foreground/30"}`}
                  onClick={() => {
                    setSelectedEndpoint(ep.id);
                    setDeliveryPage(1);
                  }}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="font-medium text-sm truncate">{ep.name}</p>
                      <p className="text-xs text-muted-foreground truncate">
                        {ep.url}
                      </p>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {(ep.events as string[]).slice(0, 3).map((ev: any) => (
                          <Badge
                            key={ev}
                            variant="secondary"
                            className="text-xs"
                          >
                            {ev}
                          </Badge>
                        ))}
                        {(ep.events as string[]).length > 3 && (
                          <Badge variant="secondary" className="text-xs">
                            +{(ep.events as string[]).length - 3}
                          </Badge>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <Badge variant={ep.isActive ? "default" : "secondary"}>
                        {ep.isActive ? "Active" : "Paused"}
                      </Badge>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7"
                        onClick={e => {
                          e.stopPropagation();
                          pingMutation.mutate({ id: ep.id });
                        }}
                      >
                        <Zap className="w-3 h-3" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7"
                        onClick={e => {
                          e.stopPropagation();
                          rotateMutation.mutate({ id: ep.id });
                        }}
                      >
                        <RotateCcw className="w-3 h-3" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7 text-destructive"
                        onClick={e => {
                          e.stopPropagation();
                          if (confirm("Delete endpoint?"))
                            deleteMutation.mutate({ id: ep.id });
                        }}
                      >
                        <Trash2 className="w-3 h-3" />
                      </Button>
                    </div>
                  </div>
                  {ep.lastDeliveryAt && (
                    <p className="text-xs text-muted-foreground mt-1">
                      Last delivery:{" "}
                      {new Date(ep.lastDeliveryAt).toLocaleString()} · Status:{" "}
                      {ep.lastStatusCode}
                    </p>
                  )}
                </div>
              ))}
              {endpoints.length === 0 && !isLoading && (
                <p className="text-sm text-muted-foreground text-center py-8">
                  No endpoints configured. Add one to start receiving events.
                </p>
              )}
            </CardContent>
          </Card>

          {/* Delivery history */}
          <Card>
            <CardHeader>
              <CardTitle>Delivery History</CardTitle>
              <CardDescription>
                {selectedEndpoint
                  ? `Endpoint #${selectedEndpoint}`
                  : "Select an endpoint to view history"}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!selectedEndpoint && (
                <p className="text-sm text-muted-foreground text-center py-8">
                  Click an endpoint to view its delivery history
                </p>
              )}
              {selectedEndpoint && deliveries && (
                <div className="space-y-2">
                  {deliveries.items.map((d: any) => (
                    <div key={d.id} className="border rounded p-2 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{d.eventType}</span>
                        <div className="flex items-center gap-2">
                          <span
                            className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColor(d.status)}`}
                          >
                            {d.status}
                          </span>
                          {(d.status === "failed" ||
                            d.status === "retrying") && (
                            <Button
                              size="icon"
                              variant="ghost"
                              className="h-5 w-5"
                              onClick={() =>
                                retryMutation.mutate({ deliveryId: d.id })
                              }
                            >
                              <RefreshCw className="w-3 h-3" />
                            </Button>
                          )}
                        </div>
                      </div>
                      <div className="flex justify-between text-muted-foreground mt-1">
                        <span>
                          Attempt {d.attemptCount}/{d.maxAttempts}
                        </span>
                        {d.statusCode && <span>HTTP {d.statusCode}</span>}
                        <span>{new Date(d.createdAt).toLocaleString()}</span>
                      </div>
                    </div>
                  ))}
                  {deliveries.items.length === 0 && (
                    <p className="text-sm text-muted-foreground text-center py-4">
                      No deliveries yet
                    </p>
                  )}
                  {deliveries.total > 15 && (
                    <div className="flex justify-between items-center pt-2">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={deliveryPage === 1}
                        onClick={() => setDeliveryPage(p => p - 1)}
                      >
                        Prev
                      </Button>
                      <span className="text-xs text-muted-foreground">
                        Page {deliveryPage} of{" "}
                        {Math.ceil(deliveries.total / 15)}
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={deliveryPage * 15 >= deliveries.total}
                        onClick={() => setDeliveryPage(p => p + 1)}
                      >
                        Next
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Create endpoint dialog */}
        <Dialog open={showCreate} onOpenChange={setShowCreate}>
          <DialogContent className="max-w-lg max-h-[80vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Add Webhook Endpoint</DialogTitle>
            </DialogHeader>
            <div className="space-y-4">
              <div>
                <Label>Name</Label>
                <Input
                  placeholder="My Production Webhook"
                  value={form.name}
                  onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                />
              </div>
              <div>
                <Label>URL</Label>
                <Input
                  placeholder="https://your-server.com/webhook"
                  value={form.url}
                  onChange={e => setForm(f => ({ ...f, url: e.target.value }))}
                />
              </div>
              <div>
                <Label className="mb-2 block">Events to subscribe</Label>
                <div className="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto border rounded p-2">
                  {ALL_EVENTS.map((ev: any) => (
                    <div key={ev} className="flex items-center gap-2">
                      <Checkbox
                        id={ev}
                        checked={form.events.includes(ev)}
                        onCheckedChange={() => toggleEvent(ev)}
                      />
                      <label htmlFor={ev} className="text-xs cursor-pointer">
                        {ev}
                      </label>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setShowCreate(false)}>
                Cancel
              </Button>
              <Button
                onClick={() => createMutation.mutate(form)}
                disabled={
                  !form.name ||
                  !form.url ||
                  form.events.length === 0 ||
                  createMutation.isPending
                }
              >
                {createMutation.isPending ? "Creating..." : "Create Endpoint"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Secret reveal dialog */}
        <Dialog open={!!showSecret} onOpenChange={() => setShowSecret(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Webhook Secret</DialogTitle>
            </DialogHeader>
            <p className="text-sm text-muted-foreground">
              Copy this secret now — it will not be shown again.
            </p>
            <div className="flex items-center gap-2 bg-muted rounded p-3 font-mono text-sm break-all">
              <span className="flex-1">{showSecret?.secret}</span>
              <Button
                size="icon"
                variant="ghost"
                className="h-7 w-7 shrink-0"
                onClick={() => {
                  navigator.clipboard.writeText(showSecret?.secret ?? "");
                  toast.success("Copied!");
                }}
              >
                <Copy className="w-4 h-4" />
              </Button>
            </div>
            <DialogFooter>
              <Button onClick={() => setShowSecret(null)}>Done</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </DashboardLayout>
  );
}
