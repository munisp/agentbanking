import apiClient from "../api";

export interface LoginCredentials {
  email: string;
  password: string;
  type?: "superadmin" | "admin" | "user" | "guest";
}

export interface LoginResponse {
  token?: string;
  access_token?: string;
  refresh_token?: string;
  keycloak_id?: string;
  expires_in?: number;
  refresh_expires_in?: number;
  token_type?: string;
  session_state?: string;
  scope?: string;
  user?: {
    id: string;
    email: string;
    name?: string;
    role?: string;
  };
  message?: string;
}

export interface AuthUser {
  id: string;
  email: string;
  name?: string;
  role?: string;
  keycloak_id?: string;
  access_level?: string;
  platform_role?: string;
  user_role?: string;
  is_verified?: boolean;
  is_suspended?: boolean;
  kyc_url?: string | null;
  created_at?: string;
  updated_at?: string;
}

class AuthService {
  private readonly AUTH_TOKEN_KEY = "auth_token";
  private readonly AUTH_USER_KEY = "auth_user";

  /**
   * Login user with email and password
   */
  async login(credentials: LoginCredentials): Promise<LoginResponse> {
    try {
      const response = await apiClient.post<LoginResponse>(
        "/auth/auth/login",
        credentials,
      );

      const { token, access_token, user, keycloak_id, refresh_token } =
        response.data;

      // Store token (support both 'token' and 'access_token' field names)
      const authToken = token || access_token;
      if (authToken) {
        this.setToken(authToken);
        localStorage.setItem("access_token", authToken);
        // Set authentication flag for App.tsx router check
        localStorage.setItem("54link-dev_auth", "true");
      }

      // Store keycloak_id if present
      if (keycloak_id) {
        localStorage.setItem("keycloak_id", keycloak_id);
      }

      // Store refresh_token if present
      if (refresh_token) {
        localStorage.setItem("refresh_token", refresh_token);
      }

      // Store user info
      if (user) {
        this.setUser(user);
      }

      return response.data;
    } catch (error: any) {
      throw this.handleError(error);
    }
  }

  /**
   * Logout current user
   */
  logout(): void {
    this.removeToken();
    this.removeUser();
    // Clear authentication flag
    localStorage.removeItem("54link-dev_auth");
  }

    async fetchUserDetails(): Promise<AuthUser | null> {
    try {
      // Resolve keycloak_id from multiple sources in priority order:
      // 1. Explicit localStorage key (set if login response contains it)
      // 2. keycloak_id field on auth_user object
      // 3. JWT sub claim — Keycloak always embeds the user UUID as `sub`
      let keycloakId = localStorage.getItem("keycloak_id");

      if (!keycloakId) {
        try {
          const u = JSON.parse(localStorage.getItem("auth_user") || "{}");
          keycloakId = u.keycloak_id || null;
        } catch {}
      }

      if (!keycloakId) {
        const token = localStorage.getItem("auth_token") || localStorage.getItem("access_token");
        if (token) {
          try {
            const payload = JSON.parse(atob(token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
            keycloakId = payload.sub || null;
            if (keycloakId) {
              localStorage.setItem("keycloak_id", keycloakId);
            }
          } catch {}
        }
      }

      if (!keycloakId) {
        console.warn("fetchUserDetails: could not resolve keycloak_id");
        return null;
      }

      const response = await apiClient.get<{ message: string; admin?: AuthUser; user?: AuthUser }>(
        `/admin/admin/keycloak/${keycloakId}`,
      );

      const userData = response.data?.admin || response.data?.user;
      if (!userData) return null;

      // Persist under auth_user so Sidebar / App.tsx can read it
      this.setUser(userData);
      // Also persist as admin_data (platform-admin convention)
      localStorage.setItem("admin_data", JSON.stringify(userData));
      if (userData.keycloak_id) {
        localStorage.setItem("keycloak_id", userData.keycloak_id);
      }

      // Compute and store platform_role so App.tsx dashboard selection works
      let platformRole = (userData.access_level && userData.access_level !== "null")
        ? userData.access_level
        : (userData.platform_role && userData.platform_role !== "null")
          ? userData.platform_role
          : "";

      if (!platformRole) {
        // Check if this admin's email matches the tenant contact → super_admin
        try {
          const cfg = JSON.parse(localStorage.getItem("tenant_config") || "{}");
          const tenantConfig = cfg.tenant || cfg;
          if (tenantConfig?.contact?.email && userData.email === tenantConfig.contact.email) {
            platformRole = "super_admin";
          }
        } catch {}
      }

      localStorage.setItem("platform_role", platformRole || "support_agent");

      return userData;
    } catch (err: any) {
      console.error("fetchUserDetails failed:", err?.message);
      return null; // non-fatal — user is already authenticated
    }
  }


  /**
   * Get current auth token
   */
  getToken(): string | null {
    return localStorage.getItem(this.AUTH_TOKEN_KEY);
  }

  /**
   * Set auth token
   */
  setToken(token: string): void {
    localStorage.setItem(this.AUTH_TOKEN_KEY, token);
  }

  /**
   * Remove auth token
   */
  removeToken(): void {
    localStorage.removeItem(this.AUTH_TOKEN_KEY);
  }

  /**
   * Get current user
   */
  getUser(): AuthUser | null {
    const userStr = localStorage.getItem(this.AUTH_USER_KEY);
    if (!userStr) return null;
    try {
      return JSON.parse(userStr);
    } catch {
      return null;
    }
  }


  /**
   * Set user info
   */
  setUser(user: AuthUser): void {
    localStorage.setItem(this.AUTH_USER_KEY, JSON.stringify(user));
  }

  /**
   * Remove user info
   */
  removeUser(): void {
    localStorage.removeItem(this.AUTH_USER_KEY);
  }

  /**
   * Change password for the currently authenticated user
   */
  async changePassword(currentPassword: string, newPassword: string, confirmPassword: string): Promise<void> {
    try {
      await apiClient.post("/auth/auth/change-password", {
        current_password: currentPassword,
        new_password: newPassword,
        confirm_password: confirmPassword,
      });
    } catch (error: any) {
      throw this.handleError(error);
    }
  }

  /**
   * Check if user is authenticated
   */
  isAuthenticated(): boolean {
    return !!this.getToken();
  }

  /**
   * Handle API errors
   */
  private handleError(error: any): Error {
    if (error.response) {
      // Server responded with error status
      const data = error.response.data;
      let message = "An error occurred during authentication";

      // Try multiple paths to extract error message
      if (data?.detail?.message) {
        message = data.detail.message;
      } else if (data?.detail && typeof data.detail === "string") {
        message = data.detail;
      } else if (data?.message) {
        message = data.message;
      } else if (data?.error) {
        message = data.error;
      }

      console.error("Auth error details:", { data, extractedMessage: message });
      return new Error(message);
    } else if (error.request) {
      // Request was made but no response received
      return new Error("Network error. Please check your connection.");
    } else {
      // Something else happened
      return new Error(error.message || "An unexpected error occurred");
    }
  }
}

// Export singleton instance
export const authService = new AuthService();
export default authService;
