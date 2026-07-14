import {
    AlertCircle,
    ArrowLeft,
    Building2,
    CheckCircle,
    CheckSquare,
    Clock,
    Eye,
    Filter,
    Plus,
    RefreshCw,
    Search,
    Shield,
    Upload,
    X,
} from "lucide-react";
import { useEffect, useState } from "react";
// import { useLocation } from "wouter";
import { Alert, AlertDescription } from "../components/ui/alert";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import {
    Card,
    CardContent,
    CardDescription,
    CardHeader,
    CardTitle,
} from "../components/ui/card";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "../components/ui/dialog";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "../components/ui/select";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "../components/ui/table";
import {
    Tabs,
    TabsContent,
    TabsList,
    TabsTrigger,
} from "../components/ui/tabs";
import { kybService } from "../services/kybService";
import type {
    Business,
    BusinessVerificationPayload,
    RegisterBusinessPayload,
} from "../types/kyb";

export default function BusinessManagement() {
  // const [, setLocation] = useLocation();
  const [businesses, setBusinesses] = useState<Business[]>([]);
  const [loading, setLoading] = useState(true);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [selectedBusiness, setSelectedBusiness] = useState<Business | null>(
    null,
  );
  const [verifying, setVerifying] = useState(false);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [addingBusiness, setAddingBusiness] = useState(false);
  const [uploadingDocuments, setUploadingDocuments] = useState(false);
  const [newBusiness, setNewBusiness] = useState<RegisterBusinessPayload>({
    business_name: "",
    registration_number: "",
    tin: "",
    contact_email: "",
    contact_phone: "",
    business_type: "",
    industry: "",
    country: "Nigeria",
    address: "",
    documents: [],
  });

  // Fetch all businesses
  const fetchBusinesses = async () => {
    try {
      setLoading(true);
      const data = await kybService.getAllBusinesses();
      setBusinesses(Array.isArray(data) ? data : []);
      setError(null);
    } catch (err: unknown) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to fetch businesses";
      setError(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBusinesses();
  }, []);

  // Filter businesses
  const filteredBusinesses = businesses.filter((business) => {
    const matchesSearch =
      business.business_name
        ?.toLowerCase()
        .includes(searchQuery.toLowerCase()) ||
      business.business_id?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      business.contact_email
        ?.toLowerCase()
        .includes(searchQuery.toLowerCase()) ||
      business.contact_phone?.toLowerCase().includes(searchQuery.toLowerCase());

    const matchesStatus =
      statusFilter === "all" || business.verification_status === statusFilter;

    return matchesSearch && matchesStatus;
  });

  // Status badge
  const getStatusBadge = (status: string) => {
    const statusConfig: Record<
      string,
      {
        variant: "default" | "secondary" | "destructive" | "outline";
        className: string;
      }
    > = {
      pending: {
        variant: "secondary",
        className: "bg-yellow-100 text-yellow-800",
      },
      approved: {
        variant: "default",
        className: "bg-green-100 text-green-800",
      },
      rejected: {
        variant: "destructive",
        className: "bg-red-100 text-red-800",
      },
      under_review: {
        variant: "outline",
        className: "bg-blue-100 text-blue-800",
      },
    };

    const config = statusConfig[status] || statusConfig.pending;

    return (
      <Badge variant={config.variant} className={config.className}>
        {status.replace("_", " ")}
      </Badge>
    );
  };

  // Handle verify business
  const handleVerifyBusiness = async (business: Business) => {
    try {
      setVerifying(true);

      const payload: BusinessVerificationPayload = {
        business_name: business.business_name,
        registration_number: business.registration_number,
        tin: business.tin,
        business_type: business.business_type,
        industry: business.industry,
        country: business.country,
        address: business.address,
        contact_email: business.contact_email,
        contact_phone: business.contact_phone,
        documents: business.documents,
        verification_path: "cac_tin_verification",
        metadata: business.metadata,
      };

      await kybService.verifyBusiness(business.business_id, payload);

      setSuccess(
        `Business "${business.business_name}" verification started successfully!`,
      );
      setError(null);

      // Refresh businesses list
      await fetchBusinesses();

      // Auto-clear success message after 5 seconds
      setTimeout(() => setSuccess(null), 5000);
    } catch (err: unknown) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to verify business";
      setError(errorMessage);
      setSuccess(null);
    } finally {
      setVerifying(false);
    }
  };

  // Handle approve business
  const handleApproveBusiness = async (business: Business) => {
    try {
      setVerifying(true);
      await kybService.updateBusinessStatus(business.business_id, "approved");
      setSuccess(`Business "${business.business_name}" approved successfully!`);
      setError(null);
      await fetchBusinesses();
      setTimeout(() => setSuccess(null), 5000);
    } catch (err: unknown) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to approve business";
      setError(errorMessage);
      setSuccess(null);
    } finally {
      setVerifying(false);
    }
  };

  // Handle document upload
  const handleDocumentUpload = async (file: File, documentType: string) => {
    try {
      setUploadingDocuments(true);
      const response = await kybService.uploadDocument(file, documentType);

      // Add the uploaded document to the newBusiness state
      setNewBusiness({
        ...newBusiness,
        documents: [
          ...(newBusiness.documents || []),
          { title: documentType, url: response.url },
        ],
      });

      setError(null);
    } catch (err: unknown) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to upload document";
      setError(errorMessage);
    } finally {
      setUploadingDocuments(false);
    }
  };

  // Remove uploaded document
  const handleRemoveDocument = (url: string) => {
    setNewBusiness({
      ...newBusiness,
      documents: newBusiness.documents?.filter((doc) => doc.url !== url),
    });
  };

  // Handle add business
  const handleAddBusiness = async () => {
    try {
      setAddingBusiness(true);
      await kybService.registerBusiness(newBusiness);
      setSuccess(
        `Business "${newBusiness.business_name}" registered successfully!`,
      );
      setError(null);
      setShowAddDialog(false);
      // Reset form
      setNewBusiness({
        business_name: "",
        registration_number: "",
        tin: "",
        contact_email: "",
        contact_phone: "",
        business_type: "",
        industry: "",
        country: "Nigeria",
        address: "",
        documents: [],
      });
      await fetchBusinesses();
      setTimeout(() => setSuccess(null), 5000);
    } catch (err: unknown) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to register business";
      setError(errorMessage);
      setSuccess(null);
    } finally {
      setAddingBusiness(false);
    }
  };

  // Stats
  const stats = {
    total: businesses.length,
    pending: businesses.filter((b) => b.verification_status === "pending")
      .length,
    approved: businesses.filter((b) => b.verification_status === "approved")
      .length,
    rejected: businesses.filter((b) => b.verification_status === "rejected")
      .length,
    under_review: businesses.filter(
      (b) => b.verification_status === "under_review",
    ).length,
  };

  return (
    <div className="container mx-auto py-8 px-4">
      <div className="mb-6">
        <Button variant="ghost" onClick={() => window.history.back()} className="mb-4">
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back
        </Button>

        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold mb-2">Business Management</h1>
            <p className="text-muted-foreground">
              View and manage all registered businesses, verify KYB information
            </p>
          </div>
          <div className="flex gap-2">
            <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
              <DialogTrigger asChild>
                <Button>
                  <Plus className="h-4 w-4 mr-2" />
                  Add Business
                </Button>
              </DialogTrigger>
              <DialogContent className="max-w-2xl">
                <DialogHeader>
                  <DialogTitle>Register New Business</DialogTitle>
                  <DialogDescription>
                    Add a new business to the system
                  </DialogDescription>
                </DialogHeader>
                <div className="grid grid-cols-2 gap-4 py-4">
                  <div className="col-span-2">
                    <Label htmlFor="business_name">Business Name *</Label>
                    <Input
                      id="business_name"
                      value={newBusiness.business_name}
                      onChange={(e) =>
                        setNewBusiness({
                          ...newBusiness,
                          business_name: e.target.value,
                        })
                      }
                      placeholder="Enter business name"
                    />
                  </div>
                  <div>
                    <Label htmlFor="registration_number">
                      Registration Number (RC)
                    </Label>
                    <Input
                      id="registration_number"
                      value={newBusiness.registration_number}
                      onChange={(e) =>
                        setNewBusiness({
                          ...newBusiness,
                          registration_number: e.target.value,
                        })
                      }
                      placeholder="RC1234567"
                    />
                  </div>
                  <div>
                    <Label htmlFor="tin">Tax Identification Number (TIN)</Label>
                    <Input
                      id="tin"
                      value={newBusiness.tin}
                      onChange={(e) =>
                        setNewBusiness({ ...newBusiness, tin: e.target.value })
                      }
                      placeholder="12345678-0001"
                    />
                  </div>
                  <div>
                    <Label htmlFor="contact_email">Contact Email</Label>
                    <Input
                      id="contact_email"
                      type="email"
                      value={newBusiness.contact_email}
                      onChange={(e) =>
                        setNewBusiness({
                          ...newBusiness,
                          contact_email: e.target.value,
                        })
                      }
                      placeholder="contact@business.com"
                    />
                  </div>
                  <div>
                    <Label htmlFor="contact_phone">Contact Phone</Label>
                    <Input
                      id="contact_phone"
                      value={newBusiness.contact_phone}
                      onChange={(e) =>
                        setNewBusiness({
                          ...newBusiness,
                          contact_phone: e.target.value,
                        })
                      }
                      placeholder="+234..."
                    />
                  </div>
                  <div>
                    <Label htmlFor="business_type">Business Type</Label>
                    <Input
                      id="business_type"
                      value={newBusiness.business_type}
                      onChange={(e) =>
                        setNewBusiness({
                          ...newBusiness,
                          business_type: e.target.value,
                        })
                      }
                      placeholder="LLC, Corporation, etc."
                    />
                  </div>
                  <div>
                    <Label htmlFor="industry">Industry</Label>
                    <Input
                      id="industry"
                      value={newBusiness.industry}
                      onChange={(e) =>
                        setNewBusiness({
                          ...newBusiness,
                          industry: e.target.value,
                        })
                      }
                      placeholder="Technology, Manufacturing, etc."
                    />
                  </div>
                  <div>
                    <Label htmlFor="country">Country</Label>
                    <Input
                      id="country"
                      value={newBusiness.country}
                      onChange={(e) =>
                        setNewBusiness({
                          ...newBusiness,
                          country: e.target.value,
                        })
                      }
                      placeholder="Nigeria"
                    />
                  </div>
                  <div className="col-span-2">
                    <Label htmlFor="address">Address</Label>
                    <Input
                      id="address"
                      value={newBusiness.address}
                      onChange={(e) =>
                        setNewBusiness({
                          ...newBusiness,
                          address: e.target.value,
                        })
                      }
                      placeholder="Business address"
                    />
                  </div>

                  <div className="col-span-2 mt-4">
                    <Label>Supporting Documents</Label>
                    <div className="mt-2 space-y-3">
                      <div className="flex gap-2">
                        <Input
                          id="document_upload"
                          type="file"
                          onChange={async (e) => {
                            const file = e.target.files?.[0];
                            if (file) {
                              await handleDocumentUpload(
                                file,
                                "business_document",
                              );
                              // Reset file input
                              e.target.value = "";
                            }
                          }}
                          disabled={uploadingDocuments}
                          className="flex-1"
                        />
                        <Button
                          type="button"
                          variant="outline"
                          disabled={uploadingDocuments}
                          onClick={() =>
                            document.getElementById("document_upload")?.click()
                          }
                        >
                          <Upload className="h-4 w-4 mr-2" />
                          {uploadingDocuments ? "Uploading..." : "Upload"}
                        </Button>
                      </div>

                      {newBusiness.documents &&
                        newBusiness.documents.length > 0 && (
                          <div className="border rounded-md p-3 space-y-2">
                            <p className="text-sm font-medium">
                              Uploaded Documents ({newBusiness.documents.length}
                              )
                            </p>
                            {newBusiness.documents.map((doc, index) => (
                              <div
                                key={index}
                                className="flex items-center justify-between bg-muted p-2 rounded text-sm"
                              >
                                <span className="flex-1 truncate">
                                  {doc.title}
                                </span>
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleRemoveDocument(doc.url)}
                                  className="h-6 w-6 p-0"
                                >
                                  <X className="h-4 w-4" />
                                </Button>
                              </div>
                            ))}
                          </div>
                        )}
                    </div>
                  </div>
                </div>
                <DialogFooter>
                  <Button
                    variant="outline"
                    onClick={() => setShowAddDialog(false)}
                    disabled={addingBusiness}
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={handleAddBusiness}
                    disabled={addingBusiness || !newBusiness.business_name}
                  >
                    {addingBusiness ? "Registering..." : "Register Business"}
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
            <Button
              onClick={fetchBusinesses}
              disabled={loading}
              variant="outline"
            >
              <RefreshCw
                className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`}
              />
              Refresh
            </Button>
          </div>
        </div>
      </div>

      {success && (
        <Alert className="mb-6 border-green-500 bg-green-50">
          <CheckCircle className="h-4 w-4 text-green-600" />
          <AlertDescription className="text-green-800">
            {success}
          </AlertDescription>
        </Alert>
      )}

      {error && (
        <Alert variant="destructive" className="mb-6">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-6">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Businesses</CardDescription>
            <CardTitle className="text-3xl">{stats.total}</CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Pending</CardDescription>
            <CardTitle className="text-3xl text-yellow-600">
              {stats.pending}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Under Review</CardDescription>
            <CardTitle className="text-3xl text-blue-600">
              {stats.under_review}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Approved</CardDescription>
            <CardTitle className="text-3xl text-green-600">
              {stats.approved}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Rejected</CardDescription>
            <CardTitle className="text-3xl text-red-600">
              {stats.rejected}
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      {/* Filters */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Filter className="h-5 w-5" />
            Filters
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="relative">
              <Search className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search by name, ID, email, phone..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10"
              />
            </div>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger>
                <SelectValue placeholder="All Statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All Statuses</SelectItem>
                <SelectItem value="pending">Pending</SelectItem>
                <SelectItem value="under_review">Under Review</SelectItem>
                <SelectItem value="approved">Approved</SelectItem>
                <SelectItem value="rejected">Rejected</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {/* Businesses Table */}
      <Card>
        <CardHeader>
          <CardTitle>Businesses ({filteredBusinesses.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Business Name</TableHead>
                  <TableHead>Contact</TableHead>
                  <TableHead>Registration</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredBusinesses.map((business) => (
                  <TableRow key={business.business_id}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <Building2 className="h-5 w-5 text-blue-600" />
                        <div>
                          <div className="font-medium">
                            {business.business_name}
                          </div>
                          <div className="text-sm text-muted-foreground">
                            {business.business_id}
                          </div>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="text-sm">
                        {business.contact_email && (
                          <div>{business.contact_email}</div>
                        )}
                        {business.contact_phone && (
                          <div className="text-muted-foreground">
                            {business.contact_phone}
                          </div>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="text-sm">
                        {business.registration_number && (
                          <div>RC: {business.registration_number}</div>
                        )}
                        {business.tin && (
                          <div className="text-muted-foreground">
                            TIN: {business.tin}
                          </div>
                        )}
                        {business.business_type && (
                          <div className="text-muted-foreground">
                            Type: {business.business_type}
                          </div>
                        )}
                        {business.industry && (
                          <div className="text-muted-foreground">
                            Industry: {business.industry}
                          </div>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      {getStatusBadge(business.verification_status)}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {new Date(business.created_at).toLocaleDateString()}
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        <Dialog>
                          <DialogTrigger asChild>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => setSelectedBusiness(business)}
                            >
                              <Eye className="h-4 w-4 mr-1" />
                              View
                            </Button>
                          </DialogTrigger>
                          <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
                            <DialogHeader>
                              <DialogTitle>Business Details</DialogTitle>
                              <DialogDescription>
                                {business.business_name} -{" "}
                                {business.business_id}
                              </DialogDescription>
                            </DialogHeader>
                            {selectedBusiness && (
                              <BusinessDetailsDialog
                                business={selectedBusiness}
                              />
                            )}
                            <DialogFooter>
                              {selectedBusiness?.verification_status ===
                                "pending" && (
                                <>
                                  <Button
                                    onClick={() =>
                                      handleVerifyBusiness(selectedBusiness)
                                    }
                                    disabled={verifying}
                                  >
                                    <Shield className="h-4 w-4 mr-2" />
                                    Start Verification
                                  </Button>
                                  <Button
                                    variant="default"
                                    onClick={() =>
                                      handleApproveBusiness(selectedBusiness)
                                    }
                                    disabled={verifying}
                                  >
                                    <CheckSquare className="h-4 w-4 mr-2" />
                                    Approve
                                  </Button>
                                </>
                              )}
                              {selectedBusiness?.verification_status ===
                                "approved" && (
                                <Button
                                  variant="outline"
                                  onClick={() =>
                                    handleVerifyBusiness(selectedBusiness)
                                  }
                                  disabled={verifying}
                                >
                                  <RefreshCw className="h-4 w-4 mr-2" />
                                  Reverify
                                </Button>
                              )}
                            </DialogFooter>
                          </DialogContent>
                        </Dialog>

                        {business.verification_status === "pending" && (
                          <Button
                            variant="default"
                            size="sm"
                            onClick={() => handleVerifyBusiness(business)}
                            disabled={verifying}
                          >
                            <Shield className="h-4 w-4 mr-1" />
                            Verify
                          </Button>
                        )}
                        {business.verification_status === "approved" && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleVerifyBusiness(business)}
                            disabled={verifying}
                          >
                            <RefreshCw className="h-4 w-4 mr-1" />
                            Reverify
                          </Button>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
                {filteredBusinesses.length === 0 && (
                  <TableRow>
                    <TableCell
                      colSpan={6}
                      className="text-center py-12 text-muted-foreground"
                    >
                      No businesses found
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

// Business Details Dialog Component
function BusinessDetailsDialog({ business }: { business: Business }) {
  return (
    <Tabs defaultValue="overview" className="w-full">
      <TabsList className="grid w-full grid-cols-3">
        <TabsTrigger value="overview">Overview</TabsTrigger>
        <TabsTrigger value="documents">Documents</TabsTrigger>
        <TabsTrigger value="verification">Verification</TabsTrigger>
      </TabsList>

      <TabsContent value="overview" className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Business Information</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-muted-foreground">Business Name</p>
                <p className="font-medium">{business.business_name}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Business ID</p>
                <p className="font-medium">{business.business_id}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">
                  Registration Number
                </p>
                <p className="font-medium">
                  {business.registration_number || "N/A"}
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">TIN</p>
                <p className="font-medium">{business.tin || "N/A"}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Business Type</p>
                <p className="font-medium">{business.business_type || "N/A"}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Industry</p>
                <p className="font-medium">{business.industry || "N/A"}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Country</p>
                <p className="font-medium">{business.country || "N/A"}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Address</p>
                <p className="font-medium">{business.address || "N/A"}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Contact Email</p>
                <p className="font-medium">{business.contact_email || "N/A"}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Contact Phone</p>
                <p className="font-medium">{business.contact_phone || "N/A"}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Tenant ID</p>
                <p className="font-medium">{business.tenant_id}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Status</p>
                <p className="font-medium capitalize">
                  {business.verification_status}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </TabsContent>

      <TabsContent value="documents">
        <Card>
          <CardHeader>
            <CardTitle>Uploaded Documents</CardTitle>
          </CardHeader>
          <CardContent>
            {business.documents && business.documents.length > 0 ? (
              <div className="space-y-2">
                {business.documents.map((doc, index) => (
                  <div
                    key={index}
                    className="flex items-center justify-between p-3 border rounded-lg"
                  >
                    <span className="font-medium">{doc.title}</span>
                    <Button variant="outline" size="sm" asChild>
                      <a
                        href={doc.url.startsWith('http') ? doc.url : `https://${doc.url}`}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        View
                      </a>
                    </Button>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-muted-foreground">No documents uploaded</p>
            )}
          </CardContent>
        </Card>
      </TabsContent>

      <TabsContent value="verification">
        <Card>
          <CardHeader>
            <CardTitle>Verification History</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 border rounded-lg">
                <div>
                  <p className="font-medium">Created At</p>
                  <p className="text-sm text-muted-foreground">
                    {new Date(business.created_at).toLocaleString()}
                  </p>
                </div>
                <Clock className="h-5 w-5 text-gray-400" />
              </div>
              {business.verification_date && (
                <div className="flex items-center justify-between p-3 border rounded-lg">
                  <div>
                    <p className="font-medium">Verified At</p>
                    <p className="text-sm text-muted-foreground">
                      {new Date(business.verification_date).toLocaleString()}
                    </p>
                  </div>
                  <CheckCircle className="h-5 w-5 text-green-600" />
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </TabsContent>
    </Tabs>
  );
}
