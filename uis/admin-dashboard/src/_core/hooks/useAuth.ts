/**
 * useAuth — reads the admin session persisted by the login flow in
 * localStorage. Returns the current user plus auth status flags.
 */

export interface AuthUser {
  id?: string | number;
  userId?: string | number;
  name: string;
  userName?: string;
  email: string;
  role?: string;
  roleId?: string | number;
  roleName?: string;
  keycloakSub?: string;
  expiresAt?: string | number;
  assignedBy?: string;
  assignedAt?: string;
}

export interface UseAuthResult {
  isAuthenticated: boolean;
  isLoading: boolean;
  /** @deprecated alias of isLoading kept for legacy call sites */
  loading: boolean;
  user: AuthUser | null;
  logout: () => void;
}

export function useAuth(_options?: {
  redirectOnUnauthenticated?: boolean;
  redirectPath?: string;
}): UseAuthResult {
  const token = localStorage.getItem("auth_token");
  const userName = localStorage.getItem("userName") || "";
  const keycloakId = localStorage.getItem("keycloakId") || "";
  const adminRole = localStorage.getItem("adminRole") || undefined;
  const isAuthenticated = !!token;

  const logout = () => {
    localStorage.removeItem("auth_token");
    localStorage.removeItem("auth_token_expires_at");
    localStorage.removeItem("userName");
    localStorage.removeItem("refreshToken");
    localStorage.removeItem("keycloakId");
    localStorage.removeItem("adminRole");
    window.location.href = "/login";
  };

  const user: AuthUser | null = isAuthenticated
    ? {
        id: keycloakId || userName,
        userId: keycloakId || userName,
        name: userName,
        userName,
        email: keycloakId,
        role: adminRole,
        keycloakSub: keycloakId || undefined,
      }
    : null;

  return {
    isAuthenticated,
    isLoading: false,
    loading: false,
    user,
    logout,
  };
}
