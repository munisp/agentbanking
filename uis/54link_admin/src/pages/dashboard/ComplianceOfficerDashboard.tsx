import { AlertTriangle, CheckCircle, FileText, Shield } from "lucide-react";

export default function ComplianceOfficerDashboard() {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-6">Compliance Officer Dashboard</h1>
      <p className="text-muted-foreground mb-8">
        Welcome, Compliance Officer! Monitor compliance and risk assessments.
      </p>

      {/* Compliance Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Compliance Score</p>
              <p className="text-2xl font-bold mt-2">96%</p>
              <p className="text-xs text-green-600 mt-1">Excellent standing</p>
            </div>
            <Shield className="h-8 w-8 text-green-500" />
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Open Risks</p>
              <p className="text-2xl font-bold mt-2">4</p>
              <p className="text-xs text-orange-600 mt-1">2 medium, 2 low</p>
            </div>
            <AlertTriangle className="h-8 w-8 text-orange-500" />
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Audits Passed</p>
              <p className="text-2xl font-bold mt-2">18/20</p>
              <p className="text-xs text-green-600 mt-1">90% success rate</p>
            </div>
            <CheckCircle className="h-8 w-8 text-blue-500" />
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-muted-foreground">Reports Due</p>
              <p className="text-2xl font-bold mt-2">3</p>
              <p className="text-xs text-orange-600 mt-1">This week</p>
            </div>
            <FileText className="h-8 w-8 text-purple-500" />
          </div>
        </div>
      </div>

      {/* Compliance Details */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-card border rounded-lg p-6">
          <h3 className="font-semibold mb-4">Risk Assessment</h3>
          <div className="space-y-3">
            <div className="p-3 border-l-4 border-orange-500 bg-orange-50 dark:bg-orange-950 rounded">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-sm font-medium">KYC Documentation Gap</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    12 customers pending verification
                  </p>
                </div>
                <span className="text-xs px-2 py-1 bg-orange-200 text-orange-800 rounded">
                  Medium
                </span>
              </div>
            </div>
            <div className="p-3 border-l-4 border-yellow-500 bg-yellow-50 dark:bg-yellow-950 rounded">
              <div className="flex justify-between items-start">
                <div>
                  <p className="text-sm font-medium">Transaction Monitoring</p>
                  <p className="text-xs text-muted-foreground mt-1">
                    3 flagged transactions
                  </p>
                </div>
                <span className="text-xs px-2 py-1 bg-yellow-200 text-yellow-800 rounded">
                  Low
                </span>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-card border rounded-lg p-6">
          <h3 className="font-semibold mb-4">Upcoming Audits</h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center py-2 border-b">
              <div>
                <p className="text-sm font-medium">AML Compliance Review</p>
                <p className="text-xs text-muted-foreground">External audit</p>
              </div>
              <span className="text-xs text-muted-foreground">In 5 days</span>
            </div>
            <div className="flex justify-between items-center py-2 border-b">
              <p className="text-sm font-medium">Data Privacy Assessment</p>
              <span className="text-xs text-muted-foreground">In 12 days</span>
            </div>
            <div className="flex justify-between items-center py-2">
              <p className="text-sm font-medium">Security Controls Review</p>
              <span className="text-xs text-muted-foreground">In 18 days</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
