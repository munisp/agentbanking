/**
 * Webhook Delivery Viewer — View delivery attempts, payloads, and retry status
 * Wired to webhooks.listDeliveries
 */
import { useState, useMemo } from "react";
import { trpc } from "@/lib/trpc";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Webhook,
  Search,
  Eye,
  RotateCw,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
} from "lucide-react";
import { toast } from "sonner";

export default function WebhookDeliveryViewer() {
  const [search, setSearch] = useState("");
  const [selectedDelivery, setSelectedDelivery] = useState<any>(null);

  const deliveries = trpc.webhooks.deliveries.useQuery(
    { endpointId: 1, page: 1, limit: 50 },
    { retry: false }
  );
  const retryMutation = trpc.webhooks.retryDelivery.useMutation({
    onSuccess: () => {
      toast.success("Retry queued");
      deliveries.refetch();
    },
    onError: e => toast.error("Retry failed: " + e.message),
  });

  const items = deliveries.data?.items ?? [];
  const filtered = useMemo(() => {
    if (!search) return items;
    const q = search.toLowerCase();
    return items.filter(
      (d: any) =>
        d.url?.toLowerCase().includes(q) ||
        d.eventType?.toLowerCase().includes(q) ||
        d.status?.toLowerCase().includes(q)
    );
  }, [items, search]);

  const statusIcon = (status: string) => {
    switch (status) {
      case "delivered":
        return <CheckCircle className="w-3 h-3 text-green-400" />;
      case "failed":
        return <XCircle className="w-3 h-3 text-red-400" />;
      case "pending":
        return <Clock className="w-3 h-3 text-yellow-400" />;
      default:
        return <AlertTriangle className="w-3 h-3 text-slate-400" />;
    }
  };

  const statusColor: Record<string, string> = {
    delivered: "border-green-600 text-green-400",
    failed: "border-red-600 text-red-400",
    pending: "border-yellow-600 text-yellow-400",
  };

  return (
    <div className="min-h-screen bg-slate-950 text-white p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Webhook className="w-6 h-6 text-blue-400" /> Webhook Delivery
            Viewer
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Monitor webhook delivery attempts, inspect payloads, and retry
            failed deliveries
          </p>
        </div>
        <div className="flex gap-2">
          <Badge
            variant="outline"
            className="text-xs border-green-600 text-green-400"
          >
            {items.filter((d: any) => d.status === "delivered").length}{" "}
            Delivered
          </Badge>
          <Badge
            variant="outline"
            className="text-xs border-red-600 text-red-400"
          >
            {items.filter((d: any) => d.status === "failed").length} Failed
          </Badge>
        </div>
      </div>

      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
        <Input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search by URL, event type, or status..."
          className="pl-9 bg-slate-800 border-slate-700 text-white"
        />
      </div>

      <Card className="bg-slate-900/50 border-slate-700">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm text-white">
            Delivery Log ({filtered.length} entries)
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0 overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-slate-700 text-slate-500">
                <th className="px-3 py-2 text-left">Status</th>
                <th className="px-3 py-2 text-left">Event</th>
                <th className="px-3 py-2 text-left">URL</th>
                <th className="px-3 py-2 text-center">HTTP</th>
                <th className="px-3 py-2 text-center">Attempts</th>
                <th className="px-3 py-2 text-left">Time</th>
                <th className="px-3 py-2 text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/50">
              {filtered.map((d: any) => (
                <tr key={d.id} className="hover:bg-slate-800/40">
                  <td className="px-3 py-2.5">
                    <div className="flex items-center gap-1">
                      {statusIcon(d.status)}
                      <Badge
                        variant="outline"
                        className={`text-[10px] ${statusColor[d.status] ?? "border-slate-600 text-slate-400"}`}
                      >
                        {d.status}
                      </Badge>
                    </div>
                  </td>
                  <td className="px-3 py-2.5 font-mono text-slate-300">
                    {d.eventType}
                  </td>
                  <td className="px-3 py-2.5 text-slate-400 max-w-[200px] truncate">
                    {d.url}
                  </td>
                  <td className="px-3 py-2.5 text-center font-mono">
                    <span
                      className={
                        d.httpStatus >= 200 && d.httpStatus < 300
                          ? "text-green-400"
                          : "text-red-400"
                      }
                    >
                      {d.httpStatus ?? "-"}
                    </span>
                  </td>
                  <td className="px-3 py-2.5 text-center text-slate-400">
                    {d.attempts ?? 1}/{d.maxAttempts ?? 3}
                  </td>
                  <td className="px-3 py-2.5 text-slate-500">
                    {d.createdAt ? new Date(d.createdAt).toLocaleString() : "-"}
                  </td>
                  <td className="px-3 py-2.5 text-center">
                    <div className="flex gap-1 justify-center">
                      <Dialog>
                        <DialogTrigger asChild>
                          <Button
                            size="icon"
                            variant="ghost"
                            className="h-6 w-6 text-blue-400"
                            onClick={() => setSelectedDelivery(d)}
                          >
                            <Eye className="w-3 h-3" />
                          </Button>
                        </DialogTrigger>
                        <DialogContent className="bg-slate-900 border-slate-700 text-white max-w-2xl">
                          <DialogHeader>
                            <DialogTitle className="text-sm">
                              Delivery Details
                            </DialogTitle>
                          </DialogHeader>
                          <div className="space-y-3 text-xs">
                            <div>
                              <span className="text-slate-500">Event:</span>{" "}
                              <span className="font-mono">{d.eventType}</span>
                            </div>
                            <div>
                              <span className="text-slate-500">URL:</span>{" "}
                              <span className="font-mono text-blue-400">
                                {d.url}
                              </span>
                            </div>
                            <div>
                              <span className="text-slate-500">Status:</span>{" "}
                              {d.status} (HTTP {d.httpStatus})
                            </div>
                            <div>
                              <span className="text-slate-500">Payload:</span>
                              <pre className="mt-1 p-2 bg-slate-800 rounded text-[10px] overflow-auto max-h-[200px]">
                                {JSON.stringify(d.payload ?? {}, null, 2)}
                              </pre>
                            </div>
                            <div>
                              <span className="text-slate-500">Response:</span>
                              <pre className="mt-1 p-2 bg-slate-800 rounded text-[10px] overflow-auto max-h-[200px]">
                                {d.responseBody ?? "No response captured"}
                              </pre>
                            </div>
                          </div>
                        </DialogContent>
                      </Dialog>
                      {d.status === "failed" && (
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-6 w-6 text-yellow-400"
                          onClick={() =>
                            retryMutation.mutate({ deliveryId: d.id })
                          }
                          disabled={retryMutation.isPending}
                        >
                          <RotateCw className="w-3 h-3" />
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td
                    colSpan={7}
                    className="px-3 py-8 text-center text-slate-600"
                  >
                    {deliveries.isLoading
                      ? "Loading..."
                      : "No deliveries found"}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
