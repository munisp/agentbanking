import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { tenantService, type Tenant, type TenantBranding } from '../services/tenant';
import { getTenantHeaders } from '../services/tenant/getTenantHeaders';
// COMMENTED OUT: UserRole removed - app is only for 54link
// import { tenantService, type Tenant, type TenantBranding, type UserRole } from '../services/tenant';

interface TenantBrandingContextType {
  tenant: Tenant | null;
  branding: TenantBranding | null;
  name: string;
  logoUrl: string | null;
  faviconUrl: string | null;
  primaryColor: string;
  secondaryColor: string;
  domain: string | null;
  headers: Record<string, string>;
  isLoading: boolean;
}

const TenantBrandingContext = createContext<TenantBrandingContextType | undefined>(undefined);

export function TenantBrandingProvider({ children }: { children: ReactNode }) {
  const [tenant, setTenant] = useState<Tenant | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  // COMMENTED OUT: User roles removed - app is only for 54link
  // const [userRole, setUserRole] = useState<UserRole | null>(null);

  useEffect(() => {
    const loadTenant = () => {
      const config = tenantService.getTenantConfig();
      setTenant(config);
      setIsLoading(false);

      // COMMENTED OUT: User role logic removed - app is only for 54link
      // Get user role
      // const role = tenantService.getUserRole();
      // setUserRole(role);

      // Always use 54Link branding
      if (config?.branding) {
        const root = document.documentElement;
        root.style.setProperty('--tenant-primary-color', config.branding.primary_color || '#22c55e');
        root.style.setProperty('--tenant-secondary-color', config.branding.secondary_color || '#16a34a');
        
        // Set favicon if available
        if (config.branding.favicon_url) {
          const link = document.querySelector("link[rel~='icon']") as HTMLLinkElement;
          if (link) {
            link.href = config.branding.favicon_url;
          } else {
            const newLink = document.createElement('link');
            newLink.rel = 'icon';
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

    // COMMENTED OUT: User role storage listener removed
    // Listen for storage changes to update when tenant config or role changes
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'tenant_config') {
        loadTenant();
      }
    };

    window.addEventListener('storage', handleStorageChange);
    
    // Also check periodically for changes
    const interval = setInterval(loadTenant, 5000);

    return () => {
      window.removeEventListener('storage', handleStorageChange);
      clearInterval(interval);
    };
  }, []);

  // Always use 54Link branding - no role-based overrides
  const branding = tenant?.branding || null;
  const name = tenant?.name || '54Link';
  const logoUrl = branding?.logo_url || null;
  const faviconUrl = branding?.favicon_url || null;
  const primaryColor = branding?.primary_color || '#22c55e';
  const secondaryColor = branding?.secondary_color || '#16a34a';
  const domain = branding?.domain || null;
  
  // Extract headers from tenant config
  const headers = getTenantHeaders(tenant);

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
        headers,
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
    throw new Error('useTenantBranding must be used within TenantBrandingProvider');
  }
  return context;
}

