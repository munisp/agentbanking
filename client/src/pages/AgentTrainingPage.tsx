import { trpc } from "@/lib/trpc";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import DashboardLayout from "@/components/DashboardLayout";

export default function AgentTrainingPage() {
  const { data, isLoading, refetch } = trpc.agentTraining.dashboard.useQuery();
  if (isLoading)
    return (
      <DashboardLayout>
        <div className="p-8 text-center animate-pulse">Loading training...</div>
      </DashboardLayout>
    );
  const d = data as any;
  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Agent Training</h1>
            <p className="text-muted-foreground">
              Courses, certifications, and compliance training
            </p>
          </div>
          <Button onClick={() => refetch()}>Refresh</Button>
        </div>
        <div className="grid grid-cols-4 gap-4">
          <Card>
            <CardContent className="pt-6">
              <div className="text-3xl font-bold">{d?.totalCourses ?? 0}</div>
              <p className="text-sm text-muted-foreground">Total Courses</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-3xl font-bold text-green-500">
                {d?.completionRate ?? 0}%
              </div>
              <p className="text-sm text-muted-foreground">Completion Rate</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-3xl font-bold text-blue-500">
                {d?.certifications?.length ?? 0}
              </div>
              <p className="text-sm text-muted-foreground">Certifications</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="pt-6">
              <div className="text-3xl font-bold text-amber-500">
                {d?.upcomingRenewals?.length ?? 0}
              </div>
              <p className="text-sm text-muted-foreground">Upcoming Renewals</p>
            </CardContent>
          </Card>
        </div>
        <Card>
          <CardHeader>
            <CardTitle>Training Courses</CardTitle>
          </CardHeader>
          <CardContent>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left">
                  <th className="p-3">Course</th>
                  <th className="p-3">Category</th>
                  <th className="p-3">Duration</th>
                  <th className="p-3">Enrolled</th>
                  <th className="p-3">Completion</th>
                  <th className="p-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {(d?.courses ?? []).map((c: any, i: number) => (
                  <tr key={i} className="border-b hover:bg-muted/50">
                    <td className="p-3 font-medium">
                      {c.title ?? c.name ?? `Course ${i + 1}`}
                    </td>
                    <td className="p-3">
                      <Badge variant="outline">{c.category ?? "General"}</Badge>
                    </td>
                    <td className="p-3">{c.duration ?? "2h"}</td>
                    <td className="p-3">{c.enrolled ?? 0}</td>
                    <td className="p-3">
                      <div className="flex items-center gap-2">
                        <Progress
                          value={c.completionRate ?? 0}
                          className="w-20 h-2"
                        />
                        <span>{c.completionRate ?? 0}%</span>
                      </div>
                    </td>
                    <td className="p-3">
                      <Badge
                        className={c.mandatory ? "bg-red-500" : "bg-blue-500"}
                      >
                        {c.mandatory ? "Mandatory" : "Optional"}
                      </Badge>
                    </td>
                  </tr>
                ))}
                {(!d?.courses || d.courses.length === 0) && (
                  <tr>
                    <td
                      colSpan={6}
                      className="p-8 text-center text-muted-foreground"
                    >
                      No courses available
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </CardContent>
        </Card>
        <div className="grid grid-cols-2 gap-4">
          <Card>
            <CardHeader>
              <CardTitle>Certifications</CardTitle>
            </CardHeader>
            <CardContent>
              {(d?.certifications ?? []).map((c: any, i: number) => (
                <div
                  key={i}
                  className="flex items-center justify-between p-3 border-b last:border-0"
                >
                  <div>
                    <p className="font-medium">{c.name ?? `Cert ${i + 1}`}</p>
                    <p className="text-xs text-muted-foreground">
                      Expires: {c.expiresAt ?? "N/A"}
                    </p>
                  </div>
                  <Badge
                    className={
                      c.status === "active" ? "bg-green-500" : "bg-amber-500"
                    }
                  >
                    {c.status ?? "Active"}
                  </Badge>
                </div>
              ))}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Upcoming Renewals</CardTitle>
            </CardHeader>
            <CardContent>
              {(d?.upcomingRenewals ?? []).map((r: any, i: number) => (
                <div
                  key={i}
                  className="flex items-center justify-between p-3 border-b last:border-0"
                >
                  <div>
                    <p className="font-medium">
                      {r.agentName ?? r.agentId ?? `Agent ${i + 1}`}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {r.certification ?? "AML Cert"}
                    </p>
                  </div>
                  <Badge variant="destructive">
                    {r.daysUntilExpiry ?? 0} days
                  </Badge>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </DashboardLayout>
  );
}
