import L from "leaflet";
import "leaflet/dist/leaflet.css";
import {
    Loader2,
    Mail,
    MapPin,
    MessageCircle,
    Navigation,
    Phone,
    Search,
    Store,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { MapContainer, Marker, Popup, TileLayer } from "react-leaflet";
import { useNavigate } from "react-router-dom";
import { messagingApi, storeMapApi } from "../utils/api";

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
  const navigate = useNavigate();
  const [stores, setStores] = useState([]);
  const [filteredStores, setFilteredStores] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [userLocation, setUserLocation] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState("all");
  const [messagingStore, setMessagingStore] = useState(null);

  useEffect(() => {
    loadStores();
    getUserLocation();
  }, []);

  useEffect(() => {
    applyFilters();
  }, [stores, searchQuery, filterType]);

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

  const applyFilters = () => {
    let filtered = [...stores];

    // Filter by type
    if (filterType !== "all") {
      filtered = filtered.filter((store) => store.store_type === filterType);
    }

    // Filter by search query
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (store) =>
          store.entity_name?.toLowerCase().includes(query) ||
          store.address?.toLowerCase().includes(query) ||
          store.area?.toLowerCase().includes(query) ||
          store.lga?.toLowerCase().includes(query) ||
          store.state?.toLowerCase().includes(query),
      );
    }

    setFilteredStores(filtered);
  };

  const findNearbyStores = async () => {
    if (!userLocation) {
      alert("Please enable location to find nearby stores");
      return;
    }

    setLoading(true);
    try {
      const data = await storeMapApi.findNearbyStores(
        userLocation.lat,
        userLocation.lng,
        10, // 10km radius
      );
      setStores(Array.isArray(data?.stores) ? data.stores : []);
    } catch (err) {
      setError(err.message || "Failed to find nearby stores");
    } finally {
      setLoading(false);
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

  const handleMessageStore = async (store) => {
    setMessagingStore(store.entity_id);
    try {
      const conversation = await messagingApi.createConversation(
        store.entity_id,
        store.entity_name,
      );
      navigate("/communication", {
        state: { conversationId: conversation.id },
      });
    } catch (err) {
      console.error("Failed to start conversation:", err);
      alert("Failed to start conversation. Please try again.");
    } finally {
      setMessagingStore(null);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2
            size={48}
            className="animate-spin mx-auto text-blue-600 mb-4"
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
            <MapPin className="text-blue-600" />
            Find Stores Near You
          </h1>
          <p className="text-gray-600 mt-1">
            Discover agents and merchants in your area
          </p>
        </div>

        {/* Search & Filters */}
        <div className="bg-white rounded-lg shadow-md p-4 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="md:col-span-1">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Search
              </label>
              <div className="relative">
                <Search
                  className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400"
                  size={20}
                />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search by name or location..."
                  className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            </div>

            <div className="md:col-span-1">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Store Type
              </label>
              <select
                value={filterType}
                onChange={(e) => setFilterType(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="all">All Types</option>
                <option value="AGENT">Agents</option>
                <option value="MERCHANT">Merchants</option>
                <option value="SUPER_AGENT">Super Agents</option>
                <option value="ATM">ATMs</option>
                <option value="BANK_BRANCH">Bank Branches</option>
              </select>
            </div>

            <div className="md:col-span-1 flex items-end">
              <button
                onClick={findNearbyStores}
                disabled={!userLocation}
                className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 transition flex items-center justify-center gap-2"
              >
                <Navigation size={20} />
                Find Nearby
              </button>
            </div>
          </div>

          <div className="mt-3 text-sm text-gray-600">
            Showing {filteredStores.length} of {stores.length} stores
          </div>
        </div>

        {/* Map */}
        <div className="bg-white rounded-lg shadow-md overflow-hidden mb-6">
          <div className="h-[500px]">
            {filteredStores.length === 0 ? (
              <div className="h-full flex items-center justify-center bg-gray-50">
                <div className="text-center">
                  <MapPin size={48} className="mx-auto text-gray-400 mb-4" />
                  <h3 className="text-lg font-semibold text-gray-900 mb-2">
                    No Stores Found
                  </h3>
                  <p className="text-gray-600">
                    {searchQuery || filterType !== "all"
                      ? "Try adjusting your search or filters"
                      : "No stores available at the moment"}
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

                {/* User location marker (primary brand color) */}
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
                {filteredStores.map((store) => (
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
                                className="text-blue-600 hover:underline"
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
                                className="text-blue-600 hover:underline"
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
                            className="flex items-center gap-1 text-sm text-blue-600 hover:underline"
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

        {/* Store Cards */}
        {filteredStores.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredStores.map((store) => (
              <div
                key={store.id}
                className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-lg transition"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1">
                    <h3 className="font-bold text-gray-900 mb-1">
                      {store.entity_name}
                    </h3>
                    <p className="text-sm text-gray-600">
                      {getStoreTypeLabel(store.store_type)}
                    </p>
                  </div>
                  <span
                    className={`text-xs font-medium ${getStatusColor(store.status)}`}
                  >
                    {store.status?.replace("_", " ")}
                  </span>
                </div>

                {store.address && (
                  <div className="flex items-start gap-2 text-sm text-gray-700 mb-2">
                    <MapPin
                      size={14}
                      className="text-gray-500 mt-0.5 flex-shrink-0"
                    />
                    <span>{store.address}</span>
                  </div>
                )}

                <div className="space-y-1 mb-3">
                  {store.phone && (
                    <div className="flex items-center gap-2 text-sm">
                      <Phone size={14} className="text-gray-500" />
                      <a
                        href={`tel:${store.phone}`}
                        className="text-blue-600 hover:underline"
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
                        className="text-blue-600 hover:underline truncate"
                      >
                        {store.email}
                      </a>
                    </div>
                  )}
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={() => handleMessageStore(store)}
                    disabled={messagingStore === store.entity_id}
                    className="flex items-center justify-center gap-2 flex-1 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 transition text-sm"
                  >
                    <MessageCircle size={16} />
                    {messagingStore === store.entity_id
                      ? "Opening..."
                      : "Message"}
                  </button>

                  <a
                    href={`https://www.google.com/maps/dir/?api=1&destination=${store.latitude},${store.longitude}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center justify-center gap-2 flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-sm"
                  >
                    <Navigation size={16} />
                    Directions
                  </a>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default StoreMap;
