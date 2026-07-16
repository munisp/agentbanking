import { Activity, AlertTriangle, CheckCircle, Clock } from "lucide-react";

export default function OperationsOfficerDashboard() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-6">Operations Officer Dashboard</h1>
      <p className="text-muted-foreground mb-8">
        Welcome, Operations Officer! Manage daily operations and workflows.
      </p>

      {/* Operations Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Pending Tasks</p>
              <p className="text-2xl font-bold mt-2">17</p>
              <p className="text-xs text-orange-600 mt-1">5 high priority</p>
            </div>
            <Clock className="h-8 w-8 text-orange-500" />
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Completed Today</p>
              <p className="text-2xl font-bold mt-2">48</p>
              <p className="text-xs text-green-600 mt-1">Above average</p>
            </div>
            <CheckCircle className="h-8 w-8 text-green-500" />
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Active Processes</p>
              <p className="text-2xl font-bold mt-2">12</p>
              <p className="text-xs text-blue-600 mt-1">Running smoothly</p>
            </div>
            <Activity className="h-8 w-8 text-blue-500" />
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Issues</p>
              <p className="text-2xl font-bold mt-2">3</p>
              <p className="text-xs text-red-600 mt-1">Need attention</p>
            </div>
            <AlertTriangle className="h-8 w-8 text-red-500" />
          </div>
        </div>
      </div>

      {/* Task Lists */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-card border rounded-lg p-6">
          <h3 className="font-semibold mb-4">High Priority Tasks</h3>
          <div className="space-y-3">
            <div className="p-3 border-l-4 border-red-500 bg-red-50 dark:bg-red-950 rounded">
              <p className="text-sm font-medium">
                Resolve transaction processing delay
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Due: Today 5 PM
              </p>
            </div>
            <div className="p-3 border-l-4 border-orange-500 bg-orange-50 dark:bg-orange-950 rounded">
              <p className="text-sm font-medium">
                Update tenant configuration - BPMGD
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Due: Tomorrow
              </p>
            </div>
            <div className="p-3 border-l-4 border-yellow-500 bg-yellow-50 dark:bg-yellow-950 rounded">
              <p className="text-sm font-medium">Review API rate limits</p>
              <p className="text-xs text-muted-foreground mt-1">
                Due: In 2 days
              </p>
            </div>
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <h3 className="font-semibold mb-4">Recent Activities</h3>
          <div className="space-y-3">
            <div className="flex items-start gap-3 py-2 border-b">
              <CheckCircle className="h-4 w-4 text-green-500 mt-0.5" />
              <div className="flex-1">
                <p className="text-sm">
                  Completed tenant onboarding - FirstBank
                </p>
                <p className="text-xs text-muted-foreground">30 minutes ago</p>
              </div>
            </div>
            <div className="flex items-start gap-3 py-2 border-b">
              <CheckCircle className="h-4 w-4 text-green-500 mt-0.5" />
              <div className="flex-1">
                <p className="text-sm">Updated system configurations</p>
                <p className="text-xs text-muted-foreground">2 hours ago</p>
              </div>
            </div>
            <div className="flex items-start gap-3 py-2">
              <CheckCircle className="h-4 w-4 text-green-500 mt-0.5" />
              <div className="flex-1">
                <p className="text-sm">Resolved API timeout issues</p>
                <p className="text-xs text-muted-foreground">4 hours ago</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
