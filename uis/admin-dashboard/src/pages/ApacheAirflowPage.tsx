import { trpc } from "@/lib/trpc";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export default function ApacheAirflowPage() {
  // @ts-ignore Sprint 85
  const { data, isLoading } = trpc.apacheAirflow.dashboard.useQuery();
  // @ts-ignore Sprint 85
  const dags = trpc.apacheAirflow.listDags.useQuery();
  // @ts-ignore Sprint 85
  const triggerDag = trpc.apacheAirflow.triggerDag.useMutation();

  if (isLoading)
    return (
      <div className="p-6 animate-pulse">Loading Airflow Dashboard...</div>
    );

  const overview = data?.overview;

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">
          Apache Airflow — Workflow Orchestration
        </h1>
        <p className="text-muted-foreground">
          DAG scheduling, task monitoring, and pipeline orchestration
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Active DAGs</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {overview?.activeDags ?? 0}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Total Tasks</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {overview?.totalTaskInstances ?? 0}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Avg Success Rate</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {overview?.avgSuccessRate ?? 0}%
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm">Failed (24h)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">
              {overview?.failedTasks24h ?? 0}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>DAGs by Tag</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {(data?.dagsByTag || []).map((t: any) => (
              <Badge
                key={t.tag}
                variant="outline"
                className="text-sm px-3 py-1"
              >
                {t.tag}: {t.count}
              </Badge>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>DAG Pipeline Status</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left p-2">DAG ID</th>
                  <th className="text-left p-2">Schedule</th>
                  <th className="text-left p-2">Success Rate</th>
                  <th className="text-left p-2">Status</th>
                  <th className="text-left p-2">Tags</th>
                  <th className="p-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {(dags.data?.dags || []).map((d: any) => (
                  <tr key={d.dagId} className="border-b">
                    <td className="p-2 font-medium">{d.dagId}</td>
                    <td className="p-2 font-mono text-xs">{d.schedule}</td>
                    <td className="p-2">{d.successRate}%</td>
                    <td className="p-2">
                      <Badge variant={d.isPaused ? "secondary" : "default"}>
                        {d.isPaused ? "Paused" : "Active"}
                      </Badge>
                    </td>
                    <td className="p-2">{d.tags?.join(", ")}</td>
                    <td className="p-2 text-center">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => triggerDag.mutate({ dagId: d.dagId })}
                      >
                        Trigger
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {data?.recentFailures && data.recentFailures.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Recent Failures (24h)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {data.recentFailures.map((f: any) => (
                <div
                  key={f.taskId}
                  className="flex items-center gap-3 p-2 border rounded text-sm"
                >
                  <Badge variant="destructive">FAILED</Badge>
                  <span className="font-medium">{f.dagId}</span>
                  <span className="text-muted-foreground">{f.taskId}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
