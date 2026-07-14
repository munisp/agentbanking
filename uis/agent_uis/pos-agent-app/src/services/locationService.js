/**
 * Location Tracking Service
 * Tracks POS device location and sends updates to backend
 * Handles geofencing checks
 */

import * as Location from "expo-location";
import * as SecureStore from "expo-secure-store";
import * as TaskManager from "expo-task-manager";
const LOCATION_TASK_NAME = "background-location-task";
const LOCATION_UPDATE_INTERVAL = 30000; // 30 seconds
const LOCATION_UPDATE_DISTANCE = 50; // 50 meters

class LocationService {
  constructor() {
    this.isTracking = false;
    this.watchSubscription = null;
    this.onLocationUpdate = null;
    this.onGeofenceViolation = null;
  }

  /**
   * Request location permissions
   */
  async requestPermissions() {
    try {
      const { status: foregroundStatus } =
        await Location.requestForegroundPermissionsAsync();

      if (foregroundStatus !== "granted") {
        throw new Error("Foreground location permission denied");
      }

      const { status: backgroundStatus } =
        await Location.requestBackgroundPermissionsAsync();

      if (backgroundStatus !== "granted") {
        console.warn("Background location permission denied");
        // Can still track in foreground
      }

      return {
        foreground: foregroundStatus === "granted",
        background: backgroundStatus === "granted",
      };
    } catch (error) {
      console.error("Error requesting location permissions:", error);
      throw error;
    }
  }

  /**
   * Check if location services are enabled
   */
  async isLocationEnabled() {
    return await Location.hasServicesEnabledAsync();
  }

  /**
   * Get current location
   */
  async getCurrentLocation() {
    try {
      const { status } = await Location.getForegroundPermissionsAsync();
      if (status !== "granted") {
        console.warn("Location permission not granted; skipping current location fetch");
        return null;
      }

      const location = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });

      return {
        latitude: location.coords.latitude,
        longitude: location.coords.longitude,
        accuracy: location.coords.accuracy,
        speed: location.coords.speed,
        timestamp: new Date(location.timestamp),
      };
    } catch (error) {
      const message = String(error?.message || error || "").toLowerCase();
      const isPermissionError =
        message.includes("not authorized") ||
        message.includes("unauthorized") ||
        message.includes("permission");

      if (isPermissionError) {
        console.warn("Location unavailable (permission denied); continuing without GPS");
        return null;
      }

      console.error("Error getting current location:", error);
      return null;
    }
  }

  /**
   * Start location tracking
   */
  async startTracking(callbacks = {}) {
    try {
      if (this.isTracking) {
        console.log("Location tracking already active");
        return;
      }

      const permissions = await this.requestPermissions();
      if (!permissions.foreground) {
        throw new Error("Location permission required");
      }

      this.onLocationUpdate = callbacks.onLocationUpdate;
      this.onGeofenceViolation = callbacks.onGeofenceViolation;

      // Start foreground location tracking
      this.watchSubscription = await Location.watchPositionAsync(
        {
          accuracy: Location.Accuracy.Balanced,
          timeInterval: LOCATION_UPDATE_INTERVAL,
          distanceInterval: LOCATION_UPDATE_DISTANCE,
        },
        (location) => this.handleLocationUpdate(location),
      );

      // Start background tracking if permission granted
      if (permissions.background) {
        await Location.startLocationUpdatesAsync(LOCATION_TASK_NAME, {
          accuracy: Location.Accuracy.Balanced,
          timeInterval: LOCATION_UPDATE_INTERVAL,
          distanceInterval: LOCATION_UPDATE_DISTANCE,
          foregroundService: {
            notificationTitle: "POS Location Tracking",
            notificationBody: "Tracking your location for security",
            notificationColor: "#0066FF",
          },
        });
      }

      this.isTracking = true;
      console.log("Location tracking started");
    } catch (error) {
      console.error("Error starting location tracking:", error);
      throw error;
    }
  }

  /**
   * Stop location tracking
   */
  async stopTracking() {
    try {
      if (this.watchSubscription) {
        this.watchSubscription.remove();
        this.watchSubscription = null;
      }

      const isTaskDefined = await TaskManager.isTaskDefined(LOCATION_TASK_NAME);
      if (isTaskDefined) {
        await Location.stopLocationUpdatesAsync(LOCATION_TASK_NAME);
      }

      this.isTracking = false;
      console.log("Location tracking stopped");
    } catch (error) {
      console.error("Error stopping location tracking:", error);
    }
  }

  /**
   * Handle location updates
   */
  async handleLocationUpdate(location) {
    try {
      const locationData = {
        latitude: location.coords.latitude,
        longitude: location.coords.longitude,
        accuracy: location.coords.accuracy,
        speed: location.coords.speed,
        timestamp: new Date(location.timestamp),
      };

      console.log("Location updated:", locationData);

      // Call callback if provided
      if (this.onLocationUpdate) {
        this.onLocationUpdate(locationData);
      }

      // Send to backend via WebSocket or HTTP
      await this.sendLocationToBackend(locationData);
    } catch (error) {
      console.error("Error handling location update:", error);
    }
  }

  /**
   * Send location to backend
   */
  async sendLocationToBackend(locationData) {
    try {
      const agentId = await SecureStore.getItemAsync("agentId");
      const keycloakId = await SecureStore.getItemAsync("keycloakId");
      const tenantId = await SecureStore.getItemAsync("tenantId");
      const deviceId = await this.getDeviceId();

      const payload = {
        device_id: deviceId,
        agent_id: agentId || keycloakId,
        tenant_id: tenantId || "default",
        latitude: locationData.latitude,
        longitude: locationData.longitude,
        accuracy: locationData.accuracy,
        speed: locationData.speed,
      };

      // Try WebSocket first (if connected)
      const wsService = require("./realtimeService").default;
      if (wsService.isConnected()) {
        wsService.sendMessage({
          type: "location_update",
          payload,
        });
      } else {
        // Fallback to HTTP
        const response = await fetch(
          "https://54agent.upi.dev/realtime/api/v1/location/update",
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
            },
            body: JSON.stringify(payload),
          },
        );

        if (!response.ok) {
          throw new Error("Failed to send location update");
        }
      }
    } catch (error) {
      console.error("Error sending location to backend:", error);
    }
  }

  /**
   * Get device ID
   */
  async getDeviceId() {
    let deviceId = await SecureStore.getItemAsync("deviceId");
    if (!deviceId) {
      deviceId = `POS-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
      await SecureStore.setItemAsync("deviceId", deviceId);
    }
    return deviceId;
  }

  /**
   * Calculate distance between two coordinates (in km)
   */
  calculateDistance(lat1, lon1, lat2, lon2) {
    const R = 6371; // Radius of Earth in km
    const dLat = this.toRad(lat2 - lat1);
    const dLon = this.toRad(lon2 - lon1);
    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(this.toRad(lat1)) *
        Math.cos(this.toRad(lat2)) *
        Math.sin(dLon / 2) *
        Math.sin(dLon / 2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  }

  toRad(degrees) {
    return degrees * (Math.PI / 180);
  }
}

// Define background task
TaskManager.defineTask(LOCATION_TASK_NAME, async ({ data, error }) => {
  if (error) {
    console.error("Background location task error:", error);
    return;
  }

  if (data) {
    const { locations } = data;
    const locationService = new LocationService();

    for (const location of locations) {
      await locationService.handleLocationUpdate(location);
    }
  }
});

export default new LocationService();
