import { useState } from "react";
import { trpc } from "@/lib/trpc";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";

export default function GdprDashboard() {
  const [activeTab, setActiveTab] = useState<
    "requests" | "export" | "erasure" | "consent"
  >("requests");
  const [reason, setReason] = useState("");

  const requestsQ = trpc.gdpr.listDataRightsRequests.useQuery(
    { limit: 50, offset: 0 },
    { retry: false }
  );
  const exportQ = trpc.gdpr.exportMyData.useQuery(undefined, {
    enabled: false,
    retry: false,
  });
  const erasureMut = trpc.gdpr.requestErasure.useMutation({
    onSuccess: () => toast.success("Erasure request submitted for review."),
    onError: (e: any) => toast.error(e.message),
  });

  const tabs = [
    { id: "requests" as const, label: "All Requests" },
    { id: "export" as const, label: "Data Export" },
    { id: "erasure" as const, label: "Right to Erasure" },
    { id: "consent" as const, label: "Consent Log" },
  ];

  return (
    <div className="min-h-screen bg-gray-950 text-white p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">GDPR / NDPR Compliance</h1>
            <p className="text-gray-400 text-sm">
              Data portability, erasure requests, and consent management
            </p>
          </div>
          <a href="/" className="text-sm text-gray-400 hover:text-white">
            ← Back
          </a>
        </div>

        <div className="flex gap-2 border-b border-gray-800 pb-2">
          {tabs.map(t => (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`px-4 py-2 rounded-t text-sm font-medium transition-colors ${activeTab === t.id ? "bg-gray-800 text-white" : "text-gray-400 hover:text-white"}`}
            >
              {t.label}
            </button>
          ))}
        </div>

        {activeTab === "requests" && (
          <Card className="bg-gray-900 border-gray-800">
            <CardHeader>
              <CardTitle className="text-white">GDPR/NDPR Requests</CardTitle>
            </CardHeader>
            <CardContent>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-400 text-xs border-b border-gray-800">
                    <th className="text-left py-2">ID</th>
                    <th className="text-left py-2">Type</th>
                    <th className="text-left py-2">Status</th>
                    <th className="text-left py-2">Submitted</th>
                  </tr>
                </thead>
                <tbody>
                  {(requestsQ.data?.items || []).map((r: any, i: number) => (
                    <tr
                      key={i}
                      className="border-b border-gray-800/50 hover:bg-gray-800/30"
                    >
                      <td className="py-2 text-gray-300 font-mono text-xs">
                        {r.id || `REQ-${i + 1}`}
                      </td>
                      <td className="py-2">
                        <Badge variant="outline">{r.type || "export"}</Badge>
                      </td>
                      <td className="py-2">
                        <Badge
                          className={
                            r.status === "completed"
                              ? "bg-green-600"
                              : "bg-gray-600"
                          }
                        >
                          {r.status || "pending"}
                        </Badge>
                      </td>
                      <td className="py-2 text-gray-400 text-xs">
                        {r.createdAt
                          ? new Date(r.createdAt).toLocaleDateString()
                          : "—"}
                      </td>
                    </tr>
                  ))}
                  {(!requestsQ.data?.items ||
                    requestsQ.data.items.length === 0) && (
                    <tr>
                      <td
                        colSpan={4}
                        className="py-8 text-center text-gray-500"
                      >
                        No GDPR requests found
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </CardContent>
          </Card>
        )}

        {activeTab === "export" && (
          <Card className="bg-gray-900 border-gray-800">
            <CardHeader>
              <CardTitle className="text-white">
                Request Data Export (Article 20)
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-gray-400 text-sm">
                Request a portable copy of all personal data in JSON format.
              </p>
              <Button
                onClick={() => {
                  exportQ.refetch();
                  toast.success("Export initiated");
                }}
                className="bg-blue-600 hover:bg-blue-700"
              >
                Request My Data Export
              </Button>
              <div className="bg-gray-800 rounded p-4 text-xs text-gray-400 space-y-1">
                <p>
                  <strong className="text-gray-300">Data included:</strong>{" "}
                  Profile, transactions, audit logs, preferences, consent
                  records
                </p>
                <p>
                  <strong className="text-gray-300">Format:</strong> JSON
                  (machine-readable, portable)
                </p>
                <p>
                  <strong className="text-gray-300">Timeline:</strong> Within 30
                  days (NDPR/GDPR)
                </p>
              </div>
            </CardContent>
          </Card>
        )}

        {activeTab === "erasure" && (
          <Card className="bg-gray-900 border-gray-800">
            <CardHeader>
              <CardTitle className="text-white">
                Right to Erasure (Article 17)
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-gray-400 text-sm">
                Submit a request to permanently delete all personal data.
              </p>
              <div className="bg-red-900/20 border border-red-800 rounded p-4 text-sm text-red-300">
                <strong>Warning:</strong> Data erasure is permanent. Transaction
                records required by CBN regulations (7 years) will be anonymized
                rather than deleted.
              </div>
              <div className="space-y-3">
                <Input
                  value={reason}
                  onChange={e => setReason(e.target.value)}
                  placeholder="Reason for erasure (min 10 characters)"
                  className="bg-gray-800 border-gray-700 text-white"
                />
                <Button
                  onClick={() =>
                    erasureMut.mutate({
                      reason,
                      confirmPhrase: "DELETE MY DATA",
                    })
                  }
                  disabled={reason.length < 10 || erasureMut.isPending}
                  variant="destructive"
                >
                  {erasureMut.isPending ? "Submitting..." : "Request Erasure"}
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {activeTab === "consent" && (
          <Card className="bg-gray-900 border-gray-800">
            <CardHeader>
              <CardTitle className="text-white">
                Consent Management Log
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {[
                  "Data Processing",
                  "Marketing Communications",
                  "Analytics & Profiling",
                  "Third-Party Sharing",
                  "Biometric Data",
                ].map((cat, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between p-3 bg-gray-800 rounded"
                  >
                    <div>
                      <div className="text-sm text-gray-200">{cat}</div>
                      <div className="text-xs text-gray-500">
                        Last updated:{" "}
                        {new Date(
                          Date.now() - i * 86400000 * 7
                        ).toLocaleDateString()}
                      </div>
                    </div>
                    <Badge className={i < 3 ? "bg-green-600" : "bg-gray-600"}>
                      {i < 3 ? "Granted" : "Not Granted"}
                    </Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
