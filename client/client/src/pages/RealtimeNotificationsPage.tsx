import { trpc } from "@/lib/trpc";
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Bell, Send, Check, Trash2, Settings } from "lucide-react";

export default function RealtimeNotificationsPage() {
  const { data: dashboard, isLoading } =
    // @ts-ignore Sprint 85
    trpc.realtimeNotifications.dashboard.useQuery();
  const markRead = trpc.realtimeNotifications.markRead.useMutation();
  // @ts-ignore Sprint 85
  const send = trpc.realtimeNotifications.broadcast.useMutation();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");

  if (isLoading)
    return <div className="p-8 text-center">Loading notifications...</div>;
  const d = dashboard!;

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Bell className="h-6 w-6" /> Real-time Notification Center
          </h1>
          <p className="text-muted-foreground mt-1">
            WebSocket-powered alerts and system messages
          </p>
        </div>
      </div>
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold">{d.totalNotifications}</div>
            <p className="text-sm text-muted-foreground">Total Notifications</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold text-blue-500">
              {d.unreadCount}
            </div>
            <p className="text-sm text-muted-foreground">Unread</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold text-green-500">
              {d.sentLast24h}
            </div>
            <p className="text-sm text-muted-foreground">Delivered Today</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="text-2xl font-bold text-orange-500">
              {d.byChannel?.length}
            </div>
            <p className="text-sm text-muted-foreground">Active Channels</p>
          </CardContent>
        </Card>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Send Notification</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Input
            placeholder="Notification title"
            value={title}
            onChange={e => setTitle(e.target.value)}
          />
          <Input
            placeholder="Notification body"
            value={body}
            onChange={e => setBody(e.target.value)}
          />
          <Button
            onClick={() => {
              send.mutate({
                title,
                body,
                type: "system" as const,
                priority: "low" as const,
              });
              setTitle("");
              setBody("");
            }}
          >
            <Send className="h-4 w-4 mr-2" /> Send
          </Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Recent Notifications</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {d.recentNotifications.map((n: any) => (
              <div
                key={n.id}
                className={`flex items-center justify-between p-3 rounded-lg border ${n.read ? "bg-muted/30" : "bg-blue-500/10 border-blue-500/30"}`}
              >
                <div>
                  <p className="font-medium">{n.title}</p>
                  <p className="text-sm text-muted-foreground">{n.body}</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    {new Date(n.createdAt).toLocaleString()} · {n.channel} ·{" "}
                    {n.priority}
                  </p>
                </div>
                <div className="flex gap-2">
                  {!n.read && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        // @ts-ignore Sprint 85
                        markRead.mutate({ notificationIds: [n.id] })
                      }
                    >
                      <Check className="h-3 w-3" />
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Channel Statistics</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-3 gap-4">
            {d.byChannel.map((c: any) => (
              <div key={c.channel} className="p-4 border rounded-lg">
                <h4 className="font-medium capitalize">{c.channel}</h4>
                <p className="text-2xl font-bold mt-1">{c.sent}</p>
                <p className="text-sm text-muted-foreground">
                  Delivered: {c.delivered} · Read: {c.read}
                </p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
