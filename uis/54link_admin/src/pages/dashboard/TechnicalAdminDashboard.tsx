import { Activity, Cpu, Database, HardDrive, Server, Zap } from "lucide-react";

export default function TechnicalAdminDashboard() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-6">Technical Admin Dashboard</h1>
      <p className="text-muted-foreground mb-8">
        Welcome, Technical Admin! Manage infrastructure and DevOps.
      </p>

      {/* Infrastructure Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">CPU Usage</p>
              <p className="text-2xl font-bold mt-2">42%</p>
              <p className="text-xs text-green-600 mt-1">Optimal</p>
            </div>
            <Cpu className="h-8 w-8 text-blue-500" />
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Memory</p>
              <p className="text-2xl font-bold mt-2">68%</p>
              <p className="text-xs text-orange-600 mt-1">Moderate</p>
            </div>
            <HardDrive className="h-8 w-8 text-orange-500" />
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">API Uptime</p>
              <p className="text-2xl font-bold mt-2">99.9%</p>
              <p className="text-xs text-green-600 mt-1">Excellent</p>
            </div>
            <Activity className="h-8 w-8 text-green-500" />
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Response Time</p>
              <p className="text-2xl font-bold mt-2">145ms</p>
              <p className="text-xs text-green-600 mt-1">Fast</p>
            </div>
            <Zap className="h-8 w-8 text-purple-500" />
          </div>
        </div>
      </div>

      {/* System Details */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
        <div className="bg-card border rounded-lg p-6">
          <h3 className="font-semibold mb-4 flex items-center gap-2">
            <Server className="h-5 w-5" />
            Server Status
          </h3>
          <div className="space-y-2">
            <div className="flex justify-between items-center p-2 rounded hover:bg-accent">
              <span className="text-sm">API Server 1</span>
              <span className="text-xs px-2 py-1 bg-green-100 text-green-700 rounded">
                Healthy
              </span>
            </div>
            <div className="flex justify-between items-center p-2 rounded hover:bg-accent">
              <span className="text-sm">API Server 2</span>
              <span className="text-xs px-2 py-1 bg-green-100 text-green-700 rounded">
                Healthy
              </span>
            </div>
            <div className="flex justify-between items-center p-2 rounded hover:bg-accent">
              <span className="text-sm">Worker Server</span>
              <span className="text-xs px-2 py-1 bg-green-100 text-green-700 rounded">
                Healthy
              </span>
            </div>
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <h3 className="font-semibold mb-4 flex items-center gap-2">
            <Database className="h-5 w-5" />
            Database Status
          </h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-sm">Connections</span>
              <span className="text-sm font-bold">847 / 1000</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm">Query Time (avg)</span>
              <span className="text-sm font-bold text-green-600">12ms</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm">Storage Used</span>
              <span className="text-sm font-bold">2.4 TB / 5 TB</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm">Last Backup</span>
              <span className="text-sm font-bold text-green-600">
                2 hours ago
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Deployments */}
      <div className="bg-card border rounded-lg p-6">
        <h3 className="font-semibold mb-4">Recent Deployments</h3>
        <div className="space-y-2">
          <div className="flex justify-between items-center p-3 border rounded">
            <div>
              <p className="text-sm font-medium">
                API v2.4.1 - Security patches
              </p>
              <p className="text-xs text-muted-foreground">
                Deployed 2 hours ago
              </p>
            </div>
            <span className="text-xs px-2 py-1 bg-green-100 text-green-700 rounded">
              Success
            </span>
          </div>
          <div className="flex justify-between items-center p-3 border rounded">
            <div>
              <p className="text-sm font-medium">
                Worker Service v1.8.0 - Performance improvements
              </p>
              <p className="text-xs text-muted-foreground">
                Deployed yesterday
              </p>
            </div>
            <span className="text-xs px-2 py-1 bg-green-100 text-green-700 rounded">
              Success
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
