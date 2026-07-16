import { trpc } from "@/lib/trpc";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Database, Shield, HardDrive, RefreshCw } from "lucide-react";

export default function BackupDRPage() {
  // @ts-ignore Sprint 85
  const { data } = trpc.backupDr.dashboard.useQuery();
  // @ts-ignore Sprint 85
  const triggerMut = trpc.backupDr.triggerBackup.useMutation();
  // @ts-ignore Sprint 85
  const testMut = trpc.backupDr.testFailover.useMutation();

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Backup & Disaster Recovery</h1>
          <p className="text-muted-foreground">
            Automated backups, DR testing, failover readiness
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            onClick={() => triggerMut.mutate({ type: "full" })}
            disabled={triggerMut.isPending}
          >
            <Database className="w-4 h-4 mr-2" /> Full Backup
          </Button>
          <Button
            variant="outline"
            onClick={() => testMut.mutate()}
            disabled={testMut.isPending}
          >
            <Shield className="w-4 h-4 mr-2" /> Test Failover
          </Button>
        </div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {[
          // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
          {
            label: "Last Backup",
            value: data?.lastBackup
              ? new Date(data.lastBackup.timestamp).toLocaleString()
              : "N/A",
          },
          { label: "DR Region", value: data?.drStatus?.drRegion ?? "N/A" },
          { label: "RPO", value: data?.drStatus?.rpo ?? "N/A" },
          { label: "RTO", value: data?.drStatus?.rto ?? "N/A" },
        ].map((s, i) => (
          <Card key={i}>
            <CardContent className="pt-4">
              <p className="text-lg font-bold">{s.value}</p>
              <p className="text-xs text-muted-foreground">{s.label}</p>
            </CardContent>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Recent Backups</CardTitle>
        </CardHeader>
        <CardContent>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b">
                <th className="text-left p-2">ID</th>
                <th className="text-left p-2">Type</th>
                <th className="text-left p-2">Size</th>
                <th className="text-left p-2">Status</th>
                <th className="text-left p-2">Date</th>
              </tr>
            </thead>
            <tbody>
              {(data?.recentBackups ?? []).map((b: any, i: number) => (
                <tr key={i} className="border-b">
                  <td className="p-2">{b.id}</td>
                  <td className="p-2">
                    <Badge>{b.type}</Badge>
                  </td>
                  <td className="p-2">{b.sizeMb} MB</td>
                  <td className="p-2">
                    <Badge
                      variant={
                        b.status === "completed" ? "default" : "destructive"
                      }
                    >
                      {b.status}
                    </Badge>
                  </td>
                  <td className="p-2">
                    {new Date(b.timestamp).toLocaleDateString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </CardContent>
      </Card>
    </div>
  );
}
