import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useTenantBranding } from "@/contexts/TenantBrandingContext";
import { exportToExcel, exportToPDF } from "@/lib/exportUtils";
import apiClient from "@/services/api";
import { BACKEND_URL } from "@/const";
// import { te } from 'date-fns/locale';
import {
  Activity,
  Building2,
  Download,
  Edit,
  Eye,
  FileText,
  Key,
  Plus,
  Search,
  Trash2,
  TrendingUp,
  Upload,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { Link } from "wouter";
import { trpc } from "../lib/trpc";
import { tenantService, type Tenant, type FeatureFlagConfig } from "../services/tenant";

export default function BankManagement() {
  const [searchTerm, setSearchTerm] = useState("");
  const [filterTier, setFilterTier] = useState("all");
  const [filterStatus, setFilterStatus] = useState("all");
  const { primaryColor, secondaryColor } = useTenantBranding();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  // Removed unused metrics state
  const [isLoading, setIsLoading] = useState(true);
  const [selectedTenant, setSelectedTenant] = useState<Tenant | null>(null);
  const [isDetailsDialogOpen, setIsDetailsDialogOpen] = useState(false);
  const [isEditDialogOpen, setIsEditDialogOpen] = useState(false);
  const [editFormData, setEditFormData] = useState<Record<string, string>>({});
  const [isUploadingCac, setIsUploadingCac] = useState(false);
  const [isUploadingCbn, setIsUploadingCbn] = useState(false);
  const [isUploadingLogo, setIsUploadingLogo] = useState(false);
  const [isUploadingFavicon, setIsUploadingFavicon] = useState(false);
  const cacFileInputRef = useRef<HTMLInputElement>(null);
  const cbnFileInputRef = useRef<HTMLInputElement>(null);
  const logoFileInputRef = useRef<HTMLInputElement>(null);
  const faviconFileInputRef = useRef<HTMLInputElement>(null);
  const [cacDocument, setCacDocument] = useState<File | null>(null);
  const [cbnLicense, setCbnLicense] = useState<File | null>(null);
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [faviconFile, setFaviconFile] = useState<File | null>(null);
  const [editFeatureFlags, setEditFeatureFlags] = useState<Set<string>>(new Set());
  const [globalFeatures, setGlobalFeatures] = useState<FeatureFlagConfig[]>([]);

  // Fetch tenants function
  const fetchTenants = async (setLoading = true) => {
    if (setLoading) {
      setIsLoading(true);
    }
    try {
      const response = await tenantService.getAllTenants();
      if (response) {
        setTenants(response.tenants || []);
      } else {
        setTenants([]);
      }
    } catch (error) {
      console.error("Error fetching tenants:", error);
      const errorMessage =
        error instanceof Error ? error.message : "Failed to fetch tenants";
      if (setLoading) {
        toast.error(errorMessage);
      }
      setTenants([]);
    } finally {
      if (setLoading) {
        setIsLoading(false);
      }
    }
  };

  // Fetch tenants on mount and set up auto-refresh
  useEffect(() => {
    fetchTenants(true);
    tenantService.getGlobalFeatures().then(setGlobalFeatures);
    // Refresh every 10 seconds (silently in background)
    const interval = setInterval(() => fetchTenants(false), 10000);
    return () => clearInterval(interval);
  }, []);

  // Refetch function for mutations
  const refetch = () => {
    fetchTenants(false);
  };

  // Mutations
  const updateTenantMutation = trpc.tenant.update.useMutation({
    onSuccess: () => {
      toast.success("Tenant updated successfully");
      refetch();
    },
    onError: (error: Error) => {
      toast.error(`Failed to update tenant: ${error.message}`);
    },
  });

  const deleteTenantMutation = trpc.tenant.delete.useMutation({
    onSuccess: () => {
      toast.success("Tenant deleted successfully");
      refetch();
    },
    onError: (error: Error) => {
      toast.error(`Failed to delete tenant: ${error.message}`);
    },
  });

  const rotateApiKeyMutation = trpc.tenant.rotateApiKey.useMutation({
    onSuccess: () => {
      toast.success("API key rotated successfully");
      refetch();
    },
    onError: (error: Error) => {
      toast.error(`Failed to rotate API key: ${error.message}`);
    },
  });

  const filteredTenants = tenants.filter((tenant) => {
    const matchesSearch =
      tenant.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      tenant.tenant_id.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesTier =
      filterTier === "all" || tenant.billing?.plan === filterTier;
    const matchesStatus =
      filterStatus === "all" || tenant.status === filterStatus;
    return matchesSearch && matchesTier && matchesStatus;
  });

  const getTierColor = (tier: string) => {
    switch (tier) {
      case "enterprise":
        return "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-300";
      case "premium":
        return "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300";
      case "standard":
        return "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300";
      default:
        return "bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300";
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "active":
        return "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300";
      case "pending":
        return "bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300";
      case "suspended":
        return "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300";
      default:
        return "bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300";
    }
  };

  const handleExportExcel = () => {
    const data = filteredTenants.map((t) => ({
      "Tenant ID": t.tenant_id,
      Name: t.name,
      Tier: t.billing?.plan || "N/A",
      Status: t.status,
      Email: t.contact?.email || "",
      Phone: t.contact?.phone || "",
      Created: new Date(t.created_at).toLocaleDateString(),
    }));
    exportToExcel(data, "tenants");
  };

  const handleExportPDF = () => {
    const data = filteredTenants.map((t) => [
      t.tenant_id,
      t.name,
      t.billing?.plan || "N/A",
      t.status,
      new Date(t.created_at).toLocaleDateString(),
    ]);
    exportToPDF(
      ["Tenant ID", "Name", "Tier", "Status", "Created"],
      data.flat(),
      "tenants-report",
      "Tenants Report",
    );
  };

  const handleFileChange = async (type: "cac" | "cbn", file: File | null) => {
    if (file) {
      // Validate file size (max 10MB)
      if (file.size > 10 * 1024 * 1024) {
        toast.error("File size must be less than 10MB");
        return;
      }

      // Set uploading state
      if (type === "cac") {
        setIsUploadingCac(true);
      } else {
        setIsUploadingCbn(true);
      }

      try {
        // Create FormData for file upload
        const formDataUpload = new FormData();
        formDataUpload.append("file", file);

        // Upload to document upload endpoint using apiClient
        const response = await apiClient.post<{ url: string }>(
          `${BACKEND_URL}/document/upload`,
          formDataUpload,
          {
            headers: {
              "Content-Type": "multipart/form-data",
            },
            timeout: 120000,
          },
        );

        // Extract URL from response
        const documentUrl = response.data.url;

        // Update form data with URL
        setEditFormData((prev) => ({
          ...prev,
          [type === "cac" ? "cacCertificateUrl" : "cbnLicenseUrl"]: documentUrl,
        }));

        // Store file for display
        if (type === "cac") {
          setCacDocument(file);
        } else {
          setCbnLicense(file);
        }

        toast.success(
          `${type === "cac" ? "CAC Certificate" : "CBN License"} uploaded successfully`,
        );
      } catch (error: any) {
        console.error(`Error uploading ${type.toUpperCase()} document:`, error);
        const errorMessage =
          error?.response?.data?.message ||
          error?.message ||
          "Failed to upload document";
        toast.error(errorMessage);
      } finally {
        if (type === "cac") {
          setIsUploadingCac(false);
        } else {
          setIsUploadingCbn(false);
        }
      }
    }
  };

  const handleImageUpload = async (
    type: "logo" | "favicon",
    file: File | null,
  ) => {
    if (file) {
      // Validate file size (max 5MB for images)
      if (file.size > 5 * 1024 * 1024) {
        toast.error("Image size must be less than 5MB");
        return;
      }

      // Validate file type
      if (!file.type.startsWith("image/")) {
        toast.error("Please upload an image file");
        return;
      }

      // Set uploading state
      if (type === "logo") {
        setIsUploadingLogo(true);
      } else {
        setIsUploadingFavicon(true);
      }

      try {
        // Create FormData for file upload
        const formDataUpload = new FormData();
        formDataUpload.append("file", file);

        // Upload to document upload endpoint using apiClient
        const response = await apiClient.post<{ url: string }>(
          `${BACKEND_URL}/document/upload`,
          formDataUpload,
          {
            headers: {
              "Content-Type": "multipart/form-data",
            },
            timeout: 120000,
          },
        );

        // Extract URL from response
        const imageUrl = response.data.url;

        // Update form data with URL
        setEditFormData((prev) => ({
          ...prev,
          [type === "logo" ? "logoUrl" : "faviconUrl"]: imageUrl,
        }));

        // Store file for display
        if (type === "logo") {
          setLogoFile(file);
        } else {
          setFaviconFile(file);
        }

        toast.success(
          `${type === "logo" ? "Logo" : "Favicon"} uploaded successfully`,
        );
      } catch (error: any) {
        console.error(`Error uploading ${type}:`, error);
        const errorMessage =
          error?.response?.data?.message ||
          error?.message ||
          "Failed to upload image";
        toast.error(errorMessage);
      } finally {
        if (type === "logo") {
          setIsUploadingLogo(false);
        } else {
          setIsUploadingFavicon(false);
        }
      }
    }
  };

  const removeFile = (type: "cac" | "cbn" | "logo" | "favicon") => {
    if (type === "cac") {
      setCacDocument(null);
      setEditFormData((prev) => ({ ...prev, cacCertificateUrl: "" }));
      if (cacFileInputRef.current) {
        cacFileInputRef.current.value = "";
      }
    } else if (type === "cbn") {
      setCbnLicense(null);
      setEditFormData((prev) => ({ ...prev, cbnLicenseUrl: "" }));
      if (cbnFileInputRef.current) {
        cbnFileInputRef.current.value = "";
      }
    } else if (type === "logo") {
      setLogoFile(null);
      setEditFormData((prev) => ({ ...prev, logoUrl: "" }));
      if (logoFileInputRef.current) {
        logoFileInputRef.current.value = "";
      }
    } else {
      setFaviconFile(null);
      setEditFormData((prev) => ({ ...prev, faviconUrl: "" }));
      if (faviconFileInputRef.current) {
        faviconFileInputRef.current.value = "";
      }
    }
  };

  const handleSuspendTenant = (tenantId: string) => {
    if (confirm("Are you sure you want to suspend this tenant?")) {
      updateTenantMutation.mutate({ tenantId, status: "suspended" });
    }
  };

  const handleActivateTenant = (tenantId: string) => {
    updateTenantMutation.mutate({ tenantId, status: "active" });
  };

  const handleDeleteTenant = (tenantId: string) => {
    try {
      if (confirm("Are you sure you want to delete this tenant? This action cannot be undone.")) {
        tenantService.deleteTenant(tenantId).then(() => {
          toast.success("Tenant deleted successfully");
          refetch();
        }).catch((error) => {          console.error("Error deleting tenant:", error);
          const errorMessage =
            error instanceof Error ? error.message : "Failed to delete tenant";
          toast.error(errorMessage);
        });
      }
    } catch (error) {      console.error("Error deleting tenant:", error);
      const errorMessage =
        error instanceof Error ? error.message : "Failed to delete tenant";
      toast.error(errorMessage);
    }
  };

  const handleViewDetails = (tenant: Tenant) => {
    setSelectedTenant(tenant);
    setIsDetailsDialogOpen(true);
  };

  const handleEditTenant = (tenant: Tenant) => {
    setSelectedTenant(tenant);
    setEditFormData({
      name: tenant.name || "",
      type: "bank", // Default type since it's not in Tenant interface
      status: tenant.status || "active",
      cacCertificateUrl: tenant.cac_certificate_url || "",
      cbnLicenseUrl: tenant.cbn_license_url || "",
      logoUrl: tenant.branding?.logo_url || "",
      faviconUrl: tenant.branding?.favicon_url || "",
      primaryColor: tenant.branding?.primary_color || "#22c55e",
      secondaryColor: tenant.branding?.secondary_color || "#16a34a",
      domain: tenant.branding?.domain || "",
      contactName: tenant.contact?.name || "",
      contactEmail: tenant.contact?.email || "",
      contactPhone: tenant.contact?.phone || "",
      billingPlan: tenant.billing?.plan || "premium",
    });
    // Pre-populate enabled feature flags from tenant
    const enabledFlagNames = new Set(
      (tenant.feature_flags || [])
        .filter((f) => f.is_enabled)
        .map((f) => f.name),
    );
    setEditFeatureFlags(enabledFlagNames);
    // Reset file states
    setCacDocument(null);
    setCbnLicense(null);
    setLogoFile(null);
    setFaviconFile(null);
    setIsEditDialogOpen(true);
  };

  const toggleFeatureFlag = (flagKey: string) => {
    setEditFeatureFlags((prev) => {
      const next = new Set(prev);
      if (next.has(flagKey)) {
        next.delete(flagKey);
      } else {
        next.add(flagKey);
      }
      return next;
    });
  };

  const handleUpdateTenant = async () => {
    if (!selectedTenant) return;

    try {
      const updateData: Record<string, unknown> = {};

      // Flat fields
      if (editFormData.name && editFormData.name !== selectedTenant.name) {
        updateData.name = editFormData.name;
      }
      if (editFormData.type) {
        updateData.type = editFormData.type;
      }
      if (editFormData.cacCertificateUrl !== (selectedTenant.cac_certificate_url || "")) {
        updateData.cacCertificateUrl = editFormData.cacCertificateUrl;
      }
      if (editFormData.cbnLicenseUrl !== (selectedTenant.cbn_license_url || "")) {
        updateData.cbnLicenseUrl = editFormData.cbnLicenseUrl;
      }
      if (editFormData.billingPlan && editFormData.billingPlan !== (selectedTenant.billing?.plan || "")) {
        updateData.plan = editFormData.billingPlan;
      }

      // Contact — nested object as API expects
      const contactChanged =
        editFormData.contactName !== (selectedTenant.contact?.name || "") ||
        editFormData.contactEmail !== (selectedTenant.contact?.email || "") ||
        editFormData.contactPhone !== (selectedTenant.contact?.phone || "");
      if (contactChanged) {
        updateData.contact = {
          name: editFormData.contactName,
          email: editFormData.contactEmail,
          phone: editFormData.contactPhone,
        };
      }

      // Branding — nested object as API expects
      const brandingChanged =
        editFormData.logoUrl !== (selectedTenant.branding?.logo_url || "") ||
        editFormData.faviconUrl !== (selectedTenant.branding?.favicon_url || "") ||
        editFormData.primaryColor !== (selectedTenant.branding?.primary_color || "") ||
        editFormData.secondaryColor !== (selectedTenant.branding?.secondary_color || "") ||
        editFormData.domain !== (selectedTenant.branding?.domain || "");
      if (brandingChanged) {
        updateData.branding = {
          logoUrl: editFormData.logoUrl,
          faviconUrl: editFormData.faviconUrl,
          primaryColor: editFormData.primaryColor,
          secondaryColor: editFormData.secondaryColor,
          domain: editFormData.domain,
        };
      }

      // Features — API expects { flag, config }[] of only enabled features
      const currentEnabledFlagNames = new Set(
        (selectedTenant.feature_flags || [])
          .filter((f) => f.is_enabled)
          .map((f) => f.name),
      );
      const flagsChanged =
        editFeatureFlags.size !== currentEnabledFlagNames.size ||
        [...editFeatureFlags].some((k) => !currentEnabledFlagNames.has(k)) ||
        [...currentEnabledFlagNames].some((k) => !editFeatureFlags.has(k));

      if (flagsChanged) {
        const existingConfigs = new Map(
          (selectedTenant.feature_flags || []).map((f) => [f.name, f.config || {}]),
        );
        updateData.features = [...editFeatureFlags].map((name) => ({
          flag: name,
          config: existingConfigs.get(name) || {},
        }));
      }

      if (Object.keys(updateData).length === 0) {
        toast.info("No changes to save");
        return;
      }

      await tenantService.updateTenant(selectedTenant.tenant_id, updateData);
      toast.success("Tenant updated successfully");
      setIsEditDialogOpen(false);
      fetchTenants(false);
    } catch (error) {
      console.error("Error updating tenant:", error);
      const errorMessage =
        error instanceof Error ? error.message : "Failed to update tenant";
      toast.error(errorMessage);
    }
  };

  const handleRotateApiKey = (tenantId: string) => {
    if (
      confirm(
        "Are you sure you want to rotate the API key? The old key will stop working immediately.",
      )
    ) {
      rotateApiKeyMutation.mutate({ tenantId });
    }
  };

  // Helper to convert metrics values to numbers
  const getMetricValue = (value: string | number): number => {
    if (typeof value === "number") return value;
    if (typeof value === "string") {
      const parsed = parseInt(value, 10);
      return isNaN(parsed) ? 0 : parsed;
    }
    return 0;
  };

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900 p-6 space-y-6">
      {/* Header */}
      <div
        className="rounded-2xl px-8 py-7 flex items-center justify-between mb-2"
        style={{
          background: `linear-gradient(135deg, ${primaryColor} 0%, ${secondaryColor} 100%)`,
        }}
      >
        <div>
          <div className="flex items-center gap-3 mb-1">
            <div className="p-2 bg-white/15 rounded-lg">
              <Building2 className="w-6 h-6 text-white" />
            </div>
            <h1 className="text-3xl font-bold text-white tracking-tight">Tenant Management</h1>
          </div>
          <p className="text-white/70 text-sm font-medium ml-1">
            Manage all MFBs on the 54link-dev platform
          </p>
        </div>
        <Link href="/onboarding">
          <a
            className="flex items-center gap-2 px-5 py-3 bg-white rounded-xl font-semibold text-sm hover:bg-white/90 transition-all shadow-lg hover:shadow-xl"
            style={{ color: primaryColor }}
          >
            <Plus className="h-4 w-4" />
            <span>Onboard New MFB</span>
          </a>
        </Link>
      </div>

      <div>
        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-3xl font-bold text-slate-900 dark:text-white">
                  {isLoading ? "..." : getMetricValue(tenants.length)}
                </div>
                <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                  Total Tenants
                </div>
              </div>
              <div className="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                <Building2 className="w-6 h-6 text-blue-600 dark:text-blue-400" />
              </div>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-3xl font-bold text-slate-900 dark:text-white">
                  {isLoading
                    ? "..."
                    : getMetricValue(
                        tenants.filter((t) => t.billing?.plan === "enterprise")
                          .length,
                      )}
                </div>
                <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                  Enterprise
                </div>
              </div>
              <div className="p-3 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
                <TrendingUp className="w-6 h-6 text-purple-600 dark:text-purple-400" />
              </div>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-3xl font-bold text-slate-900 dark:text-white">
                  {isLoading
                    ? "..."
                    : getMetricValue(
                        tenants.filter((t) => t.billing?.plan === "premium")
                          .length,
                      )}
                </div>
                <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                  Premium
                </div>
              </div>
              <div className="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                <Activity className="w-6 h-6 text-blue-600 dark:text-blue-400" />
              </div>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-3xl font-bold text-slate-900 dark:text-white">
                  {isLoading
                    ? "..."
                    : getMetricValue(
                        tenants.filter((t) => t.billing?.plan === "standard")
                          .length,
                      )}
                </div>
                <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">
                  Standard
                </div>
              </div>
              <div className="p-3 bg-green-100 dark:bg-green-900/30 rounded-lg">
                <Building2 className="w-6 h-6 text-green-600 dark:text-green-400" />
              </div>
            </div>
          </div>
        </div>

        {/* Filters and Search */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg p-6 border border-slate-200 dark:border-slate-700 mb-6">
          <div className="flex flex-col md:flex-row gap-4">
            <div className="flex-1 relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-slate-400 w-5 h-5" />
              <input
                type="text"
                placeholder="Search by name or tenant ID..."
                className="w-full pl-10 pr-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
            <select
              className="px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white"
              value={filterTier}
              onChange={(e) => setFilterTier(e.target.value)}
            >
              <option value="all">All Tiers</option>
              <option value="enterprise">Enterprise</option>
              <option value="premium">Premium</option>
              <option value="standard">Standard</option>
            </select>
            <select
              className="px-4 py-2 border border-slate-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-slate-900 dark:text-white"
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
            >
              <option value="all">All Status</option>
              <option value="active">Active</option>
              <option value="pending">Pending</option>
              <option value="suspended">Suspended</option>
            </select>
            <button
              onClick={handleExportExcel}
              className="px-4 py-2 bg-green-600 text-white rounded-lg font-semibold hover:bg-green-700 transition-colors flex items-center gap-2"
            >
              <Download className="w-5 h-5" />
              Excel
            </button>
            <button
              onClick={handleExportPDF}
              className="px-4 py-2 bg-red-600 text-white rounded-lg font-semibold hover:bg-red-700 transition-colors flex items-center gap-2"
            >
              <Download className="w-5 h-5" />
              PDF
            </button>
          </div>
        </div>

        {/* Table */}
        <div className="bg-white dark:bg-slate-800 rounded-xl shadow-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
          {isLoading ? (
            <div className="p-12 text-center">
              <Activity className="w-12 h-12 text-slate-400 animate-spin mx-auto mb-4" />
              <p className="text-slate-600 dark:text-slate-400">
                Loading tenants...
              </p>
            </div>
          ) : filteredTenants.length === 0 ? (
            <div className="p-12 text-center">
              <Building2 className="w-12 h-12 text-slate-400 mx-auto mb-4" />
              <p className="text-slate-600 dark:text-slate-400">
                No tenants found
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-50 dark:bg-slate-700/50 border-b border-slate-200 dark:border-slate-700">
                  <tr>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">
                      Tenant
                    </th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">
                      Type
                    </th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">
                      Tier
                    </th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">
                      Status
                    </th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">
                      Contact
                    </th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">
                      Joined
                    </th>
                    <th className="px-6 py-4 text-left text-sm font-semibold text-slate-900 dark:text-white">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-700">
                  {filteredTenants.map((tenant) => (
                    <tr
                      key={tenant.id}
                      className="hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors"
                    >
                      <td className="px-6 py-4">
                        <div>
                          <div className="font-semibold text-slate-900 dark:text-white">
                            {tenant.name}
                          </div>
                          <div className="text-sm text-slate-600 dark:text-slate-400">
                            {tenant.tenant_id}
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className="text-sm text-slate-900 dark:text-white">
                          Tenant
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <span
                          className={`px-3 py-1 rounded-full text-xs font-semibold ${getTierColor(tenant.billing?.plan || "basic")} capitalize`}
                        >
                          {tenant.billing?.plan || "N/A"}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <span
                          className={`px-3 py-1 rounded-full text-xs font-semibold ${getStatusColor(tenant.status)} capitalize`}
                        >
                          {tenant.status}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <div className="text-sm">
                          <div className="text-slate-900 dark:text-white">
                            {tenant.contact?.email || "N/A"}
                          </div>
                          <div className="text-slate-600 dark:text-slate-400">
                            {tenant.contact?.phone || "N/A"}
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-sm text-slate-900 dark:text-white">
                        {new Date(tenant.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleViewDetails(tenant)}
                            title="View Details"
                          >
                            <Eye className="w-4 h-4" />
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleEditTenant(tenant)}
                            title="Edit Tenant"
                          >
                            <Edit className="w-4 h-4" />
                          </Button>
                          {tenant.status === "suspended" ? (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() =>
                                handleActivateTenant(tenant.tenant_id)
                              }
                              disabled={updateTenantMutation.isPending}
                            >
                              Activate
                            </Button>
                          ) : (
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() =>
                                handleSuspendTenant(tenant.tenant_id)
                              }
                              disabled={updateTenantMutation.isPending}
                            >
                              Suspend
                            </Button>
                          )}
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleRotateApiKey(tenant.tenant_id)}
                            disabled={rotateApiKeyMutation.isPending}
                            title="Rotate API Key"
                          >
                            <Key className="w-4 h-4" />
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => handleDeleteTenant(tenant.tenant_id)}
                            disabled={deleteTenantMutation.isPending}
                            className="text-red-600 hover:text-red-700"
                            title="Delete Tenant"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Pagination Info */}
        {tenants.length > 0 && (
          <div className="mt-4 text-center text-sm text-slate-600 dark:text-slate-400">
            Showing {filteredTenants.length} of {tenants.length} tenants
          </div>
        )}
      </div>

      {/* Tenant Details Dialog */}
      <Dialog open={isDetailsDialogOpen} onOpenChange={setIsDetailsDialogOpen}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Tenant Details</DialogTitle>
            <DialogDescription>
              Complete information for {selectedTenant?.name}
            </DialogDescription>
          </DialogHeader>

          {selectedTenant && (
            <div className="space-y-6">
              {/* Basic Information */}
              <div>
                <h3 className="text-lg font-semibold mb-3 text-slate-900 dark:text-white">
                  Basic Information
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-slate-600 dark:text-slate-400">
                      Name
                    </p>
                    <p className="font-medium text-slate-900 dark:text-white">
                      {selectedTenant.name}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-slate-600 dark:text-slate-400">
                      Tenant ID
                    </p>
                    <p className="font-medium text-slate-900 dark:text-white">
                      {selectedTenant.tenant_id}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-slate-600 dark:text-slate-400">
                      Status
                    </p>
                    <span
                      className={`inline-block px-3 py-1 rounded-full text-xs font-semibold ${getStatusColor(selectedTenant.status)} capitalize`}
                    >
                      {selectedTenant.status}
                    </span>
                  </div>
                  <div>
                    <p className="text-sm text-slate-600 dark:text-slate-400">
                      Created At
                    </p>
                    <p className="font-medium text-slate-900 dark:text-white">
                      {new Date(selectedTenant.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>
              </div>

              {/* Contact Information */}
              <div>
                <h3 className="text-lg font-semibold mb-3 text-slate-900 dark:text-white">
                  Contact Information
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-slate-600 dark:text-slate-400">
                      Name
                    </p>
                    <p className="font-medium text-slate-900 dark:text-white">
                      {selectedTenant.contact?.name || "N/A"}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-slate-600 dark:text-slate-400">
                      Email
                    </p>
                    <p className="font-medium text-slate-900 dark:text-white">
                      {selectedTenant.contact?.email || "N/A"}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-slate-600 dark:text-slate-400">
                      Phone
                    </p>
                    <p className="font-medium text-slate-900 dark:text-white">
                      {selectedTenant.contact?.phone || "N/A"}
                    </p>
                  </div>
                </div>
              </div>

              {/* Branding */}
              <div>
                <h3 className="text-lg font-semibold mb-3 text-slate-900 dark:text-white">
                  Branding
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-slate-600 dark:text-slate-400">
                      Logo URL
                    </p>
                    <p className="font-medium text-slate-900 dark:text-white break-all">
                      {selectedTenant.branding?.logo_url || "N/A"}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-slate-600 dark:text-slate-400">
                      Primary Color
                    </p>
                    <div className="flex items-center gap-2">
                      <div
                        className="w-6 h-6 rounded border"
                        style={{
                          backgroundColor:
                            selectedTenant.branding?.primary_color,
                        }}
                      ></div>
                      <p className="font-medium text-slate-900 dark:text-white">
                        {selectedTenant.branding?.primary_color || "N/A"}
                      </p>
                    </div>
                  </div>
                  <div>
                    <p className="text-sm text-slate-600 dark:text-slate-400">
                      Secondary Color
                    </p>
                    <div className="flex items-center gap-2">
                      <div
                        className="w-6 h-6 rounded border"
                        style={{
                          backgroundColor:
                            selectedTenant.branding?.secondary_color,
                        }}
                      ></div>
                      <p className="font-medium text-slate-900 dark:text-white">
                        {selectedTenant.branding?.secondary_color || "N/A"}
                      </p>
                    </div>
                  </div>
                  <div>
                    <p className="text-sm text-slate-600 dark:text-slate-400">
                      Domain
                    </p>
                    <p className="font-medium text-slate-900 dark:text-white">
                      {selectedTenant.branding?.domain || "N/A"}
                    </p>
                  </div>
                </div>
              </div>

              {/* Billing */}
              <div>
                <h3 className="text-lg font-semibold mb-3 text-slate-900 dark:text-white">
                  Billing
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <p className="text-sm text-slate-600 dark:text-slate-400">
                      Plan
                    </p>
                    <span
                      className={`inline-block px-3 py-1 rounded-full text-xs font-semibold ${getTierColor(selectedTenant.billing?.plan || "basic")} capitalize`}
                    >
                      {selectedTenant.billing?.plan || "N/A"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Documents/Certificates */}
              <div>
                <h3 className="text-lg font-semibold mb-3 text-slate-900 dark:text-white">
                  Documents & Certificates
                </h3>
                <div className="grid grid-cols-1 gap-4">
                  <div>
                    <p className="text-sm text-slate-600 dark:text-slate-400 mb-2">
                      CAC Certificate
                    </p>
                    {selectedTenant.cac_certificate_url ? (
                      <a
                        href={selectedTenant.cac_certificate_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 text-blue-600 dark:text-blue-400 hover:underline"
                      >
                        <FileText className="w-4 h-4" />
                        <span className="font-medium break-all">
                          {selectedTenant.cac_certificate_url}
                        </span>
                      </a>
                    ) : (
                      <p className="text-sm text-slate-500 dark:text-slate-400 italic">
                        Not uploaded
                      </p>
                    )}
                  </div>
                  <div>
                    <p className="text-sm text-slate-600 dark:text-slate-400 mb-2">
                      CBN License
                    </p>
                    {selectedTenant.cbn_license_url ? (
                      <a
                        href={selectedTenant.cbn_license_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-2 text-blue-600 dark:text-blue-400 hover:underline"
                      >
                        <FileText className="w-4 h-4" />
                        <span className="font-medium break-all">
                          {selectedTenant.cbn_license_url}
                        </span>
                      </a>
                    ) : (
                      <p className="text-sm text-slate-500 dark:text-slate-400 italic">
                        Not uploaded
                      </p>
                    )}
                  </div>
                </div>
              </div>

              {/* Feature Flags */}
              <div>
                <h3 className="text-lg font-semibold mb-3 text-slate-900 dark:text-white">
                  Feature Flags ({selectedTenant.feature_flags?.length || 0})
                </h3>
                <div className="grid grid-cols-1 gap-2 max-h-60 overflow-y-auto">
                  {selectedTenant.feature_flags?.map((flag) => (
                    <div
                      key={flag.id}
                      className="p-3 bg-slate-50 dark:bg-slate-700/50 rounded-lg"
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <p className="font-medium text-slate-900 dark:text-white">
                            {flag.name}
                          </p>
                          <p className="text-xs text-slate-600 dark:text-slate-400 mt-1">
                            {Object.keys(flag.config || {}).length > 0
                              ? `Config: ${JSON.stringify(flag.config).substring(0, 100)}...`
                              : "No config"}
                          </p>
                        </div>
                        <span
                          className={`px-2 py-1 rounded text-xs font-semibold ${
                            flag.is_enabled
                              ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
                              : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400"
                          }`}
                        >
                          {flag.is_enabled ? "Enabled" : "Disabled"}
                        </span>
                      </div>
                    </div>
                  )) || (
                    <p className="text-sm text-slate-600 dark:text-slate-400">
                      No feature flags
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Tenant Edit Dialog */}
      <Dialog open={isEditDialogOpen} onOpenChange={setIsEditDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Edit Tenant</DialogTitle>
            <DialogDescription>
              Update tenant information for {selectedTenant?.name}
            </DialogDescription>
          </DialogHeader>

          {selectedTenant && (
            <div className="space-y-6">
              {/* Basic Information */}
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                  Basic Information
                </h3>

                <div className="space-y-2">
                  <Label htmlFor="name">Tenant Name</Label>
                  <Input
                    id="name"
                    value={editFormData.name || ""}
                    onChange={(e) =>
                      setEditFormData({ ...editFormData, name: e.target.value })
                    }
                    placeholder="Enter tenant name"
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="type">Tenant Type</Label>
                    <Select
                      value={editFormData.type || "bank"}
                      onValueChange={(value) =>
                        setEditFormData({ ...editFormData, type: value })
                      }
                    >
                      <SelectTrigger id="type">
                        <SelectValue placeholder="Select type" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="bank">Bank</SelectItem>
                        <SelectItem value="microfinance">
                          Microfinance
                        </SelectItem>
                        <SelectItem value="fintech">Fintech</SelectItem>
                        <SelectItem value="insurance">Insurance</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="status">Status</Label>
                    <Select
                      value={editFormData.status || "active"}
                      onValueChange={(value) =>
                        setEditFormData({ ...editFormData, status: value })
                      }
                    >
                      <SelectTrigger id="status">
                        <SelectValue placeholder="Select status" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="active">Active</SelectItem>
                        <SelectItem value="suspended">Suspended</SelectItem>
                        <SelectItem value="inactive">Inactive</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="billingPlan">Billing Plan</Label>
                  <Select
                    value={editFormData.billingPlan || "premium"}
                    onValueChange={(value) =>
                      setEditFormData({ ...editFormData, billingPlan: value })
                    }
                  >
                    <SelectTrigger id="billingPlan">
                      <SelectValue placeholder="Select billing plan" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="basic">Basic</SelectItem>
                      <SelectItem value="premium">Premium</SelectItem>
                      <SelectItem value="enterprise">Enterprise</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              {/* Contact Information */}
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                  Contact Information
                </h3>

                <div className="space-y-2">
                  <Label htmlFor="contactName">Contact Name</Label>
                  <Input
                    id="contactName"
                    value={editFormData.contactName || ""}
                    onChange={(e) =>
                      setEditFormData({
                        ...editFormData,
                        contactName: e.target.value,
                      })
                    }
                    placeholder="Enter contact name"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="contactEmail">Contact Email</Label>
                  <Input
                    id="contactEmail"
                    type="email"
                    value={editFormData.contactEmail || ""}
                    onChange={(e) =>
                      setEditFormData({
                        ...editFormData,
                        contactEmail: e.target.value,
                      })
                    }
                    placeholder="Enter contact email"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="contactPhone">Contact Phone</Label>
                  <Input
                    id="contactPhone"
                    value={editFormData.contactPhone || ""}
                    onChange={(e) =>
                      setEditFormData({
                        ...editFormData,
                        contactPhone: e.target.value,
                      })
                    }
                    placeholder="Enter contact phone"
                  />
                </div>
              </div>

              {/* Documents */}
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                  Documents & Certificates
                </h3>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* CAC Certificate Upload */}
                  <div>
                    <Label className="mb-2 block">CAC Certificate</Label>
                    <div
                      className="border-2 border-dashed rounded-lg p-6 text-center transition-all cursor-pointer hover:shadow-md"
                      style={{
                        borderColor:
                          cacDocument || editFormData.cacCertificateUrl
                            ? primaryColor
                            : "#d1d5db",
                        backgroundColor:
                          cacDocument || editFormData.cacCertificateUrl
                            ? `${primaryColor}08`
                            : "#f9fafb",
                        opacity: isUploadingCac ? 0.6 : 1,
                        cursor: isUploadingCac ? "not-allowed" : "pointer",
                      }}
                      onClick={() =>
                        !isUploadingCac && cacFileInputRef.current?.click()
                      }
                    >
                      {isUploadingCac ? (
                        <div className="space-y-2">
                          <p
                            className="text-sm font-medium"
                            style={{ color: primaryColor }}
                          >
                            Uploading document...
                          </p>
                        </div>
                      ) : cacDocument ? (
                        <div className="space-y-2">
                          <FileText
                            className="w-8 h-8 mx-auto"
                            style={{ color: primaryColor }}
                          />
                          <p
                            className="text-sm font-medium"
                            style={{ color: primaryColor }}
                          >
                            {cacDocument.name}
                          </p>
                          <p className="text-xs text-gray-500">
                            {(cacDocument.size / 1024 / 1024).toFixed(2)} MB
                          </p>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              removeFile("cac");
                            }}
                            style={{ borderColor: "#ef4444", color: "#ef4444" }}
                          >
                            <X className="w-4 h-4 mr-1" />
                            Remove
                          </Button>
                        </div>
                      ) : editFormData.cacCertificateUrl ? (
                        <div className="space-y-2">
                          <FileText
                            className="w-8 h-8 mx-auto"
                            style={{ color: primaryColor }}
                          />
                          <p className="text-sm font-medium text-gray-700">
                            Current: Document Uploaded
                          </p>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <Upload className="w-4 h-4 mr-1" />
                            Replace
                          </Button>
                        </div>
                      ) : (
                        <>
                          <Upload
                            className="w-8 h-8 mx-auto mb-2"
                            style={{ color: primaryColor }}
                          />
                          <p className="text-sm text-gray-600">
                            Click to upload
                          </p>
                        </>
                      )}
                      <input
                        ref={cacFileInputRef}
                        type="file"
                        className="hidden"
                        accept=".pdf,.png,.jpg,.jpeg"
                        onChange={(e) => {
                          const file = e.target.files?.[0] || null;
                          handleFileChange("cac", file);
                        }}
                      />
                    </div>
                  </div>

                  {/* CBN License Upload */}
                  <div>
                    <Label className="mb-2 block">CBN License</Label>
                    <div
                      className="border-2 border-dashed rounded-lg p-6 text-center transition-all cursor-pointer hover:shadow-md"
                      style={{
                        borderColor:
                          cbnLicense || editFormData.cbnLicenseUrl
                            ? primaryColor
                            : "#d1d5db",
                        backgroundColor:
                          cbnLicense || editFormData.cbnLicenseUrl
                            ? `${primaryColor}08`
                            : "#f9fafb",
                        opacity: isUploadingCbn ? 0.6 : 1,
                        cursor: isUploadingCbn ? "not-allowed" : "pointer",
                      }}
                      onClick={() =>
                        !isUploadingCbn && cbnFileInputRef.current?.click()
                      }
                    >
                      {isUploadingCbn ? (
                        <div className="space-y-2">
                          <p
                            className="text-sm font-medium"
                            style={{ color: primaryColor }}
                          >
                            Uploading document...
                          </p>
                        </div>
                      ) : cbnLicense ? (
                        <div className="space-y-2">
                          <FileText
                            className="w-8 h-8 mx-auto"
                            style={{ color: primaryColor }}
                          />
                          <p
                            className="text-sm font-medium"
                            style={{ color: primaryColor }}
                          >
                            {cbnLicense.name}
                          </p>
                          <p className="text-xs text-gray-500">
                            {(cbnLicense.size / 1024 / 1024).toFixed(2)} MB
                          </p>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              removeFile("cbn");
                            }}
                            style={{ borderColor: "#ef4444", color: "#ef4444" }}
                          >
                            <X className="w-4 h-4 mr-1" />
                            Remove
                          </Button>
                        </div>
                      ) : editFormData.cbnLicenseUrl ? (
                        <div className="space-y-2">
                          <FileText
                            className="w-8 h-8 mx-auto"
                            style={{ color: primaryColor }}
                          />
                          <p className="text-sm font-medium text-gray-700">
                            Current: Document Uploaded
                          </p>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <Upload className="w-4 h-4 mr-1" />
                            Replace
                          </Button>
                        </div>
                      ) : (
                        <>
                          <Upload
                            className="w-8 h-8 mx-auto mb-2"
                            style={{ color: primaryColor }}
                          />
                          <p className="text-sm text-gray-600">
                            Click to upload
                          </p>
                        </>
                      )}
                      <input
                        ref={cbnFileInputRef}
                        type="file"
                        className="hidden"
                        accept=".pdf,.png,.jpg,.jpeg"
                        onChange={(e) => {
                          const file = e.target.files?.[0] || null;
                          handleFileChange("cbn", file);
                        }}
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* Branding */}
              <div className="space-y-4">
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                  Branding
                </h3>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Logo Upload */}
                  <div>
                    <Label className="mb-2 block">Logo</Label>
                    <div
                      className="border-2 border-dashed rounded-lg p-6 text-center transition-all cursor-pointer hover:shadow-md"
                      style={{
                        borderColor:
                          logoFile || editFormData.logoUrl
                            ? primaryColor
                            : "#d1d5db",
                        backgroundColor:
                          logoFile || editFormData.logoUrl
                            ? `${primaryColor}08`
                            : "#f9fafb",
                        opacity: isUploadingLogo ? 0.6 : 1,
                        cursor: isUploadingLogo ? "not-allowed" : "pointer",
                      }}
                      onClick={() =>
                        !isUploadingLogo && logoFileInputRef.current?.click()
                      }
                    >
                      {isUploadingLogo ? (
                        <div className="space-y-2">
                          <p
                            className="text-sm font-medium"
                            style={{ color: primaryColor }}
                          >
                            Uploading logo...
                          </p>
                        </div>
                      ) : logoFile ? (
                        <div className="space-y-2">
                          <img
                            src={URL.createObjectURL(logoFile)}
                            alt="Logo preview"
                            className="w-16 h-16 mx-auto object-contain"
                          />
                          <p
                            className="text-sm font-medium"
                            style={{ color: primaryColor }}
                          >
                            {logoFile.name}
                          </p>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              removeFile("logo");
                            }}
                            style={{ borderColor: "#ef4444", color: "#ef4444" }}
                          >
                            <X className="w-4 h-4 mr-1" />
                            Remove
                          </Button>
                        </div>
                      ) : editFormData.logoUrl ? (
                        <div className="space-y-2">
                          <img
                            src={editFormData.logoUrl}
                            alt="Current logo"
                            className="w-16 h-16 mx-auto object-contain"
                          />
                          <p className="text-sm font-medium text-gray-700">
                            Current Logo
                          </p>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <Upload className="w-4 h-4 mr-1" />
                            Replace
                          </Button>
                        </div>
                      ) : (
                        <>
                          <Upload
                            className="w-8 h-8 mx-auto mb-2"
                            style={{ color: primaryColor }}
                          />
                          <p className="text-sm text-gray-600">
                            Click to upload logo
                          </p>
                        </>
                      )}
                      <input
                        ref={logoFileInputRef}
                        type="file"
                        className="hidden"
                        accept="image/*"
                        onChange={(e) => {
                          const file = e.target.files?.[0] || null;
                          handleImageUpload("logo", file);
                        }}
                      />
                    </div>
                  </div>

                  {/* Favicon Upload */}
                  <div>
                    <Label className="mb-2 block">Favicon</Label>
                    <div
                      className="border-2 border-dashed rounded-lg p-6 text-center transition-all cursor-pointer hover:shadow-md"
                      style={{
                        borderColor:
                          faviconFile || editFormData.faviconUrl
                            ? primaryColor
                            : "#d1d5db",
                        backgroundColor:
                          faviconFile || editFormData.faviconUrl
                            ? `${primaryColor}08`
                            : "#f9fafb",
                        opacity: isUploadingFavicon ? 0.6 : 1,
                        cursor: isUploadingFavicon ? "not-allowed" : "pointer",
                      }}
                      onClick={() =>
                        !isUploadingFavicon &&
                        faviconFileInputRef.current?.click()
                      }
                    >
                      {isUploadingFavicon ? (
                        <div className="space-y-2">
                          <p
                            className="text-sm font-medium"
                            style={{ color: primaryColor }}
                          >
                            Uploading favicon...
                          </p>
                        </div>
                      ) : faviconFile ? (
                        <div className="space-y-2">
                          <img
                            src={URL.createObjectURL(faviconFile)}
                            alt="Favicon preview"
                            className="w-16 h-16 mx-auto object-contain"
                          />
                          <p
                            className="text-sm font-medium"
                            style={{ color: primaryColor }}
                          >
                            {faviconFile.name}
                          </p>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              removeFile("favicon");
                            }}
                            style={{ borderColor: "#ef4444", color: "#ef4444" }}
                          >
                            <X className="w-4 h-4 mr-1" />
                            Remove
                          </Button>
                        </div>
                      ) : editFormData.faviconUrl ? (
                        <div className="space-y-2">
                          <img
                            src={editFormData.faviconUrl}
                            alt="Current favicon"
                            className="w-16 h-16 mx-auto object-contain"
                          />
                          <p className="text-sm font-medium text-gray-700">
                            Current Favicon
                          </p>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <Upload className="w-4 h-4 mr-1" />
                            Replace
                          </Button>
                        </div>
                      ) : (
                        <>
                          <Upload
                            className="w-8 h-8 mx-auto mb-2"
                            style={{ color: primaryColor }}
                          />
                          <p className="text-sm text-gray-600">
                            Click to upload favicon
                          </p>
                        </>
                      )}
                      <input
                        ref={faviconFileInputRef}
                        type="file"
                        className="hidden"
                        accept="image/*"
                        onChange={(e) => {
                          const file = e.target.files?.[0] || null;
                          handleImageUpload("favicon", file);
                        }}
                      />
                    </div>
                  </div>
                </div>

                {/* Colors and Domain */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
                  <div className="space-y-2">
                    <Label htmlFor="primaryColor">Primary Color</Label>
                    <div className="flex gap-2">
                      <Input
                        id="primaryColor"
                        type="color"
                        value={editFormData.primaryColor || "#22c55e"}
                        onChange={(e) =>
                          setEditFormData({
                            ...editFormData,
                            primaryColor: e.target.value,
                          })
                        }
                        className="w-20 h-10 cursor-pointer"
                      />
                      <Input
                        type="text"
                        value={editFormData.primaryColor || "#22c55e"}
                        onChange={(e) =>
                          setEditFormData({
                            ...editFormData,
                            primaryColor: e.target.value,
                          })
                        }
                        placeholder="#22c55e"
                        className="flex-1"
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="secondaryColor">Secondary Color</Label>
                    <div className="flex gap-2">
                      <Input
                        id="secondaryColor"
                        type="color"
                        value={editFormData.secondaryColor || "#16a34a"}
                        onChange={(e) =>
                          setEditFormData({
                            ...editFormData,
                            secondaryColor: e.target.value,
                          })
                        }
                        className="w-20 h-10 cursor-pointer"
                      />
                      <Input
                        type="text"
                        value={editFormData.secondaryColor || "#16a34a"}
                        onChange={(e) =>
                          setEditFormData({
                            ...editFormData,
                            secondaryColor: e.target.value,
                          })
                        }
                        placeholder="#16a34a"
                        className="flex-1"
                      />
                    </div>
                  </div>
                </div>

                <div className="space-y-2 mt-4">
                  <Label htmlFor="domain">Domain</Label>
                  <Input
                    id="domain"
                    type="url"
                    value={editFormData.domain || ""}
                    onChange={(e) =>
                      setEditFormData({
                        ...editFormData,
                        domain: e.target.value,
                      })
                    }
                    placeholder="https://example.com"
                  />
                </div>
              </div>

              {/* Feature Management */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                    Features
                  </h3>
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-1 rounded-full text-xs font-semibold bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300">
                      {editFeatureFlags.size} / {globalFeatures.length} enabled
                    </span>
                    <button
                      type="button"
                      onClick={() => setEditFeatureFlags(new Set(globalFeatures.map((f) => f.name)))}
                      className="px-2 py-1 text-xs font-semibold rounded border border-green-300 text-green-700 dark:border-green-700 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-900/20 transition-colors"
                    >
                      Select All
                    </button>
                    <button
                      type="button"
                      onClick={() => setEditFeatureFlags(new Set())}
                      className="px-2 py-1 text-xs font-semibold rounded border border-slate-300 text-slate-600 dark:border-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-700/30 transition-colors"
                    >
                      Deselect All
                    </button>
                  </div>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-1 max-h-72 overflow-y-auto border border-slate-200 dark:border-slate-700 rounded-lg p-2">
                  {globalFeatures.map((feature) => {
                    const isEnabled = editFeatureFlags.has(feature.name);
                    return (
                      <label
                        key={feature.id || feature.name}
                        className={`flex items-center gap-3 px-3 py-2 rounded-lg cursor-pointer transition-colors ${
                          isEnabled
                            ? "bg-green-50 dark:bg-green-900/20"
                            : "hover:bg-slate-50 dark:hover:bg-slate-700/30"
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={isEnabled}
                          onChange={() => toggleFeatureFlag(feature.name)}
                          className="h-4 w-4 rounded cursor-pointer accent-green-600 shrink-0"
                        />
                        <span className="text-sm font-medium text-slate-900 dark:text-white capitalize">
                          {feature.name.replace(/_/g, " ")}
                        </span>
                      </label>
                    );
                  })}
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex justify-end gap-3 pt-4 border-t border-slate-200 dark:border-slate-700">
                <Button
                  variant="outline"
                  onClick={() => setIsEditDialogOpen(false)}
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleUpdateTenant}
                  style={{ backgroundColor: primaryColor }}
                  className="text-white"
                >
                  Save Changes
                </Button>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
