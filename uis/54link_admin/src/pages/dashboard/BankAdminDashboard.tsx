import {
    Activity,
    AlertCircle,
    Building2,
    DollarSign,
    TrendingUp,
    Users,
} from "lucide-react";
import { useDashboardData } from "../../hooks/useDashboardData";

export default function BankAdminDashboard() {
  const { tenants, transactions, users, metrics, loading } = useDashboardData();

  const totalTenants = tenants.length;
  const totalCustomers = users.length;
  const totalTransactions = metrics.total_count;
  const totalVolume = metrics.total_volume;
  const successTxns = transactions.filter(
    (t) => t.status?.toLowerCase() === "success",
  ).length;
  const systemHealth =
    totalTransactions > 0
      ? ((successTxns / totalTransactions) * 100).toFixed(2)
      : "0.00";

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-6">Bank Admin Dashboard</h1>
      <p className="text-muted-foreground mb-8">
        Welcome, Bank Admin! Manage bank operations and oversee all activities.
      </p>

      {/* Bank Overview Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Total Tenants</p>
              <p className="text-2xl font-bold mt-2">{loading ? '...' : totalTenants}</p>
              <p className="text-xs text-green-600 mt-1">Active banks</p>
            </div>
            <Building2 className="h-8 w-8 text-blue-500" />
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Active Users</p>
              <p className="text-2xl font-bold mt-2">{loading ? '...' : totalCustomers.toLocaleString()}</p>
              <p className="text-xs text-green-600 mt-1">All tenants</p>
            </div>
            <Users className="h-8 w-8 text-green-500" />
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">
                Transaction Volume
              </p>
              <p className="text-2xl font-bold mt-2">{loading ? '...' : `₦${(totalVolume / 1000000).toFixed(1)}M`}</p>
              <p className="text-xs text-green-600 mt-1">All time</p>
            </div>
            <DollarSign className="h-8 w-8 text-purple-500" />
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">System Health</p>
              <p className="text-2xl font-bold mt-2">{loading ? '...' : `${systemHealth}%`}</p>
              <p className="text-xs text-green-600 mt-1">Success rate</p>
            </div>
            <Activity className="h-8 w-8 text-orange-500" />
          </div>
        </div>
      </div>

      {/* Tenant Performance */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div className="bg-card border rounded-lg p-6">
          <h3 className="font-semibold mb-4">Top Performing Tenants</h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center p-3 border-b">
              <div className="flex items-center gap-3">
                <Building2 className="h-4 w-4 text-blue-500" />
                <div>
                  <p className="text-sm font-medium">FirstBank Nigeria</p>
                  <p className="text-xs text-muted-foreground">ID: FBNNG</p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-sm font-bold text-green-600">₦2.1B</p>
                <p className="text-xs text-muted-foreground">Monthly vol.</p>
              </div>
            </div>
            <div className="flex justify-between items-center p-3 border-b">
              <div className="flex items-center gap-3">
                <Building2 className="h-4 w-4 text-blue-500" />
                <div>
                  <p className="text-sm font-medium">Zenith Bank</p>
                  <p className="text-xs text-muted-foreground">ID: ZBPLC</p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-sm font-bold text-green-600">₦1.8B</p>
                <p className="text-xs text-muted-foreground">Monthly vol.</p>
              </div>
            </div>
            <div className="flex justify-between items-center p-3">
              <div className="flex items-center gap-3">
                <Building2 className="h-4 w-4 text-blue-500" />
                <div>
                  <p className="text-sm font-medium">GT Bank</p>
                  <p className="text-xs text-muted-foreground">ID: GTBNG</p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-sm font-bold text-green-600">₦1.5B</p>
                <p className="text-xs text-muted-foreground">Monthly vol.</p>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <h3 className="font-semibold mb-4">System Alerts</h3>
          <div className="space-y-3">
            <div className="p-3 border-l-4 border-yellow-500 bg-yellow-50 dark:bg-yellow-950 rounded">
              <div className="flex items-start gap-2">
                <AlertCircle className="h-4 w-4 text-yellow-600 mt-0.5" />
                <div>
                  <p className="text-sm font-medium">High API usage detected</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Tenant: FBNNG - Consider scaling
                  </p>
                </div>
              </div>
            </div>
            <div className="p-3 border-l-4 border-blue-500 bg-blue-50 dark:bg-blue-950 rounded">
              <div className="flex items-start gap-2">
                <AlertCircle className="h-4 w-4 text-blue-600 mt-0.5" />
                <div>
                  <p className="text-sm font-medium">
                    3 pending onboarding requests
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Awaiting approval
                  </p>
                </div>
              </div>
            </div>
            <div className="p-3 border-l-4 border-green-500 bg-green-50 dark:bg-green-950 rounded">
              <div className="flex items-start gap-2">
                <TrendingUp className="h-4 w-4 text-green-600 mt-0.5" />
                <div>
                  <p className="text-sm font-medium">
                    Strong growth this quarter
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    +28% user acquisition
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="bg-card border rounded-lg p-6">
        <h3 className="font-semibold mb-4">Quick Actions</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <button className="p-4 border rounded-lg hover:bg-accent transition-colors text-left">
            <Building2 className="h-5 w-5 mb-2 text-blue-500" />
            <p className="text-sm font-medium">Onboard New Tenant</p>
            <p className="text-xs text-muted-foreground mt-1">
              Add a new banking institution
            </p>
          </button>
          <button className="p-4 border rounded-lg hover:bg-accent transition-colors text-left">
            <Users className="h-5 w-5 mb-2 text-green-500" />
            <p className="text-sm font-medium">Create Admin User</p>
            <p className="text-xs text-muted-foreground mt-1">
              Add administrator account
            </p>
          </button>
          <button className="p-4 border rounded-lg hover:bg-accent transition-colors text-left">
            <Activity className="h-5 w-5 mb-2 text-purple-500" />
            <p className="text-sm font-medium">System Health</p>
            <p className="text-xs text-muted-foreground mt-1">
              View detailed metrics
            </p>
          </button>
        </div>
      </div>
    </div>
  );
}
