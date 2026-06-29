import { useEffect, useState } from "react";
import { authApi, STORAGE, userApi } from "../utils/api";

const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === "true";

export const useAuth = () => {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    initAuth();
  }, []);

  const initAuth = async () => {
    const storedToken = localStorage.getItem(STORAGE.TOKEN);
    const storedUser = localStorage.getItem(STORAGE.USER);
    const tokenExpiry = localStorage.getItem(STORAGE.TOKEN_EXPIRY);

    if (!storedToken || !storedUser) {
      setIsLoading(false);
      return;
    }

    // Check if token is expired
    if (tokenExpiry && Date.now() > parseInt(tokenExpiry)) {
      const refreshed = await attemptRefresh();
      if (!refreshed) {
        clearAuthData();
        setIsLoading(false);
        return;
      }
    }

    try {
      console.log("Initializing auth with stored user:", storedUser);
      setUser(JSON.parse(storedUser));
    } catch (error) {
      console.error("Error parsing stored user:", error);
      clearAuthData();
    }

    setIsLoading(false);
  };

  const attemptRefresh = async () => {
    const refreshToken = localStorage.getItem(STORAGE.REFRESH_TOKEN);
    if (!refreshToken) return false;

    try {
      const response = await authApi.refresh(refreshToken);
      _storeTokens(response);
      return true;
    } catch (error) {
      console.error("Token refresh failed:", error);
      return false;
    }
  };

  const _storeTokens = (response) => {
    // Auth service may wrap the payload in a `data` key
    const payload = response.data ?? response;
    const { access_token, refresh_token, expires_in } = payload;

    if (access_token) localStorage.setItem(STORAGE.TOKEN, access_token);
    if (refresh_token)
      localStorage.setItem(STORAGE.REFRESH_TOKEN, refresh_token);
    localStorage.setItem(
      STORAGE.TOKEN_EXPIRY,
      String(Date.now() + (expires_in || 3600) * 1000),
    );
  };

  /** Extract keycloakId from wherever the auth service puts it */
  const _extractKeycloakId = (response) => {
    const payload = response.data ?? response;
    return (
      payload.keycloakId ??
      payload.keycloak_id ??
      response.keycloakId ??
      response.keycloak_id ??
      null
    );
  };

  const clearAuthData = () => {
    localStorage.removeItem(STORAGE.TOKEN);
    localStorage.removeItem(STORAGE.REFRESH_TOKEN);
    localStorage.removeItem(STORAGE.TOKEN_EXPIRY);
    localStorage.removeItem(STORAGE.USER);
    localStorage.removeItem(STORAGE.KEYCLOAK_ID);
  };

  const login = async (credentials) => {
    try {
      setIsLoading(true);

      // Demo mode: skip authentication
      if (DEMO_MODE) {
        const demoUser = {
          id: "demo-customer-001",
          keycloakId: "demo-keycloak-customer",
          name: "Demo Customer",
          email: "customer@demo.com",
          phone: "+1234567890",
          firstName: "Demo",
          lastName: "Customer",
          uin: "DEMO123456",
          status: "active",
          kycStatus: "verified",
          tenantId: "54agent",
        };

        localStorage.setItem(STORAGE.TOKEN, "demo-token");
        localStorage.setItem(STORAGE.USER, JSON.stringify(demoUser));
        localStorage.setItem(STORAGE.KEYCLOAK_ID, demoUser.keycloakId);
        setUser(demoUser);
        setIsLoading(false);
        return demoUser;
      }

      // Call real auth API
      const response = await authApi.login(
        credentials.email,
        credentials.password,
      );
      _storeTokens(response);

      // Extract keycloakId from wherever the auth service places it
      const keycloakId = _extractKeycloakId(response);
      if (keycloakId) localStorage.setItem(STORAGE.KEYCLOAK_ID, keycloakId);

      // Fetch full user profile from user-service
      const profileResponse = await userApi.getProfile(keycloakId);
      const userProfile = profileResponse.user || profileResponse;

      const userData = {
        id: userProfile.id,
        keycloakId,
        name:
          userProfile.name ||
          `${userProfile.first_name} ${userProfile.last_name}`,
        email: userProfile.email,
        phone: userProfile.phone_number || userProfile.phone || "",
        firstName: userProfile.first_name,
        lastName: userProfile.last_name,
        uin: userProfile.uin,
        status: userProfile.status,
        kycStatus: userProfile.kyc_verification_status,
        kycVerificationUrl: userProfile.kyc_verification_url || null,
        tenantId: userProfile.tenant_id,
      };

      localStorage.setItem(STORAGE.USER, JSON.stringify(userData));
      setUser(userData);
      return userData;
    } catch (error) {
      console.error("Login error:", error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    try {
      setIsLoading(true);
      const refreshToken = localStorage.getItem(STORAGE.REFRESH_TOKEN);

      if (refreshToken) {
        await authApi
          .logout(refreshToken)
          .catch((err) => console.error("Logout API call failed:", err));
      }

      clearAuthData();
      setUser(null);
    } catch (error) {
      console.error("Logout error:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const refreshProfile = async () => {
    const keycloakId = localStorage.getItem(STORAGE.KEYCLOAK_ID);
    if (!keycloakId) return;

    try {
      const profileResponse = await userApi.getProfile(keycloakId);
      const userProfile = profileResponse.user || profileResponse;

      const userData = {
        id: userProfile.id,
        keycloakId,
        name:
          userProfile.name ||
          `${userProfile.first_name} ${userProfile.last_name}`,
        email: userProfile.email,
        phone: userProfile.phone_number || userProfile.phone || "",
        firstName: userProfile.first_name,
        lastName: userProfile.last_name,
        uin: userProfile.uin,
        status: userProfile.status,
        kycStatus: userProfile.kyc_verification_status,
        kycVerificationUrl: userProfile.kyc_verification_url || null,
        tenantId: userProfile.tenant_id,
      };

      localStorage.setItem(STORAGE.USER, JSON.stringify(userData));
      setUser(userData);
    } catch (error) {
      console.error("Failed to refresh profile:", error);
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

export default useAuth;
