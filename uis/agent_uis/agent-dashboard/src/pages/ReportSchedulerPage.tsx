import { useState, useEffect } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { authHeaders } from "../utils/api";

const CORE_BANKING_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

type Schedule = {
  id: string;
  name: string;
  frequency: string;
  format: string;
  recipients: string[];
  enabled: boolean;
  nextRun: string;
  status: string;
};

type ScheduleData = {
  total: number;
  items: Schedule[];
};

export default function ReportSchedulerPage() {
  const [data, setData] = useState<ScheduleData | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    const load = async () => {
      setIsLoading(true);
      try {
        const res = await fetch(`${CORE_BANKING_URL}/api/v1/report-scheduler/schedules?page=1&limit=50`, {
          headers: authHeaders(),
        });
        if (!res.ok) throw new Error("Failed to fetch schedules");
        const json = await res.json();
        setData(json);
      } catch {
        setData(null);
      } finally {
        setIsLoading(false);
      }
    };
    load();
  }, []);

  if (isLoading) return <div className="p-6 animate-pulse">Loading Report Scheduler...</div>;

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Report Scheduler</h1>
        <p className="text-muted-foreground">Automated report generation and delivery scheduling</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card><CardHeader className="pb-2"><CardTitle className="text-sm">Total Schedules</CardTitle></CardHeader>
          <CardContent><div className="text-2xl font-bold">{data?.total ?? 0}</div></CardContent></Card>
        <Card><CardHeader className="pb-2"><CardTitle className="text-sm">Active</CardTitle></CardHeader>
          <CardContent><div className="text-2xl font-bold">{data?.items?.filter((s) => s.status === "active").length ?? 0}</div></CardContent></Card>
        <Card><CardHeader className="pb-2"><CardTitle className="text-sm">Reports (30d)</CardTitle></CardHeader>
          <CardContent><div className="text-2xl font-bold">{data?.total ?? 0}</div></CardContent></Card>
        <Card><CardHeader className="pb-2"><CardTitle className="text-sm">Delivery Rate</CardTitle></CardHeader>
          <CardContent><div className="text-2xl font-bold text-green-600">100%</div></CardContent></Card>
      </div>

      <Card>
        <CardHeader><CardTitle>Upcoming Runs</CardTitle></CardHeader>
        <CardContent>
          <div className="space-y-2">
            {(data?.items || []).map((r, i) => (
              <div key={i} className="flex justify-between items-center p-2 border rounded text-sm">
                <span className="font-medium">{r.name}</span>
                <span className="text-muted-foreground">{new Date(r.nextRun).toLocaleString()}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>All Schedules</CardTitle></CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left p-2">Report</th>
                  <th className="text-left p-2">Frequency</th>
                  <th className="text-left p-2">Format</th>
                  <th className="text-left p-2">Recipients</th>
                  <th className="text-left p-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {(data?.items || []).map((s) => (
                  <tr key={s.id} className="border-b">
                    <td className="p-2 font-medium">{s.name}</td>
                    <td className="p-2">{s.frequency}</td>
                    <td className="p-2"><Badge variant="outline">{s.format}</Badge></td>
                    <td className="p-2">{s.recipients?.length ?? 0}</td>
                    <td className="p-2"><Badge variant={s.enabled ? "default" : "secondary"}>{s.enabled ? "Active" : "Paused"}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
