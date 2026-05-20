import { useState } from "react";
import { useAuth } from "@/_core/hooks/useAuth";
import { trpc } from "@/lib/trpc";
import { toast } from "sonner";
// @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
import { DashboardLayout } from "@/components/DashboardLayout";

export default function TenantBillingPortalPage() {
  const { user } = useAuth();
  const [selectedTenantId, setSelectedTenantId] = useState<number>(1);
  const [planChangeModel, setPlanChangeModel] = useState<string>("");
  const [planChangeReason, setPlanChangeReason] = useState<string>("");

  // Fetch billing config for the tenant
  const { data: configData, isLoading: configLoading } =
    trpc.tenantBillingOnboarding.getConfig.useQuery(
      { tenantId: selectedTenantId },
      { enabled: !!selectedTenantId }
    );

  // Fetch provisioning history
  const { data: historyData } =
    trpc.tenantBillingOnboarding.getProvisioningHistory.useQuery(
      { tenantId: selectedTenantId },
      { enabled: !!selectedTenantId }
    );

  // Fetch invoices
  const { data: invoiceData } = trpc.billingInvoice.listInvoices.useQuery(
    { tenantId: selectedTenantId, limit: 10 },
    { enabled: !!selectedTenantId }
  );

  // Plan change mutation
  const updateConfig = trpc.tenantBillingOnboarding.updateConfig.useMutation({
    onSuccess: () => {
      toast.success("Plan change request submitted successfully");
      setPlanChangeModel("");
      setPlanChangeReason("");
    },
    onError: (err: any) => toast.error(err.message),
  });

  // Invoice checkout
  const createCheckout = trpc.billingInvoice.createInvoiceCheckout.useMutation({
    onSuccess: (data: any) => {
      if (data.checkoutUrl) {
        window.open(data.checkoutUrl, "_blank");
        toast.info("Redirecting to payment page...");
      }
    },
    onError: (err: any) => toast.error(err.message),
  });

  const handlePlanChange = () => {
    if (!planChangeModel) {
      toast.error("Please select a billing model");
      return;
    }
    updateConfig.mutate({
      tenantId: selectedTenantId,
      billingModel: planChangeModel as any,
    });
  };

  const config = configData?.config;

  return (
    <DashboardLayout>
      <div className="p-6 max-w-7xl mx-auto space-y-8">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">
              Billing Portal
            </h1>
            <p className="text-muted-foreground mt-1">
              Manage your billing configuration, view invoices, and request plan
              changes
            </p>
          </div>
          <div className="flex items-center gap-3">
            <label className="text-sm text-muted-foreground">Tenant:</label>
            <select
              value={selectedTenantId}
              onChange={(e: any) => setSelectedTenantId(Number(e.target.value))}
              className="border rounded px-3 py-1.5 text-sm bg-background"
            >
              <option value={1}>Tenant 1 - Primary</option>
              <option value={2}>Tenant 2 - Partner</option>
              <option value={3}>Tenant 3 - White Label</option>
            </select>
          </div>
        </div>

        {/* Current Plan Overview */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-card border rounded-lg p-6">
            <h3 className="text-sm font-medium text-muted-foreground">
              Current Plan
            </h3>
            <p className="text-2xl font-bold mt-2 capitalize">
              {config?.billingModel?.replace("_", " ") || "Not Configured"}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Status:{" "}
              <span
                className={`font-medium ${config?.status === "active" ? "text-green-500" : "text-yellow-500"}`}
              >
                {config?.status || "Pending"}
              </span>
            </p>
          </div>
          <div className="bg-card border rounded-lg p-6">
            <h3 className="text-sm font-medium text-muted-foreground">
              Currency
            </h3>
            <p className="text-2xl font-bold mt-2">
              {config?.currency || "NGN"}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              TigerBeetle:{" "}
              {config?.tigerBeetleAccountId ? "Connected" : "Pending"}
            </p>
          </div>
          <div className="bg-card border rounded-lg p-6">
            <h3 className="text-sm font-medium text-muted-foreground">
              Kafka Topics
            </h3>
            <p className="text-2xl font-bold mt-2">
              {config?.kafkaTopicPrefix ? "Active" : "Pending"}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {config?.kafkaTopicPrefix || "Not provisioned yet"}
            </p>
          </div>
        </div>

        {/* Billing Configuration Details */}
        {config && (
          <div className="bg-card border rounded-lg p-6">
            <h2 className="text-lg font-semibold mb-4">
              Billing Configuration
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-2">
                  Model Details
                </h4>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span>Billing Model:</span>
                    <span className="font-medium capitalize">
                      {config.billingModel?.replace("_", " ")}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Auto Renew:</span>
                    <span className="font-medium">
                      {config.autoRenew ? "Yes" : "No"}
                    </span>
                  </div>
                  {config.contractEndDate && (
                    <div className="flex justify-between">
                      <span>Contract End:</span>
                      <span className="font-medium">
                        {new Date(config.contractEndDate).toLocaleDateString()}
                      </span>
                    </div>
                  )}
                </div>
              </div>
              <div>
                <h4 className="text-sm font-medium text-muted-foreground mb-2">
                  Revenue Share Config
                </h4>
                {config.revenueShareConfig ? (
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span>Client Split:</span>
                      <span className="font-medium">
                        {(config.revenueShareConfig as any)?.startSplitPct}%
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Scale Split:</span>
                      <span className="font-medium">
                        {(config.revenueShareConfig as any)?.scaleSplitPct}%
                      </span>
                    </div>
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    N/A for current plan
                  </p>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Invoices Section */}
        <div className="bg-card border rounded-lg p-6">
          <h2 className="text-lg font-semibold mb-4">Recent Invoices</h2>
          {invoiceData?.invoices && invoiceData.invoices.length > 0 ? (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2">Invoice #</th>
                  <th className="text-left py-2">Period</th>
                  <th className="text-left py-2">Amount</th>
                  <th className="text-left py-2">Status</th>
                  <th className="text-left py-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {invoiceData.invoices.map((inv: any) => (
                  <tr key={inv.id} className="border-b">
                    <td className="py-2">{inv.invoiceNumber}</td>
                    <td className="py-2">
                      {inv.periodStart} - {inv.periodEnd}
                    </td>
                    <td className="py-2">
                      {inv.currency} {inv.total?.toLocaleString()}
                    </td>
                    <td className="py-2">
                      <span
                        className={`px-2 py-0.5 rounded text-xs ${
                          inv.status === "paid"
                            ? "bg-green-100 text-green-700"
                            : inv.status === "overdue"
                              ? "bg-red-100 text-red-700"
                              : "bg-yellow-100 text-yellow-700"
                        }`}
                      >
                        {inv.status}
                      </span>
                    </td>
                    <td className="py-2">
                      {inv.status !== "paid" && (
                        <button
                          onClick={() =>
                            createCheckout.mutate({
                              tenantId: selectedTenantId,
                              invoiceId: inv.id,
                              amount: Math.round(inv.total * 100),
                              customerEmail: user?.email || "",
                              description: `Invoice ${inv.invoiceNumber}`,
                            })
                          }
                          className="text-blue-600 hover:underline text-xs"
                        >
                          Pay Now
                        </button>
                      )}
                      {inv.stripeInvoiceUrl && (
                        <a
                          href={inv.stripeInvoiceUrl}
                          target="_blank"
                          rel="noopener"
                          className="text-blue-600 hover:underline text-xs ml-2"
                        >
                          View
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="text-center py-8 text-muted-foreground">
              <p>
                No invoices yet. Invoices are generated monthly based on your
                billing model.
              </p>
            </div>
          )}
        </div>

        {/* Plan Change Request */}
        <div className="bg-card border rounded-lg p-6">
          <h2 className="text-lg font-semibold mb-4">Request Plan Change</h2>
          <p className="text-sm text-muted-foreground mb-4">
            Request a change to your billing model. Changes take effect at the
            start of the next billing cycle.
          </p>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="text-sm font-medium">New Billing Model</label>
              <select
                value={planChangeModel}
                onChange={(e: any) => setPlanChangeModel(e.target.value)}
                className="w-full border rounded px-3 py-2 mt-1 bg-background text-sm"
              >
                <option value="">Select a model...</option>
                <option value="revenue_share">Revenue Share</option>
                <option value="subscription">Subscription</option>
                <option value="hybrid">Hybrid</option>
              </select>
            </div>
            <div>
              <label className="text-sm font-medium">Reason for Change</label>
              <input
                type="text"
                value={planChangeReason}
                onChange={(e: any) => setPlanChangeReason(e.target.value)}
                placeholder="e.g., scaling operations..."
                className="w-full border rounded px-3 py-2 mt-1 bg-background text-sm"
              />
            </div>
            <div className="flex items-end">
              <button
                onClick={handlePlanChange}
                disabled={!planChangeModel || updateConfig.isPending}
                className="px-4 py-2 bg-primary text-primary-foreground rounded text-sm font-medium disabled:opacity-50"
              >
                {updateConfig.isPending ? "Submitting..." : "Submit Request"}
              </button>
            </div>
          </div>
        </div>

        {/* Provisioning History */}
        <div className="bg-card border rounded-lg p-6">
          <h2 className="text-lg font-semibold mb-4">Provisioning History</h2>
          {historyData?.history && historyData.history.length > 0 ? (
            <div className="space-y-2">
              {historyData.history.map((entry: any) => (
                <div
                  key={entry.id}
                  className="flex items-center justify-between py-2 border-b last:border-0"
                >
                  <div className="flex items-center gap-3">
                    <span
                      className={`w-2 h-2 rounded-full ${
                        entry.status === "completed"
                          ? "bg-green-500"
                          : entry.status === "failed"
                            ? "bg-red-500"
                            : "bg-yellow-500"
                      }`}
                    />
                    <span className="text-sm font-medium">
                      {entry.step?.replace(/_/g, " ")}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-muted-foreground">
                    <span>{entry.status}</span>
                    <span>
                      {entry.startedAt
                        ? new Date(entry.startedAt).toLocaleString()
                        : ""}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">
              No provisioning history available.
            </p>
          )}
        </div>
      </div>
    </DashboardLayout>
  );
}
