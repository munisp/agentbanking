/**
 * React Hook for Real-time Services
 * Provides easy access to location tracking and notifications
 */

import { useCallback, useEffect, useState } from "react";
import locationService from "../services/locationService";
import realtimeService from "../services/realtimeService";

export function useRealtime() {
  const [isConnected, setIsConnected] = useState(false);
  const [isLocationTracking, setIsLocationTracking] = useState(false);
  const [lastTransaction, setLastTransaction] = useState(null);
  const [geofenceViolation, setGeofenceViolation] = useState(null);
  const [currentLocation, setCurrentLocation] = useState(null);

  useEffect(() => {
    // Connect to real-time service
    realtimeService.connect();

    // Register event handlers
    realtimeService.on("connected", () => setIsConnected(true));
    realtimeService.on("disconnected", () => setIsConnected(false));
    realtimeService.on("transaction_received", handleTransaction);
    realtimeService.on("geofence_violation", handleGeofenceViolation);

    // Auto-start location tracking on initialization
    const initLocationTracking = async () => {
      try {
        await locationService.startTracking({
          onLocationUpdate: (location) => {
            setCurrentLocation(location);
          },
          onGeofenceViolation: (violation) => {
            setGeofenceViolation(violation);
          },
        });
        setIsLocationTracking(true);
      } catch (error) {
        console.error("Failed to auto-start location tracking:", error);
      }
    };

    initLocationTracking();

    // Cleanup
    return () => {
      realtimeService.off("transaction_received", handleTransaction);
      realtimeService.off("geofence_violation", handleGeofenceViolation);
      locationService.stopTracking().catch(console.error);
    };
  }, []);

  const handleTransaction = useCallback((transaction) => {
    setLastTransaction(transaction);
  }, []);

  const handleGeofenceViolation = useCallback((violation) => {
    setGeofenceViolation(violation);
  }, []);

  // Location tracking is automatic and cannot be controlled by user (security measure)
  // These methods are kept for backward compatibility but should not be called
  const startLocationTracking = useCallback(async () => {
    console.warn(
      "Location tracking is automatically managed and cannot be manually started",
    );
    return Promise.resolve();
  }, []);

  const stopLocationTracking = useCallback(async () => {
    console.warn(
      "Location tracking is automatically managed and cannot be manually stopped",
    );
    return Promise.resolve();
  }, []);

  const getCurrentLocation = useCallback(async () => {
    const location = await locationService.getCurrentLocation();
    setCurrentLocation(location);
    return location;
  }, []);

  return {
    isConnected,
    isLocationTracking,
    lastTransaction,
    geofenceViolation,
    currentLocation,
    startLocationTracking,
    stopLocationTracking,
    getCurrentLocation,
    clearTransaction: () => setLastTransaction(null),
    clearGeofenceViolation: () => setGeofenceViolation(null),
  };
}
