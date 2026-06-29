// @ts-nocheck
import { trpc } from "@/lib/trpc";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function RateLimitDashboard() {
  const overviewQ = trpc.rateLimitDashboard.overview.useQuery();

  return (
    <div className="min-h-screen bg-gray-950 text-white p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">API Rate Limiting</h1>
            <p className="text-gray-400">
              Per-endpoint usage and throttle events
            </p>
          </div>
          <a href="/" className="text-sm text-gray-400 hover:text-white">
            ← Back
          </a>
        </div>

        {/* KPIs */}
        {overviewQ.data && (
          <div className="grid grid-cols-3 gap-4">
            <Card className="bg-gray-900 border-gray-800">
              <CardContent className="pt-4">
                <div className="text-2xl font-bold text-white">
                  {overviewQ.data.totals.requestsPerMinute.toLocaleString()}
                </div>
                <div className="text-sm text-gray-400">Requests/min</div>
              </CardContent>
            </Card>
            <Card className="bg-gray-900 border-gray-800">
              <CardContent className="pt-4">
                <div className="text-2xl font-bold text-orange-400">
                  {overviewQ.data.totals.totalThrottled}
                </div>
                <div className="text-sm text-gray-400">Total Throttled</div>
              </CardContent>
            </Card>
            <Card className="bg-gray-900 border-gray-800">
              <CardContent className="pt-4">
                <div className="text-2xl font-bold text-red-400">
                  {overviewQ.data.hotEndpoints.length}
                </div>
                <div className="text-sm text-gray-400">
                  Hot Endpoints (&gt;80%)
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Endpoint Table */}
        <Card className="bg-gray-900 border-gray-800">
          <CardHeader>
            <CardTitle className="text-white">Endpoint Usage</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-400 border-b border-gray-800">
                    <th className="text-left py-2 px-3">Endpoint</th>
                    <th className="text-left py-2 px-3">Method</th>
                    <th className="text-right py-2 px-3">RPM</th>
                    <th className="text-right py-2 px-3">Limit</th>
                    <th className="text-right py-2 px-3">Utilization</th>
                    <th className="text-right py-2 px-3">Throttled</th>
                  </tr>
                </thead>
                <tbody>
                  {overviewQ.data?.endpoints.map(ep => {
                    const util = Math.round(
                      (ep.requestsPerMinute / ep.limit) * 100
                    );
                    const utilColor =
                      util > 90
                        ? "text-red-400"
                        : util > 70
                          ? "text-yellow-400"
                          : "text-green-400";
                    return (
                      <tr
                        key={ep.endpoint}
                        className="border-b border-gray-800 hover:bg-gray-800/50"
                      >
                        <td className="py-3 px-3 font-mono text-xs text-gray-300">
                          {ep.endpoint}
                        </td>
                        <td className="py-3 px-3">
                          <Badge
                            variant="outline"
                            className="text-gray-400 border-gray-600 text-xs"
                          >
                            {ep.method}
                          </Badge>
                        </td>
                        <td className="py-3 px-3 text-right text-white">
                          {ep.requestsPerMinute.toLocaleString()}
                        </td>
                        <td className="py-3 px-3 text-right text-gray-400">
                          {ep.limit.toLocaleString()}
                        </td>
                        <td className="py-3 px-3 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <div className="w-20 bg-gray-700 rounded-full h-2 overflow-hidden">
                              <div
                                className={`h-full rounded-full ${util > 90 ? "bg-red-500" : util > 70 ? "bg-yellow-500" : "bg-green-500"}`}
                                style={{ width: `${Math.min(util, 100)}%` }}
                              />
                            </div>
                            <span className={`text-xs ${utilColor}`}>
                              {util}%
                            </span>
                          </div>
                        </td>
                        <td className="py-3 px-3 text-right">
                          {ep.throttledCount > 0 ? (
                            <span className="text-red-400">
                              {ep.throttledCount}
                            </span>
                          ) : (
                            <span className="text-gray-600">0</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
