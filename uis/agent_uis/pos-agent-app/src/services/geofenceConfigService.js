/**
 * Geofence Configuration Service
 * Utility for setting up and managing geofence parameters
 */

import * as SecureStore from "expo-secure-store";

class GeofenceConfigService {
  /**
   * Configure geofence for an agent
   * @param {number} centerLat - Latitude of geofence center
   * @param {number} centerLon - Longitude of geofence center
   * @param {number} radiusKm - Radius of geofence in kilometers
   */
  async configureGeofence(centerLat, centerLon, radiusKm) {
    try {
      await SecureStore.setItemAsync(
        "geofence_center_lat",
        centerLat.toString(),
      );
      await SecureStore.setItemAsync(
        "geofence_center_lon",
        centerLon.toString(),
      );
      await SecureStore.setItemAsync("geofence_radius_km", radiusKm.toString());

      console.log("Geofence configured:", {
        centerLat,
        centerLon,
        radiusKm,
      });

      return true;
    } catch (error) {
      console.error("Error configuring geofence:", error);
      throw error;
    }
  }

  /**
   * Get current geofence configuration
   */
  async getGeofenceConfig() {
    try {
      const centerLat = await SecureStore.getItemAsync("geofence_center_lat");
      const centerLon = await SecureStore.getItemAsync("geofence_center_lon");
      const radiusKm = await SecureStore.getItemAsync("geofence_radius_km");

      if (!centerLat || !centerLon || !radiusKm) {
        return null;
      }

      return {
        centerLat: parseFloat(centerLat),
        centerLon: parseFloat(centerLon),
        radiusKm: parseFloat(radiusKm),
      };
    } catch (error) {
      console.error("Error getting geofence config:", error);
      return null;
    }
  }

  /**
   * Clear geofence configuration
   */
  async clearGeofence() {
    try {
      await SecureStore.deleteItemAsync("geofence_center_lat");
      await SecureStore.deleteItemAsync("geofence_center_lon");
      await SecureStore.deleteItemAsync("geofence_radius_km");

      console.log("Geofence configuration cleared");
      return true;
    } catch (error) {
      console.error("Error clearing geofence:", error);
      throw error;
    }
  }

  /**
   * Set geofence from agent's registered location
   * This would typically be called after agent onboarding or location verification
   */
  async setGeofenceFromLocation(latitude, longitude, defaultRadiusKm = 5) {
    return await this.configureGeofence(latitude, longitude, defaultRadiusKm);
  }

  /**
   * Example: Configure test geofence for Lagos, Nigeria
   * Call this for testing purposes
   */
  async setupTestGeofence() {
    // Lagos, Nigeria coordinates
    const lagosLat = 6.5244;
    const lagosLon = 3.3792;
    const radiusKm = 10; // 10km radius

    return await this.configureGeofence(lagosLat, lagosLon, radiusKm);
  }
}

export default new GeofenceConfigService();
