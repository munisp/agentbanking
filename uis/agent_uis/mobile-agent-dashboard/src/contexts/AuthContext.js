import * as SecureStore from "expo-secure-store";
import React, { createContext, useContext, useEffect, useState } from "react";
import { authService } from "../services/authService";

const AuthContext = createContext({});

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [kycStatus, setKycStatus] = useState(null); // 'verified', 'pending', 'rejected', or null

  useEffect(() => {
    checkAuthStatus();
  }, []);

  const checkAuthStatus = async () => {
    try {
      const token = await SecureStore.getItemAsync("authToken");
      if (token) {
        // Validate token and get agent profile data
        const agentProfile = await authService.validateToken(token);
        setUser(agentProfile);
        setIsAuthenticated(true);
        
        // Check KYC status from agent profile (matching core banking app pattern)
        const kycVerificationStatus = agentProfile?.kyc_verification_status || agentProfile?.kyc_status;
        setKycStatus(kycVerificationStatus || null);
        
        // Store KYC status
        if (kycVerificationStatus) {
          await SecureStore.setItemAsync("kycStatus", kycVerificationStatus);
        }
      }
    } catch (error) {
      const errorMsg = error?.message || String(error) || "Auth check failed";
      console.error("Auth check failed:", errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  const login = async (email, password) => {
    try {
      console.log("Attempting login with email:", email);
      const response = await authService.login(email, password);
      await SecureStore.setItemAsync("authToken", response.token);
      setUser(response.agentProfile);
      setIsAuthenticated(true);
      
      // Check KYC status from agent profile (matching core banking app pattern)
      const agentProfile = response.agentProfile;
      const kycVerificationStatus = agentProfile?.kyc_verification_status || agentProfile?.kyc_status;
      setKycStatus(kycVerificationStatus || null);
      
      // Store KYC status
      if (kycVerificationStatus) {
        await SecureStore.setItemAsync("kycStatus", kycVerificationStatus);
      }
      
      // Add KYC status to response for caller to handle
      return {
        ...response,
        kycStatus: kycVerificationStatus,
        isKycVerified: kycVerificationStatus === 'verified',
      };
    } catch (error) {
      const errorMsg =
        error?.message ||
        error?.details ||
        (typeof error === "string" ? error : String(error)) ||
        "Login failed. Please check your credentials and try again.";
      console.error("Login failed - Full error:", error);
      console.error("Login failed - Error message:", errorMsg);
      throw new Error(errorMsg);
    }
  };

  const signup = async (userData) => {
    try {
      const response = await authService.signup(userData);
      return response;
    } catch (error) {
      const errorMsg = error?.message || String(error) || "Signup failed";
      console.error("Signup failed:", errorMsg);
      throw error;
    }
  };

  const logout = async () => {
    try {
      await SecureStore.deleteItemAsync("authToken");
      setUser(null);
      setIsAuthenticated(false);
    } catch (error) {
      const errorMsg = error?.message || String(error) || "Logout failed";
      console.error("Logout failed:", errorMsg);
    }
  };

  const updateUser = (userData) => {
    setUser((prev) => ({ ...prev, ...userData }));
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated,
        isLoading,
        kycStatus,
        isKycVerified: kycStatus === 'verified',
        login,
        signup,
        logout,
        updateUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
};

export default AuthContext;
