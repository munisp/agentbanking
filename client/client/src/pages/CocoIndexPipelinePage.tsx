import { trpc } from "@/lib/trpc";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Activity,
  Play,
  Pause,
  Database,
  Loader2,
  RefreshCw,
} from "lucide-react";
export default function CocoIndexPipelinePage() {
  // @ts-ignore Sprint 85
  const analytics = trpc.cocoIndexPipeline.analytics.useQuery();
  // @ts-ignore Sprint 85
  const pipelines = trpc.cocoIndexPipeline.listPipelines.useQuery();
  // @ts-ignore Sprint 85
  const runs = trpc.cocoIndexPipeline.listRuns.useQuery();
  // @ts-ignore Sprint 85
  const triggerMut = trpc.cocoIndexPipeline.triggerRun.useMutation({
    // @ts-ignore Sprint 85
    onSuccess: d => {
      if (d.success)
        alert(`Pipeline triggered: ${d.recordsProcessed} records processed`);
    },
  });
  // @ts-ignore Sprint 85
  const toggleMut = trpc.cocoIndexPipeline.togglePipeline.useMutation({
    onSuccess: () => {
      pipelines.refetch();
    },
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">CocoIndex Data Pipeline</h1>
          <p className="text-muted-foreground">
            ETL orchestration: PostgreSQL CDC → Qdrant / FalkorDB / Lakehouse
          </p>
        </div>
        <Badge variant="default">
          {analytics.data?.activePipelines ?? 0} active pipelines
        </Badge>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">
              Total Pipelines
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {analytics.data?.totalPipelines ?? 0}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">
              Records Processed
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {(analytics.data?.totalRecordsProcessed ?? 0).toLocaleString()}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">
              Success Rate
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {analytics.data?.successRate ?? 100}%
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-muted-foreground">
              Avg Throughput
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {analytics.data?.avgThroughput ?? 0} rec/s
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="pipelines">
        <TabsList>
          <TabsTrigger value="pipelines">
            <Database className="w-4 h-4 mr-1" />
            Pipelines
          </TabsTrigger>
          <TabsTrigger value="runs">
            <Activity className="w-4 h-4 mr-1" />
            Run History
          </TabsTrigger>
          <TabsTrigger value="sinks">
            <RefreshCw className="w-4 h-4 mr-1" />
            Sink Distribution
          </TabsTrigger>
        </TabsList>

        <TabsContent value="pipelines" className="space-y-4">
          {pipelines.data?.pipelines?.map((p: any) => (
            <Card key={p.id}>
              <CardContent className="pt-4">
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="font-semibold">{p.name}</h3>
                      <Badge
                        variant={
                          p.status === "active"
                            ? "default"
                            : p.status === "paused"
                              ? "secondary"
                              : "destructive"
                        }
                      >
                        {p.status}
                      </Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">
                      {p.sourceType} → {p.transformCount} transforms →{" "}
                      {p.sinkType} | Schedule: {p.schedule}
                    </p>
                    {p.lastRun && (
                      <p className="text-xs text-muted-foreground mt-1">
                        Last run: {p.lastRun.recordsProcessed.toLocaleString()}{" "}
                        records, {p.lastRun.errors} errors
                      </p>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        toggleMut.mutate({
                          pipelineId: p.id,
                          action: p.status === "active" ? "pause" : "resume",
                        })
                      }
                    >
                      {p.status === "active" ? (
                        <Pause className="w-4 h-4" />
                      ) : (
                        <Play className="w-4 h-4" />
                      )}
                    </Button>
                    <Button
                      size="sm"
                      onClick={() => triggerMut.mutate({ pipelineId: p.id })}
                      disabled={triggerMut.isPending}
                    >
                      {triggerMut.isPending ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Play className="w-4 h-4" />
                      )}
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </TabsContent>

        <TabsContent value="runs" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Recent Pipeline Runs</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {runs.data?.runs?.map((r: any) => (
                  <div
                    key={r.id}
                    className="p-3 border rounded-lg flex justify-between items-center"
                  >
                    <div>
                      <p className="font-medium">{r.pipelineId}</p>
                      <p className="text-sm text-muted-foreground">
                        {r.recordsProcessed.toLocaleString()} records |{" "}
                        {r.recordsFailed} failed | {r.metrics.throughput} rec/s
                      </p>
                    </div>
                    <Badge
                      variant={
                        r.status === "completed"
                          ? "default"
                          : r.status === "failed"
                            ? "destructive"
                            : "secondary"
                      }
                    >
                      {r.status}
                    </Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="sinks" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Sink Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4">
                <div className="p-4 border rounded-lg text-center">
                  <p className="text-2xl font-bold">
                    {analytics.data?.sinkDistribution?.qdrant ?? 0}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Qdrant Pipelines
                  </p>
                </div>
                <div className="p-4 border rounded-lg text-center">
                  <p className="text-2xl font-bold">
                    {analytics.data?.sinkDistribution?.falkordb ?? 0}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    FalkorDB Pipelines
                  </p>
                </div>
                <div className="p-4 border rounded-lg text-center">
                  <p className="text-2xl font-bold">
                    {analytics.data?.sinkDistribution?.iceberg ?? 0}
                  </p>
                  <p className="text-sm text-muted-foreground">
                    Iceberg/Lakehouse Pipelines
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
