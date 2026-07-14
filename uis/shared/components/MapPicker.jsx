import { Icon } from "leaflet";
import "leaflet/dist/leaflet.css";
import { Loader, MapPin } from "lucide-react";
import React, { useEffect, useState } from "react";
import {
    MapContainer,
    Marker,
    Popup,
    TileLayer,
    useMapEvents,
} from "react-leaflet";

// Fix for default marker icon
const defaultIcon = new Icon({
  iconUrl:
    "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowUrl:
    "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
  shadowSize: [41, 41],
});

// Custom hook to handle map clicks
function MapClickHandler({ onLocationSelect }) {
  useMapEvents({
    click(e) {
      const { lat, lng } = e.latlng;
      onLocationSelect({ latitude: lat, longitude: lng });
    },
  });
  return null;
}

/**
 * MapPicker Component
 * A reusable map component for picking store locations
 *
 * Props:
 *   - latitude: Current latitude (null or number)
 *   - longitude: Current longitude (null or number)
 *   - onLocationSelect: Callback function(lat, lng)
 *   - title: Title for the map section
 *   - height: Height of the map container (default: "400px")
 *   - searchable: Show search input for location (default: false)
 */
export const MapPicker = ({
  latitude = null,
  longitude = null,
  onLocationSelect,
  title = "Select Store Location",
  height = "400px",
  searchable = false,
}) => {
  const [mapCenter, setMapCenter] = useState(
    latitude && longitude ? [latitude, longitude] : [6.5244, 3.3792], // Default to Lagos
  );
  const [selectedLocation, setSelectedLocation] = useState(
    latitude && longitude ? { latitude, longitude } : null,
  );
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);

  const handleLocationSelect = (location) => {
    setSelectedLocation(location);
    setMapCenter([location.latitude, location.longitude]);
    if (onLocationSelect) {
      onLocationSelect(location.latitude, location.longitude);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;

    setIsSearching(true);
    try {
      // Using OpenStreetMap's nominatim API for geocoding
      const response = await fetch(
        `https://nominatim.openstreetmap.org/search?q=${encodeURIComponent(
          searchQuery + ", Nigeria",
        )}&format=json&limit=1`,
      );
      const data = await response.json();

      if (data && data.length > 0) {
        const { lat, lon } = data[0];
        handleLocationSelect({
          latitude: parseFloat(lat),
          longitude: parseFloat(lon),
        });
      } else {
        alert("Location not found. Please try a different search.");
      }
    } catch (error) {
      console.error("Error searching location:", error);
      alert("Error searching location. Please try again.");
    } finally {
      setIsSearching(false);
    }
  };

  const handleUseCurrentLocation = () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const { latitude, longitude } = position.coords;
          handleLocationSelect({ latitude, longitude });
        },
        (error) => {
          console.error("Geolocation error:", error);
          alert(
            "Unable to get your location. Please enable location services.",
          );
        },
      );
    } else {
      alert("Geolocation is not supported by your browser.");
    }
  };

  return (
    <div className="w-full">
      {/* Title */}
      <div className="mb-4">
        <h3 className="text-lg font-semibold text-gray-900 mb-2 flex items-center gap-2">
          <MapPin size={20} />
          {title}
        </h3>
        <p className="text-sm text-gray-600">
          Click on the map to select a location, or search for a location below.
        </p>
      </div>

      {/* Search Section */}
      {searchable && (
        <div className="mb-4 flex gap-2">
          <div className="flex-1 flex gap-2">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === "Enter" && handleSearch()}
              placeholder="Search location (address, city, street name...)"
              className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={handleSearch}
              disabled={isSearching}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 transition flex items-center gap-2"
            >
              {isSearching ? (
                <Loader size={18} className="animate-spin" />
              ) : null}
              Search
            </button>
          </div>
          <button
            onClick={handleUseCurrentLocation}
            className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition"
            title="Use your current location"
          >
            📍
          </button>
        </div>
      )}

      {/* Map Container */}
      <div
        className="rounded-lg border border-gray-300 overflow-hidden bg-gray-50"
        style={{ height }}
      >
        <MapContainer
          center={mapCenter}
          zoom={13}
          style={{ height: "100%", width: "100%" }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          {selectedLocation && (
            <Marker
              position={[selectedLocation.latitude, selectedLocation.longitude]}
              icon={defaultIcon}
            >
              <Popup>
                <div className="text-sm">
                  <p className="font-semibold">Selected Location</p>
                  <p>Latitude: {selectedLocation.latitude.toFixed(6)}</p>
                  <p>Longitude: {selectedLocation.longitude.toFixed(6)}</p>
                </div>
              </Popup>
            </Marker>
          )}

          <MapClickHandler onLocationSelect={handleLocationSelect} />
        </MapContainer>
      </div>

      {/* Coordinates Display */}
      {selectedLocation && (
        <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Latitude
              </label>
              <p className="font-mono text-sm font-semibold text-blue-700">
                {selectedLocation.latitude.toFixed(6)}
              </p>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">
                Longitude
              </label>
              <p className="font-mono text-sm font-semibold text-blue-700">
                {selectedLocation.longitude.toFixed(6)}
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MapPicker;
