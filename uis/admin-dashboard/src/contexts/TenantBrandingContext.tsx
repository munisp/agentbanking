import {
    createContext,
    useContext,
    useEffect,
    useState,
    type ReactNode,
} from "react";
import {
    tenantService,
    type Tenant,
    type TenantBranding,
} from "../services/tenant";

interface TenantBrandingContextType {
  tenant: Tenant | null;
  branding: TenantBranding | null;
  name: string;
  logoUrl: string | null;
  faviconUrl: string | null;
  primaryColor: string;
  secondaryColor: string;
  domain: string | null;
  isLoading: boolean;
}

const TenantBrandingContext = createContext<
  TenantBrandingContextType | undefined
>(undefined);

export function TenantBrandingProvider({ children }: { children: ReactNode }) {
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadTenant = () => {
      const config = tenantService.getTenantConfig();
      setTenant(config);
      setIsLoading(false);

      // Use tenant branding from config
      if (config?.branding) {
        const root = document.documentElement;
        const primary = config.branding.primary_color || "#002082";
        const secondary = config.branding.secondary_color || "#6CC049";
        root.style.setProperty("--tenant-primary-color", primary);
        root.style.setProperty("--tenant-secondary-color", secondary);
        // Extra aliases consumed by component inline styles
        root.style.setProperty("--color-primary", primary);
        root.style.setProperty("--color-secondary", secondary);

        // Set favicon if available
        if (config.branding.favicon_url) {
          const link = document.querySelector(
            "link[rel~='icon']",
          ) as HTMLLinkElement;
          if (link) {
            link.href = config.branding.favicon_url;
          } else {
            const newLink = document.createElement("link");
            newLink.rel = "icon";
            newLink.href = config.branding.favicon_url;
            document.head.appendChild(newLink);
          }
        }

        // Update page title
        if (config?.name) {
          document.title = `${config.name} - Admin Portal`;
        }
      }
    };

    loadTenant();

    // Listen for storage changes to update when tenant config changes
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === "tenant_config") {
        loadTenant();
      }
    };

    window.addEventListener("storage", handleStorageChange);

    // Also check periodically for changes
    const interval = setInterval(loadTenant, 5000);

    return () => {
      window.removeEventListener("storage", handleStorageChange);
      clearInterval(interval);
    };
  }, []);

  // Use tenant branding from config
  const branding = tenant?.branding || null;
  const name = tenant?.name || "54agent Admin";
  const logoUrl = branding?.logo_url || null;
  const faviconUrl = branding?.favicon_url || null;
  const primaryColor = branding?.primary_color || "#002082";
  const secondaryColor = branding?.secondary_color || "#6CC049";
  const domain = branding?.domain || null;

  return (
    <TenantBrandingContext.Provider
      value={{
        tenant,
        branding,
        name,
        logoUrl,
        faviconUrl,
        primaryColor,
        secondaryColor,
        domain,
        isLoading,
      }}
    >
      {children}
    </TenantBrandingContext.Provider>
  );
}

export function useTenantBranding() {
  const context = useContext(TenantBrandingContext);
  if (context === undefined) {
    throw new Error(
      "useTenantBranding must be used within TenantBrandingProvider",
    );
  }
  return context;
}
