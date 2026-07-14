import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { developerPlatformService } from "@/services/developerPlatform";
import type {
    AppPendingReview,
    AppReviewDetails,
    ApproveAppRequest,
    RejectAppRequest,
} from "@/types/developerPlatform";
import { AlertCircle, CheckCircle, Clock, XCircle } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";

export default function AppReview() {
  const [apps, setApps] = useState<AppPendingReview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedApp, setSelectedApp] = useState<AppReviewDetails | null>(null);
  const [detailsDialog, setDetailsDialog] = useState(false);
  const [approveDialog, setApproveDialog] = useState(false);
  const [rejectDialog, setRejectDialog] = useState(false);

  useEffect(() => {
    loadApps();
  }, []);

  const loadApps = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await developerPlatformService.listAppsPendingReview();
      setApps(response.apps);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to load apps";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const loadAppDetails = async (appId: string) => {
    try {
      const details = await developerPlatformService.getAppReviewDetails(appId);
      setSelectedApp(details);
      setDetailsDialog(true);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to load app details";
      toast.error(message);
    }
  };

  const handleApprove = async (data: ApproveAppRequest) => {
    if (!selectedApp) return;

    try {
      await developerPlatformService.approveApp(selectedApp.app_id, data);
      toast.success(`${selectedApp.name} has been approved and published.`);
      setApproveDialog(false);
      setDetailsDialog(false);
      loadApps();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to approve app";
      toast.error(message);
    }
  };

  const handleReject = async (data: RejectAppRequest) => {
    if (!selectedApp) return;

    try {
      await developerPlatformService.rejectApp(selectedApp.app_id, data);
      toast.success(`${selectedApp.name} has been rejected.`);
      setRejectDialog(false);
      setDetailsDialog(false);
      loadApps();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to reject app";
      toast.error(message);
    }
  };

  const getReviewStatusBadge = (status: string) => {
    type VariantConfig = { variant: string; icon: React.ElementType };
    const variants: Record<string, VariantConfig> = {
      pending: { variant: "secondary", icon: Clock },
      in_progress: { variant: "outline", icon: Clock },
      completed: { variant: "default", icon: CheckCircle },
      failed: { variant: "destructive", icon: XCircle },
    };
    const config = variants[status] || variants.pending;
    const Icon = config.icon;
    return (
      <Badge variant={config.variant as "default" | "destructive" | "outline" | "secondary"}>
        <Icon className="mr-1 h-3 w-3" />
        {status}
      </Badge>
    );
  };

  if (error) {
    return (
      <div className="p-6">
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
        <Button onClick={loadApps} className="mt-4">
          Retry
        </Button>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">App Review & Approval</h1>
          <p className="text-muted-foreground">
            Review and approve apps pending submission
          </p>
        </div>
        <Button onClick={loadApps} variant="outline">
          Refresh
        </Button>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Pending Review
            </CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{apps.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">High Priority</CardTitle>
            <AlertCircle className="h-4 w-4 text-red-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">
              {apps.filter((a) => a.priority === "high").length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Avg Review Time
            </CardTitle>
            <Clock className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">3.5 days</div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>App</TableHead>
                <TableHead>Developer</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Version</TableHead>
                <TableHead>Submitted</TableHead>
                <TableHead>Days in Review</TableHead>
                <TableHead>Priority</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={9} className="text-center py-8">
                    Loading apps...
                  </TableCell>
                </TableRow>
              ) : apps.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={9} className="text-center py-8">
                    No apps pending review
                  </TableCell>
                </TableRow>
              ) : (
                apps.map((app) => (
                  <TableRow key={app.app_id}>
                    <TableCell>
                      <div className="font-medium">{app.name}</div>
                    </TableCell>
                    <TableCell>
                      <div>
                        <div className="text-sm">{app.developer_name}</div>
                        <div className="text-xs text-muted-foreground">
                          {app.organization_name}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{app.category}</Badge>
                    </TableCell>
                    <TableCell>{app.version}</TableCell>
                    <TableCell>
                      {new Date(app.submitted_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          app.days_in_review > 5 ? "destructive" : "secondary"
                        }
                      >
                        {app.days_in_review} days
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          app.priority === "high"
                            ? "destructive"
                            : app.priority === "normal"
                              ? "default"
                              : "secondary"
                        }
                      >
                        {app.priority}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        {getReviewStatusBadge(app.review_status.security_scan)}
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => loadAppDetails(app.app_id)}
                      >
                        Review
                      </Button>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* App Details Dialog */}
      {selectedApp && (
        <Dialog open={detailsDialog} onOpenChange={setDetailsDialog}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>{selectedApp.name}</DialogTitle>
              <DialogDescription>
                Version {selectedApp.version}
              </DialogDescription>
            </DialogHeader>

            <Tabs defaultValue="overview">
              <TabsList>
                <TabsTrigger value="overview">Overview</TabsTrigger>
                <TabsTrigger value="security">Security</TabsTrigger>
                <TabsTrigger value="compliance">Compliance</TabsTrigger>
                <TabsTrigger value="testing">Testing</TabsTrigger>
              </TabsList>

              <TabsContent value="overview" className="space-y-4">
                <div>
                  <h3 className="font-semibold mb-2">Description</h3>
                  <p className="text-sm text-muted-foreground">
                    {selectedApp.description}
                  </p>
                </div>
                <div>
                  <h3 className="font-semibold mb-2">Developer</h3>
                  <p className="text-sm">
                    Organization: {selectedApp.organization_id}
                  </p>
                  <p className="text-sm">
                    Developer: {selectedApp.developer_id}
                  </p>
                </div>
                <div>
                  <h3 className="font-semibold mb-2">API Scopes</h3>
                  <div className="flex flex-wrap gap-2">
                    {selectedApp.api_scopes.map((scope) => (
                      <Badge key={scope} variant="secondary">
                        {scope}
                      </Badge>
                    ))}
                  </div>
                </div>
                <div>
                  <h3 className="font-semibold mb-2">Risk Assessment</h3>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-sm">Risk Level:</span>
                      <Badge
                        variant={
                          selectedApp.risk_assessment.risk_level === "low"
                            ? "default"
                            : selectedApp.risk_assessment.risk_level ===
                                "medium"
                              ? "secondary"
                              : "destructive"
                        }
                      >
                        {selectedApp.risk_assessment.risk_level}
                      </Badge>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm">Data Sensitivity:</span>
                      <Badge variant="outline">
                        {selectedApp.risk_assessment.data_sensitivity}
                      </Badge>
                    </div>
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="security" className="space-y-4">
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Security Scan</span>
                    {getReviewStatusBadge(
                      selectedApp.review_checklist.security_scan.status,
                    )}
                  </div>
                  <div className="flex justify-between text-sm">
                    <span>Findings:</span>
                    <span>
                      {selectedApp.review_checklist.security_scan.findings}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span>Severity:</span>
                    <Badge>
                      {selectedApp.review_checklist.security_scan.severity}
                    </Badge>
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="compliance" className="space-y-4">
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-sm">GDPR Compliant</span>
                    {selectedApp.review_checklist.compliance_check
                      .gdpr_compliant ? (
                      <CheckCircle className="h-4 w-4 text-green-600" />
                    ) : (
                      <XCircle className="h-4 w-4 text-red-600" />
                    )}
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm">NDPR Compliant</span>
                    {selectedApp.review_checklist.compliance_check
                      .ndpr_compliant ? (
                      <CheckCircle className="h-4 w-4 text-green-600" />
                    ) : (
                      <XCircle className="h-4 w-4 text-red-600" />
                    )}
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm">PCI DSS Compliant</span>
                    {selectedApp.review_checklist.compliance_check
                      .pci_dss_compliant ? (
                      <CheckCircle className="h-4 w-4 text-green-600" />
                    ) : (
                      <XCircle className="h-4 w-4 text-red-600" />
                    )}
                  </div>
                </div>
              </TabsContent>

              <TabsContent value="testing" className="space-y-4">
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-sm">Test Cases</span>
                    <span className="text-sm font-medium">
                      {
                        selectedApp.review_checklist.functionality_test
                          .test_cases
                      }
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-green-600">Passed</span>
                    <span className="text-sm font-medium">
                      {selectedApp.review_checklist.functionality_test.passed}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-red-600">Failed</span>
                    <span className="text-sm font-medium">
                      {selectedApp.review_checklist.functionality_test.failed}
                    </span>
                  </div>
                </div>
              </TabsContent>
            </Tabs>

            <DialogFooter className="flex gap-2">
              <Button variant="outline" onClick={() => setDetailsDialog(false)}>
                Close
              </Button>
              <Button
                variant="destructive"
                onClick={() => {
                  setDetailsDialog(false);
                  setRejectDialog(true);
                }}
              >
                <XCircle className="mr-2 h-4 w-4" />
                Reject
              </Button>
              <Button
                onClick={() => {
                  setDetailsDialog(false);
                  setApproveDialog(true);
                }}
              >
                <CheckCircle className="mr-2 h-4 w-4" />
                Approve
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      )}

      {/* Approve Dialog */}
      <ApproveDialog
        open={approveDialog}
        onOpenChange={setApproveDialog}
        app={selectedApp}
        onConfirm={handleApprove}
      />

      {/* Reject Dialog */}
      <RejectDialog
        open={rejectDialog}
        onOpenChange={setRejectDialog}
        app={selectedApp}
        onConfirm={handleReject}
      />
    </div>
  );
}

interface ApproveDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  app: AppReviewDetails | null;
  onConfirm: (data: ApproveAppRequest) => void;
}

function ApproveDialog({
  open,
  onOpenChange,
  app,
  onConfirm,
}: ApproveDialogProps) {
  const [releaseNotes, setReleaseNotes] = useState("");
  const [featured, setFeatured] = useState(false);

  const handleSubmit = () => {
    onConfirm({
      complexity_tier: "standard",
      featured,
      categories: [app?.category || ""],
      release_notes: releaseNotes,
      notify_developer: true,
      publish_immediately: true,
    });
    setReleaseNotes("");
    setFeatured(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Approve App</DialogTitle>
          <DialogDescription>
            Approve and publish {app?.name} to the marketplace.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label htmlFor="notes">Release Notes</Label>
            <Textarea
              id="notes"
              value={releaseNotes}
              onChange={(e) => setReleaseNotes(e.target.value)}
              placeholder="App meets all compliance requirements..."
              rows={3}
            />
          </div>
          <div className="flex items-center space-x-2">
            <input
              type="checkbox"
              id="featured"
              checked={featured}
              onChange={(e) => setFeatured(e.target.checked)}
            />
            <Label htmlFor="featured">Feature this app on marketplace</Label>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit}>
            <CheckCircle className="mr-2 h-4 w-4" />
            Approve & Publish
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

interface RejectDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  app: AppReviewDetails | null;
  onConfirm: (data: RejectAppRequest) => void;
}

function RejectDialog({
  open,
  onOpenChange,
  app,
  onConfirm,
}: RejectDialogProps) {
  const [reason, setReason] = useState("");
  const [details, setDetails] = useState("");

  const handleSubmit = () => {
    onConfirm({
      reason,
      details,
      required_fixes: [],
      severity: "medium",
      allow_resubmission: true,
      notify_developer: true,
    });
    setReason("");
    setDetails("");
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Reject App</DialogTitle>
          <DialogDescription>
            Reject {app?.name} and provide feedback to the developer.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <Label htmlFor="reason">Reason *</Label>
            <Input
              id="reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="e.g., Failed security scan"
            />
          </div>
          <div>
            <Label htmlFor="details">Details *</Label>
            <Textarea
              id="details"
              value={details}
              onChange={(e) => setDetails(e.target.value)}
              placeholder="Provide specific details about why the app was rejected..."
              rows={4}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={handleSubmit}
            disabled={!reason || !details}
          >
            <XCircle className="mr-2 h-4 w-4" />
            Reject App
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
