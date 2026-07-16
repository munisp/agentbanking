import { MapPin } from "lucide-react";
import React from "react";

export default function LocationTrackingIndicator({ status }) {
  if (!status) return null;

  const getStatusColor = () => {
    if (status.permissionStatus === "granted" && status.isActive) {
      return "bg-green-100 text-green-800 border-green-300";
    }
    if (status.permissionStatus === "denied") {
      return "bg-red-100 text-red-800 border-red-300";
    }
    return "bg-gray-100 text-gray-800 border-gray-300";
  };

  const getStatusText = () => {
    if (status.error) return `Location: ${status.error}`;
    if (status.permissionStatus === "granted" && status.isActive) {
      return "Location tracking active";
    }
    if (status.permissionStatus === "denied") {
      return "Location permission denied";
    }
    return "Location tracking inactive";
  };

  const getDot = () => {
    if (status.permissionStatus === "granted" && status.isActive) {
      return (
        <span className="inline-block w-2 h-2 bg-green-600 rounded-full mr-2"></span>
      );
    }
    if (status.permissionStatus === "denied") {
      return (
        <span className="inline-block w-2 h-2 bg-red-600 rounded-full mr-2"></span>
      );
    }
    return (
      <span className="inline-block w-2 h-2 bg-gray-500 rounded-full mr-2"></span>
    );
  };

  return (
    <div
      className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border text-xs font-medium transition-all ${getStatusColor()}`}
      title={getStatusText()}
    >
      {getDot()}
      <MapPin className="w-3 h-3" />
      <span className="hidden sm:inline">{getStatusText()}</span>
    </div>
  );
}
