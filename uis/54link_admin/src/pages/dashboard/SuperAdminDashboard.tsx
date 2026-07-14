import {
    Activity,
    AlertCircle,
    Server,
    Shield,
    TrendingUp,
    Users,
} from "lucide-react";

export default function SuperAdminDashboard() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-6">Super Admin Dashboard</h1>
      <p className="text-muted-foreground mb-8">
        Welcome, Super Admin! Full system overview and control.
      </p>

      {/* System Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">System Uptime</p>
              <p className="text-2xl font-bold mt-2">99.98%</p>
              <p className="text-xs text-green-600 mt-1">Excellent</p>
            </div>
            <Activity className="h-8 w-8 text-green-500" />
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Total Users</p>
              <p className="text-2xl font-bold mt-2">1,248</p>
              <p className="text-xs text-green-600 mt-1">+45 this week</p>
            </div>
            <Users className="h-8 w-8 text-blue-500" />
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Active Servers</p>
              <p className="text-2xl font-bold mt-2">12/12</p>
              <p className="text-xs text-green-600 mt-1">All healthy</p>
            </div>
            <Server className="h-8 w-8 text-purple-500" />
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Security Score</p>
              <p className="text-2xl font-bold mt-2">A+</p>
              <p className="text-xs text-green-600 mt-1">No issues</p>
            </div>
            <Shield className="h-8 w-8 text-orange-500" />
          </div>
        </div>
      </div>

      {/* System Status */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div className="bg-card border rounded-lg p-6">
          <h3 className="font-semibold mb-4 flex items-center gap-2">
            <TrendingUp className="h-5 w-5" />
            Performance Metrics
          </h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-sm">API Response Time</span>
              <span className="text-sm font-bold text-green-600">124ms</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm">Database Queries/sec</span>
              <span className="text-sm font-bold">3,450</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm">Active Connections</span>
              <span className="text-sm font-bold">847</span>
            </div>
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <h3 className="font-semibold mb-4 flex items-center gap-2">
            <AlertCircle className="h-5 w-5" />
            System Alerts
          </h3>
          <div className="space-y-2">
            <div className="p-2 bg-yellow-50 dark:bg-yellow-950 rounded text-sm">
              <span className="font-medium">Info:</span> Scheduled maintenance
              on Sunday 3AM
            </div>
            <div className="p-2 bg-green-50 dark:bg-green-950 rounded text-sm">
              <span className="font-medium">Success:</span> Database backup
              completed
            </div>
            <div className="p-2 bg-blue-50 dark:bg-blue-950 rounded text-sm">
              <span className="font-medium">Update:</span> Security patches
              applied
            </div>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="bg-card border rounded-lg p-6">
        <h3 className="font-semibold mb-4">Quick Actions</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <button className="p-4 border rounded-lg hover:bg-accent transition-colors">
            <Users className="h-6 w-6 mb-2 mx-auto" />
            <p className="text-sm text-center">Manage Users</p>
          </button>
          <button className="p-4 border rounded-lg hover:bg-accent transition-colors">
            <Server className="h-6 w-6 mb-2 mx-auto" />
            <p className="text-sm text-center">System Config</p>
          </button>
          <button className="p-4 border rounded-lg hover:bg-accent transition-colors">
            <Shield className="h-6 w-6 mb-2 mx-auto" />
            <p className="text-sm text-center">Security</p>
          </button>
          <button className="p-4 border rounded-lg hover:bg-accent transition-colors">
            <Activity className="h-6 w-6 mb-2 mx-auto" />
            <p className="text-sm text-center">Monitoring</p>
          </button>
        </div>
      </div>
    </div>
  );
}
