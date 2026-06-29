import { Network, RefreshCw, Shield, ShieldOff, AlertCircle, CheckCircle } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_PLATFORM_MGMT_URL || import.meta.env.VITE_API_URL || "http://localhost:8010";

interface ServiceNode {
  id: string;
  name: string;
  replicas: number;
  requestsPerMin: number;
  errorRate: number;
  p99LatencyMs: number;
  mtlsEnabled: boolean;
}

interface CircuitBreakerEntry {
  source: string;
  destination: string;
  state: "closed" | "open" | "half-open";
  failureRate: number;
  lastTripped: string;
}

const MOCK_SERVICES: ServiceNode[] = [
  { id: "svc-01", name: "payment-svc", replicas: 3, requestsPerMin: 8420, errorRate: 0.3, p99LatencyMs: 142, mtlsEnabled: true },
  { id: "svc-02", name: "auth-svc", replicas: 2, requestsPerMin: 15200, errorRate: 0.1, p99LatencyMs: 38, mtlsEnabled: true },
  { id: "svc-03", name: "ledger-svc", replicas: 4, requestsPerMin: 6310, errorRate: 0.6, p99LatencyMs: 215, mtlsEnabled: true },
  { id: "svc-04", name: "agent-svc", replicas: 3, requestsPerMin: 4900, errorRate: 1.2, p99LatencyMs: 88, mtlsEnabled: false },
  { id: "svc-05", name: "notification-svc", replicas: 2, requestsPerMin: 3100, errorRate: 0.2, p99LatencyMs: 55, mtlsEnabled: true },
  { id: "svc-06", name: "kyc-svc", replicas: 2, requestsPerMin: 1200, errorRate: 0.8, p99LatencyMs: 330, mtlsEnabled: false },
];

const MOCK_CIRCUIT_BREAKERS: CircuitBreakerEntry[] = [
  { source: "payment-svc", destination: "ledger-svc", state: "closed", failureRate: 0.6, lastTripped: "2025-04-29 11:22" },
  { source: "agent-svc", destination: "payment-svc", state: "half-open", failureRate: 4.2, lastTripped: "2025-05-01 08:14" },
  { source: "auth-svc", destination: "kyc-svc", state: "open", failureRate: 12.5, lastTripped: "2025-05-02 07:05" },
  { source: "notification-svc", destination: "auth-svc", state: "closed", failureRate: 0.1, lastTripped: "2025-04-20 15:00" },
];

const CB_STYLES: Record<string, string> = {
  closed: "bg-green-100 text-green-700",
  "half-open": "bg-amber-100 text-amber-700",
  open: "bg-red-100 text-red-700",
};

const ServiceMeshDashboard: React.FC = () => {
  const [services, setServices] = useState<ServiceNode[]>([]);
  const [breakers, setBreakers] = useState<CircuitBreakerEntry[]>([]);
  const [loading, setLoading] = useState(false);

  

  useEffect(() => { fetchMeshData(); }, []);

  const fetchMeshData = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/ops/api/v1/mesh/services`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) {
        const d = await res.json();
        setServices(Array.isArray(d.services) ? d.services : MOCK_SERVICES);
        setBreakers(Array.isArray(d.circuitBreakers) ? d.circuitBreakers : MOCK_CIRCUIT_BREAKERS);
      } else { setServices(MOCK_SERVICES); setBreakers(MOCK_CIRCUIT_BREAKERS); }
    } catch { setServices(MOCK_SERVICES); setBreakers(MOCK_CIRCUIT_BREAKERS); }
    finally { setLoading(false); }
  };

  const totalCallsPerMin = services.reduce((acc, s) => acc + s.requestsPerMin, 0);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Network className="w-7 h-7 text-blue-600" /> Service Mesh Dashboard
          </h1>
          <p className="text-gray-500 text-sm mt-1">Service topology, mTLS status, and circuit breaker health</p>
        </div>
        <button onClick={fetchMeshData} className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm font-medium">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white rounded-xl shadow-sm p-6">
          <p className="text-xs text-gray-500">Total Services</p>
          <p className="text-2xl font-bold text-gray-800 mt-1">{services.length}</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm p-6">
          <p className="text-xs text-gray-500">Inter-Service Calls / min</p>
          <p className="text-2xl font-bold text-blue-600 mt-1">{totalCallsPerMin.toLocaleString()}</p>
        </div>
        <div className="bg-white rounded-xl shadow-sm p-6">
          <p className="text-xs text-gray-500">Open Circuit Breakers</p>
          <p className={`text-2xl font-bold mt-1 ${breakers.filter(b => b.state === "open").length > 0 ? "text-red-600" : "text-green-600"}`}>
            {breakers.filter(b => b.state === "open").length}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {services.map(svc => (
          <div key={svc.id} className="bg-white rounded-xl shadow-sm p-6">
            <div className="flex items-start justify-between mb-3">
              <div>
                <p className="font-semibold text-gray-900 font-mono text-sm">{svc.name}</p>
                <p className="text-xs text-gray-400 mt-0.5">{svc.replicas} replica{svc.replicas !== 1 ? "s" : ""}</p>
              </div>
              {svc.mtlsEnabled
                ? <span className="flex items-center gap-1 text-xs text-green-600 bg-green-50 px-2 py-0.5 rounded-full"><Shield className="w-3 h-3" /> mTLS</span>
                : <span className="flex items-center gap-1 text-xs text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full"><ShieldOff className="w-3 h-3" /> No mTLS</span>
              }
            </div>
            <div className="grid grid-cols-3 gap-3 text-center">
              <div>
                <p className="text-xs text-gray-400">Req/min</p>
                <p className="text-sm font-semibold text-gray-800">{svc.requestsPerMin.toLocaleString()}</p>
              </div>
              <div>
                <p className="text-xs text-gray-400">Error %</p>
                <p className={`text-sm font-semibold ${svc.errorRate > 1 ? "text-red-600" : "text-green-600"}`}>{svc.errorRate}%</p>
              </div>
              <div>
                <p className="text-xs text-gray-400">p99 ms</p>
                <p className={`text-sm font-semibold ${svc.p99LatencyMs > 200 ? "text-amber-600" : "text-gray-800"}`}>{svc.p99LatencyMs}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold text-gray-800 mb-4">Circuit Breaker Status</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 border-b border-gray-100">
                <th className="pb-3 pr-4">Source</th>
                <th className="pb-3 pr-4">Destination</th>
                <th className="pb-3 pr-4">State</th>
                <th className="pb-3 pr-4">Failure Rate</th>
                <th className="pb-3">Last Tripped</th>
              </tr>
            </thead>
            <tbody>
              {breakers.map((b, i) => (
                <tr key={i} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-3 pr-4 font-mono text-xs text-gray-700">{b.source}</td>
                  <td className="py-3 pr-4 font-mono text-xs text-gray-700">{b.destination}</td>
                  <td className="py-3 pr-4">
                    <span className="flex items-center gap-1">
                      {b.state === "open" ? <AlertCircle className="w-3.5 h-3.5 text-red-500" /> : <CheckCircle className="w-3.5 h-3.5 text-green-500" />}
                      <span className={`text-xs px-2 py-0.5 rounded-full capitalize ${CB_STYLES[b.state]}`}>{b.state}</span>
                    </span>
                  </td>
                  <td className="py-3 pr-4">
                    <span className={`text-xs font-medium ${b.failureRate > 5 ? "text-red-600" : "text-gray-600"}`}>{b.failureRate}%</span>
                  </td>
                  <td className="py-3 text-gray-500 text-xs">{b.lastTripped}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default ServiceMeshDashboard;
