import { createContext, useContext, useEffect, useState } from "react";
import { tenantService } from "../services/tenantService.js";

const TenantContext = createContext(null);

export function TenantProvider({ children }) {
  const [tenant, setTenant] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadTenant = async () => {
      try {
        // Use cached config immediately if available
        const cached = tenantService.getTenantConfig();
        if (cached) {
          setTenant(cached);
          applyBranding(cached);
        }

        // Always fetch fresh to stay up-to-date
        const tenantId = tenantService.getTenantId();
        if (tenantId) {
          const config = await tenantService.getTenant(tenantId);
          setTenant(config);
          applyBranding(config);
        } else {
          const defaultConfig = tenantService.getDefaultConfig();
          setTenant(defaultConfig);
          applyBranding(defaultConfig);
        }
      } catch (error) {
        console.error("Failed to load tenant:", error);
        const defaultConfig = tenantService.getDefaultConfig();
        setTenant(defaultConfig);
        applyBranding(defaultConfig);
      } finally {
        setIsLoading(false);
      }
    };

    loadTenant();
  }, []);

  const applyBranding = (config) => {
    if (!config?.branding) return;

    const root = document.documentElement;
    root.style.setProperty(
      "--tenant-primary-color",
      config.branding.primary_color || "#002082",
    );
    root.style.setProperty(
      "--tenant-secondary-color",
      config.branding.secondary_color || "#6CC049",
    );

    // Favicon
    if (config.branding.favicon_url) {
      const link = document.querySelector("link[rel~='icon']");
      if (link) {
        link.href = config.branding.favicon_url;
      } else {
        const newLink = document.createElement("link");
        newLink.rel = "icon";
        newLink.href = config.branding.favicon_url;
        document.head.appendChild(newLink);
      }
    }

    // Page title
    if (config?.name) {
      document.title = `${config.name} - Customer Portal`;
    }
  };

  const contextValue = {
    tenant,
    branding: tenant?.branding || null,
    name: tenant?.name || "Area Konnect by Fidelity",
    logoUrl: tenant?.branding?.logo_url || null,
    faviconUrl: tenant?.branding?.favicon_url || null,
    primaryColor: tenant?.branding?.primary_color || "#002082",
    secondaryColor: tenant?.branding?.secondary_color || "#6CC049",
    domain: tenant?.branding?.domain || null,
    isLoading,
  };

  return (
    <TenantContext.Provider value={contextValue}>
      {children}
    </TenantContext.Provider>
  );
}

export function useTenant() {
  const context = useContext(TenantContext);
  if (!context) {
    throw new Error("useTenant must be used within TenantProvider");
  }
  return context;
}

export { TenantContext };
