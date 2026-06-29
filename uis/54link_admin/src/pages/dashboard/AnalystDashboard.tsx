import { BarChart3, DollarSign, TrendingUp, Users } from "lucide-react";
import { useDashboardData } from "../../hooks/useDashboardData";

export default function AnalystDashboard() {
  const { tenants, transactions, metrics, loading } = useDashboardData();

  const totalTransactions = metrics.total_count;
  const activeTenants = tenants.length;
  const totalVolume = metrics.total_volume;
  const successfulTxns = transactions.filter(
    (t) => t.status?.toLowerCase() === "success",
  ).length;
  const successRate =
    totalTransactions > 0
      ? ((successfulTxns / totalTransactions) * 100).toFixed(1)
      : "0.0";

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-6">Analyst Dashboard</h1>
      <p className="text-muted-foreground mb-8">
        Welcome, Analyst! Here you can view reports and analytics.
      </p>

      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">
                Total Transactions
              </p>
              <p className="text-2xl font-bold mt-2">
                {loading ? "..." : totalTransactions.toLocaleString()}
              </p>
              <p className="text-xs text-muted-foreground mt-1">All time</p>
            </div>
            <BarChart3 className="h-8 w-8 text-blue-500" />
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Active Tenants</p>
              <p className="text-2xl font-bold mt-2">
                {loading ? "..." : activeTenants}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Banks onboarded
              </p>
            </div>
            <Users className="h-8 w-8 text-purple-500" />
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Total Volume</p>
              <p className="text-2xl font-bold mt-2">
                {loading ? "..." : `₦${(totalVolume / 1000000).toFixed(1)}M`}
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Total processed
              </p>
            </div>
            <DollarSign className="h-8 w-8 text-green-500" />
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Success Rate</p>
              <p className="text-2xl font-bold mt-2">
                {loading ? "..." : `${successRate}%`}
              </p>
              <p className="text-xs text-green-600 mt-1">Transaction success</p>
            </div>
            <TrendingUp className="h-8 w-8 text-orange-500" />
          </div>
        </div>
      </div>

      {/* Reports Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-card border rounded-lg p-6">
          <h3 className="font-semibold mb-4">Recent Reports</h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center py-2 border-b">
              <span className="text-sm">Monthly Transaction Report</span>
              <span className="text-xs text-muted-foreground">2 hours ago</span>
            </div>
            <div className="flex justify-between items-center py-2 border-b">
              <span className="text-sm">Tenant Activity Analysis</span>
              <span className="text-xs text-muted-foreground">1 day ago</span>
            </div>
            <div className="flex justify-between items-center py-2">
              <span className="text-sm">System Performance Report</span>
              <span className="text-xs text-muted-foreground">2 days ago</span>
            </div>
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <h3 className="font-semibold mb-4">Insights</h3>
          <div className="space-y-3">
            <div className="p-3 bg-blue-50 dark:bg-blue-950 rounded">
              <p className="text-sm font-medium">Peak Usage Time</p>
              <p className="text-xs text-muted-foreground mt-1">
                Transactions peak between 2-4 PM daily
              </p>
            </div>
            <div className="p-3 bg-green-50 dark:bg-green-950 rounded">
              <p className="text-sm font-medium">Top Performing Tenant</p>
              <p className="text-xs text-muted-foreground mt-1">
                BPMGD processed 28K transactions this month
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
