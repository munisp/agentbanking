import { trpc } from "@/lib/trpc";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import DashboardLayout from "@/components/DashboardLayout";

export default function AutomatedTestingFrameworkPage() {
  const { data, isLoading, refetch } =
    trpc.automatedTestingFramework.dashboard.useQuery();
  if (isLoading)
    return (
      <DashboardLayout>
        <div className="p-8 text-center animate-pulse">Loading tests...</div>
      </DashboardLayout>
    );
  const d = data as any;
  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Automated Testing Framework</h1>
            <p className="text-muted-foreground">
              Test suites, coverage, and regression tracking
            </p>
          </div>
          <Button onClick={() => refetch()}>Run All Tests</Button>
        </div>
        <div className="grid grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="text-3xl font-bold">{d?.totalTests ?? 0}</div>
              <p className="text-sm text-muted-foreground">Total Tests</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center gap-2">
                <div className="text-3xl font-bold text-green-500">
                  {d?.coverage ?? 0}%
                </div>
              </div>
              <p className="text-sm text-muted-foreground">Code Coverage</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-3xl font-bold text-blue-500">
                {d?.suites?.length ?? 0}
              </div>
              <p className="text-sm text-muted-foreground">Test Suites</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-3xl font-bold text-amber-500">
                {d?.loadTestResults?.length ?? 0}
              </div>
              <p className="text-sm text-muted-foreground">Load Tests</p>
            </CardContent>
          </Card>
        </div>
        <Card>
          <CardHeader>
            <CardTitle>Test Suites</CardTitle>
          </CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left">
                  <th className="p-3">Suite</th>
                  <th className="p-3">Tests</th>
                  <th className="p-3">Passing</th>
                  <th className="p-3">Failing</th>
                  <th className="p-3">Duration</th>
                  <th className="p-3">Coverage</th>
                </tr>
              </thead>
              <tbody>
                {(d?.suites ?? []).map((s: any, i: number) => (
                  <tr key={i} className="border-b hover:bg-muted/50">
                    <td className="p-3 font-medium">
                      {s.name ?? `Suite ${i + 1}`}
                    </td>
                    <td className="p-3">{s.total ?? 0}</td>
                    <td className="p-3 text-green-500">{s.passing ?? 0}</td>
                    <td className="p-3 text-red-500">{s.failing ?? 0}</td>
                    <td className="p-3">{s.duration ?? "0s"}</td>
                    <td className="p-3">
                      <Progress value={s.coverage ?? 0} className="w-20 h-2" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Regression History</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {(d?.regressionHistory ?? [])
                .slice(0, 10)
                .map((r: any, i: number) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-2 bg-muted rounded"
                  >
                    <span className="text-sm">{r.date ?? "2024-01-15"}</span>
                    <div className="flex gap-4 text-sm">
                      <span>Total: {r.total ?? 0}</span>
                      <span className="text-red-500">
                        Failing: {r.failing ?? 0}
                      </span>
                      <span className="text-muted-foreground">
                        {r.duration ?? "0s"}
                      </span>
                    </div>
                  </div>
                ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
