import { useCallback, useEffect, useState } from "react";
import { authService, type AuthUser } from "./authService";

interface UseAuthReturn {
  user: AuthUser | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  error: string | null;
}

/**
 * React hook for authentication
 */
export function useAuth(): UseAuthReturn {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Initialize auth state from localStorage
  useEffect(() => {
    const initAuth = () => {
      const token = authService.getToken();
      const userData = authService.getUser();

      setIsAuthenticated(!!token);
      setUser(userData);
      setIsLoading(false);
    };

    initAuth();
  }, []);

  /**
   * Login function
   */
  const login = useCallback(
    async (
      email: string,
      password: string,
    ) => {
      try {
        setIsLoading(true);
        setError(null);

        const response = await authService.login({ email, password });

        // Update state with user data
        console.log("Login successful, response:", response);
        const userData = response.user || authService.getUser();
        authService.fetchUserDetails().catch((err) => {
          console.error("Failed to fetch user details after login:", err);
        });
        if (userData) {
          setUser(userData);
          setIsAuthenticated(true);
        }
      } catch (err: any) {
        setError(err.message || "Login failed");
        setIsAuthenticated(false);
        setUser(null);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );

  /**
   * Logout function
   */
  const logout = useCallback(() => {
    authService.logout();
    setUser(null);
    setIsAuthenticated(false);
    setError(null);
  }, []);

  return {
    user,
    isAuthenticated,
    isLoading,
    login,
    logout,
    error,
  };
}
