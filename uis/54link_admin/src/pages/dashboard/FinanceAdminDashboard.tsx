import { CreditCard, DollarSign, TrendingUp, Wallet } from "lucide-react";
import { useDashboardData } from "../../hooks/useDashboardData";

export default function FinanceAdminDashboard() {
  const { transactions, metrics, loading } = useDashboardData();

  const totalRevenue = metrics.total_volume;
  const successTxns = transactions.filter(
    (t) => t.status?.toLowerCase() === "success",
  );
  console.log("Successful Transactions:", successTxns);
  const transactionFees = totalRevenue * 0.01; // Assume 1% fee
  const netProfit = totalRevenue * 0.65; // Assume 65% profit margin

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
              <p className="text-2xl font-bold mt-2">
                {loading
                  ? "..."
                  : `₦${(transactionFees / 1000000).toFixed(1)}M`}
              </p>
              <p className="text-xs text-green-600 mt-1">1% of revenue</p>
            </div>
            <CreditCard className="h-8 w-8 text-blue-500" />
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Net Profit</p>
              <p className="text-2xl font-bold mt-2">
                {loading ? "..." : `₦${(netProfit / 1000000).toFixed(1)}M`}
              </p>
              <p className="text-xs text-green-600 mt-1">65% margin</p>
            </div>
            <Wallet className="h-8 w-8 text-orange-500" />
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Net Profit</p>
              <p className="text-2xl font-bold mt-2">₦81.7M</p>
              <p className="text-xs text-green-600 mt-1">+22.4% growth</p>
            </div>
            <TrendingUp className="h-8 w-8 text-purple-500" />
          </div>
        </div>
      </div>

      {/* Financial Reports */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-card border rounded-lg p-6">
          <h3 className="font-semibold mb-4">Pending Invoices</h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center py-2 border-b">
              <div>
                <p className="text-sm font-medium">
                  BPMGD - January Subscription
                </p>
                <p className="text-xs text-muted-foreground">Due in 5 days</p>
              </div>
              <span className="font-bold">₦2.5M</span>
            </div>
            <div className="flex justify-between items-center py-2 border-b">
              <div>
                <p className="text-sm font-medium">FirstBank - API Usage</p>
                <p className="text-xs text-muted-foreground">Due in 12 days</p>
              </div>
              <span className="font-bold">₦1.8M</span>
            </div>
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <h3 className="font-semibold mb-4">Recent Transactions</h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center py-2 border-b">
              <div>
                <p className="text-sm font-medium">Payment Received</p>
                <p className="text-xs text-muted-foreground">
                  UBA - Monthly Fee
                </p>
              </div>
              <span className="text-green-600 font-bold">+₦3.2M</span>
            </div>
            <div className="flex justify-between items-center py-2 border-b">
              <div>
                <p className="text-sm font-medium">Infrastructure Cost</p>
                <p className="text-xs text-muted-foreground">AWS Services</p>
              </div>
              <span className="text-red-600 font-bold">-₦850K</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
