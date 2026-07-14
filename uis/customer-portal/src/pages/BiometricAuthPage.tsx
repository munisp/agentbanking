import DashboardLayout from "@/components/DashboardLayout";
import { trpc } from "@/lib/trpc";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Fingerprint, ScanFace, Eye } from "lucide-react";

export default function BiometricAuthPage() {
  const records = trpc.biometricAuth.list.useQuery();
  const analytics = trpc.biometricAuth.analytics.useQuery();
  const typeIcons: Record<string, any> = {
    fingerprint: Fingerprint,
    face: ScanFace,
    iris: Eye,
  };

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div>
          <h1 className="text-2xl font-bold">Biometric Authentication</h1>
          <p className="text-muted-foreground">
            Fingerprint, face, and iris enrollment and verification
          </p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">
                Total Enrollments
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">
                {analytics.data?.enrolled ?? 0}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">
                Total Verifications
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">
                {analytics.data?.totalVerifications ?? 0}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">
                Total Verifications
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold">
                {analytics.data?.totalVerifications ?? 0}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-muted-foreground">
                Failed Attempts
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-2xl font-bold text-red-600">
                {analytics.data?.totalFailedAttempts ?? 0}
              </p>
            </CardContent>
          </Card>
        </div>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Fingerprint className="h-5 w-5" /> Biometric Records
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left p-2">Agent</th>
                    <th className="text-left p-2">Type</th>
                    <th className="text-left p-2">Quality</th>
                    <th className="text-right p-2">Verifications</th>
                    <th className="text-right p-2">Failed</th>
                    <th className="text-left p-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {records.data?.records?.map((r: any) => {
                    const Icon = typeIcons[r.type] || Fingerprint;
                    return (
                      <tr key={r.id} className="border-b">
                        <td className="p-2">{r.agentName}</td>
                        <td className="p-2 flex items-center gap-1">
                          <Icon className="h-4 w-4" />
                          {r.type}
                        </td>
                        <td className="p-2">
                          <Badge
                            variant={r.quality > 80 ? "default" : "secondary"}
                          >
                            {r.quality}%
                          </Badge>
                        </td>
                        <td className="p-2 text-right">
                          {r.verificationCount}
                        </td>
                        <td className="p-2 text-right text-red-600">
                          {r.failedAttempts}
                        </td>
                        <td className="p-2">
                          <Badge
                            variant={
                              r.status === "active" ? "default" : "destructive"
                            }
                          >
                            {r.status}
                          </Badge>
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
    </DashboardLayout>
  );
}
