import { CreditCard, DollarSign, TrendingUp, Wallet } from "lucide-react";
import { useDashboardData } from "../../hooks/useDashboardData";

export default function FinanceAdminDashboard() {
  const { transactions, metrics, loading } = useDashboardData();

  const totalRevenue = metrics.total_volume;
  // Fee and profit-margin figures are not provided by the API — render "—"
  // instead of deriving them from assumed constants.
  const recentTransactions = transactions.slice(0, 5);

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-6">Finance Admin Dashboard</h1>
      <p className="text-muted-foreground mb-8">
        Welcome, Finance Admin! Manage financial operations and accounting.
      </p>

      {/* Financial Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Total Revenue</p>
              <p className="text-2xl font-bold mt-2">
                {loading ? "..." : `₦${(totalRevenue / 1000000).toFixed(1)}M`}
              </p>
              <p className="text-xs text-muted-foreground mt-1">All time</p>
            </div>
            <DollarSign className="h-8 w-8 text-green-500" />
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Transaction Fees</p>
              <p className="text-2xl font-bold mt-2">{loading ? "..." : "—"}</p>
              <p className="text-xs text-muted-foreground mt-1">
                Not available
              </p>
            </div>
            <CreditCard className="h-8 w-8 text-blue-500" />
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Net Profit</p>
              <p className="text-2xl font-bold mt-2">{loading ? "..." : "—"}</p>
              <p className="text-xs text-muted-foreground mt-1">
                Not available
              </p>
            </div>
            <Wallet className="h-8 w-8 text-orange-500" />
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">
                Total Transactions
              </p>
              <p className="text-2xl font-bold mt-2">
                {loading ? "..." : metrics.total_count.toLocaleString()}
              </p>
              <p className="text-xs text-muted-foreground mt-1">All time</p>
            </div>
            <TrendingUp className="h-8 w-8 text-purple-500" />
          </div>
        </div>
      </div>

      {/* Financial Reports */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-card border rounded-lg p-6">
          <h3 className="font-semibold mb-4">Pending Invoices</h3>
          <p className="text-sm text-muted-foreground py-4 text-center">
            Invoice data is not available — no invoicing source is connected.
          </p>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <h3 className="font-semibold mb-4">Recent Transactions</h3>
          {loading ? (
            <p className="text-sm text-muted-foreground py-4 text-center">
              Loading transactions…
            </p>
          ) : recentTransactions.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4 text-center">
              No recent transactions.
            </p>
          ) : (
            <div className="space-y-3">
              {recentTransactions.map((t, i) => {
                const amount = Number(t.amount ?? NaN);
                const label =
                  t.description ||
                  t.narration ||
                  t.reference ||
                  t.tx_ref ||
                  t.type ||
                  "Transaction";
                return (
                  <div
                    key={t.id ?? t.reference ?? i}
                    className="flex justify-between items-center py-2 border-b"
                  >
                    <div>
                      <p className="text-sm font-medium">{label}</p>
                      <p className="text-xs text-muted-foreground">
                        {t.status ?? "—"}
                      </p>
                    </div>
                    <span className="font-bold">
                      {Number.isFinite(amount)
                        ? `₦${amount.toLocaleString()}`
                        : "—"}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
