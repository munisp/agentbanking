import { createContext, useEffect, useState } from "react";
import { agentApi, authApi } from "../utils/api";

const AuthContext = createContext(null);
const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === "true";

const STORAGE_KEYS = {
  user: "agent_dashboard_user",
  token: "agent_dashboard_token",
  refreshToken: "agent_dashboard_refresh_token",
  tokenExpiry: "agent_dashboard_token_expiry",
  keycloakId: "keycloakId",
  tenantId: "tenantId",
  agentRole: "agentRole",
};

export const useAuth = () => {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const initAuth = async () => {
      const storedUser = localStorage.getItem(STORAGE_KEYS.user);
      const storedToken = localStorage.getItem(STORAGE_KEYS.token);
      const tokenExpiry = localStorage.getItem(STORAGE_KEYS.tokenExpiry);

      if (storedUser && storedToken) {
        // If token is expired try to refresh first
        if (tokenExpiry && Date.now() > parseInt(tokenExpiry)) {
          const refreshToken = localStorage.getItem(STORAGE_KEYS.refreshToken);
          if (refreshToken) {
            try {
              const refreshed = await authApi.refresh(refreshToken);
              _storeTokens(refreshed);
              const parsedUser = JSON.parse(storedUser);
              setUser(parsedUser);
              
              // Ensure keycloakId is in localStorage for API calls
              if (parsedUser?.keycloakId && !localStorage.getItem(STORAGE_KEYS.keycloakId)) {
                localStorage.setItem(STORAGE_KEYS.keycloakId, parsedUser.keycloakId);
                console.log("✅ Restored keycloakId to localStorage after token refresh:", parsedUser.keycloakId);
              }
              if (parsedUser?.agentRole) {
                localStorage.setItem(STORAGE_KEYS.agentRole, parsedUser.agentRole);
              }
              
              setIsLoading(false);
              return;
            } catch {
              clearAuthData();
              setIsLoading(false);
              return;
            }
          }
          clearAuthData();
          setIsLoading(false);
          return;
        }

        try {
          const parsedUser = JSON.parse(storedUser);
          setUser(parsedUser);
          
          // Ensure keycloakId is in localStorage for API calls
          if (parsedUser?.keycloakId && !localStorage.getItem(STORAGE_KEYS.keycloakId)) {
            localStorage.setItem(STORAGE_KEYS.keycloakId, parsedUser.keycloakId);
            console.log("✅ Restored keycloakId to localStorage from user object:", parsedUser.keycloakId);
          }
          if (parsedUser?.agentRole) {
            localStorage.setItem(STORAGE_KEYS.agentRole, parsedUser.agentRole);
          }
        } catch (error) {
          console.error("Error parsing stored user data:", error);
          clearAuthData();
        }
      }

      setIsLoading(false);
    };

    initAuth();
  }, []);

  const clearAuthData = () => {
    Object.values(STORAGE_KEYS).forEach((key) => localStorage.removeItem(key));
  };

  /** Persist tokens returned by the auth service. */
  const _storeTokens = ({ access_token, refresh_token, expires_in }) => {
    if (access_token) localStorage.setItem(STORAGE_KEYS.token, access_token);
    if (refresh_token)
      localStorage.setItem(STORAGE_KEYS.refreshToken, refresh_token);
    if (expires_in)
      localStorage.setItem(
        STORAGE_KEYS.tokenExpiry,
        String(Date.now() + expires_in * 1000),
      );
  };

  const login = async (credentials) => {
    try {
      setIsLoading(true);

      // Demo mode: Skip authentication
      if (DEMO_MODE) {
        const demoUser = {
          id: "demo-agent-id",
          keycloakId: "demo-agent-id",
          name: "Demo Agent",
          email: "demo@agent.com",
          phone: "+234-800-0000000",
          agentCode: "AG-DEMO-001",
          businessName: "Demo Business",
          businessAddress: "123 Demo Street",
          agentRole: "agent",
          status: "active",
          tenantId: "54agent",
          role: "agent",
        };
        localStorage.setItem(STORAGE_KEYS.user, JSON.stringify(demoUser));
        localStorage.setItem(STORAGE_KEYS.token, "demo-token");
        localStorage.setItem(STORAGE_KEYS.keycloakId, "demo-agent-id");
        localStorage.setItem(STORAGE_KEYS.tenantId, "54agent");
        localStorage.setItem(STORAGE_KEYS.agentRole, "agent");
        setUser(demoUser);
        setIsLoading(false);
        return;
      }

      if (!credentials.email || !credentials.password) {
        throw new Error("Email and password are required");
      }

      // Call the real auth API
      const response = await authApi.login(
        credentials.email,
        credentials.password,
      );

      console.log("🔐 Login response:", response);

      // Store tokens
      _storeTokens(response);

      // Auth response may carry user info at root or nested
      const rawUser = response.user ?? response.agent ?? response;
      let keycloakId =
        rawUser.keycloak_id ?? rawUser.keycloakId ?? response.keycloak_id;

      console.log("🔑 Initial keycloakId from response:", keycloakId);

      // Fallback: decode JWT sub claim (Keycloak always puts keycloak ID in sub)
      if (!keycloakId && response.access_token) {
        try {
          const payload = JSON.parse(atob(response.access_token.split(".")[1]));
          keycloakId = payload.sub;
          console.log("🔑 Extracted keycloakId from JWT:", keycloakId);
        } catch (err) {
          console.error("Failed to decode JWT:", err);
        }
      }

      if (keycloakId) {
        localStorage.setItem(STORAGE_KEYS.keycloakId, keycloakId);
        console.log("✅ Stored keycloakId in localStorage:", keycloakId);
      } else {
        console.error("❌ No keycloakId found in login response or JWT!");
        console.error("Response data:", { response, rawUser });
      }

      // Try to enrich with the full agent profile
      let profileData = rawUser;
      if (keycloakId) {
        try {
          // Use the new endpoint that returns { message, agent }
          const profileResp = await agentApi.getAgentByKeycloakId(keycloakId);
          profileData = profileResp.agent ?? profileResp ?? rawUser;
        } catch {
          // Non-fatal — use what the login response already provided
        }
      }

      const userData = {
        id: profileData.id ?? keycloakId,
        keycloakId,
        name:
          profileData.name ||
          `${profileData.first_name ?? ""} ${profileData.last_name ?? ""}`.trim() ||
          credentials.email.split("@")[0],
        email: profileData.email ?? credentials.email,
        phone: profileData.phone_number ?? profileData.phone ?? "",
        agentCode: profileData.uin ?? "",
        businessName: profileData.business_name ?? "",
        businessAddress: profileData.business_address ?? "",
        agentRole: profileData.agent_role ?? "agent",
        status: profileData.status ?? "active",
        kycStatus: profileData.kyc_verification_status ?? "pending",
        kycUrl: profileData.kyc_verification_url ?? null,
        onboardingStatus: profileData.onboarding_status ?? "in_progress",
        isApproved: profileData.is_approved ?? false,
        tenantId:
          profileData.tenant_id ?? localStorage.getItem(STORAGE_KEYS.tenantId),
        role: "agent",
      };

      localStorage.setItem(STORAGE_KEYS.user, JSON.stringify(userData));
      localStorage.setItem(STORAGE_KEYS.agentRole, userData.agentRole);
      setUser(userData);
    } catch (error) {
      console.error("Login error:", error);
      throw new Error(error.message || "Login failed. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    try {
      setIsLoading(true);
      const refreshToken = localStorage.getItem(STORAGE_KEYS.refreshToken);
      if (refreshToken) {
        try {
          await authApi.logout(refreshToken);
        } catch {
          // Ignore — clear locally regardless
        }
      }
    } catch (error) {
      console.error("Logout error:", error);
    } finally {
      clearAuthData();
      setUser(null);
      setIsLoading(false);
    }
  };

  /** Re-fetch agent profile and update stored user data. */
  const refreshProfile = async () => {
    const keycloakId = localStorage.getItem(STORAGE_KEYS.keycloakId);
    if (!keycloakId) return;
    try {
      const profileResp = await agentApi.getAgentByKeycloakId(keycloakId);
      const profileData = profileResp.agent ?? profileResp;
      const updated = {
        ...user,
        name:
          profileData.name ??
          `${profileData.first_name ?? ""} ${profileData.last_name ?? ""}`.trim(),
        phone: profileData.phone_number ?? profileData.phone ?? user?.phone,
        businessName: profileData.business_name ?? user?.businessName,
        status: profileData.status ?? user?.status,
        kycStatus: profileData.kyc_verification_status ?? user?.kycStatus,
        kycUrl: profileData.kyc_verification_url ?? user?.kycUrl,
        agentRole: profileData.agent_role ?? user?.agentRole ?? "agent",
      };
      localStorage.setItem(STORAGE_KEYS.user, JSON.stringify(updated));
      localStorage.setItem(STORAGE_KEYS.agentRole, updated.agentRole);
      setUser(updated);
    } catch (error) {
      console.error("Profile refresh error:", error);
    }
  };

  return {
    user,
    isAuthenticated: !!user,
    isLoading,
    login,
    logout,
    refreshProfile,
  };
};

export { AuthContext };
export default useAuth;
