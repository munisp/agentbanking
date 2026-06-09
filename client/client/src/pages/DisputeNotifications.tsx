import { useState } from "react";
import {
  Bell,
  RefreshCw,
  Search,
  Mail,
  MessageSquare,
  Smartphone,
} from "lucide-react";
import { trpc } from "@/lib/trpc";
import DashboardLayout from "@/components/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";

const CHANNEL_ICONS: Record<string, any> = {
  email: Mail,
  sms: Smartphone,
  push: MessageSquare,
};
const STATUS_COLORS: Record<string, string> = {
  delivered: "bg-emerald-500/20 text-emerald-400",
  sent: "bg-blue-500/20 text-blue-400",
  failed: "bg-red-500/20 text-red-400",
  pending: "bg-yellow-500/20 text-yellow-400",
};

export default function DisputeNotifications() {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const listQuery = trpc.disputeNotifications.listNotifications.useQuery({
    page,
    limit: 20,
    search: search || undefined,
  });
  // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
  const statsQuery = trpc.disputeNotifications.getStats.useQuery();

  const notifications = (listQuery.data as any)?.notifications ?? [];
  const total = (listQuery.data as any)?.total ?? 0;
  const stats = statsQuery.data as any;

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Bell className="h-6 w-6" /> Dispute Notifications
            </h1>
            <p className="text-muted-foreground">
              Automated dispute status change alerts via email and SMS
            </p>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              listQuery.refetch();
              statsQuery.refetch();
              toast.success("Data refreshed");
            }}
          >
            <RefreshCw className="h-4 w-4 mr-1" /> Refresh
          </Button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">
                Total Sent
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">
                {stats?.totalSent ?? total}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">
                Delivered
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-500">
                {stats?.delivered ?? "—"}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">
                Failed
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-red-500">
                {stats?.failed ?? "—"}
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">
                Channels Active
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats?.channels ?? 3}</div>
              <p className="text-xs text-muted-foreground">Email, SMS, Push</p>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Notification Log ({total})</CardTitle>
              <div className="relative w-64">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  className="pl-9"
                  placeholder="Search by dispute ref..."
                  value={search}
                  onChange={(e: any) => {
                    setSearch(e.target.value);
                    setPage(1);
                  }}
                />
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {listQuery.isLoading ? (
              <p className="text-muted-foreground text-center py-8">
                Loading notifications...
              </p>
            ) : notifications.length === 0 ? (
              <p className="text-muted-foreground text-center py-8">
                No notifications found
              </p>
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left py-3 px-2">ID</th>
                        <th className="text-left py-3 px-2">Dispute Ref</th>
                        <th className="text-left py-3 px-2">Channel</th>
                        <th className="text-left py-3 px-2">Recipient</th>
                        <th className="text-left py-3 px-2">Subject</th>
                        <th className="text-left py-3 px-2">Status</th>
                        <th className="text-left py-3 px-2">Sent At</th>
                      </tr>
                    </thead>
                    <tbody>
                      {notifications.map((n: any) => {
                        const ChannelIcon = CHANNEL_ICONS[n.channel] ?? Bell;
                        return (
                          <tr key={n.id} className="border-b hover:bg-muted/50">
                            <td className="py-3 px-2 font-mono text-xs">
                              #{n.id}
                            </td>
                            <td className="py-3 px-2 font-mono text-xs">
                              {n.disputeRef}
                            </td>
                            <td className="py-3 px-2">
                              <span className="flex items-center gap-1">
                                <ChannelIcon className="h-3 w-3" />
                                {n.channel}
                              </span>
                            </td>
                            <td className="py-3 px-2 text-xs">{n.recipient}</td>
                            <td className="py-3 px-2 max-w-[200px] truncate">
                              {n.subject}
                            </td>
                            <td className="py-3 px-2">
                              <Badge className={STATUS_COLORS[n.status] ?? ""}>
                                {n.status}
                              </Badge>
                            </td>
                            <td className="py-3 px-2 text-muted-foreground text-xs">
                              {n.sentAt
                                ? new Date(n.sentAt).toLocaleString()
                                : "—"}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
                <div className="flex justify-between items-center mt-4">
                  <p className="text-sm text-muted-foreground">
                    Page {page} of {Math.ceil(total / 20) || 1}
                  </p>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={page <= 1}
                      onClick={() => setPage(p => p - 1)}
                    >
                      Previous
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={page >= Math.ceil(total / 20)}
                      onClick={() => setPage(p => p + 1)}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
