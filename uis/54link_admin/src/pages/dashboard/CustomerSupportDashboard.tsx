import { usePermissions } from "@/_core/hooks/usePermissions";
import { AlertCircle, CheckCircle, Clock, Headphones, Ticket } from "lucide-react";
import { useEffect } from "react";
import { useDashboardData } from "../../hooks/useDashboardData";

export default function CustomerSupportDashboard() {
  const { transactions, loading } = useDashboardData();
  const { checkPermissions } = usePermissions();

  useEffect(() => {
    checkPermissions([
      { resourceType: "platform", permission: "provide_support" },
    ]);
  }, []);

  const failedTxns = transactions.filter(
    (t) => t.status?.toLowerCase() === "failed",
  );
  const pendingTxns = transactions.filter(
    (t) => t.status?.toLowerCase() === "pending",
  );
  const today = new Date();
  const resolvedToday = transactions.filter((t) => {
    if (t.status?.toLowerCase() !== "success") return false;
    const txnDate = new Date(t.created_at || t.timestamp);
    return txnDate.toDateString() === today.toDateString();
  });
  const recentIssues = [...failedTxns, ...pendingTxns].slice(0, 5);

  return (
    <div className="p-8">
      <div className="flex items-center gap-3 mb-2">
        <Headphones className="w-8 h-8" />
        <h1 className="text-2xl font-bold">Customer Support Dashboard</h1>
      </div>
      <p className="text-muted-foreground mb-8">
        Welcome, Customer Support! Manage tickets and customer queries.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Failed Transactions</p>
              <p className="text-2xl font-bold mt-2">
                {loading ? "..." : failedTxns.length}
              </p>
              <p className="text-xs text-orange-600 mt-1">Need attention</p>
            </div>
            <Ticket className="h-8 w-8 text-orange-500" />
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Pending</p>
              <p className="text-2xl font-bold mt-2">
                {loading ? "..." : pendingTxns.length}
              </p>
              <p className="text-xs text-yellow-600 mt-1">Awaiting processing</p>
            </div>
            <Clock className="h-8 w-8 text-yellow-500" />
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Resolved Today</p>
              <p className="text-2xl font-bold mt-2">
                {loading ? "..." : resolvedToday.length}
              </p>
              <p className="text-xs text-green-600 mt-1">Successful today</p>
            </div>
            <CheckCircle className="h-8 w-8 text-green-500" />
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Total Issues</p>
              <p className="text-2xl font-bold mt-2">
                {loading ? "..." : (failedTxns.length + pendingTxns.length)}
              </p>
              <p className="text-xs text-orange-600 mt-1">Failed + pending</p>
            </div>
            <Clock className="h-8 w-8 text-blue-500" />
          </div>
        </div>
      </div>

      <div className="bg-card border rounded-lg p-6">
        <h3 className="font-semibold mb-4">Recent Issues (Failed & Pending Transactions)</h3>
        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="animate-pulse h-14 bg-muted rounded" />
            ))}
          </div>
        ) : recentIssues.length === 0 ? (
          <div className="flex flex-col items-center py-8 text-center">
            <CheckCircle className="h-10 w-10 text-green-500 mb-2" />
            <p className="text-sm text-muted-foreground">No issues found. All transactions are successful!</p>
          </div>
        ) : (
          <div className="space-y-3">
            {recentIssues.map((t, i) => (
              <div key={t.id || i} className="flex justify-between items-start p-3 border rounded hover:bg-accent">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`text-xs px-2 py-1 rounded ${t.status?.toLowerCase() === "failed" ? "bg-red-100 text-red-700" : "bg-yellow-100 text-yellow-700"}`}>
                      {t.status?.toLowerCase() === "failed" ? "Failed" : "Pending"}
                    </span>
                    <p className="text-sm font-medium truncate">
                      {t.reference || t.transaction_id || `TXN-${i + 1}`}
                    </p>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Amount: ₦{((t.amount || 0) / 100).toLocaleString()} •{" "}
                    {t.created_at ? new Date(t.created_at).toLocaleString() : "—"}
                  </p>
                </div>
                {t.status?.toLowerCase() === "failed" ? (
                  <AlertCircle className="h-4 w-4 text-red-500 shrink-0 mt-1" />
                ) : (
                  <Clock className="h-4 w-4 text-yellow-500 shrink-0 mt-1" />
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
