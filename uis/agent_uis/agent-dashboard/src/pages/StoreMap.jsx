import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Loader2, Mail, MapPin, Navigation, Phone, Store } from "lucide-react";
import React, { useEffect, useState } from "react";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import { storeMapApi } from "../utils/api";

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

const StoreMap = () => {
  const [stores, setStores] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [userLocation, setUserLocation] = useState(null);

  useEffect(() => {
    loadStores();
    getUserLocation();
  }, []);

  const loadStores = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await storeMapApi.getAllStores();
      setStores(Array.isArray(data) ? data : []);
    } catch (err) {
      setError(err.message || "Failed to load stores");
    } finally {
      setLoading(false);
    }
  };

  const getUserLocation = () => {
    if ("geolocation" in navigator) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setUserLocation({
            lat: pos.coords.latitude,
            lng: pos.coords.longitude,
          });
        },
        (error) => {
          console.warn("Unable to get user location:", error);
        },
      );
    }
  };

  // Default center (Lagos, Nigeria)
  const defaultCenter = { lat: 6.5244, lng: 3.3792 };
  const center = userLocation || defaultCenter;

  const getStatusColor = (status) => {
    switch (status) {
      case "OPEN":
        return "text-green-600";
      case "CLOSED":
        return "text-red-600";
      case "TEMPORARILY_CLOSED":
        return "text-yellow-600";
      case "SUSPENDED":
        return "text-gray-600";
      default:
        return "text-gray-600";
    }
  };

  const getStoreTypeLabel = (type) => {
    const labels = {
      AGENT: "Agent",
      MERCHANT: "Merchant",
      SUPER_AGENT: "Super Agent",
      AGGREGATOR: "Aggregator",
      POS_TERMINAL: "POS Terminal",
      ATM: "ATM",
      BANK_BRANCH: "Bank Branch",
    };
    return labels[type] || type;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2
            size={48}
            className="animate-spin mx-auto mb-4"
            style={{ color: "var(--tenant-primary-color,#002082)" }}
          />
          <p className="text-gray-600">Loading stores...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 max-w-md">
          <p className="text-red-700">{error}</p>
          <button
            onClick={loadStores}
            className="mt-4 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto p-6">
        {/* Header */}
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
            <MapPin style={{ color: "var(--tenant-primary-color,#002082)" }} />
            Store Locations
          </h1>
          <p className="text-gray-600 mt-1">
            View all registered stores and their locations
          </p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center gap-3">
              <div
                className="p-3 rounded-lg"
                style={{ backgroundColor: "rgba(0,79,113,0.1)" }}
              >
                <Store style={{ color: "var(--tenant-primary-color,#002082)" }} size={24} />
              </div>
              <div>
                <p className="text-sm text-gray-600">Total Stores</p>
                <p className="text-2xl font-bold text-gray-900">
                  {stores.length}
                </p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-green-100 rounded-lg">
                <Store className="text-green-600" size={24} />
              </div>
              <div>
                <p className="text-sm text-gray-600">Open Now</p>
                <p className="text-2xl font-bold text-gray-900">
                  {stores.filter((s) => s.status === "OPEN").length}
                </p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-purple-100 rounded-lg">
                <Store className="text-purple-600" size={24} />
              </div>
              <div>
                <p className="text-sm text-gray-600">Merchants</p>
                <p className="text-2xl font-bold text-gray-900">
                  {stores.filter((s) => s.store_type === "MERCHANT").length}
                </p>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center gap-3">
              <div className="p-3 bg-orange-100 rounded-lg">
                <Store className="text-orange-600" size={24} />
              </div>
              <div>
                <p className="text-sm text-gray-600">Agents</p>
                <p className="text-2xl font-bold text-gray-900">
                  {stores.filter((s) => s.store_type === "AGENT").length}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Map */}
        <div className="bg-white rounded-lg shadow-md overflow-hidden">
          <div className="h-[600px]">
            {stores.length === 0 ? (
              <div className="h-full flex items-center justify-center bg-gray-50">
                <div className="text-center">
                  <MapPin size={48} className="mx-auto text-gray-400 mb-4" />
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">
                    No Stores Yet
                  </h3>
                  <p className="text-gray-600">
                    Register businesses with locations to see them on the map
                  </p>
                </div>
              </div>
            ) : (
              <MapContainer
                center={[center.lat, center.lng]}
                zoom={12}
                style={{ height: "100%", width: "100%" }}
              >
                <TileLayer
                  attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />

                {/* User location marker (blue) */}
                {userLocation && (
                  <Marker
                    position={[userLocation.lat, userLocation.lng]}
                    icon={L.divIcon({
                      className: "custom-icon",
                      html: `<div style="background-color: var(--tenant-primary-color,#002082); width: 16px; height: 16px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 4px rgba(0,0,0,0.3);"></div>`,
                      iconSize: [22, 22],
                      iconAnchor: [11, 11],
                    })}
                  >
                    <Popup>
                      <div className="text-sm">
                        <p className="font-semibold">Your Location</p>
                      </div>
                    </Popup>
                  </Marker>
                )}

                {/* Store markers */}
                {stores.map((store) => (
                  <Marker
                    key={store.id}
                    position={[
                      parseFloat(store.latitude),
                      parseFloat(store.longitude),
                    ]}
                  >
                    <Popup maxWidth={300}>
                      <div className="p-2">
                        <h3 className="font-bold text-lg mb-2">
                          {store.entity_name}
                        </h3>

                        <div className="space-y-1 mb-3">
                          <div className="flex items-center gap-2 text-sm">
                            <Store size={14} className="text-gray-500" />
                            <span className="text-gray-700">
                              {getStoreTypeLabel(store.store_type)}
                            </span>
                          </div>

                          {store.address && (
                            <div className="flex items-start gap-2 text-sm">
                              <MapPin
                                size={14}
                                className="text-gray-500 mt-0.5"
                              />
                              <span className="text-gray-700">
                                {store.address}
                              </span>
                            </div>
                          )}

                          {store.phone && (
                            <div className="flex items-center gap-2 text-sm">
                              <Phone size={14} className="text-gray-500" />
                              <a
                                href={`tel:${store.phone}`}
                                className="hover:underline"
                                style={{ color: "var(--tenant-primary-color,#002082)" }}
                              >
                                {store.phone}
                              </a>
                            </div>
                          )}

                          {store.email && (
                            <div className="flex items-center gap-2 text-sm">
                              <Mail size={14} className="text-gray-500" />
                              <a
                                href={`mailto:${store.email}`}
                                className="hover:underline"
                                style={{ color: "var(--tenant-primary-color,#002082)" }}
                              >
                                {store.email}
                              </a>
                            </div>
                          )}
                        </div>

                        <div className="flex items-center justify-between pt-2 border-t">
                          <span
                            className={`text-sm font-medium ${getStatusColor(store.status)}`}
                          >
                            {store.status?.replace("_", " ")}
                          </span>

                          <a
                            href={`https://www.google.com/maps/dir/?api=1&destination=${store.latitude},${store.longitude}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-1 text-sm hover:underline"
                            style={{ color: "var(--tenant-primary-color,#002082)" }}
                          >
                            <Navigation size={14} />
                            Directions
                          </a>
                        </div>
                      </div>
                    </Popup>
                  </Marker>
                ))}
              </MapContainer>
            )}
          </div>
        </div>

        {/* Store List */}
        {stores.length > 0 && (
          <div className="mt-6 bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-bold text-gray-900 mb-4">
              Store Directory
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {stores.map((store) => (
                <div
                  key={store.id}
                  className="border border-gray-200 rounded-lg p-4 hover:border-blue-500 transition"
                >
                  <h3 className="font-semibold text-gray-900 mb-1">
                    {store.entity_name}
                  </h3>
                  <p className="text-sm text-gray-600 mb-2">
                    {getStoreTypeLabel(store.store_type)}
                  </p>
                  {store.address && (
                    <p className="text-sm text-gray-700 mb-2">
                      {store.address}
                    </p>
                  )}
                  <div className="flex items-center justify-between">
                    <span
                      className={`text-xs font-medium ${getStatusColor(store.status)}`}
                    >
                      {store.status?.replace("_", " ")}
                    </span>
                    <a
                      href={`https://www.google.com/maps/dir/?api=1&destination=${store.latitude},${store.longitude}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs hover:underline flex items-center gap-1"
                      style={{ color: "var(--tenant-primary-color,#002082)" }}
                    >
                      <Navigation size={12} />
                      Get Directions
                    </a>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default StoreMap;
