import * as Location from "expo-location";
import { useEffect, useState } from "react";

export function useLocationTrackingStatus() {
  const [status, setStatus] = useState({
    isActive: false,
    permissionStatus: "undetermined", // undetermined, granted, denied
    error: null,
  });

  useEffect(() => {
    const checkPermissions = async () => {
      try {
        const { status: permStatus } =
          await Location.getForegroundPermissionsAsync();

        if (permStatus === "granted") {
          setStatus({
            isActive: true,
            permissionStatus: "granted",
            error: null,
          });
        } else if (permStatus === "denied") {
          setStatus({
            isActive: false,
            permissionStatus: "denied",
            error: "Location permission denied",
          });
        } else {
          setStatus({
            isActive: false,
            permissionStatus: "undetermined",
            error: "Permission not requested yet",
          });
        }
      } catch (error) {
        setStatus({
          isActive: false,
          permissionStatus: "undetermined",
          error: error.message,
        });
      }
    };

    checkPermissions();
  }, []);

  return status;
}
