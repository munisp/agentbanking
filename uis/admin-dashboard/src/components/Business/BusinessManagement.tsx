import {
    Building2,
    CheckCircle2,
    Filter,
    Link2,
    Monitor,
    Search,
    Store as StoreIcon,
    Unlink,
    Users,
    XCircle,
} from "lucide-react";
import { useEffect, useState } from "react";
import {
    api,
    type AgentBusiness,
    type AgentRecord,
    type POSTerminal,
    type StoreRecord,
} from "../../utils/api";

export default function BusinessManagement() {
  const [businesses, setBusinesses] = useState<AgentBusiness[]>([]);
  const [agents, setAgents] = useState<AgentRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [selectedBusiness, setSelectedBusiness] =
    useState<AgentBusiness | null>(null);
  const [showLinkModal, setShowLinkModal] = useState(false);
  const [showDetailsModal, setShowDetailsModal] = useState(false);

  const [businessStores, setBusinessStores] = useState<StoreRecord[]>([]);
  const [businessTerminals, setBusinessTerminals] = useState<POSTerminal[]>([]);

  const [searchTerm, setSearchTerm] = useState("");
  const [filterStatus, setFilterStatus] = useState<
    "all" | "verified" | "unverified"
  >("all");
  const [filterAgent, setFilterAgent] = useState<string>("all");

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [businessesRes, agentsRes] = await Promise.all([
        api.getBusinesses(),
        api.getAgents(),
      ]);

      setBusinesses(businessesRes);
      setAgents(agentsRes.agents);
    } catch (err: any) {
      setError(err.message || "Failed to load data");
    } finally {
      setLoading(false);
    }
  };

  const handleLinkToAgent = async (agentKeycloakId: string) => {
    if (!selectedBusiness) return;

    try {
      await api.linkBusinessToAgent({
        agent_keycloak_id: agentKeycloakId,
        business_id: selectedBusiness.business_id,
      });

      setSuccess(`Business linked to agent successfully!`);
      setShowLinkModal(false);
      setSelectedBusiness(null);
      fetchData();
      setTimeout(() => setSuccess(null), 5000);
    } catch (err: any) {
      setError(err.message || "Failed to link business to agent");
    }
  };

  const handleUnlink = async (business: AgentBusiness) => {
    if (!confirm(`Are you sure you want to unlink ${business.business_name}?`))
      return;

    try {
      await api.unlinkBusiness(business.business_id);
      setSuccess(`Business unlinked successfully!`);
      fetchData();
      setTimeout(() => setSuccess(null), 5000);
    } catch (err: any) {
      setError(err.message || "Failed to unlink business");
    }
  };

  const viewBusinessDetails = async (business: AgentBusiness) => {
    setSelectedBusiness(business);
    setShowDetailsModal(true);

    try {
      const [stores, terminals] = await Promise.all([
        api.getBusinessStores(business.business_id),
        api.getBusinessPOSTerminals(business.business_id),
      ]);

      setBusinessStores(stores);
      setBusinessTerminals(terminals);
    } catch (err: any) {
      console.error("Failed to load business details:", err);
    }
  };

  const filteredBusinesses = businesses.filter((business) => {
    const matchesSearch =
      business.business_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      business.business_id.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesStatus =
      filterStatus === "all" ||
      (filterStatus === "verified" && business.is_verified) ||
      (filterStatus === "unverified" && !business.is_verified);

    const matchesAgent =
      filterAgent === "all" ||
      (filterAgent === "unlinked" && !business.agent_keycloak_id) ||
      business.agent_keycloak_id === filterAgent;

    return matchesSearch && matchesStatus && matchesAgent;
  });

  const getAgentName = (keycloakId?: string) => {
    if (!keycloakId) return "Unlinked";
    const agent = agents.find((a) => a.keycloak_id === keycloakId);
    return agent ? `${agent.first_name} ${agent.last_name}` : "Unknown";
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-gray-600">Loading businesses...</div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Building2 className="w-7 h-7" />
            Business Management
          </h1>
          <p className="text-gray-600 mt-1">
            Manage verified businesses and link them to agents
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

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-4 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
            <input
              type="text"
              placeholder="Search businesses..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
            />
          </div>

          <select
            value={filterStatus}
            onChange={(e) => setFilterStatus(e.target.value as any)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
          >
            <option value="all">All Statuses</option>
            <option value="verified">Verified Only</option>
            <option value="unverified">Unverified Only</option>
          </select>

          <select
            value={filterAgent}
            onChange={(e) => setFilterAgent(e.target.value)}
            className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
          >
            <option value="all">All Agents</option>
            <option value="unlinked">Unlinked</option>
            {agents.map((agent) => (
              <option key={agent.keycloak_id} value={agent.keycloak_id}>
                {agent.first_name} {agent.last_name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-gray-600 text-sm">Total Businesses</div>
          <div className="text-2xl font-bold text-gray-900">
            {businesses.length}
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-gray-600 text-sm">Verified</div>
          <div className="text-2xl font-bold text-green-600">
            {businesses.filter((b) => b.is_verified).length}
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-gray-600 text-sm">Linked to Agents</div>
          <div className="text-2xl font-bold text-[var(--tenant-primary-color,#004F71)]">
            {businesses.filter((b) => b.agent_keycloak_id).length}
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="text-gray-600 text-sm">Unlinked</div>
          <div className="text-2xl font-bold text-orange-600">
            {businesses.filter((b) => !b.agent_keycloak_id).length}
          </div>
        </div>
      </div>

      {/* Businesses Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Business
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Registration
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Status
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Linked Agent
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {filteredBusinesses.map((business) => (
              <tr key={business.id} className="hover:bg-gray-50">
                <td className="px-6 py-4">
                  <div className="flex items-center">
                    <Building2 className="w-5 h-5 text-gray-400 mr-3" />
                    <div>
                      <div className="text-sm font-medium text-gray-900">
                        {business.business_name}
                      </div>
                      <div className="text-sm text-gray-500">
                        {business.business_id}
                      </div>
                    </div>
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="text-sm text-gray-900">
                    {business.registration_number || "N/A"}
                  </div>
                  <div className="text-sm text-gray-500">
                    TIN: {business.tin || "N/A"}
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  {business.is_verified ? (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
                      <CheckCircle2 className="w-3 h-3" />
                      Verified
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                      <XCircle className="w-3 h-3" />
                      Unverified
                    </span>
                  )}
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="text-sm text-gray-900">
                    {getAgentName(business.agent_keycloak_id)}
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-sm space-x-2">
                  <button
                    onClick={() => viewBusinessDetails(business)}
                    className="text-[var(--tenant-primary-color,#004F71)] hover:text-[color-mix(in srgb, var(--tenant-primary-color,#002082) 40%, black)]"
                  >
                    View
                  </button>
                  {business.is_verified && !business.agent_keycloak_id && (
                    <button
                      onClick={() => {
                        setSelectedBusiness(business);
                        setShowLinkModal(true);
                      }}
                      className="text-green-600 hover:text-green-800"
                    >
                      Link to Agent
                    </button>
                  )}
                  {business.agent_keycloak_id && (
                    <button
                      onClick={() => handleUnlink(business)}
                      className="text-red-600 hover:text-red-800"
                    >
                      Unlink
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Link Modal */}
      {showLinkModal && selectedBusiness && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-md w-full">
            <h2 className="text-xl font-bold mb-4">Link Business to Agent</h2>
            <p className="text-gray-600 mb-4">
              Select an agent to link{" "}
              <strong>{selectedBusiness.business_name}</strong> to:
            </p>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {agents.map((agent) => (
                <button
                  key={agent.keycloak_id}
                  onClick={() => handleLinkToAgent(agent.keycloak_id)}
                  className="w-full text-left px-4 py-2 border rounded-lg hover:bg-[rgba(0,79,113,0.05)] hover:border-[rgba(0,79,113,0.3)]"
                >
                  <div className="font-medium">
                    {agent.first_name} {agent.last_name}
                  </div>
                  <div className="text-sm text-gray-500">{agent.email}</div>
                </button>
              ))}
            </div>
            <div className="mt-4 flex justify-end">
              <button
                onClick={() => {
                  setShowLinkModal(false);
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

      {/* Details Modal */}
      {showDetailsModal && selectedBusiness && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-2xl w-full max-h-[80vh] overflow-y-auto">
            <h2 className="text-xl font-bold mb-4">
              {selectedBusiness.business_name}
            </h2>

            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="text-sm text-gray-600">Business ID</div>
                  <div className="font-medium">
                    {selectedBusiness.business_id}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-600">
                    Registration Number
                  </div>
                  <div className="font-medium">
                    {selectedBusiness.registration_number || "N/A"}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-600">TIN</div>
                  <div className="font-medium">
                    {selectedBusiness.tin || "N/A"}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-600">Business Type</div>
                  <div className="font-medium">
                    {selectedBusiness.business_type || "N/A"}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-600">Industry</div>
                  <div className="font-medium">
                    {selectedBusiness.industry || "N/A"}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-600">Country</div>
                  <div className="font-medium">
                    {selectedBusiness.country || "N/A"}
                  </div>
                </div>
              </div>

              <div>
                <div className="text-sm text-gray-600">Address</div>
                <div className="font-medium">
                  {selectedBusiness.address || "N/A"}
                </div>
              </div>

              <div className="border-t pt-4">
                <h3 className="font-bold mb-2 flex items-center gap-2">
                  <StoreIcon className="w-4 h-4" />
                  Stores ({businessStores.length})
                </h3>
                {businessStores.length > 0 ? (
                  <ul className="list-disc list-inside">
                    {businessStores.map((store) => (
                      <li key={store.id}>{store.name}</li>
                    ))}
                  </ul>
                ) : (
                  <div className="text-gray-500">No stores linked</div>
                )}
              </div>

              <div className="border-t pt-4">
                <h3 className="font-bold mb-2 flex items-center gap-2">
                  <Monitor className="w-4 h-4" />
                  POS Terminals ({businessTerminals.length})
                </h3>
                {businessTerminals.length > 0 ? (
                  <ul className="list-disc list-inside">
                    {businessTerminals.map((terminal) => (
                      <li key={terminal.id}>
                        {terminal.location} - {terminal.model}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <div className="text-gray-500">No POS terminals linked</div>
                )}
              </div>
            </div>

            <div className="mt-6 flex justify-end">
              <button
                onClick={() => {
                  setShowDetailsModal(false);
                  setSelectedBusiness(null);
                }}
                className="px-4 py-2 bg-gray-200 text-gray-700 hover:bg-gray-300 rounded-lg"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
