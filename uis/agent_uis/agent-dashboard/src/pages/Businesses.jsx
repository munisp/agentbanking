import {
    Building2,
    CheckCircle2,
    Link2,
    Monitor,
    Search,
    Store as StoreIcon,
    XCircle,
} from "lucide-react";
import React, { useEffect, useState } from "react";
import { businessApi, inventoryApi, posTerminalApi } from "../utils/api";

const Businesses = () => {
  const [businesses, setBusinesses] = useState([]);
  const [stores, setStores] = useState([]);
  const [terminals, setTerminals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const [selectedBusiness, setSelectedBusiness] = useState(null);
  const [showLinkStoreModal, setShowLinkStoreModal] = useState(false);
  const [showLinkTerminalModal, setShowLinkTerminalModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");

  const keycloakId = localStorage.getItem("keycloakId");

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch agent's businesses, stores, and terminals
      const [businessesRes, storesRes, terminalsRes] = await Promise.all([
        businessApi.getAgentBusinesses(keycloakId),
        inventoryApi.getStores(keycloakId),
        posTerminalApi.getTerminals({ assigned_to: keycloakId }),
      ]);

      setBusinesses(businessesRes || []);
      setStores(storesRes || []);
      setTerminals(terminalsRes || []);
    } catch (err) {
      setError(err.message || "Failed to load data");
    } finally {
      setLoading(false);
    }
  };

  const handleLinkStore = async (storeId) => {
    if (!selectedBusiness) return;

    try {
      await businessApi.linkStoreToBusiness(
        storeId,
        selectedBusiness.business_id,
      );
      setSuccess("Store linked to business successfully!");
      setShowLinkStoreModal(false);
      setSelectedBusiness(null);
      fetchData();
      setTimeout(() => setSuccess(null), 5000);
    } catch (err) {
      setError(err.message || "Failed to link store to business");
    }
  };

  const handleLinkTerminal = async (terminalId) => {
    if (!selectedBusiness) return;

    try {
      await businessApi.linkPOSTerminalToBusiness(
        terminalId,
        selectedBusiness.business_id,
      );
      setSuccess("POS terminal linked to business successfully!");
      setShowLinkTerminalModal(false);
      setSelectedBusiness(null);
      fetchData();
      setTimeout(() => setSuccess(null), 5000);
    } catch (err) {
      setError(err.message || "Failed to link terminal to business");
    }
  };

  const filteredBusinesses = businesses.filter((business) =>
    business.business_name.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  const getBusinessStores = (businessId) =>
    stores.filter((s) => s.business_id === businessId);

  const getBusinessTerminals = (businessId) =>
    terminals.filter((t) => t.business_id === businessId);

  const getUnlinkedStores = () => stores.filter((s) => !s.business_id);

  const getUnlinkedTerminals = () => terminals.filter((t) => !t.business_id);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-600">Loading businesses...</div>
      </div>
    );
  }

  const oldBusinesses = [
    // Mock data kept for reference but not used
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Building2 className="h-7 w-7" />
            My Businesses
          </h1>
          <p className="text-gray-600 mt-1">
            Manage verified businesses and link stores &amp; POS terminals
          </p>
        </div>
      </div>

      {/* Alerts */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {error}
        </div>
      )}
      {success && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg">
          {success}
        </div>
      )}

      {/* Search Bar */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
        <input
          type="text"
          placeholder="Search businesses..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
      </div>

      {/* Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Verified Businesses</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">
            {businesses.filter((b) => b.is_verified).length}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Total Stores</p>
          <p className="text-2xl font-bold text-blue-600 mt-1">
            {stores.length}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">POS Terminals</p>
          <p className="text-2xl font-bold text-purple-600 mt-1">
            {terminals.length}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Unlinked Assets</p>
          <p className="text-2xl font-bold text-orange-600 mt-1">
            {getUnlinkedStores().length + getUnlinkedTerminals().length}
          </p>
        </div>
      </div>

      {/* Businesses Grid */}
      {filteredBusinesses.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-lg shadow">
          <Building2 className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600 mb-2">No businesses found.</p>
          <p className="text-sm text-gray-500">
            Contact your admin to link verified businesses to your account.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {filteredBusinesses.map((business) => {
            const businessStores = getBusinessStores(business.business_id);
            const businessTerminals = getBusinessTerminals(
              business.business_id,
            );

            return (
              <div
                key={business.id}
                className="bg-white rounded-lg shadow hover:shadow-lg transition-shadow"
              >
                <div className="p-6">
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex items-center space-x-3">
                      <div className="p-3 bg-blue-100 rounded-lg">
                        <Building2 className="h-6 w-6 text-blue-600" />
                      </div>
                      <div>
                        <h3 className="font-semibold text-gray-900">
                          {business.business_name}
                        </h3>
                        {business.is_verified ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800 mt-1">
                            <CheckCircle2 className="w-3 h-3" />
                            Verified
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-800 mt-1">
                            <XCircle className="w-3 h-3" />
                            Pending
                          </span>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Business Details */}
                  <div className="space-y-2 mb-4">
                    {business.registration_number && (
                      <div className="text-sm text-gray-600">
                        <span className="font-medium">Reg No:</span>{" "}
                        {business.registration_number}
                      </div>
                    )}
                    {business.industry && (
                      <div className="text-sm text-gray-600">
                        <span className="font-medium">Industry:</span>{" "}
                        {business.industry}
                      </div>
                    )}
                    {business.address && (
                      <div className="text-sm text-gray-600">
                        <span className="font-medium">Address:</span>{" "}
                        {business.address}
                      </div>
                    )}
                  </div>

                  {/* Linked Assets */}
                  <div className="border-t pt-4 space-y-3">
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2 text-sm font-medium text-gray-700">
                          <StoreIcon className="w-4 h-4" />
                          Stores ({businessStores.length})
                        </div>
                        <button
                          onClick={() => {
                            setSelectedBusiness(business);
                            setShowLinkStoreModal(true);
                          }}
                          className="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1"
                        >
                          <Link2 className="w-3 h-3" />
                          Link Store
                        </button>
                      </div>
                      {businessStores.length > 0 ? (
                        <ul className="text-sm text-gray-600 space-y-1">
                          {businessStores.map((store) => (
                            <li
                              key={store.id}
                              className="flex items-center gap-2"
                            >
                              <div className="w-1.5 h-1.5 bg-blue-500 rounded-full" />
                              {store.name}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-xs text-gray-500">
                          No stores linked
                        </p>
                      )}
                    </div>

                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2 text-sm font-medium text-gray-700">
                          <Monitor className="w-4 h-4" />
                          POS Terminals ({businessTerminals.length})
                        </div>
                        <button
                          onClick={() => {
                            setSelectedBusiness(business);
                            setShowLinkTerminalModal(true);
                          }}
                          className="text-xs text-blue-600 hover:text-blue-800 flex items-center gap-1"
                        >
                          <Link2 className="w-3 h-3" />
                          Link Terminal
                        </button>
                      </div>
                      {businessTerminals.length > 0 ? (
                        <ul className="text-sm text-gray-600 space-y-1">
                          {businessTerminals.map((terminal) => (
                            <li
                              key={terminal.id}
                              className="flex items-center gap-2"
                            >
                              <div className="w-1.5 h-1.5 bg-purple-500 rounded-full" />
                              {terminal.location} - {terminal.model}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-xs text-gray-500">
                          No terminals linked
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Link Store Modal */}
      {showLinkStoreModal && selectedBusiness && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full">
            <h2 className="text-xl font-bold mb-4">Link Store to Business</h2>
            <p className="text-gray-600 mb-4">
              Select a store to link to{" "}
              <strong>{selectedBusiness.business_name}</strong>:
            </p>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {getUnlinkedStores().length > 0 ? (
                getUnlinkedStores().map((store) => (
                  <button
                    key={store.id}
                    onClick={() => handleLinkStore(store.id)}
                    className="w-full text-left px-4 py-2 border rounded-lg hover:bg-blue-50 hover:border-blue-300 flex items-center gap-3"
                  >
                    <StoreIcon className="w-5 h-5 text-blue-600" />
                    <div>
                      <div className="font-medium">{store.name}</div>
                      {store.description && (
                        <div className="text-sm text-gray-500">
                          {store.description}
                        </div>
                      )}
                    </div>
                  </button>
                ))
              ) : (
                <div className="text-center py-8 text-gray-500">
                  All stores are already linked to a business.
                </div>
              )}
            </div>
            <div className="mt-4 flex justify-end">
              <button
                onClick={() => {
                  setShowLinkStoreModal(false);
                  setSelectedBusiness(null);
                }}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Link Terminal Modal */}
      {showLinkTerminalModal && selectedBusiness && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full">
            <h2 className="text-xl font-bold mb-4">
              Link POS Terminal to Business
            </h2>
            <p className="text-gray-600 mb-4">
              Select a terminal to link to{" "}
              <strong>{selectedBusiness.business_name}</strong>:
            </p>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {getUnlinkedTerminals().length > 0 ? (
                getUnlinkedTerminals().map((terminal) => (
                  <button
                    key={terminal.id}
                    onClick={() => handleLinkTerminal(terminal.id)}
                    className="w-full text-left px-4 py-2 border rounded-lg hover:bg-blue-50 hover:border-blue-300 flex items-center gap-3"
                  >
                    <Monitor className="w-5 h-5 text-purple-600" />
                    <div>
                      <div className="font-medium">{terminal.location}</div>
                      <div className="text-sm text-gray-500">
                        {terminal.model} - {terminal.serial_number}
                      </div>
                    </div>
                  </button>
                ))
              ) : (
                <div className="text-center py-8 text-gray-500">
                  All terminals are already linked to a business.
                </div>
              )}
            </div>
            <div className="mt-4 flex justify-end">
              <button
                onClick={() => {
                  setShowLinkTerminalModal(false);
                  setSelectedBusiness(null);
                }}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Businesses;
