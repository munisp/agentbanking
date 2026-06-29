// @ts-nocheck
import { useState } from "react";
import DashboardLayout from "@/components/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { trpc } from "@/lib/trpc";
import {
  Brain,
  Database,
  Network,
  Cpu,
  FlaskConical,
  Workflow,
  Activity,
  CheckCircle,
  XCircle,
  Play,
  ArrowUpDown,
  RefreshCw,
} from "lucide-react";

export default function LakehouseAiDashboard() {
  const [tab, setTab] = useState("overview");
  const health = trpc.lakehouseAi.health.useQuery(undefined, {
    refetchInterval: 30000,
  });
  const analytics = trpc.lakehouseAi.analytics.useQuery(undefined, {
    refetchInterval: 15000,
  });
  const models = trpc.lakehouseAi.listModels.useQuery();
  const batchJobs = trpc.lakehouseAi.listBatchJobs.useQuery(undefined, {
    refetchInterval: 5000,
  });
  const lineage = trpc.lakehouseAi.dataLineage.useQuery();
  const promoteMut = trpc.lakehouseAi.promoteModel.useMutation({
    onSuccess: () => models.refetch(),
  });
  const submitBatch = trpc.lakehouseAi.submitBatchJob.useMutation({
    onSuccess: () => batchJobs.refetch(),
  });

  const svcStatus = health.data?.services ?? {};
  const stats = analytics.data;

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Brain className="h-7 w-7 text-purple-500" /> Lakehouse AI
              Integration
            </h1>
            <p className="text-muted-foreground mt-1">
              Unified AI/ML platform — Qdrant · FalkorDB · CocoIndex · Ollama ·
              ART
            </p>
          </div>
          <Badge variant={health.data?.allHealthy ? "default" : "destructive"}>
            {health.data?.allHealthy ? "All Services Healthy" : "Degraded"}
          </Badge>
        </div>

        {/* Service Health Cards */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {[
            {
              key: "qdrant",
              label: "Qdrant",
              icon: Database,
              color: "text-blue-500",
            },
            {
              key: "falkordb",
              label: "FalkorDB",
              icon: Network,
              color: "text-green-500",
            },
            {
              key: "ollama",
              label: "Ollama",
              icon: Cpu,
              color: "text-orange-500",
            },
            {
              key: "lakehouse",
              label: "Lakehouse",
              icon: Activity,
              color: "text-cyan-500",
            },
            {
              key: "cocoindex",
              label: "CocoIndex",
              icon: Workflow,
              color: "text-purple-500",
            },
          ].map(svc => (
            <Card key={svc.key}>
              <CardContent className="pt-4 text-center">
                <svc.icon className={`h-8 w-8 mx-auto ${svc.color}`} />
                <p className="font-medium mt-2">{svc.label}</p>
                <Badge
                  variant={
                    (svcStatus as any)[svc.key] === "connected"
                      ? "default"
                      : "secondary"
                  }
                  className="mt-1"
                >
                  {(svcStatus as any)[svc.key] === "connected" ? (
                    <>
                      <CheckCircle className="h-3 w-3 mr-1" /> Connected
                    </>
                  ) : (
                    <>
                      <XCircle className="h-3 w-3 mr-1" /> Fallback
                    </>
                  )}
                </Badge>
              </CardContent>
            </Card>
          ))}
        </div>

        <Tabs value={tab} onValueChange={setTab}>
          <TabsList>
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="models">Model Registry</TabsTrigger>
            <TabsTrigger value="batch">Batch Inference</TabsTrigger>
            <TabsTrigger value="lineage">Data Lineage</TabsTrigger>
          </TabsList>

          {/* Overview Tab */}
          <TabsContent value="overview" className="space-y-4">
            {stats && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">Qdrant Vectors</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-2xl font-bold">
                      {stats.services.qdrant.vectors.toLocaleString()}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {stats.services.qdrant.collections} collections · p99{" "}
                      {stats.services.qdrant.latencyP99Ms}ms
                    </p>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">FalkorDB Graph</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-2xl font-bold">
                      {stats.services.falkordb.nodes.toLocaleString()}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {stats.services.falkordb.edges.toLocaleString()} edges ·{" "}
                      {stats.services.falkordb.queriesPerSec} q/s
                    </p>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">Ollama LLM</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-2xl font-bold">
                      {stats.services.ollama.models}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      models · {stats.services.ollama.tokensPerSec} tok/s
                    </p>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm">Lakehouse</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-2xl font-bold">
                      {(
                        stats.services.lakehouse.totalRecords / 1000000
                      ).toFixed(1)}
                      M
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {stats.services.lakehouse.tables} tables ·{" "}
                      {stats.services.lakehouse.storageGb}GB
                    </p>
                  </CardContent>
                </Card>
              </div>
            )}
            {stats && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Feature Store</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-xl font-bold">
                      {stats.featureStore.totalFeatures} features
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {stats.featureStore.entityTypes.join(", ") ||
                        "No entities yet"}
                    </p>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Model Registry</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-xl font-bold">
                      {stats.modelRegistry.totalModels} models
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {stats.modelRegistry.production} in production · avg
                      accuracy{" "}
                      {(stats.modelRegistry.avgAccuracy * 100).toFixed(1)}%
                    </p>
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader>
                    <CardTitle className="text-sm">Batch Inference</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-xl font-bold">
                      {stats.batchInference.totalRecordsProcessed.toLocaleString()}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {stats.batchInference.running} running ·{" "}
                      {stats.batchInference.completed} completed
                    </p>
                  </CardContent>
                </Card>
              </div>
            )}
          </TabsContent>

          {/* Model Registry Tab */}
          <TabsContent value="models" className="space-y-4">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left">
                    <th className="p-2">Model</th>
                    <th className="p-2">Version</th>
                    <th className="p-2">Framework</th>
                    <th className="p-2">Type</th>
                    <th className="p-2">Status</th>
                    <th className="p-2">Key Metric</th>
                    <th className="p-2">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {models.data?.models.map(m => (
                    <tr key={m.id} className="border-b">
                      <td className="p-2 font-medium">{m.name}</td>
                      <td className="p-2">{m.version}</td>
                      <td className="p-2">
                        <Badge variant="outline">{m.framework}</Badge>
                      </td>
                      <td className="p-2">{m.type}</td>
                      <td className="p-2">
                        <Badge
                          variant={
                            m.status === "production"
                              ? "default"
                              : m.status === "staging"
                                ? "secondary"
                                : "outline"
                          }
                        >
                          {m.status}
                        </Badge>
                      </td>
                      <td className="p-2">
                        {Object.entries(m.metrics)
                          .slice(0, 1)
                          .map(([k, v]) => (
                            <span key={k}>
                              {k}:{" "}
                              {typeof v === "number" && v < 1
                                ? (v * 100).toFixed(1) + "%"
                                : v}
                            </span>
                          ))}
                      </td>
                      <td className="p-2">
                        {m.status === "staging" && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() =>
                              promoteMut.mutate({
                                modelId: m.id,
                                targetStatus: "production",
                              })
                            }
                          >
                            <ArrowUpDown className="h-3 w-3 mr-1" /> Promote
                          </Button>
                        )}
                        {m.status === "production" && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() =>
                              promoteMut.mutate({
                                modelId: m.id,
                                targetStatus: "archived",
                              })
                            }
                          >
                            Archive
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </TabsContent>

          {/* Batch Inference Tab */}
          <TabsContent value="batch" className="space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="font-semibold">Batch Jobs</h3>
              <Button
                size="sm"
                onClick={() =>
                  submitBatch.mutate({
                    modelId: "mdl-fraud-001",
                    inputSource: "lakehouse://gold/transactions_daily",
                    outputSink: "qdrant://transaction_embeddings",
                    recordsTotal: 25000,
                  })
                }
              >
                <Play className="h-3 w-3 mr-1" /> New Batch Job
              </Button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left">
                    <th className="p-2">Job ID</th>
                    <th className="p-2">Model</th>
                    <th className="p-2">Source → Sink</th>
                    <th className="p-2">Progress</th>
                    <th className="p-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {batchJobs.data?.jobs.map(j => (
                    <tr key={j.id} className="border-b">
                      <td className="p-2 font-mono">{j.id}</td>
                      <td className="p-2">{j.modelId}</td>
                      <td className="p-2 text-xs">
                        {j.inputSource} → {j.outputSink}
                      </td>
                      <td className="p-2">
                        <div className="flex items-center gap-2">
                          <div className="w-24 h-2 bg-muted rounded-full overflow-hidden">
                            <div
                              className="h-full bg-primary rounded-full"
                              style={{
                                width: `${(j.recordsProcessed / j.recordsTotal) * 100}%`,
                              }}
                            />
                          </div>
                          <span className="text-xs">
                            {Math.round(
                              (j.recordsProcessed / j.recordsTotal) * 100
                            )}
                            %
                          </span>
                        </div>
                      </td>
                      <td className="p-2">
                        <Badge
                          variant={
                            j.status === "completed"
                              ? "default"
                              : j.status === "running"
                                ? "secondary"
                                : j.status === "failed"
                                  ? "destructive"
                                  : "outline"
                          }
                        >
                          {j.status === "running" && (
                            <RefreshCw className="h-3 w-3 mr-1 animate-spin" />
                          )}
                          {j.status}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </TabsContent>

          {/* Data Lineage Tab */}
          <TabsContent value="lineage" className="space-y-4">
            <h3 className="font-semibold">
              Data Pipelines (Lakehouse → AI Services)
            </h3>
            <div className="space-y-3">
              {lineage.data?.pipelines.map(p => (
                <Card key={p.id}>
                  <CardContent className="pt-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <p className="font-medium">{p.name}</p>
                        <div className="flex items-center gap-2 mt-1 text-xs text-muted-foreground">
                          <Badge variant="outline">{p.source.type}</Badge>
                          <span>→</span>
                          <Badge variant="outline">{p.transform.type}</Badge>
                          <span>→</span>
                          <Badge variant="outline">{p.sink.type}</Badge>
                        </div>
                        <p className="text-xs text-muted-foreground mt-1">
                          Schedule: {p.schedule} ·{" "}
                          {p.recordsPerRun.toLocaleString()} records/run
                        </p>
                      </div>
                      <div className="text-right">
                        <Badge
                          variant={
                            p.status === "active" ? "default" : "secondary"
                          }
                        >
                          {p.status}
                        </Badge>
                        <p className="text-xs text-muted-foreground mt-1">
                          Steps: {p.transform.steps.join(" → ")}
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </DashboardLayout>
  );
}
