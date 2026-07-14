import L from "leaflet";
import { MapPin } from "lucide-react";
import React, { useEffect, useRef } from "react";
import {
    MapContainer,
    Marker,
    TileLayer,
    useMap,
    useMapEvents,
} from "react-leaflet";

// Fix for default marker icons in React-Leaflet
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl:
    "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png",
  iconUrl:
    "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png",
  shadowUrl:
    "https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png",
});

// Flies the map to a new position whenever it changes (e.g. after geocoding)
function FlyToLocation({ position }) {
  const map = useMap();
  const prevPos = useRef(null);
  useEffect(() => {
    if (!position) return;
    const prev = prevPos.current;
    // Only fly if position actually changed (prevents flying on every render)
    if (!prev || prev.lat !== position.lat || prev.lng !== position.lng) {
      map.flyTo([position.lat, position.lng], Math.max(map.getZoom(), 15), {
        duration: 1.2,
      });
      prevPos.current = position;
    }
  }, [position, map]);
  return null;
}

// Component to handle map clicks — calls onPick directly, no internal state
function LocationMarker({ position, onPick }) {
  const map = useMapEvents({
    click(e) {
      map.flyTo(e.latlng, map.getZoom());
      onPick(e.latlng.lat, e.latlng.lng);
    },
  });

  return position === null ? null : <Marker position={position} />;
}

/**
 * MapPicker
 * Fully controlled component — position is derived from (latitude, longitude) props.
 * onLocationChange(lat, lng) is called only on user interaction (click or geolocation),
 * never in response to prop changes, so there is no feedback loop.
 */
const MapPicker = ({
  latitude,
  longitude,
  onLocationChange,
  className = "",
}) => {
  const parsedLat = parseFloat(latitude);
  const parsedLng = parseFloat(longitude);
  const position =
    !isNaN(parsedLat) && !isNaN(parsedLng)
      ? { lat: parsedLat, lng: parsedLng }
      : null;

  const defaultCenter = { lat: 6.5244, lng: 3.3792 }; // Lagos
  const center = position || defaultCenter;

  const getCurrentLocation = () => {
    if (!("geolocation" in navigator)) {
      alert("Geolocation is not supported by your browser");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => onLocationChange(pos.coords.latitude, pos.coords.longitude),
      () =>
        alert("Unable to get your location. Please click on the map instead."),
    );
  };

  return (
    <div className={className}>
      <div className="mb-2 flex items-center justify-end">
        <button
          type="button"
          onClick={getCurrentLocation}
          className="flex items-center gap-1 px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
        >
          <MapPin size={16} />
          Use My Location
        </button>
      </div>

      <div className="rounded-lg overflow-hidden border border-gray-300 shadow-sm">
        <MapContainer
          center={[center.lat, center.lng]}
          zoom={13}
          style={{ height: "300px", width: "100%" }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <FlyToLocation position={position} />
          <LocationMarker position={position} onPick={onLocationChange} />
        </MapContainer>
      </div>

      <p className="mt-2 text-xs text-gray-500">
        {position
          ? `Pinned at ${position.lat.toFixed(6)}, ${position.lng.toFixed(6)}`
          : 'Click the map or press "Use My Location" to pin your store'}
      </p>
    </div>
  );
};

export default MapPicker;
