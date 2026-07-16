import { trpc } from "@/lib/trpc";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import DashboardLayout from "@/components/DashboardLayout";

export default function BatchProcessingPage() {
  const { data, isLoading, refetch } =
    trpc.batchProcessing.dashboard.useQuery();
  if (isLoading)
    return (
      <DashboardLayout>
        <div className="p-8 text-center animate-pulse">
          Loading batch jobs...
        </div>
      </DashboardLayout>
    );
  const d = data as any;
  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Batch Processing</h1>
            <p className="text-muted-foreground">
              Bulk transaction and data processing jobs
            </p>
          </div>
          <Button onClick={() => refetch()}>Refresh</Button>
        </div>
        <div className="grid grid-cols-3 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="text-3xl font-bold">{d?.totalJobs ?? 0}</div>
              <p className="text-sm text-muted-foreground">Total Jobs</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-3xl font-bold text-blue-500">
                {d?.avgProcessingTime ?? "0s"}
              </div>
              <p className="text-sm text-muted-foreground">
                Avg Processing Time
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-3xl font-bold text-green-500">
                {
                  (d?.jobs ?? []).filter((j: any) => j.status === "completed")
                    .length
                }
              </div>
              <p className="text-sm text-muted-foreground">Completed Today</p>
            </CardContent>
          </Card>
        </div>
        <Card>
          <CardHeader>
            <CardTitle>Batch Jobs</CardTitle>
          </CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left">
                  <th className="p-3">Job ID</th>
                  <th className="p-3">Type</th>
                  <th className="p-3">Records</th>
                  <th className="p-3">Progress</th>
                  <th className="p-3">Status</th>
                  <th className="p-3">Started</th>
                </tr>
              </thead>
              <tbody>
                {(d?.jobs ?? []).map((j: any, i: number) => (
                  <tr key={i} className="border-b hover:bg-muted/50">
                    <td className="p-3 font-mono">
                      {j.id ?? `BATCH-${i + 1}`}
                    </td>
                    <td className="p-3">{j.type ?? "transaction"}</td>
                    <td className="p-3">
                      {j.processedRecords ?? 0}/{j.totalRecords ?? 0}
                    </td>
                    <td className="p-3">
                      <div className="flex items-center gap-2">
                        <Progress
                          value={j.progress ?? 0}
                          className="w-24 h-2"
                        />
                        <span className="text-xs">{j.progress ?? 0}%</span>
                      </div>
                    </td>
                    <td className="p-3">
                      <Badge
                        className={
                          j.status === "completed"
                            ? "bg-green-500"
                            : j.status === "running"
                              ? "bg-blue-500"
                              : j.status === "failed"
                                ? "bg-red-500"
                                : "bg-amber-500"
                        }
                      >
                        {j.status ?? "pending"}
                      </Badge>
                    </td>
                    <td className="p-3 text-xs">{j.startedAt ?? "N/A"}</td>
                  </tr>
                ))}
                {(!d?.jobs || d.jobs.length === 0) && (
                  <tr>
                    <td
                      colSpan={6}
                      className="p-8 text-center text-muted-foreground"
                    >
                      No batch jobs
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
