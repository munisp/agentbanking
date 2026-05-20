// @ts-nocheck
/**
 * Billing Dashboard Page — Sprint 80
 * Real-time billing metrics, revenue splits, reconciliation status,
 * audit trail, and tenant onboarding. RBAC-aware.
 */
import { useState, useMemo } from "react";
import { useAuth } from "@/_core/hooks/useAuth";
import { trpc } from "@/lib/trpc";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";

function formatNGN(amount: number): string {
  return new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency: "NGN",
    maximumFractionDigits: 0,
  }).format(amount);
}

function formatNumber(n: number): string {
  return new Intl.NumberFormat("en-NG").format(n);
}

export default function BillingDashboardPage() {
  const { user } = useAuth();

  const [tenantId] = useState(1);
  const [activeTab, setActiveTab] = useState("overview");

  // Live split metrics
  const { data: liveMetrics, isLoading: metricsLoading } =
    trpc.billingLedger.getLiveSplitMetrics.useQuery(
      { tenantId },
      { refetchInterval: 30000 }
    );

  // Revenue stream (real-time)
  const { data: revenueStream } =
    trpc.liveBillingDashboard.getRevenueStream.useQuery(
      { clientId: "XMTS", tenantId },
      { refetchInterval: 10000 }
    );

  // Reconciliation metrics
  const { data: reconMetrics } = trpc.revenueReconciliation.getMetrics.useQuery(
    { tenantId }
  );

  // Audit log
  const { data: auditLog } = trpc.billingAudit.query.useQuery({
    tenantId,
    limit: 20,
  });

  // Billing config
  const { data: billingConfig } =
    trpc.billingLedger.getClientBillingConfig.useQuery(
      // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch
      { tenantId, clientId: "XMTS" }
    );

  // Run reconciliation mutation
  const runRecon = trpc.revenueReconciliation.runReconciliation.useMutation({
    onSuccess: (data: any) => {
      toast.success(
        `Reconciliation Complete: Match rate ${data.matchRatePct}% | ${data.discrepantRecords} discrepancies`
      );
    },
    onError: (err: any) => {
      toast.error(`Reconciliation Failed: ${err.message}`);
    },
  });

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">
            Billing Engine Dashboard
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Real-time billing metrics, RBAC-enforced • Tenant {tenantId}
          </p>
        </div>
        <div className="flex gap-2">
          <Badge variant="outline" className="text-xs">
            {billingConfig?.billingModel || "loading..."}
          </Badge>
          <Badge
            variant={billingConfig?.provisioned ? "default" : "destructive"}
            className="text-xs"
          >
            {billingConfig?.provisioned ? "Provisioned" : "Not Provisioned"}
          </Badge>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Today's Gross Fees
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {metricsLoading
                ? "..."
                : formatNGN(liveMetrics?.today?.grossFees || 0)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {formatNumber(liveMetrics?.today?.transactionCount || 0)}{" "}
              transactions
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Platform Revenue (Today)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {formatNGN(liveMetrics?.today?.netPlatformRevenue || 0)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              Net after switch fees
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Month-to-Date Revenue
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {formatNGN(liveMetrics?.thisMonth?.grossFees || 0)}
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {formatNumber(liveMetrics?.thisMonth?.transactionCount || 0)}{" "}
              total tx
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Reconciliation Health
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {reconMetrics?.avgMatchRatePct || 0}%
            </div>
            <p className="text-xs text-muted-foreground mt-1">
              {reconMetrics?.batchesProcessed || 0} batches processed
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="overview">Revenue Stream</TabsTrigger>
          <TabsTrigger value="reconciliation">Reconciliation</TabsTrigger>
          <TabsTrigger value="audit">Audit Trail</TabsTrigger>
          <TabsTrigger value="onboarding">Tenant Config</TabsTrigger>
        </TabsList>

        {/* Revenue Stream Tab */}
        <TabsContent value="overview" className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Last Minute</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Transactions</span>
                    <span className="font-mono">
                      {formatNumber(
                        revenueStream?.lastMinute?.transactions || 0
                      )}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Gross Fees</span>
                    <span className="font-mono">
                      {formatNGN(revenueStream?.lastMinute?.grossFees || 0)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">
                      Platform Share
                    </span>
                    <span className="font-mono text-green-600">
                      {formatNGN(revenueStream?.lastMinute?.platformShare || 0)}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Last Hour</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Transactions</span>
                    <span className="font-mono">
                      {formatNumber(revenueStream?.lastHour?.transactions || 0)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Gross Fees</span>
                    <span className="font-mono">
                      {formatNGN(revenueStream?.lastHour?.grossFees || 0)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">
                      Platform Share
                    </span>
                    <span className="font-mono text-green-600">
                      {formatNGN(revenueStream?.lastHour?.platformShare || 0)}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Monthly breakdown */}
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">
                Revenue Split Breakdown (This Month)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <p className="text-xs text-muted-foreground">
                    Platform Share
                  </p>
                  <p className="text-lg font-bold">
                    {formatNGN(liveMetrics?.thisMonth?.platformShare || 0)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Client Share</p>
                  <p className="text-lg font-bold">
                    {formatNGN(liveMetrics?.thisMonth?.clientShare || 0)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">
                    Agent Commissions
                  </p>
                  <p className="text-lg font-bold">
                    {formatNGN(liveMetrics?.thisMonth?.agentCommissions || 0)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Switch Fees</p>
                  <p className="text-lg font-bold">
                    {formatNGN(liveMetrics?.thisMonth?.switchFees || 0)}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Reconciliation Tab */}
        <TabsContent value="reconciliation" className="space-y-4">
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={() =>
                runRecon.mutate({
                  clientId: "XMTS",
                  tenantId,
                  source: "tigerbeetle",
                  target: "postgres",
                  periodHours: 24,
                })
              }
              disabled={runRecon.isPending}
            >
              {runRecon.isPending
                ? "Running..."
                : "Run TigerBeetle ↔ Postgres"}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() =>
                runRecon.mutate({
                  clientId: "XMTS",
                  tenantId,
                  source: "postgres",
                  target: "interswitch",
                  periodHours: 24,
                })
              }
              disabled={runRecon.isPending}
            >
              Run Postgres ↔ Interswitch
            </Button>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Reconciliation Summary</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <p className="text-xs text-muted-foreground">Total Batches</p>
                  <p className="text-lg font-bold">
                    {formatNumber(reconMetrics?.batchesProcessed || 0)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">
                    Records Reconciled
                  </p>
                  <p className="text-lg font-bold">
                    {formatNumber(reconMetrics?.totalRecordsReconciled || 0)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Auto-Resolved</p>
                  <p className="text-lg font-bold text-green-600">
                    {formatNumber(reconMetrics?.autoResolved || 0)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Manual Review</p>
                  <p className="text-lg font-bold text-amber-600">
                    {formatNumber(reconMetrics?.manualReviewRequired || 0)}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Audit Trail Tab */}
        <TabsContent value="audit" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">
                Recent Billing Audit Events
              </CardTitle>
            </CardHeader>
            <CardContent>
              {auditLog?.logs?.length === 0 && (
                <p className="text-sm text-muted-foreground">
                  No audit events recorded yet.
                </p>
              )}
              <div className="space-y-2">
                {auditLog?.logs?.map((entry: any, i: number) => (
                  <div
                    key={i}
                    className="flex items-center justify-between py-2 border-b last:border-0"
                  >
                    <div>
                      <p className="text-sm font-medium">{entry.action}</p>
                      <p className="text-xs text-muted-foreground">
                        {entry.userName} • {entry.resourceType}/
                        {entry.resourceId}
                      </p>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {entry.createdAt
                        ? new Date(entry.createdAt).toLocaleString()
                        : ""}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tenant Config Tab */}
        <TabsContent value="onboarding" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Billing Configuration</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-muted-foreground">Billing Model</p>
                  <p className="text-sm font-medium">
                    {billingConfig?.billingModel || "Not configured"}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Auto Renew</p>
                  <p className="text-sm font-medium">
                    {billingConfig?.autoRenew ? "Yes" : "No"}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">
                    Effective Date
                  </p>
                  <p className="text-sm font-medium">
                    {billingConfig?.effectiveDate
                      ? new Date(
                          billingConfig.effectiveDate
                        ).toLocaleDateString()
                      : "N/A"}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Contract End</p>
                  <p className="text-sm font-medium">
                    {billingConfig?.contractEndDate
                      ? new Date(
                          billingConfig.contractEndDate
                        ).toLocaleDateString()
                      : "N/A"}
                  </p>
                </div>
              </div>

              {billingConfig?.revenueShareConfig ? (
                <div className="mt-4 pt-4 border-t">
                  <h4 className="text-sm font-medium mb-2">
                    Revenue Share Config
                  </h4>
                  <pre className="text-xs bg-muted p-2 rounded overflow-auto">
                    {String(
                      JSON.stringify(billingConfig.revenueShareConfig, null, 2)
                    )}
                  </pre>
                </div>
              ) : null}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
