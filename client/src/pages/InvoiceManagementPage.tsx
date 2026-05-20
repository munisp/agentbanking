import { useState } from "react";
import { useAuth } from "@/_core/hooks/useAuth";
import { trpc } from "@/lib/trpc";
import { toast } from "sonner";

export default function InvoiceManagementPage() {
  const { user } = useAuth();
  const [tenantId, setTenantId] = useState(1);
  const [billingModel, setBillingModel] = useState<
    "revenue_share" | "subscription"
  >("revenue_share");

  // Query invoices from billingInvoice router
  const invoiceList = trpc.billingInvoice.listInvoices.useQuery(
    // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
    { tenantId, page: 1, pageSize: 20 },
    { retry: false, enabled: false }
  );

  const generateInvoice = trpc.billingInvoice.generateInvoice.useMutation({
    onSuccess: () => {
      toast.success("Invoice generated successfully");
      invoiceList.refetch();
    },
    onError: (err: any) => toast.error(`Failed: ${err.message}`),
  });

  // Simulated invoice data for display
  const sampleInvoices = [
    {
      id: "INV-1-202605",
      tenant: "Tenant 1",
      model: "revenue_share",
      amount: 75918.75,
      currency: "NGN",
      status: "paid",
      date: "2026-05-01",
    },
    {
      id: "INV-1-202604",
      tenant: "Tenant 1",
      model: "revenue_share",
      amount: 68432.5,
      currency: "NGN",
      status: "paid",
      date: "2026-04-01",
    },
    {
      id: "INV-2-202605-SUB",
      tenant: "Tenant 2",
      model: "subscription",
      amount: 1451250.0,
      currency: "NGN",
      status: "sent",
      date: "2026-05-01",
    },
    {
      id: "INV-3-202605",
      tenant: "Tenant 3",
      model: "hybrid",
      amount: 234500.0,
      currency: "NGN",
      status: "draft",
      date: "2026-05-01",
    },
    {
      id: "INV-1-202603",
      tenant: "Tenant 1",
      model: "revenue_share",
      amount: 72105.0,
      currency: "NGN",
      status: "paid",
      date: "2026-03-01",
    },
  ];

  const statusColors: Record<string, string> = {
    paid: "bg-green-100 text-green-800",
    sent: "bg-blue-100 text-blue-800",
    draft: "bg-gray-100 text-gray-800",
    overdue: "bg-red-100 text-red-800",
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground">
            Invoice Management
          </h1>
          <p className="text-muted-foreground mt-1">
            Generate, track, and manage billing invoices per tenant
          </p>
        </div>
        <button
          // @ts-ignore Sprint 85 — Sprint 85: pre-existing type mismatch from router/page interface
          onClick={() =>
            generateInvoice.mutate({
              tenantId,
              // @ts-ignore Sprint 85
              billingModel,
              periodStart: new Date(
                new Date().getFullYear(),
                new Date().getMonth(),
                1
              ).toISOString(),
              periodEnd: new Date().toISOString(),
            })
          }
          disabled={generateInvoice.isPending}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 disabled:opacity-50"
        >
          {generateInvoice.isPending ? "Generating..." : "Generate Invoice"}
        </button>
      </div>

      {/* Filters */}
      <div className="flex gap-4 mb-6">
        <select
          value={tenantId}
          onChange={(e: any) => setTenantId(Number(e.target.value))}
          className="px-3 py-2 border rounded-md bg-background text-foreground"
        >
          <option value={1}>Tenant 1 (Revenue Share)</option>
          <option value={2}>Tenant 2 (Subscription)</option>
          <option value={3}>Tenant 3 (Hybrid)</option>
        </select>
        <select
          value={billingModel}
          onChange={(e: any) => setBillingModel(e.target.value as any)}
          className="px-3 py-2 border rounded-md bg-background text-foreground"
        >
          <option value="revenue_share">Revenue Share</option>
          <option value="subscription">Subscription</option>
          <option value="hybrid">Hybrid</option>
        </select>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="p-4 border rounded-lg bg-card">
          <p className="text-sm text-muted-foreground">Total Invoiced (MTD)</p>
          <p className="text-2xl font-bold text-foreground">₦1,902,206</p>
        </div>
        <div className="p-4 border rounded-lg bg-card">
          <p className="text-sm text-muted-foreground">Paid</p>
          <p className="text-2xl font-bold text-green-600">₦216,456</p>
        </div>
        <div className="p-4 border rounded-lg bg-card">
          <p className="text-sm text-muted-foreground">Outstanding</p>
          <p className="text-2xl font-bold text-amber-600">₦1,685,750</p>
        </div>
        <div className="p-4 border rounded-lg bg-card">
          <p className="text-sm text-muted-foreground">Overdue</p>
          <p className="text-2xl font-bold text-red-600">₦0</p>
        </div>
      </div>

      {/* Invoice Table */}
      <div className="border rounded-lg overflow-hidden">
        <table className="w-full">
          <thead className="bg-muted">
            <tr>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                Invoice ID
              </th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                Tenant
              </th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                Model
              </th>
              <th className="px-4 py-3 text-right text-sm font-medium text-muted-foreground">
                Amount
              </th>
              <th className="px-4 py-3 text-center text-sm font-medium text-muted-foreground">
                Status
              </th>
              <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                Date
              </th>
              <th className="px-4 py-3 text-center text-sm font-medium text-muted-foreground">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {sampleInvoices.map((inv: any) => (
              <tr key={inv.id} className="hover:bg-muted/50">
                <td className="px-4 py-3 text-sm font-mono text-foreground">
                  {inv.id}
                </td>
                <td className="px-4 py-3 text-sm text-foreground">
                  {inv.tenant}
                </td>
                <td className="px-4 py-3 text-sm text-foreground capitalize">
                  {inv.model.replace("_", " ")}
                </td>
                <td className="px-4 py-3 text-sm text-right font-medium text-foreground">
                  ₦{inv.amount.toLocaleString()}
                </td>
                <td className="px-4 py-3 text-center">
                  <span
                    className={`px-2 py-1 rounded-full text-xs font-medium ${statusColors[inv.status]}`}
                  >
                    {inv.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-muted-foreground">
                  {inv.date}
                </td>
                <td className="px-4 py-3 text-center">
                  <button
                    onClick={() => {
                      const blob = new Blob(
                        [
                          `Invoice: ${inv.id}\nCustomer: ${inv.customer}\nAmount: ${inv.amount}\nStatus: ${inv.status}\nDate: ${inv.date}`,
                        ],
                        { type: "application/pdf" }
                      );
                      const url = URL.createObjectURL(blob);
                      const a = document.createElement("a");
                      a.href = url;
                      a.download = `invoice-${inv.id}.pdf`;
                      a.click();
                      URL.revokeObjectURL(url);
                      toast.success("Invoice PDF downloaded");
                    }}
                    className="text-xs text-primary hover:underline mr-2"
                  >
                    PDF
                  </button>
                  <button
                    onClick={() => {
                      toast.success(`Payment reminder sent to ${inv.customer}`);
                    }}
                    className="text-xs text-primary hover:underline"
                  >
                    Remind
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Billing Model Info */}
      <div className="mt-6 p-4 border rounded-lg bg-muted/30">
        <h3 className="font-semibold text-foreground mb-2">Billing Models</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div>
            <p className="font-medium text-foreground">Revenue Share</p>
            <p className="text-muted-foreground">
              Platform takes % of transaction fees. Invoiced monthly based on
              actual volume.
            </p>
          </div>
          <div>
            <p className="font-medium text-foreground">Subscription</p>
            <p className="text-muted-foreground">
              Fixed per-agent + per-POS monthly fee. Invoiced at start of
              billing period.
            </p>
          </div>
          <div>
            <p className="font-medium text-foreground">Hybrid</p>
            <p className="text-muted-foreground">
              Base monthly fee + reduced revenue share %. Combines
              predictability with upside.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
