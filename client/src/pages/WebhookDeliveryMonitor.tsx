import { useState } from "react";
import DashboardLayout from "@/components/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { trpc } from "@/lib/trpc";
import { toast } from "sonner";
import {
  Webhook,
  RotateCcw,
  AlertOctagon,
  CheckCircle2,
  Clock,
  Send,
} from "lucide-react";

export default function WebhookDeliveryMonitor() {
  const [activeTab, setActiveTab] = useState("all");

  // @ts-ignore Sprint 85
  const deliveries = trpc.sprint23.webhookDelivery.list.useQuery(
    activeTab !== "all" && activeTab !== "dead_letter"
      ? { status: activeTab }
      : undefined
  );
  const deadLetterQueue =
    // @ts-ignore Sprint 85
    trpc.sprint23.webhookDelivery.deadLetterQueue.useQuery();
  const utils = trpc.useUtils();

  // @ts-ignore Sprint 85
  const retryDlq = trpc.sprint23.webhookDelivery.retryDeadLetter.useMutation({
    onSuccess: () => {
      // @ts-ignore Sprint 85
      utils.sprint23.webhookDelivery.list.invalidate();
      // @ts-ignore Sprint 85
      utils.sprint23.webhookDelivery.deadLetterQueue.invalidate();
      toast.success("Dead letter re-queued for retry");
    },
  });

  const statusIcon = (status: string) => {
    switch (status) {
      case "success":
        return <CheckCircle2 className="w-4 h-4 text-green-400" />;
      case "pending":
        return <Clock className="w-4 h-4 text-yellow-400" />;
      case "failed":
        return <RotateCcw className="w-4 h-4 text-orange-400" />;
      case "dead_letter":
        return <AlertOctagon className="w-4 h-4 text-red-400" />;
      default:
        return null;
    }
  };

  const items =
    activeTab === "dead_letter" ? deadLetterQueue.data : deliveries.data;

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Webhook className="w-6 h-6 text-indigo-400" />
              Webhook Delivery Monitor
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Monitor webhook deliveries, retry queue, and dead letter queue
            </p>
          </div>
        </div>

        {/* Summary */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card className="border-green-500/30">
            <CardContent className="pt-4 text-center">
              <CheckCircle2 className="w-6 h-6 mx-auto text-green-400 mb-1" />
              <p className="text-xl font-bold">
                {deliveries.data?.filter((d: any) => d.status === "success")
                  .length ?? 0}
              </p>
              <p className="text-xs text-muted-foreground">Delivered</p>
            </CardContent>
          </Card>
          <Card className="border-yellow-500/30">
            <CardContent className="pt-4 text-center">
              <Clock className="w-6 h-6 mx-auto text-yellow-400 mb-1" />
              <p className="text-xl font-bold">
                {deliveries.data?.filter((d: any) => d.status === "pending")
                  .length ?? 0}
              </p>
              <p className="text-xs text-muted-foreground">Pending</p>
            </CardContent>
          </Card>
          <Card className="border-orange-500/30">
            <CardContent className="pt-4 text-center">
              <RotateCcw className="w-6 h-6 mx-auto text-orange-400 mb-1" />
              <p className="text-xl font-bold">
                {deliveries.data?.filter((d: any) => d.status === "failed")
                  .length ?? 0}
              </p>
              <p className="text-xs text-muted-foreground">Retrying</p>
            </CardContent>
          </Card>
          <Card className="border-red-500/30">
            <CardContent className="pt-4 text-center">
              <AlertOctagon className="w-6 h-6 mx-auto text-red-400 mb-1" />
              <p className="text-xl font-bold">
                {deadLetterQueue.data?.length ?? 0}
              </p>
              <p className="text-xs text-muted-foreground">Dead Letter</p>
            </CardContent>
          </Card>
        </div>

        {/* Tabs */}
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="all">All</TabsTrigger>
            <TabsTrigger value="pending">Pending</TabsTrigger>
            <TabsTrigger value="success">Success</TabsTrigger>
            <TabsTrigger value="failed">Failed</TabsTrigger>
            <TabsTrigger value="dead_letter">Dead Letter</TabsTrigger>
          </TabsList>
          <TabsContent value={activeTab}>
            <Card>
              <CardContent className="pt-4">
                {!items || items.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground">
                    <Send className="w-12 h-12 mx-auto mb-2 opacity-30" />
                    <p>No webhook deliveries in this category</p>
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-border">
                          <th className="text-left py-2 px-3">ID</th>
                          <th className="text-left py-2 px-3">URL</th>
                          <th className="text-center py-2 px-3">Status</th>
                          <th className="text-center py-2 px-3">Attempts</th>
                          <th className="text-center py-2 px-3">Response</th>
                          <th className="text-right py-2 px-3">Next Retry</th>
                          {activeTab === "dead_letter" && (
                            <th className="text-center py-2 px-3">Actions</th>
                          )}
                        </tr>
                      </thead>
                      <tbody>
                        {items.map((d: any) => (
                          <tr
                            key={d.id}
                            className="border-b border-border/50 hover:bg-muted/30"
                          >
                            <td className="py-2 px-3 font-mono text-xs">
                              {d.id}
                            </td>
                            <td className="py-2 px-3 text-xs truncate max-w-[200px]">
                              {d.url}
                            </td>
                            <td className="text-center py-2 px-3">
                              <div className="flex items-center justify-center gap-1">
                                {statusIcon(d.status)}
                                <Badge
                                  variant={
                                    d.status === "success"
                                      ? "default"
                                      : d.status === "dead_letter"
                                        ? "destructive"
                                        : "secondary"
                                  }
                                >
                                  {d.status}
                                </Badge>
                              </div>
                            </td>
                            <td className="text-center py-2 px-3">
                              {d.attempts}/{d.maxAttempts}
                            </td>
                            <td className="text-center py-2 px-3">
                              {d.responseCode ?? "—"}
                            </td>
                            <td className="text-right py-2 px-3 text-xs text-muted-foreground">
                              {d.nextRetryAt
                                ? new Date(d.nextRetryAt).toLocaleTimeString()
                                : "—"}
                            </td>
                            {activeTab === "dead_letter" && (
                              <td className="text-center py-2 px-3">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() =>
                                    retryDlq.mutate({ deliveryId: d.id })
                                  }
                                >
                                  <RotateCcw className="w-4 h-4 mr-1" /> Retry
                                </Button>
                              </td>
                            )}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </DashboardLayout>
  );
}
