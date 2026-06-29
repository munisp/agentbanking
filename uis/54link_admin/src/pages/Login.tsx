import aicpa from "@/assets/certifications/aicpa.png";
import iso from "@/assets/certifications/iso.png";
import nist from "@/assets/certifications/nist.png";
import pci from "@/assets/certifications/pci.png";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useTenantBranding } from "@/contexts/TenantBrandingContext";
import apiClient from "@/services/api";
import { useAuth } from "@/services/auth";
import { temporalAccessService } from "@/services/temporalAccessService";
import { tenantService } from "@/services/tenant";
import { AlertCircle, ExternalLink, LogIn, Eye, EyeOff, ShieldAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { useLocation } from "wouter";

interface GetTenantResponse {
  message: string;
  tenant?: any;
  data?: any;
}

interface AdminData {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  phone: string;
  uin: string;
  tenant_id: string;
  keycloak_id: string;
  is_verified: boolean;
  is_suspended: boolean;
  platform_role?: string;
  access_level?: string;
  kyc_url?: string;
  created_at: string;
  updated_at: string;
}

interface GetAdminResponse {
  message: string;
  admin: AdminData;
}

export default function Login() {
  const [, setLocation] = useLocation();
  const { login, isLoading, error: authError } = useAuth();
  const { name, logoUrl, primaryColor, secondaryColor } = useTenantBranding();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  // Removed unused state for user type
  const [error, setError] = useState("");
  const [isLoadingTenant, setIsLoadingTenant] = useState(true);
  const [showKycModal, setShowKycModal] = useState(false);
  const [adminData, setAdminData] = useState<AdminData | null>(null);
  const [showPassword, setShowPassword] = useState(false);

  // Fetch tenant config on mount - MUST complete before login
  useEffect(() => {
    const fetchTenantConfig = async () => {
      setIsLoadingTenant(true);
      try {
        // Check if tenant config already exists in localStorage
        const existingConfig = localStorage.getItem("tenant_config");
        if (existingConfig) {
          try {
            const parsed = JSON.parse(existingConfig);
            const tenantConfig = parsed.tenant || parsed;
            // Check if it has the required auth config
            const authFeature = tenantConfig?.feature_flags?.find(
              (f: any) => f.name === "auth",
            );
            if (
              authFeature?.config?.realm &&
              authFeature?.config?.public_rsa_key
            ) {
              console.log("Tenant config already loaded with auth config");
              setIsLoadingTenant(false);
              return;
            }
          } catch (e) {
            // Invalid config, fetch new one
          }
        }

        // Try to get tenant ID from environment or localStorage
        const tenantId =
          import.meta.env.VITE_TENANT_ID ||
          localStorage.getItem("tenant_id") ||
          "bpmgd";

        // Fetch tenant config from API (this endpoint might not require auth)
        try {
          const response = await apiClient.get<GetTenantResponse>(
            `/tenant-management/tenant/${tenantId}`,
          );

          if (
            response.data.message === "success" &&
            (response.data.tenant || response.data.data)
          ) {
            const tenant = response.data.tenant || response.data.data;

            // Store tenant config in localStorage
            localStorage.setItem("tenant_config", JSON.stringify(tenant));
            console.log("Tenant config loaded and stored for login");
          }
        } catch (apiError: any) {
          // If API call fails, use default config from tenantService
          console.warn(
            "Failed to fetch tenant config from API, using default:",
            apiError?.message,
          );
          const defaultConfig = tenantService.getTenantConfig();
          if (defaultConfig) {
            localStorage.setItem(
              "tenant_config",
              JSON.stringify(defaultConfig),
            );
          }
        }
      } catch (error: unknown) {
        const errorMessage =
          error instanceof Error ? error.message : "Unknown error";
        console.error(
          "Failed to fetch tenant config before login:",
          errorMessage,
        );
        // Don't set error here - allow login to proceed with default config
      } finally {
        setIsLoadingTenant(false);
      }
    };

    fetchTenantConfig();
  }, []);

  // COMMENTED OUT: Tenant fetching removed - using 54link default data only
  // Fetch tenant config on mount - MUST complete before login
  // useEffect(() => {
  //   const fetchTenantConfig = async () => {
  //     setIsLoadingTenant(true);
  //     try {
  //       // Load tenant config (now uses mock data)
  //       await tenantService.getTenant();
  //       console.log('Tenant config loaded for login');
  //
  //       // Load saved user role from localStorage
  //       const savedRole = localStorage.getItem('user_role') as UserRole | null;
  //       if (savedRole && ['admin', 'super_admin', 'super_tenant'].includes(savedRole)) {
  //         setUserRole(savedRole);
  //       }
  //     } catch (error: unknown) {
  //       const errorMessage = error instanceof Error ? error.message : 'Unknown error';
  //       console.error('Failed to fetch tenant config before login:', errorMessage);
  //       setError(`Failed to load tenant configuration: ${errorMessage}`);
  //     } finally {
  //       setIsLoadingTenant(false);
  //     }
  //   };
  //
  //   fetchTenantConfig();
  // }, []);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    // Ensure tenant config is loaded before attempting login
    if (isLoadingTenant) {
      setError("Please wait, loading tenant configuration...");
      return;
    }

    // Double-check tenant config exists
    const tenantConfig = tenantService.getTenantConfig();
    if (!tenantConfig) {
      setError("Tenant configuration is required. Please refresh the page.");
      return;
    }

    // Ensure tenant config is stored in localStorage for header extraction
    const storedConfig = localStorage.getItem("tenant_config");
    if (!storedConfig) {
      localStorage.setItem("tenant_config", JSON.stringify(tenantConfig));
    }

    try {
      // COMMENTED OUT: User roles removed - app is only for 54link
      // Store selected role in localStorage
      // localStorage.setItem('user_role', userRole);

      await login(email, password);

      // Fetch admin data by keycloak ID after successful login
      try {
        // Wait a bit for localStorage to be populated
        await new Promise((resolve) => setTimeout(resolve, 100));

        const token = localStorage.getItem("access_token");
        const keycloakId = localStorage.getItem("keycloak_id");
        const tenantId =
          import.meta.env.VITE_TENANT_ID ||
          localStorage.getItem("tenant_id") ||
          "bpmgd";

        console.log("Fetching admin data with keycloak_id:", keycloakId);

        if (keycloakId) {
          const response = await apiClient.get<GetAdminResponse>(
            `/admin/admin/keycloak/${keycloakId}`,
            {
              headers: {
                Authorization: `Bearer ${token}`,
              },
            },
          );

          console.log("Admin data response:", response.data);

          if (response.data.message === "success" && response.data.admin) {
            const admin = response.data.admin;
            setAdminData(admin);

            // Store admin data in localStorage
            localStorage.setItem("admin_data", JSON.stringify(admin));

            // Ensure keycloak_id is always stored as a top-level key so usePermissions can find it
            if (admin.keycloak_id && !localStorage.getItem("keycloak_id")) {
              localStorage.setItem("keycloak_id", admin.keycloak_id);
            }

            // Set platform role based on admin data or tenant contact email match
            try {
              const tenantConfigStr = localStorage.getItem("tenant_config");

              // Backend returns access_level (v2.perm named role string)
              let platformRole: string =
                admin.access_level != null && admin.access_level !== "null"
                  ? String(admin.access_level)
                  : "";

              // If no platform_role, check if email matches tenant contact (grant super_admin)
              if (!platformRole && tenantConfigStr && admin.email) {
                const tenantConfig = JSON.parse(tenantConfigStr);
                const contactEmail = tenantConfig?.contact?.email;

                if (contactEmail && admin.email === contactEmail) {
                  platformRole = "super_admin";
                }
              }

              // Default to support_agent if still not set
              if (!platformRole) {
                platformRole = "support_agent";
              }

              localStorage.setItem("platform_role", platformRole);
            } catch (err) {
              console.error("Failed to set platform role:", err);
              localStorage.setItem("platform_role", "support_agent");
            }

            // Check if admin is verified
            if (!admin.is_verified) {
              console.log("Admin not verified, showing KYC modal");
              setShowKycModal(true);
              return; // Don't redirect yet
            }
          }

          // Fetch temporal access grants for this admin and cache locally
          try {
            const grants = await temporalAccessService.listUserGrants(
              tenantId,
              // keycloakId,
            );
            localStorage.setItem(
              "temporal_access_grants",
              JSON.stringify(grants),
            );
          } catch (temporalError) {
            console.error(
              "Failed to fetch temporal access grants:",
              temporalError,
            );
            localStorage.removeItem("temporal_access_grants");
          }
        } else {
          console.error("No keycloak_id found in localStorage");
        }
      } catch (adminError) {
        console.error("Failed to fetch admin data:", adminError);
        // Continue to dashboard even if admin fetch fails
      }

      // COMMENTED OUT: Onboarding check removed - app is only for 54link
      // Check if onboarding is complete
      // const isOnboardingComplete = onboardingService.isOnboardingComplete();
      //
      // // Redirect to onboarding if not complete, otherwise to dashboard
      // if (!isOnboardingComplete) {
      //   setLocation('/admin/onboarding');
      // } else {
      //   setLocation('/');
      // }

      // Always redirect to dashboard after login
      setLocation("/");
    } catch (err: any) {
      console.error("Full error object:", err);
      console.error("Error response:", err?.response);
      console.error("Error response data:", err?.response?.data);

      let errorMessage = "Login failed. Please check your credentials.";

      // Try multiple paths to extract the error message
      if (err?.response?.data?.detail?.message) {
        errorMessage = err.response.data.detail.message;
      } else if (err?.response?.data?.detail) {
        if (typeof err.response.data.detail === "string") {
          errorMessage = err.response.data.detail;
        } else if (typeof err.response.data.detail === "object") {
          errorMessage = err.response.data.detail.message || JSON.stringify(err.response.data.detail);
        }
      } else if (err?.response?.data?.message) {
        errorMessage = err.response.data.message;
      } else if (err?.response?.data) {
        errorMessage = typeof err.response.data === "string" ? err.response.data : err.response.data.message || "Invalid credentials";
      } else if (err instanceof Error) {
        errorMessage = err.message;
      }

      console.error("Final error message:", errorMessage);
      setError(errorMessage);
    }
  };

  const displayError = error || authError;

  const handleLogout = () => {
    localStorage.clear();
    setShowKycModal(false);
    setEmail("");
    setPassword("");
  };

  const handleCompleteVerification = () => {
    if (adminData?.kyc_url) {
      window.open(adminData.kyc_url, "_blank");
    }
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden"
      style={{
        background: `linear-gradient(135deg, ${primaryColor}08 0%, ${secondaryColor}08 25%, ${primaryColor}05 50%, ${secondaryColor}12 100%)`,
      }}
    >
      {/* Decorative gradient blur background */}
      <div
        className="absolute inset-0 opacity-30"
        style={{
          background: `radial-gradient(circle at 20% 50%, ${primaryColor}15 0%, transparent 50%), radial-gradient(circle at 80% 80%, ${secondaryColor}15 0%, transparent 50%)`,
        }}
      />

      {/* KYC Verification Modal */}
      <Dialog open={showKycModal} onOpenChange={setShowKycModal}>
        <DialogContent className="sm:max-w-[500px]">
          <div className="flex flex-col items-center text-center space-y-4 py-4">
            {/* Warning Icon */}
            <div className="w-16 h-16 bg-orange-500 rounded-full flex items-center justify-center">
              <ShieldAlert className="w-8 h-8 text-white" />
            </div>

            {/* Title */}
            <DialogHeader>
              <DialogTitle className="text-2xl font-bold">
                KYC Verification Required
              </DialogTitle>
              <DialogDescription className="text-base text-gray-600 mt-2">
                To ensure the security of our platform and comply with
                regulatory requirements, you need to complete your identity
                verification before accessing your account.
              </DialogDescription>
            </DialogHeader>

            {/* Info Boxes */}
            <div className="w-full space-y-3 mt-4">
              {/* Why KYC is Required */}
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-left">
                <div className="flex items-start gap-2">
                  <AlertCircle className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" />
                  <div>
                    <h4 className="font-semibold text-blue-900 text-sm mb-1">
                      Why KYC is Required
                    </h4>
                    <p className="text-blue-700 text-sm">
                      KYC (Know Your Customer) verification helps us protect
                      your account and maintain a secure banking environment for
                      all users.
                    </p>
                  </div>
                </div>
              </div>

              {/* Quick & Simple Process */}
              <div className="bg-green-50 border border-green-200 rounded-lg p-4 text-left">
                <div className="flex items-start gap-2">
                  <AlertCircle className="w-5 h-5 text-green-600 mt-0.5 flex-shrink-0" />
                  <div>
                    <h4 className="font-semibold text-green-900 text-sm mb-1">
                      Quick & Simple Process
                    </h4>
                    <p className="text-green-700 text-sm">
                      The verification process only takes a few minutes. You'll
                      need a valid government-issued ID and a clear photo.
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex gap-3 w-full mt-6">
              <Button
                variant="outline"
                onClick={handleLogout}
                className="flex-1"
              >
                Logout
              </Button>
              <Button
                onClick={handleCompleteVerification}
                className="flex-1 bg-orange-500 hover:bg-orange-600 text-white"
              >
                Complete Verification
                <ExternalLink className="w-4 h-4 ml-2" />
              </Button>
            </div>

            {/* Footer Note */}
            <p className="text-xs text-gray-500 mt-4">
              After completing verification, please log in again to access your
              account
            </p>
          </div>
        </DialogContent>
      </Dialog>

      {/* Main Card */}
      <Card className="w-full max-w-md relative z-10 shadow-2xl backdrop-blur-sm border-0" style={{ backgroundColor: 'rgba(255, 255, 255, 0.95)' }}>
        {/* Top border accent */}
        <div
          className="absolute top-0 left-0 right-0 h-1.5"
          style={{
            background: `linear-gradient(90deg, ${primaryColor}, ${secondaryColor})`,
          }}
        />

        <div className="p-8">
          {/* Header */}
          <div className="text-center mb-8">
            {logoUrl && (
              <img
                src={logoUrl}
                alt={`${name} logo`}
                className="w-16 h-16 mx-auto mb-4 rounded-lg shadow-md"
              />
            )}
            <h1
              className="text-4xl font-bold mb-2"
              style={{ color: primaryColor }}
            >
              {name}
            </h1>
            <p className="text-sm tracking-wide font-medium" style={{ color: `${primaryColor}80` }}>
              SECURE ADMIN PORTAL
            </p>
          </div>

          {/* Form */}
          <form onSubmit={handleLogin} className="space-y-5">
            <div className="space-y-2">
              <label className="block text-sm font-semibold text-gray-700">
                Email Address
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-3 border-2 border-gray-200 rounded-lg focus:border-transparent transition-all duration-200 focus:outline-none focus:ring-2"
                placeholder="admin@company.com"
                style={{ '--tw-ring-color': primaryColor } as React.CSSProperties}
                required
              />
            </div>

            <div className="space-y-2">
              <label className="block text-sm font-semibold text-gray-700">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-4 py-3 pr-12 border-2 border-gray-200 rounded-lg focus:border-transparent transition-all duration-200 focus:outline-none focus:ring-2"
                  placeholder="••••••••"
                  style={{ '--tw-ring-color': primaryColor } as React.CSSProperties}
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-500 hover:text-gray-700 transition-colors"
                >
                  {showPassword ? (
                    <EyeOff className="h-5 w-5" />
                  ) : (
                    <Eye className="h-5 w-5" />
                  )}
                </button>
              </div>
            </div>

            {displayError && (
              <div className="bg-red-50 border-l-4 border-red-500 text-red-700 px-4 py-3 rounded-lg text-sm font-medium">
                {displayError}
              </div>
            )}

            <Button
              type="submit"
              className="w-full py-3 text-white font-semibold tracking-wide hover:shadow-lg transition-all duration-200 mt-6"
              style={{
                backgroundColor: primaryColor,
              }}
              disabled={isLoading}
            >
              <LogIn className="h-4 w-4 mr-2" />
              {isLoading ? "Signing In..." : "Sign In Securely"}
            </Button>
          </form>

          {/* Divider */}
          <div className="my-8 flex items-center gap-3">
            <div className="flex-1 h-px bg-gray-200" />
            <span className="text-xs text-gray-500 font-medium">SECURITY & COMPLIANCE</span>
            <div className="flex-1 h-px bg-gray-200" />
          </div>

          {/* Compliance Certificates */}
          <div className="flex flex-col items-center">
            <p className="text-xs text-gray-600 font-semibold mb-4 tracking-wide">
              CERTIFIED & COMPLIANT WITH INDUSTRY STANDARDS
            </p>
            <div className="flex gap-4 justify-center items-center flex-wrap">
              <img src={aicpa} alt="AICPA" className="h-24 w-auto opacity-75 hover:opacity-100 transition-opacity duration-300" />
              <img src={iso} alt="ISO" className="h-24 w-auto opacity-75 hover:opacity-100 transition-opacity duration-300" />
              <img src={nist} alt="NIST" className="h-24 w-auto opacity-75 hover:opacity-100 transition-opacity duration-300" />
              <img src={pci} alt="PCI" className="h-24 w-auto opacity-75 hover:opacity-100 transition-opacity duration-300" />
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
