import * as SecureStore from "expo-secure-store";
import { agentApi, authApi, userApi } from "./apiService";
import tenantService from "./tenantService";

class AuthService {
  async login(email, password) {
    try {
      // Make sure tenant config is loaded first
      console.log("Loading tenant configuration...", email, password);
      const tenantId = await tenantService.getTenantId();
      await tenantService.getTenant(tenantId);

      // Call the real auth API - use 'user' type as API only accepts: superadmin, admin, user, guest
      const response = await authApi.login(email, password, "user");
      console.log("Login response:", response);
      console.log("keycloak_id in response:", response.keycloak_id);

      // Store auth token securely
      if (response.access_token) {
        await SecureStore.setItemAsync("authToken", response.access_token);
      } else {
        throw new Error("No access token in login response");
      }

      if (response.refresh_token) {
        await SecureStore.setItemAsync("refreshToken", response.refresh_token);
      }

      // Store keycloak_id from root level of response
      if (response.keycloak_id) {
        await SecureStore.setItemAsync("keycloakId", response.keycloak_id);
        console.log("Stored keycloak_id:", response.keycloak_id);
      } else {
        console.warn("No keycloak_id in login response");
      }

      // Fetch user details and agent profile using keycloak_id
      let agentProfile = null;
      let userDetails = null;
      if (response.keycloak_id) {
        try {
          // Fetch user details from user service
          const userResp = await userApi.getUserByKeycloakId(
            response.keycloak_id,
          );
          userDetails = userResp.user ?? userResp;
          await SecureStore.setItemAsync(
            "userDetails",
            JSON.stringify(userDetails),
          );
          console.log("User details fetched:", userDetails);
        } catch (error) {
          const errorMsg =
            error?.message || String(error) || "Error fetching user details";
          console.error("Error fetching user details:", errorMsg);
        }

        try {
          // Fetch agent profile from agent service
          const profileResp = await agentApi.getAgentByKeycloakId(
            response.keycloak_id,
          );
          agentProfile = profileResp.agent ?? profileResp;
          await SecureStore.setItemAsync(
            "agentProfile",
            JSON.stringify(agentProfile),
          );
          console.log("Agent profile fetched:", agentProfile);

          // Store agent ID for commission API calls
          if (agentProfile?.id) {
            await SecureStore.setItemAsync("agentId", agentProfile.id);
            console.log("Stored agent ID:", agentProfile.id);
          }

          // Store display name from user details or agent profile
          // Agent API returns 'name' not 'full_name'
          const displayName =
            userDetails?.name ||
            agentProfile?.name ||
            agentProfile?.business_name ||
            userDetails?.email ||
            agentProfile?.email ||
            "Agent";
          await SecureStore.setItemAsync("displayName", displayName);
          console.log("Display name set to:", displayName);
        } catch (error) {
          const errorMsg =
            error?.message || String(error) || "Error fetching agent profile";
          console.error("Error fetching agent profile:", errorMsg);
        }
      }

      console.log("Login successful, returning data...");
      return {
        token: response.access_token,
        refreshToken: response.refresh_token,
        keycloakId: response.keycloak_id,
        userDetails,
        agentProfile,
      };
    } catch (error) {
      const errorMsg =
        error?.message ||
        error?.detail ||
        (typeof error === "string" ? error : String(error)) ||
        "Login failed. Please try again.";
      console.error("Login error:", error);
      console.error("Login error message:", errorMsg);
      throw new Error(errorMsg);
    }
  }

  async signup(userData) {
    try {
      // This would typically go through the orchestrator for agent registration
      // For now, we'll throw an error as signup should be done via admin panel
      throw new Error(
        "Agent registration is managed through the admin panel. Please contact your administrator.",
      );
    } catch (error) {
      throw error;
    }
  }

  async validateToken(token) {
    try {
      // Get stored keycloak ID
      const keycloakId = await SecureStore.getItemAsync("keycloakId");
      if (!keycloakId) {
        throw new Error("No keycloak ID found");
      }

      // Get cached agent profile
      const cachedProfileStr = await SecureStore.getItemAsync("agentProfile");
      const cachedProfile = cachedProfileStr
        ? JSON.parse(cachedProfileStr)
        : null;

      // Try to fetch fresh agent profile
      try {
        const profileResp = await agentApi.getAgentByKeycloakId(keycloakId);
        const agentProfile = profileResp.agent ?? profileResp;
        await SecureStore.setItemAsync(
          "agentProfile",
          JSON.stringify(agentProfile),
        );

        // Update agent ID if changed
        if (agentProfile?.id) {
          await SecureStore.setItemAsync("agentId", agentProfile.id);
        }

        return agentProfile;
      } catch (error) {
        const errorMsg =
          error?.message || String(error) || "Error validating token";
        console.error("Error validating token:", errorMsg);
        // Return cached profile if API call fails
        if (cachedProfile) {
          return cachedProfile;
        }
        throw new Error("No agent profile available");
      }
    } catch (error) {
      const errorMsg =
        error?.message || String(error) || "Token validation error";
      console.error("Token validation error:", errorMsg);
      throw error;
    }
  }

  async logout() {
    try {
      // Get refresh token for logout
      const refreshToken = await SecureStore.getItemAsync("refreshToken");

      // Call logout API if we have a refresh token
      if (refreshToken) {
        try {
          await authApi.logout(refreshToken);
        } catch (error) {
          const errorMsg =
            error?.message || String(error) || "Logout API error";
          console.error("Logout API error:", errorMsg);
          // Continue with local cleanup even if API call fails
        }
      }

      // Clear all stored data
      await SecureStore.deleteItemAsync("authToken");
      await SecureStore.deleteItemAsync("refreshToken");
      await SecureStore.deleteItemAsync("userDetails");
      await SecureStore.deleteItemAsync("agentProfile");
      await SecureStore.deleteItemAsync("agentId");
      await SecureStore.deleteItemAsync("keycloakId");
      await SecureStore.deleteItemAsync("displayName");
      await SecureStore.deleteItemAsync("ledgerId");

      return { success: true };
    } catch (error) {
      const errorMsg = error?.message || String(error) || "Logout error";
      console.error("Logout error:", errorMsg);
      throw error;
    }
  }

  async refreshAccessToken() {
    try {
      const refreshToken = await SecureStore.getItemAsync("refreshToken");
      if (!refreshToken) {
        throw new Error("No refresh token available");
      }

      const response = await authApi.refresh(refreshToken);

      if (response.access_token) {
        await SecureStore.setItemAsync("authToken", response.access_token);
      }

      if (response.refresh_token) {
        await SecureStore.setItemAsync("refreshToken", response.refresh_token);
      }

      return response;
    } catch (error) {
      const errorMsg = error?.message || String(error) || "Token refresh error";
      console.error("Token refresh error:", errorMsg);
      throw error;
    }
  }

  async resetPassword(email) {
    try {
      // This would need to be implemented on the backend
      throw new Error(
        "Password reset functionality coming soon. Please contact support.",
      );
    } catch (error) {
      throw error;
    }
  }
}

export const authService = new AuthService();
export default authService;
