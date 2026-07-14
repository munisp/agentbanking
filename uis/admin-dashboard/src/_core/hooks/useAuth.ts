export function useAuth(_options?: { redirectOnUnauthenticated?: boolean; redirectPath?: string }) {
  const token = localStorage.getItem("auth_token");
  const userName = localStorage.getItem("userName") || "";
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

  return {
    isAuthenticated,
    isLoading: false,
    user: isAuthenticated ? { name: userName, email: localStorage.getItem("keycloakId") || "" } : null,
    logout,
  };
}
