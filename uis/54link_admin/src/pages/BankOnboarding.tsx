import { Button } from "@/components/ui/button";
import {
  Activity,
  ArrowLeft,
  ArrowRight,
  Building2,
  Check,
  Eye,
  FileText,
  Flag,
  Key,
  Palette,
  Upload,
  X,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import CascadingAddressDropdown from "../components/shared/CascadingAddressDropdown";
import { useTenantBranding } from "../contexts/TenantBrandingContext";
import apiClient from "../services/api";
import { BACKEND_URL } from "../const";

export const TenantFeatureFlag = {
  // Core
  AUTH: "auth",
  USER_MANAGEMENT: "user_management",
  ACCOUNTS: "accounts",
  PAYMENTS: "payments",
  REPORTING: "reporting",
  NOTIFICATIONS: "notifications",
  KYC_KYB: "kyc_kyb",
  COMPLIANCE: "compliance",
  AUDIT: "audit",

  // Banking Channels
  MOBILE_BANKING: "mobile_banking",
  USSD_BANKING: "ussd_banking",
  WHATSAPP_BANKING: "whatsapp_banking",
  AGENT_BANKING: "agent_banking",
  CHATBOT: "chatbot",
  POS_TERMINAL: "pos_terminal",

  // Payments & Transfers
  BILL_PAYMENTS: "bill_payments",
  QR_PAYMENTS: "qr_payments",
  BULK_PAYMENTS: "bulk_payments",
  STANDING_ORDERS: "standing_orders",
  REMITTANCE: "remittance",
  ATM_MANAGEMENT: "atm_management",

  // Cards & Accounts
  TELLER: "teller",
  CARD_MANAGEMENT: "card_management",
  VIRTUAL_ACCOUNTS: "virtual_accounts",
  FX: "fx",

  // Lending & Credit
  LOANS: "loans",
  EDUCATION_LOANS: "education_loans",
  MORTGAGE: "mortgage",
  LPO: "lpo",
  BNPL: "bnpl",

  // Savings & Investments
  SAVINGS: "savings",
  SMART_SAVINGS: "smart_savings",
  ESUSU: "esusu",
  ESCROW: "escrow",
  INVESTMENT: "investment",

  // Risk, Fraud & Compliance
  FRAUD_DETECTION: "fraud_detection",
  RISK_MANAGEMENT: "risk_management",
  DISPUTE: "dispute",
  AML_COMPLIANCE: "aml_compliance",
  SANCTIONS_SCREENING: "sanctions_screening",
  REGULATORY_REPORTING: "regulatory_reporting",

  // Insurance
  INSURANCE: "insurance",
  ETHERISC: "etherisc",

  // Treasury & Finance
  TREASURY: "treasury",
  CHART_OF_ACCOUNTS: "chart_of_accounts",
  RECONCILIATION: "reconciliation",
  FINANCE: "finance",

  // Specialised Finance
  ISLAMIC_BANKING: "islamic_banking",
  AGRICULTURE_FINANCE: "agriculture_finance",
  SUPPLY_CHAIN_FINANCE: "supply_chain_finance",
  TRADE_FINANCE: "trade_finance",
  CARBON_CREDITS: "carbon_credits",
  COOPERATIVE_MANAGEMENT: "cooperative_management",
  DIASPORA_BANKING: "diaspora_banking",
  MICROFINANCE: "microfinance",

  // Wealth & Capital Markets
  WEALTH_MANAGEMENT: "wealth_management",
  PENSION: "pension",
  LEASING: "leasing",
  SECURITIES_TRADING: "securities_trading",

  // Operations & Workflow
  EMPLOYEE_MANAGEMENT: "employee_management",
  RELATIONSHIP_MANAGER: "relationship_manager",
  DOCUMENT_MANAGEMENT: "document_management",
  COMMUNICATION_HUB: "communication_hub",
  MERCHANT_MANAGEMENT: "merchant_management",
  SALARY_PROCESSING: "salary_processing",
  MAKER_CHECKER: "maker_checker",
  PRODUCT_FACTORY: "product_factory",
  GAMIFICATION: "gamification",

  // Platform & Integration
  OPEN_BANKING: "open_banking",
  BIOMETRIC_AUTH: "biometric_auth",
  DEVELOPER_PLATFORM: "developer_platform",
  ERP_INTEGRATION: "erp_integration",
  TEMPORAL_ACCESS: "temporal_access",
} as const;

interface GlobalFeaturesResponse {
  features?: string[];
  data?: string[];
  [key: string]: any;
}

interface DocumentUploadResponse {
  url: string;
  id: string;
  filename: string;
  content_type: string;
  ocr: any;
}

const steps = [
  { id: 1, title: "Tenant Information", icon: Building2 },
  { id: 2, title: "Documents", icon: FileText },
  { id: 3, title: "API Setup", icon: Key },
  { id: 4, title: "Feature Selection", icon: Flag },
  { id: 5, title: "Branding", icon: Palette },
  { id: 6, title: "Review & Launch", icon: Eye },
];

export default function TenantOnboarding() {
  const { primaryColor, secondaryColor, name, logoUrl } = useTenantBranding();
  const [currentStep, setCurrentStep] = useState(1);
  const [isCreating, setIsCreating] = useState(false);
  const cacFileInputRef = useRef<HTMLInputElement>(null);
  const cbnFileInputRef = useRef<HTMLInputElement>(null);
  const logoFileInputRef = useRef<HTMLInputElement>(null);
  const faviconFileInputRef = useRef<HTMLInputElement>(null);
  const [isUploadingCac, setIsUploadingCac] = useState(false);
  const [isUploadingCbn, setIsUploadingCbn] = useState(false);
  const [isUploadingLogo, setIsUploadingLogo] = useState(false);
  const [isUploadingFavicon, setIsUploadingFavicon] = useState(false);
  const [formData, setFormData] = useState({
    // Step 1: Tenant Info
    tenantName: "",
    type: "bank" as "bank" | "microfinance" | "fintech" | "insurance",
    tier: "Basic",
    contactEmail: "",
    contactPhone: "",
    firstName: "",
    lastName: "",
    uin: "",
    password: "",
    address: "",
    country: "",
    city: "",
    state: "",
    postalCode: "",
    // Step 2: Documents
    cacDocument: null as File | null,
    cbnLicense: null as File | null,
    cacCertificateUrl: "",
    cbnLicenseUrl: "",
    // Step 3: API
    webhookUrl: "",
    callbackUrl: "",
    // Step 4: Features
    features: [
      TenantFeatureFlag.AUTH,
      TenantFeatureFlag.USER_MANAGEMENT,
      TenantFeatureFlag.ACCOUNTS,
      TenantFeatureFlag.PAYMENTS,
      TenantFeatureFlag.REPORTING,
      TenantFeatureFlag.NOTIFICATIONS,
      TenantFeatureFlag.KYC_KYB,
      TenantFeatureFlag.COMPLIANCE,
      TenantFeatureFlag.DISPUTE,
    ] as string[],
    // Branding
    domain: "",
    logoFile: null as File | null,
    faviconFile: null as File | null,
    logoUrl: "",
    faviconUrl: "",
    primaryColor: primaryColor,
    secondaryColor: secondaryColor,
  });

  // Global features state
  const [globalFeatures, setGlobalFeatures] = useState<string[]>([]);
  const [featuresLoading, setFeaturesLoading] = useState(false);
  const [featuresFetched, setFeaturesFetched] = useState(false);

  // Fetch global features
  const fetchGlobalFeatures = useCallback(async () => {
    setFeaturesLoading(true);
    try {
      const response = await apiClient.get<GlobalFeaturesResponse>(
        `/tenant-management/tenant/features/global`,
      );
      const data = response.data;

      // Handle different response structures
      let features: string[] = [];
      if (Array.isArray(data)) {
        features = data;
      } else if (data.features && Array.isArray(data.features)) {
        features = data.features;
      } else if (data.data && Array.isArray(data.data)) {
        features = data.data;
      } else if (data.tenants && Array.isArray(data.tenants)) {
        features = data.tenants.filter((t) => t.is_enabled).map((t) => t.name);
      }
      setGlobalFeatures(features);
      setFeaturesFetched(true);
    } catch (error: any) {
      console.error("Error fetching global features:", error);
      const errorMessage =
        error?.response?.data?.message ||
        error?.message ||
        "Failed to fetch global features";
      toast.error(errorMessage);
      // Fallback to hardcoded features if API fails - use all TenantFeatureFlag values
      setGlobalFeatures(Object.values(TenantFeatureFlag));
      setFeaturesFetched(true);
    } finally {
      setFeaturesLoading(false);
    }
  }, []);

  // Fetch features when step 4 is reached
  useEffect(() => {
    if (currentStep === 4 && !featuresFetched) {
      fetchGlobalFeatures();
    }
  }, [currentStep, featuresFetched, fetchGlobalFeatures]);

  // Set default essential features when global features are loaded
  useEffect(() => {
    if (globalFeatures.length > 0) {
      const essentialFeatures = [
        TenantFeatureFlag.AUTH,
        TenantFeatureFlag.USER_MANAGEMENT,
        TenantFeatureFlag.ACCOUNTS,
        TenantFeatureFlag.PAYMENTS,
      ];
      const availableEssential = essentialFeatures.filter((f) =>
        globalFeatures.includes(f),
      );
      if (availableEssential.length > 0) {
        setFormData((prev) => {
          // Ensure essential features are always included
          const currentFeatures = prev.features || [];
          const mergedFeatures = [
            ...new Set([...availableEssential, ...currentFeatures]),
          ];
          // Only update if features changed
          if (
            mergedFeatures.length !== currentFeatures.length ||
            !availableEssential.every((f) => currentFeatures.includes(f))
          ) {
            return {
              ...prev,
              features: mergedFeatures,
            };
          }
          return prev;
        });
      }
    }
  }, [globalFeatures]);

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
        const response = await apiClient.post<DocumentUploadResponse>(
          `${BACKEND_URL}/document/upload`,
          formDataUpload,
          {
            headers: {
              "Content-Type": "multipart/form-data",
            },
            timeout: 120000, // 2 minutes timeout for document upload processing
          },
        );

        // Extract URL from response
        const documentUrl = response.data.url;

        // Update form data with file and URL
        setFormData((prev) => ({
          ...prev,
          [type === "cac" ? "cacDocument" : "cbnLicense"]: file,
          [type === "cac" ? "cacCertificateUrl" : "cbnLicenseUrl"]: documentUrl,
        }));

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

  const removeFile = (type: "cac" | "cbn") => {
    setFormData((prev) => ({
      ...prev,
      [type === "cac" ? "cacDocument" : "cbnLicense"]: null,
      [type === "cac" ? "cacCertificateUrl" : "cbnLicenseUrl"]: "",
    }));
    if (type === "cac" && cacFileInputRef.current) {
      cacFileInputRef.current.value = "";
    }
    if (type === "cbn" && cbnFileInputRef.current) {
      cbnFileInputRef.current.value = "";
    }
  };

  // Handle image upload for logo and favicon
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
        const response = await apiClient.post<DocumentUploadResponse>(
          `${BACKEND_URL}/document/upload`,
          formDataUpload,
          {
            headers: {
              "Content-Type": "multipart/form-data",
            },
            timeout: 120000, // 2 minutes timeout for document upload processing
          },
        );

        // Extract URL from response
        const imageUrl = response.data.url;

        // Update form data with file and URL
        setFormData((prev) => ({
          ...prev,
          [type === "logo" ? "logoFile" : "faviconFile"]: file,
          [type === "logo" ? "logoUrl" : "faviconUrl"]: imageUrl,
        }));

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

  const removeImage = (type: "logo" | "favicon") => {
    setFormData((prev) => ({
      ...prev,
      [type === "logo" ? "logoFile" : "faviconFile"]: null,
      [type === "logo" ? "logoUrl" : "faviconUrl"]: "",
    }));
    if (type === "logo" && logoFileInputRef.current) {
      logoFileInputRef.current.value = "";
    }
    if (type === "favicon" && faviconFileInputRef.current) {
      faviconFileInputRef.current.value = "";
    }
  };

  const nextStep = () => {
    // Validate Step 1: Tenant Information
    if (currentStep === 1) {
      if (
        !formData.tenantName ||
        !formData.contactEmail ||
        !formData.password
      ) {
        toast.error(
          "Please fill in all required fields (Tenant Name, Contact Email, Password)",
        );
        return;
      }
    }

    // Validate Step 2: Documents
    if (currentStep === 2) {
      if (!formData.cacCertificateUrl || !formData.cbnLicenseUrl) {
        toast.error("Please upload both CAC Certificate and CBN License");
        return;
      }
    }

    // Validate Step 3: API Configuration
    if (currentStep === 3) {
      if (!formData.webhookUrl || !formData.callbackUrl) {
        toast.error("Please provide both Webhook URL and Callback URL");
        return;
      }
    }

    // Validate Step 4: Features
    if (currentStep === 4) {
      if (formData.features.length === 0) {
        toast.error("Please select at least one feature");
        return;
      }
    }

    if (currentStep < 6) setCurrentStep(currentStep + 1);
  };

  const prevStep = () => {
    if (currentStep > 1) setCurrentStep(currentStep - 1);
  };

  const toggleFeature = (feature: string) => {
    setFormData((prev) => ({
      ...prev,
      features: prev.features.includes(feature)
        ? prev.features.filter((f) => f !== feature)
        : [...prev.features, feature],
    }));
  };

  const handleLaunchTenant = async () => {
    // Validate required fields
    if (!formData.tenantName || !formData.contactEmail || !formData.password) {
      toast.error("Please fill in all required fields");
      return;
    }

    // Validate documents are uploaded
    if (!formData.cacCertificateUrl || !formData.cbnLicenseUrl) {
      toast.error(
        "Please upload both CAC Certificate and CBN License documents",
      );
      return;
    }

    if (formData.features.length === 0) {
      toast.error("Please select at least one feature");
      return;
    }

    // Map tier to plan
    const planMap: Record<string, string> = {
      Basic: "standard",
      Pro: "premium",
      Enterprise: "enterprise",
    };
    const plan = planMap[formData.tier] || "premium";

    setIsCreating(true);
    try {
      const payload = {
        name: formData.tenantName,
        type: formData.type,
        cacCertificateUrl: formData.cacCertificateUrl,
        cbnLicenseUrl: formData.cbnLicenseUrl,
        contact: {
          email: formData.contactEmail,
          firstName: formData.firstName || formData.contactEmail.split("@")[0],
          lastName: formData.lastName || "",
          phone: formData.contactPhone,
          uin: formData.uin || "",
          password: formData.password,
          address: formData.address || "",
          city: formData.city || "",
          state: formData.state || "",
          postalCode: formData.postalCode || "",
        },
        branding: {
          domain:
            formData.domain ||
            `${formData.tenantName.toLowerCase().replace(/\s+/g, "")}.com`,
          logoUrl: formData.logoUrl || "",
          faviconUrl: formData.faviconUrl || "",
          primaryColor: formData.primaryColor || primaryColor,
          secondaryColor: formData.secondaryColor || secondaryColor,
        },
        featureFlags: formData.features,
        plan: plan,
      };

      const tenantResponse = await apiClient.post<{ tenant?: { tenant_id?: string; id?: string }; tenant_id?: string; id?: string }>("/orchestrator/tenant", payload);

      // Auto-create billing account for the new tenant
      const createdTenantId =
        tenantResponse.data?.tenant?.tenant_id ||
        tenantResponse.data?.tenant?.id ||
        tenantResponse.data?.tenant_id ||
        tenantResponse.data?.id;

      if (createdTenantId) {
        const planFeeMap: Record<string, number> = {
          standard: 500000,
          premium: 2000000,
          enterprise: 5000000,
        };
        try {
          await apiClient.post("/billing-orchestrator/v1/billing/profiles", {
            tenant_id: createdTenantId,
            pricing_model: plan === "enterprise" ? "hybrid" : "subscription",
            monthly_fee: planFeeMap[plan] ?? 500000,
            status: "active",
          });
        } catch {
          // Non-blocking — billing profile creation failure should not prevent tenant launch
          console.warn("Billing profile creation failed for tenant:", createdTenantId);
        }
      }

      toast.success(`Tenant "${formData.tenantName}" created successfully!`);

      // Reset form and redirect or show success
      setTimeout(() => {
        window.location.href = "/tenants";
      }, 2000);
    } catch (error: any) {
      console.error("Error creating tenant:", error);
      const errorMessage =
        error?.response?.data?.message ||
        error?.message ||
        "Failed to create tenant";
      toast.error(errorMessage);
    } finally {
      setIsCreating(false);
    }
  };

  const renderStepContent = () => {
    switch (currentStep) {
      case 1:
        return (
          <div className="space-y-8">
            <div>
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
                Tenant Information
              </h2>
              <p className="text-gray-600 dark:text-gray-400">
                Enter basic information about the tenant
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Tenant Name *
                </label>
                <input
                  type="text"
                  value={formData.tenantName}
                  onChange={(e) =>
                    setFormData({ ...formData, tenantName: e.target.value })
                  }
                  className="w-full px-4 py-3 border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 transition-all"
                  style={
                    { "--tw-ring-color": primaryColor } as React.CSSProperties
                  }
                  placeholder="e.g., Wema Tenant"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Tenant Type *
                </label>
                <select
                  value={formData.type}
                  onChange={(e) =>
                    setFormData({
                      ...formData,
                      type: e.target.value as
                        | "bank"
                        | "microfinance"
                        | "fintech"
                        | "insurance",
                    })
                  }
                  className="w-full px-4 py-3 border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 transition-all"
                  style={
                    { "--tw-ring-color": primaryColor } as React.CSSProperties
                  }
                >
                  <option value="bank">Bank</option>
                  <option value="microfinance">Microfinance</option>
                  <option value="fintech">Fintech</option>
                  <option value="insurance">Insurance</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Subscription Tier *
                </label>
                <select
                  value={formData.tier}
                  onChange={(e) =>
                    setFormData({ ...formData, tier: e.target.value })
                  }
                  className="w-full px-4 py-3 border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 transition-all"
                  style={
                    { "--tw-ring-color": primaryColor } as React.CSSProperties
                  }
                >
                  <option value="Basic">Standard</option>
                  <option value="Pro">Premium</option>
                  <option value="Enterprise">Enterprise</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Contact Email *
                </label>
                <input
                  type="email"
                  value={formData.contactEmail}
                  onChange={(e) =>
                    setFormData({ ...formData, contactEmail: e.target.value })
                  }
                  className="w-full px-4 py-3 border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 transition-all"
                  style={
                    { "--tw-ring-color": primaryColor } as React.CSSProperties
                  }
                  placeholder="admin@wematenant.com"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Contact Phone *
                </label>
                <input
                  type="tel"
                  value={formData.contactPhone}
                  onChange={(e) =>
                    setFormData({ ...formData, contactPhone: e.target.value })
                  }
                  className="w-full px-4 py-3 border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 transition-all"
                  style={
                    { "--tw-ring-color": primaryColor } as React.CSSProperties
                  }
                  placeholder="+234 800 000 0000"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  First Name
                </label>
                <input
                  type="text"
                  value={formData.firstName}
                  onChange={(e) =>
                    setFormData({ ...formData, firstName: e.target.value })
                  }
                  className="w-full px-4 py-3 border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 transition-all"
                  style={
                    { "--tw-ring-color": primaryColor } as React.CSSProperties
                  }
                  placeholder="John"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Last Name
                </label>
                <input
                  type="text"
                  value={formData.lastName}
                  onChange={(e) =>
                    setFormData({ ...formData, lastName: e.target.value })
                  }
                  className="w-full px-4 py-3 border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 transition-all"
                  style={
                    { "--tw-ring-color": primaryColor } as React.CSSProperties
                  }
                  placeholder="Doe"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  NIN (National Identification Number)
                </label>
                <input
                  type="text"
                  value={formData.uin}
                  onChange={(e) =>
                    setFormData({ ...formData, uin: e.target.value })
                  }
                  className="w-full px-4 py-3 border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 transition-all"
                  style={
                    { "--tw-ring-color": primaryColor } as React.CSSProperties
                  }
                  placeholder="1234567890"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Password *
                </label>
                <input
                  type="password"
                  value={formData.password}
                  onChange={(e) =>
                    setFormData({ ...formData, password: e.target.value })
                  }
                  className="w-full px-4 py-3 border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 transition-all"
                  style={
                    { "--tw-ring-color": primaryColor } as React.CSSProperties
                  }
                  placeholder="••••••••"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Address
                </label>
                <input
                  type="text"
                  value={formData.address}
                  onChange={(e) =>
                    setFormData({ ...formData, address: e.target.value })
                  }
                  className="w-full px-4 py-3 border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 transition-all"
                  style={
                    { "--tw-ring-color": primaryColor } as React.CSSProperties
                  }
                  placeholder="123 Main Street"
                />
              </div>

              {/* Cascading Address Dropdowns */}
              <div className="md:col-span-2">
                <CascadingAddressDropdown
                  country={formData.country}
                  state={formData.state}
                  city={formData.city}
                  onCountryChange={(value) =>
                    setFormData({ ...formData, country: value })
                  }
                  onStateChange={(value) =>
                    setFormData({ ...formData, state: value })
                  }
                  onCityChange={(value) =>
                    setFormData({ ...formData, city: value })
                  }
                  primaryColor={primaryColor}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Postal Code
                </label>
                <input
                  type="text"
                  value={formData.postalCode}
                  onChange={(e) =>
                    setFormData({ ...formData, postalCode: e.target.value })
                  }
                  className="w-full px-4 py-3 border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 transition-all"
                  style={
                    { "--tw-ring-color": primaryColor } as React.CSSProperties
                  }
                  placeholder="100001"
                />
              </div>
            </div>
          </div>
        );

      case 2:
        return (
          <div className="space-y-8">
            <div>
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
                Upload Documents
              </h2>
              <p className="text-gray-600 dark:text-gray-400">
                Upload required regulatory documents
              </p>
            </div>

            <div className="space-y-6">
              <div
                className="border-2 border-dashed rounded-xl p-8 text-center transition-all hover:shadow-lg"
                style={{
                  borderColor: formData.cacDocument ? primaryColor : "#d1d5db",
                  backgroundColor: formData.cacDocument
                    ? `${primaryColor}08`
                    : "#f9fafb",
                  opacity: isUploadingCac ? 0.6 : 1,
                  cursor: isUploadingCac ? "not-allowed" : "pointer",
                }}
                onMouseEnter={(e) => {
                  if (!formData.cacDocument && !isUploadingCac) {
                    e.currentTarget.style.borderColor = primaryColor;
                    e.currentTarget.style.backgroundColor = `${primaryColor}08`;
                  }
                }}
                onMouseLeave={(e) => {
                  if (!formData.cacDocument && !isUploadingCac) {
                    e.currentTarget.style.borderColor = "#d1d5db";
                    e.currentTarget.style.backgroundColor = "#f9fafb";
                  }
                }}
                onClick={() =>
                  !isUploadingCac && cacFileInputRef.current?.click()
                }
              >
                <div
                  className="w-16 h-16 rounded-full mx-auto mb-4 flex items-center justify-center"
                  style={{ backgroundColor: `${primaryColor}15` }}
                >
                  {isUploadingCac ? (
                    <Activity
                      className="w-8 h-8 animate-spin"
                      style={{ color: primaryColor }}
                    />
                  ) : formData.cacDocument ? (
                    <Check
                      className="w-8 h-8"
                      style={{ color: primaryColor }}
                    />
                  ) : (
                    <FileText
                      className="w-8 h-8"
                      style={{ color: primaryColor }}
                    />
                  )}
                </div>
                <p className="font-semibold text-gray-900 dark:text-white mb-2 text-lg">
                  CAC Certificate *
                </p>
                {isUploadingCac ? (
                  <div className="space-y-2">
                    <p
                      className="text-sm font-medium"
                      style={{ color: primaryColor }}
                    >
                      Uploading document...
                    </p>
                  </div>
                ) : formData.cacDocument ? (
                  <div className="space-y-2">
                    <p
                      className="text-sm font-medium"
                      style={{ color: primaryColor }}
                    >
                      {formData.cacDocument.name}
                    </p>
                    <p className="text-xs text-gray-500">
                      {(formData.cacDocument.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        removeFile("cac");
                      }}
                      style={{ borderColor: "#ef4444", color: "#ef4444" }}
                      className="hover:bg-red-50 mt-2"
                    >
                      <X className="w-4 h-4 mr-1" />
                      Remove
                    </Button>
                  </div>
                ) : (
                  <>
                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                      Click to upload or drag and drop
                    </p>
                    <Button
                      variant="outline"
                      style={{ borderColor: primaryColor, color: primaryColor }}
                      className="hover:bg-opacity-10"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Upload className="w-4 h-4 mr-2" />
                      Choose File
                    </Button>
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

              <div
                className="border-2 border-dashed rounded-xl p-8 text-center transition-all hover:shadow-lg"
                style={{
                  borderColor: formData.cbnLicense ? primaryColor : "#d1d5db",
                  backgroundColor: formData.cbnLicense
                    ? `${primaryColor}08`
                    : "#f9fafb",
                  opacity: isUploadingCbn ? 0.6 : 1,
                  cursor: isUploadingCbn ? "not-allowed" : "pointer",
                }}
                onMouseEnter={(e) => {
                  if (!formData.cbnLicense && !isUploadingCbn) {
                    e.currentTarget.style.borderColor = primaryColor;
                    e.currentTarget.style.backgroundColor = `${primaryColor}08`;
                  }
                }}
                onMouseLeave={(e) => {
                  if (!formData.cbnLicense && !isUploadingCbn) {
                    e.currentTarget.style.borderColor = "#d1d5db";
                    e.currentTarget.style.backgroundColor = "#f9fafb";
                  }
                }}
                onClick={() =>
                  !isUploadingCbn && cbnFileInputRef.current?.click()
                }
              >
                <div
                  className="w-16 h-16 rounded-full mx-auto mb-4 flex items-center justify-center"
                  style={{ backgroundColor: `${primaryColor}15` }}
                >
                  {isUploadingCbn ? (
                    <Activity
                      className="w-8 h-8 animate-spin"
                      style={{ color: primaryColor }}
                    />
                  ) : formData.cbnLicense ? (
                    <Check
                      className="w-8 h-8"
                      style={{ color: primaryColor }}
                    />
                  ) : (
                    <FileText
                      className="w-8 h-8"
                      style={{ color: primaryColor }}
                    />
                  )}
                </div>
                <p className="font-semibold text-gray-900 dark:text-white mb-2 text-lg">
                  CBN Tenanting License *
                </p>
                {isUploadingCbn ? (
                  <div className="space-y-2">
                    <p
                      className="text-sm font-medium"
                      style={{ color: primaryColor }}
                    >
                      Uploading document...
                    </p>
                  </div>
                ) : formData.cbnLicense ? (
                  <div className="space-y-2">
                    <p
                      className="text-sm font-medium"
                      style={{ color: primaryColor }}
                    >
                      {formData.cbnLicense.name}
                    </p>
                    <p className="text-xs text-gray-500">
                      {(formData.cbnLicense.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        removeFile("cbn");
                      }}
                      style={{ borderColor: "#ef4444", color: "#ef4444" }}
                      className="hover:bg-red-50 mt-2"
                    >
                      <X className="w-4 h-4 mr-1" />
                      Remove
                    </Button>
                  </div>
                ) : (
                  <>
                    <p className="text-sm text-gray-600 dark:text-gray-400 mb-4">
                      Click to upload or drag and drop
                    </p>
                    <Button
                      variant="outline"
                      style={{ borderColor: primaryColor, color: primaryColor }}
                      className="hover:bg-opacity-10"
                      onClick={(e) => e.stopPropagation()}
                    >
                      <Upload className="w-4 h-4 mr-2" />
                      Choose File
                    </Button>
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
        );

      case 3:
        return (
          <div className="space-y-8">
            <div>
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
                API Configuration
              </h2>
              <p className="text-gray-600 dark:text-gray-400">
                Configure API endpoints and authentication
              </p>
            </div>

            <div className="space-y-6">
              <div>
                <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                  Webhook URL *
                </label>
                <input
                  type="url"
                  value={formData.webhookUrl}
                  onChange={(e) =>
                    setFormData({ ...formData, webhookUrl: e.target.value })
                  }
                  className="w-full px-4 py-3 border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 transition-all"
                  style={
                    { "--tw-ring-color": primaryColor } as React.CSSProperties
                  }
                  placeholder="https://api.wematenant.com/webhooks"
                />
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
                  We'll send transaction notifications to this URL
                </p>
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                  Callback URL *
                </label>
                <input
                  type="url"
                  value={formData.callbackUrl}
                  onChange={(e) =>
                    setFormData({ ...formData, callbackUrl: e.target.value })
                  }
                  className="w-full px-4 py-3 border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 transition-all"
                  style={
                    { "--tw-ring-color": primaryColor } as React.CSSProperties
                  }
                  placeholder="https://api.wematenant.com/callback"
                />
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
                  Redirect URL after authentication
                </p>
              </div>

              <div
                className="border rounded-lg p-4"
                style={{
                  backgroundColor: `${primaryColor}15`,
                  borderColor: `${primaryColor}40`,
                }}
              >
                <h3
                  className="font-semibold mb-2"
                  style={{ color: primaryColor }}
                >
                  API Credentials
                </h3>
                <p
                  className="text-sm mb-3"
                  style={{ color: `${primaryColor}dd` }}
                >
                  Your API keys will be generated after onboarding is complete
                </p>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span style={{ color: primaryColor }}>API Key:</span>
                    <span className="font-mono" style={{ color: primaryColor }}>
                      Generated after launch
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span style={{ color: primaryColor }}>Secret Key:</span>
                    <span className="font-mono" style={{ color: primaryColor }}>
                      Generated after launch
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        );

      case 4:
        return (
          <div className="space-y-8">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
                  Select Features
                </h2>
                <p className="text-gray-600 dark:text-gray-400">
                  Choose the features you want to enable
                </p>
              </div>
              {featuresLoading && (
                <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                  <Activity className="w-4 h-4 animate-spin" />
                  Loading features...
                </div>
              )}
            </div>

            {featuresLoading && globalFeatures.length === 0 ? (
              <div className="text-center py-12 text-gray-600 dark:text-gray-400">
                <Activity className="w-8 h-8 animate-spin mx-auto mb-2" />
                <p>Loading available features...</p>
              </div>
            ) : globalFeatures.length === 0 ? (
              <div className="text-center py-12 text-gray-600 dark:text-gray-400">
                <p>No features available. Please try again later.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {globalFeatures.map((feature) => (
                  <button
                    key={feature}
                    onClick={() => toggleFeature(feature)}
                    className={`p-5 border-2 rounded-xl text-left transition-all hover:shadow-md ${
                      formData.features.includes(feature)
                        ? "shadow-md"
                        : "border-gray-300 dark:border-slate-600 hover:border-gray-400"
                    }`}
                    style={
                      formData.features.includes(feature)
                        ? {
                            borderColor: primaryColor,
                            backgroundColor: `${primaryColor}10`,
                            boxShadow: `0 4px 6px -1px ${primaryColor}20`,
                          }
                        : {}
                    }
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <h3 className="font-semibold text-gray-900 dark:text-white capitalize text-base">
                          {feature.replace(/_/g, " ")}
                        </h3>
                      </div>
                      {formData.features.includes(feature) && (
                        <div
                          className="ml-3 flex-shrink-0 w-6 h-6 rounded-full flex items-center justify-center"
                          style={{ backgroundColor: primaryColor }}
                        >
                          <Check className="w-4 h-4 text-white" />
                        </div>
                      )}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        );

      case 5:
        return (
          <div className="space-y-8">
            <div>
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
                Branding Configuration
              </h2>
              <p className="text-gray-600 dark:text-gray-400">
                Customize your tenant's branding and appearance
              </p>
            </div>

            <div className="space-y-6">
              <div>
                <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                  Domain *
                </label>
                <input
                  type="text"
                  value={formData.domain}
                  onChange={(e) =>
                    setFormData({ ...formData, domain: e.target.value })
                  }
                  className="w-full px-4 py-3 border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 transition-all"
                  style={
                    { "--tw-ring-color": primaryColor } as React.CSSProperties
                  }
                  placeholder="example.com"
                />
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
                  Your tenant's domain name
                </p>
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                  Logo
                </label>
                {!formData.logoFile ? (
                  <div>
                    <input
                      type="file"
                      ref={logoFileInputRef}
                      accept="image/*"
                      className="hidden"
                      onChange={(e) => {
                        const file = e.target.files?.[0] || null;
                        handleImageUpload("logo", file);
                      }}
                    />
                    <button
                      type="button"
                      onClick={() => logoFileInputRef.current?.click()}
                      disabled={isUploadingLogo}
                      className="w-full px-4 py-3 border-2 border-dashed border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-white hover:border-gray-400 dark:hover:border-slate-500 transition-colors flex items-center justify-center gap-2"
                    >
                      {isUploadingLogo ? (
                        <>
                          <Activity className="w-5 h-5 animate-spin" />
                          <span>Uploading...</span>
                        </>
                      ) : (
                        <>
                          <Upload className="w-5 h-5" />
                          <span>Upload Logo Image</span>
                        </>
                      )}
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-slate-700 rounded-lg border border-gray-200 dark:border-slate-600">
                    <div className="w-12 h-12 rounded border border-gray-300 dark:border-slate-500 overflow-hidden">
                      <img
                        src={
                          formData.logoUrl ||
                          URL.createObjectURL(formData.logoFile)
                        }
                        alt="Logo preview"
                        className="w-full h-full object-cover"
                      />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                        {formData.logoFile.name}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        {(formData.logoFile.size / 1024).toFixed(1)} KB
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeImage("logo")}
                      className="p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                    >
                      <X className="w-5 h-5" />
                    </button>
                  </div>
                )}
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
                  Upload your tenant's logo image (PNG, JPG, SVG)
                </p>
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                  Favicon
                </label>
                {!formData.faviconFile ? (
                  <div>
                    <input
                      type="file"
                      ref={faviconFileInputRef}
                      accept="image/*"
                      className="hidden"
                      onChange={(e) => {
                        const file = e.target.files?.[0] || null;
                        handleImageUpload("favicon", file);
                      }}
                    />
                    <button
                      type="button"
                      onClick={() => faviconFileInputRef.current?.click()}
                      disabled={isUploadingFavicon}
                      className="w-full px-4 py-3 border-2 border-dashed border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-white hover:border-gray-400 dark:hover:border-slate-500 transition-colors flex items-center justify-center gap-2"
                    >
                      {isUploadingFavicon ? (
                        <>
                          <Activity className="w-5 h-5 animate-spin" />
                          <span>Uploading...</span>
                        </>
                      ) : (
                        <>
                          <Upload className="w-5 h-5" />
                          <span>Upload Favicon Image</span>
                        </>
                      )}
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-slate-700 rounded-lg border border-gray-200 dark:border-slate-600">
                    <div className="w-12 h-12 rounded border border-gray-300 dark:border-slate-500 overflow-hidden">
                      <img
                        src={
                          formData.faviconUrl ||
                          URL.createObjectURL(formData.faviconFile)
                        }
                        alt="Favicon preview"
                        className="w-full h-full object-cover"
                      />
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                        {formData.faviconFile.name}
                      </p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        {(formData.faviconFile.size / 1024).toFixed(1)} KB
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => removeImage("favicon")}
                      className="p-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                    >
                      <X className="w-5 h-5" />
                    </button>
                  </div>
                )}
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
                  Upload your tenant's favicon (ICO, PNG)
                </p>
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                  Primary Color *
                </label>
                <div className="flex gap-2">
                  <input
                    type="color"
                    value={formData.primaryColor || primaryColor}
                    onChange={(e) =>
                      setFormData({ ...formData, primaryColor: e.target.value })
                    }
                    className="w-16 h-12 border border-gray-300 dark:border-slate-600 rounded-lg cursor-pointer"
                  />
                  <input
                    type="text"
                    value={formData.primaryColor || primaryColor}
                    onChange={(e) =>
                      setFormData({ ...formData, primaryColor: e.target.value })
                    }
                    className="flex-1 px-4 py-3 border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 transition-all"
                    style={
                      { "--tw-ring-color": primaryColor } as React.CSSProperties
                    }
                    placeholder="#3b82f6"
                  />
                </div>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
                  Main brand color used throughout the interface
                </p>
              </div>

              <div>
                <label className="block text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
                  Secondary Color *
                </label>
                <div className="flex gap-2">
                  <input
                    type="color"
                    value={formData.secondaryColor || secondaryColor}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        secondaryColor: e.target.value,
                      })
                    }
                    className="w-16 h-12 border border-gray-300 dark:border-slate-600 rounded-lg cursor-pointer"
                  />
                  <input
                    type="text"
                    value={formData.secondaryColor || secondaryColor}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        secondaryColor: e.target.value,
                      })
                    }
                    className="flex-1 px-4 py-3 border border-gray-300 dark:border-slate-600 rounded-lg bg-white dark:bg-slate-700 text-gray-900 dark:text-white focus:outline-none focus:ring-2 transition-all"
                    style={
                      { "--tw-ring-color": primaryColor } as React.CSSProperties
                    }
                    placeholder="#10b981"
                  />
                </div>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-2">
                  Secondary brand color for accents and highlights
                </p>
              </div>

              <div
                className="border rounded-lg p-4 mt-6"
                style={{
                  backgroundColor: `${formData.primaryColor || primaryColor}15`,
                  borderColor: `${formData.primaryColor || primaryColor}40`,
                }}
              >
                <h3
                  className="font-semibold mb-2"
                  style={{ color: formData.primaryColor || primaryColor }}
                >
                  Preview
                </h3>
                <p className="text-sm text-gray-600 dark:text-gray-400 mb-3">
                  Your branding colors will be applied throughout the tenant
                  interface
                </p>
                <div className="flex gap-3">
                  <div className="flex-1">
                    <div
                      className="h-12 rounded-lg flex items-center justify-center text-white font-medium"
                      style={{
                        backgroundColor: formData.primaryColor || primaryColor,
                      }}
                    >
                      Primary Color
                    </div>
                  </div>
                  <div className="flex-1">
                    <div
                      className="h-12 rounded-lg flex items-center justify-center text-white font-medium"
                      style={{
                        backgroundColor:
                          formData.secondaryColor || secondaryColor,
                      }}
                    >
                      Secondary Color
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        );

      case 6:
        return (
          <div className="space-y-8">
            <div>
              <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
                Review & Launch
              </h2>
              <p className="text-gray-600 dark:text-gray-400">
                Review your configuration before launching
              </p>
            </div>

            <div className="space-y-6">
              <div
                className="border rounded-xl p-6 shadow-sm"
                style={{
                  backgroundColor: `${primaryColor}05`,
                  borderColor: `${primaryColor}20`,
                }}
              >
                <h3 className="font-semibold text-gray-900 dark:text-white mb-6 text-lg flex items-center gap-2">
                  <Building2
                    className="w-5 h-5"
                    style={{ color: primaryColor }}
                  />
                  Tenant Information
                </h3>
                <dl className="grid grid-cols-2 gap-6 text-sm">
                  <div>
                    <dt className="text-gray-600 dark:text-gray-400 mb-1 text-xs uppercase tracking-wide">
                      Tenant Name
                    </dt>
                    <dd className="font-semibold text-gray-900 dark:text-white text-base">
                      {formData.tenantName || "Not provided"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-gray-600 dark:text-gray-400 mb-1 text-xs uppercase tracking-wide">
                      Tenant Type
                    </dt>
                    <dd className="font-semibold text-gray-900 dark:text-white text-base capitalize">
                      {formData.type || "Not provided"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-gray-600 dark:text-gray-400 mb-1 text-xs uppercase tracking-wide">
                      Tier
                    </dt>
                    <dd className="font-semibold text-gray-900 dark:text-white text-base">
                      {formData.tier}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-gray-600 dark:text-gray-400 mb-1 text-xs uppercase tracking-wide">
                      Contact Email
                    </dt>
                    <dd className="font-semibold text-gray-900 dark:text-white text-base">
                      {formData.contactEmail || "Not provided"}
                    </dd>
                  </div>
                </dl>
              </div>

              <div
                className="border rounded-xl p-6 shadow-sm"
                style={{
                  backgroundColor: `${primaryColor}05`,
                  borderColor: `${primaryColor}20`,
                }}
              >
                <h3 className="font-semibold text-gray-900 dark:text-white mb-6 text-lg flex items-center gap-2">
                  <FileText
                    className="w-5 h-5"
                    style={{ color: primaryColor }}
                  />
                  Documents
                </h3>
                <dl className="grid grid-cols-1 gap-4 text-sm">
                  <div>
                    <dt className="text-gray-600 dark:text-gray-400 mb-1 text-xs uppercase tracking-wide">
                      CAC Certificate
                    </dt>
                    <dd className="font-semibold text-gray-900 dark:text-white text-base">
                      {formData.cacDocument ? (
                        <div className="flex items-center gap-2">
                          <Check
                            className="w-4 h-4"
                            style={{ color: primaryColor }}
                          />
                          <span>{formData.cacDocument.name}</span>
                        </div>
                      ) : (
                        <span className="text-red-600">Not uploaded</span>
                      )}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-gray-600 dark:text-gray-400 mb-1 text-xs uppercase tracking-wide">
                      CBN License
                    </dt>
                    <dd className="font-semibold text-gray-900 dark:text-white text-base">
                      {formData.cbnLicense ? (
                        <div className="flex items-center gap-2">
                          <Check
                            className="w-4 h-4"
                            style={{ color: primaryColor }}
                          />
                          <span>{formData.cbnLicense.name}</span>
                        </div>
                      ) : (
                        <span className="text-red-600">Not uploaded</span>
                      )}
                    </dd>
                  </div>
                </dl>
              </div>

              <div
                className="border rounded-xl p-6 shadow-sm"
                style={{
                  backgroundColor: `${primaryColor}05`,
                  borderColor: `${primaryColor}20`,
                }}
              >
                <h3 className="font-semibold text-gray-900 dark:text-white mb-6 text-lg flex items-center gap-2">
                  <Flag className="w-5 h-5" style={{ color: primaryColor }} />
                  Selected Features ({formData.features.length})
                </h3>
                <div className="flex flex-wrap gap-2">
                  {formData.features.length > 0 ? (
                    formData.features.map((f) => (
                      <span
                        key={f}
                        className="px-3 py-1 rounded-full text-sm font-medium capitalize"
                        style={{
                          backgroundColor: `${primaryColor}20`,
                          color: primaryColor,
                        }}
                      >
                        {f.replace(/_/g, " ")}
                      </span>
                    ))
                  ) : (
                    <p className="text-gray-600 dark:text-gray-400">
                      No features selected
                    </p>
                  )}
                </div>
              </div>

              <div
                className="border rounded-xl p-6 shadow-sm"
                style={{
                  backgroundColor: `${primaryColor}05`,
                  borderColor: `${primaryColor}20`,
                }}
              >
                <h3 className="font-semibold text-gray-900 dark:text-white mb-6 text-lg flex items-center gap-2">
                  <Palette
                    className="w-5 h-5"
                    style={{ color: primaryColor }}
                  />
                  Branding Configuration
                </h3>
                <dl className="grid grid-cols-2 gap-6 text-sm">
                  <div>
                    <dt className="text-gray-600 dark:text-gray-400 mb-1 text-xs uppercase tracking-wide">
                      Domain
                    </dt>
                    <dd className="font-semibold text-gray-900 dark:text-white text-base">
                      {formData.domain || "Not provided"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-gray-600 dark:text-gray-400 mb-1 text-xs uppercase tracking-wide">
                      Logo URL
                    </dt>
                    <dd className="font-semibold text-gray-900 dark:text-white text-base break-all">
                      {formData.logoUrl || "Not provided"}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-gray-600 dark:text-gray-400 mb-1 text-xs uppercase tracking-wide">
                      Favicon URL
                    </dt>
                    <dd className="font-semibold text-gray-900 dark:text-white text-base break-all">
                      {formData.faviconUrl || "Not provided"}
                    </dd>
                  </div>
                  <div className="col-span-2">
                    <dt className="text-gray-600 dark:text-gray-400 mb-2 text-xs uppercase tracking-wide">
                      Colors
                    </dt>
                    <dd className="flex gap-4">
                      <div className="flex items-center gap-2">
                        <div
                          className="w-8 h-8 rounded border border-gray-300 dark:border-slate-600"
                          style={{
                            backgroundColor:
                              formData.primaryColor || primaryColor,
                          }}
                        />
                        <div>
                          <div className="text-xs text-gray-500 dark:text-gray-400">
                            Primary
                          </div>
                          <div className="font-semibold text-gray-900 dark:text-white text-sm">
                            {formData.primaryColor || primaryColor}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <div
                          className="w-8 h-8 rounded border border-gray-300 dark:border-slate-600"
                          style={{
                            backgroundColor:
                              formData.secondaryColor || secondaryColor,
                          }}
                        />
                        <div>
                          <div className="text-xs text-gray-500 dark:text-gray-400">
                            Secondary
                          </div>
                          <div className="font-semibold text-gray-900 dark:text-white text-sm">
                            {formData.secondaryColor || secondaryColor}
                          </div>
                        </div>
                      </div>
                    </dd>
                  </div>
                </dl>
              </div>

              <div
                className="border rounded-lg p-6"
                style={{
                  backgroundColor: `${secondaryColor}20`,
                  borderColor: `${secondaryColor}40`,
                }}
              >
                <h3
                  className="font-semibold mb-2"
                  style={{ color: secondaryColor }}
                >
                  Ready to Launch!
                </h3>
                <p className="text-sm" style={{ color: `${secondaryColor}dd` }}>
                  Your tenant will be onboarded and ready to use within 5
                  minutes. You'll receive API credentials via email.
                </p>
              </div>
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div
      className="min-h-screen dark:from-slate-900 dark:via-slate-900 dark:to-slate-900"
      style={{
        background: `linear-gradient(to bottom right, ${primaryColor}15, ${secondaryColor}15)`,
      }}
    >
      <div className="container py-8">
        {/* Header with Logo */}
        {(logoUrl || name) && (
          <div className="mb-8 text-center">
            {logoUrl && (
              <img
                src={logoUrl}
                alt={`${name} logo`}
                className="w-16 h-16 rounded object-contain mx-auto mb-4"
              />
            )}
            {name && (
              <h1
                className="text-3xl font-bold"
                style={{ color: primaryColor }}
              >
                {name}
              </h1>
            )}
          </div>
        )}

        {/* Progress Steps */}
        <div className="mb-12">
          <div className="max-w-5xl mx-auto px-4">
            <div className="relative flex items-center justify-between">
              {/* Progress line background */}
              <div
                className="absolute top-6 left-0 right-0 h-1 z-0"
                style={{
                  background: `linear-gradient(to right, ${secondaryColor} 0%, ${secondaryColor} ${((currentStep - 1) / (steps.length - 1)) * 100}%, #e5e7eb ${((currentStep - 1) / (steps.length - 1)) * 100}%, #e5e7eb 100%)`,
                }}
              />

              {/* Steps */}
              {steps.map((step) => {
                const Icon = step.icon;
                const isCompleted = step.id < currentStep;
                const isCurrent = step.id === currentStep;
                const isUpcoming = step.id > currentStep;

                return (
                  <div
                    key={step.id}
                    className="relative z-10 flex flex-col items-center flex-1"
                  >
                    {/* Step circle */}
                    <div
                      className={`relative w-14 h-14 rounded-full flex items-center justify-center transition-all duration-300 shadow-lg ${
                        isCompleted
                          ? "text-white scale-110"
                          : isCurrent
                            ? "text-white scale-110 ring-4"
                            : "bg-white dark:bg-slate-800 text-gray-400 border-2 border-gray-300 dark:border-slate-600"
                      }`}
                      style={
                        isCompleted || isCurrent
                          ? {
                              backgroundColor: isCompleted
                                ? secondaryColor
                                : primaryColor,
                            }
                          : {}
                      }
                    >
                      {isCompleted ? (
                        <Check className="w-7 h-7" />
                      ) : (
                        <Icon
                          className={`w-6 h-6 ${isCurrent ? "animate-pulse" : ""}`}
                        />
                      )}
                      {/* Step number badge for upcoming steps */}
                      {isUpcoming && (
                        <span className="absolute -top-1 -right-1 w-5 h-5 bg-gray-300 dark:bg-slate-600 text-gray-600 dark:text-gray-400 text-xs font-bold rounded-full flex items-center justify-center">
                          {step.id}
                        </span>
                      )}
                    </div>

                    {/* Step label */}
                    <div className="mt-4 text-center max-w-30">
                      <p
                        className={`text-sm font-semibold transition-colors ${
                          isCurrent
                            ? ""
                            : isCompleted
                              ? "text-gray-700 dark:text-gray-300"
                              : "text-gray-500 dark:text-gray-500"
                        }`}
                        style={isCurrent ? { color: primaryColor } : {}}
                      >
                        {step.title}
                      </p>
                      {isCurrent && (
                        <div
                          className="mt-1 h-1 w-8 rounded-full mx-auto"
                          style={{ backgroundColor: primaryColor }}
                        />
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Content */}
        <div className="max-w-5xl mx-auto px-4">
          <div className="bg-white dark:bg-slate-800 rounded-2xl shadow-xl border border-gray-200 dark:border-slate-700 overflow-hidden">
            {/* Step indicator header */}
            <div
              className="px-8 py-6 border-b border-gray-200 dark:border-slate-700"
              style={{
                background: `linear-gradient(135deg, ${primaryColor}08, ${secondaryColor}08)`,
              }}
            >
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
                    Step {currentStep} of {steps.length}
                  </h2>
                  <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                    {steps[currentStep - 1]?.title}
                  </p>
                </div>
                <div
                  className="px-4 py-2 rounded-full text-sm font-semibold text-white"
                  style={{ backgroundColor: primaryColor }}
                >
                  {Math.round((currentStep / steps.length) * 100)}% Complete
                </div>
              </div>
            </div>

            {/* Form content */}
            <div className="p-8">{renderStepContent()}</div>

            {/* Navigation Buttons */}
            <div className="px-8 py-6 border-t border-gray-200 dark:border-slate-700 bg-gray-50 dark:bg-slate-900/50">
              <div className="flex justify-between items-center">
                <Button
                  onClick={prevStep}
                  disabled={currentStep === 1}
                  variant="outline"
                  className="min-w-30"
                >
                  <ArrowLeft className="w-4 h-4 mr-2" />
                  Previous
                </Button>

                <div className="flex gap-2">
                  {steps.map((step) => (
                    <div
                      key={step.id}
                      className={`w-2 h-2 rounded-full transition-all ${
                        step.id === currentStep
                          ? "w-8"
                          : step.id < currentStep
                            ? "opacity-100"
                            : "opacity-30"
                      }`}
                      style={{
                        backgroundColor:
                          step.id <= currentStep ? primaryColor : "#d1d5db",
                      }}
                    />
                  ))}
                </div>

                {currentStep < 5 ? (
                  <Button
                    onClick={nextStep}
                    style={{ backgroundColor: primaryColor }}
                    className="hover:opacity-90 min-w-30 text-white"
                  >
                    Next
                    <ArrowRight className="w-4 h-4 ml-2" />
                  </Button>
                ) : (
                  <Button
                    onClick={handleLaunchTenant}
                    disabled={isCreating}
                    style={{ backgroundColor: secondaryColor }}
                    className="hover:opacity-90 min-w-35 text-white disabled:opacity-50"
                  >
                    {isCreating ? (
                      <>
                        <Activity className="w-4 h-4 mr-2 animate-spin" />
                        Creating...
                      </>
                    ) : (
                      <>
                        Launch Tenant
                        <Check className="w-4 h-4 ml-2" />
                      </>
                    )}
                  </Button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
