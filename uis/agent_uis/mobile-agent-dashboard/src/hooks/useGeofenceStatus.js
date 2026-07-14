/**
 * Hook for tracking geofence status
 * Returns the current geofence status: in-zone, warning, or out-of-zone
 */

import * as Location from "expo-location";
import * as SecureStore from "expo-secure-store";
import { useEffect, useState } from "react";

/**
 * Geofence status levels:
 * - "in-zone": User is well within the geofence (green)
 * - "warning": User is approaching the boundary (yellow)
 * - "out-of-zone": User is outside the geofence (red)
 * - "unknown": No geofence configured or unable to determine
 */

export function useGeofenceStatus() {
  const [status, setStatus] = useState("unknown");
  const [distance, setDistance] = useState(null);
  const [geofenceRadius, setGeofenceRadius] = useState(null);
  const [centerLocation, setCenterLocation] = useState(null);
  const [isTracking, setIsTracking] = useState(false);

  useEffect(() => {
    let locationSubscription = null;
    let mounted = true;

    const initializeTracking = async () => {
      try {
        // Get geofence configuration from secure store
        const centerLat = await SecureStore.getItemAsync("geofence_center_lat");
        const centerLon = await SecureStore.getItemAsync("geofence_center_lon");
        const radius = await SecureStore.getItemAsync("geofence_radius_km");

        if (!centerLat || !centerLon || !radius) {
          console.log("No geofence configured");
          setStatus("unknown");
          return;
        }

        setCenterLocation({
          latitude: parseFloat(centerLat),
          longitude: parseFloat(centerLon),
        });
        setGeofenceRadius(parseFloat(radius));

        // Request location permissions
        const { status: foregroundStatus } =
          await Location.requestForegroundPermissionsAsync();

        if (foregroundStatus !== "granted") {
          console.warn("Location permission not granted");
          setStatus("unknown");
          return;
        }

        // Start watching location
        setIsTracking(true);
        locationSubscription = await Location.watchPositionAsync(
          {
            accuracy: Location.Accuracy.Balanced,
            timeInterval: 10000, // Update every 10 seconds
            distanceInterval: 20, // Or when moved 20 meters
          },
          (location) => {
            if (!mounted) return;

            const currentLat = location.coords.latitude;
            const currentLon = location.coords.longitude;

            // Calculate distance from center
            const distanceFromCenter = calculateDistance(
              parseFloat(centerLat),
              parseFloat(centerLon),
              currentLat,
              currentLon,
            );

            setDistance(distanceFromCenter);

            // Determine status based on distance
            const radiusKm = parseFloat(radius);
            const warningThreshold = radiusKm * 0.8; // Warning when within 80% of radius

            if (distanceFromCenter <= warningThreshold) {
              setStatus("in-zone");
            } else if (distanceFromCenter <= radiusKm) {
              setStatus("warning");
            } else {
              setStatus("out-of-zone");
            }
          },
        );
      } catch (error) {
        console.error("Error initializing geofence tracking:", error);
        setStatus("unknown");
      }
    };

    initializeTracking();

    return () => {
      mounted = false;
      if (locationSubscription) {
        locationSubscription.remove();
      }
      setIsTracking(false);
    };
  }, []);

  return {
    status,
    distance,
    geofenceRadius,
    centerLocation,
    isTracking,
  };
}

/**
 * Calculate distance between two coordinates (in km)
 * Using Haversine formula
 */
function calculateDistance(lat1, lon1, lat2, lon2) {
  const R = 6371; // Radius of Earth in km
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(toRad(lat1)) *
      Math.cos(toRad(lat2)) *
      Math.sin(dLon / 2) *
      Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

function toRad(degrees) {
  return degrees * (Math.PI / 180);
}
