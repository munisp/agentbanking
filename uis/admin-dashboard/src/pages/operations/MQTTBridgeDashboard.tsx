import { Radio, RefreshCw, Users, Activity, List, Clock } from "lucide-react";
import React, { useEffect, useRef, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_PLATFORM_MGMT_URL || import.meta.env.VITE_API_URL || "http://localhost:8010";

interface MQTTTopic {
  topic: string;
  subscribers: number;
  messagesPerSec: number;
  lastMessage: string;
}

interface MQTTStats {
  connectedClients: number;
  messagesPerSec: number;
  topicsCount: number;
  queueDepth: number;
  brokerStatus: "Connected" | "Disconnected";
}

const MQTTBridgeDashboard: React.FC = () => {
  const [stats, setStats] = useState<MQTTStats | null>(null);
  const [topics, setTopics] = useState<MQTTTopic[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [logLines] = useState<string[]>([]);
  const logRef = useRef<HTMLDivElement>(null);

  

  useEffect(() => { fetchBrokerData(); }, []);

  const fetchBrokerData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${CORE_URL}/ops/api/v1/mqtt/stats`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) {
        const d = await res.json();
        setStats(d.stats ?? null);
        setTopics(Array.isArray(d.topics) ? d.topics : []);
      } else { setError("Failed to load MQTT broker data."); }
    } catch { setError("Failed to load MQTT broker data."); }
    finally { setLoading(false); }
  };

  const metricCards = [
    { label: "Connected Clients", value: stats ? stats.connectedClients.toLocaleString() : "—", icon: <Users className="w-5 h-5 text-indigo-500" />, color: "text-indigo-600" },
    { label: "Messages / sec", value: stats ? stats.messagesPerSec.toLocaleString() : "—", icon: <Activity className="w-5 h-5 text-blue-500" />, color: "text-blue-600" },
    { label: "Active Topics", value: stats ? stats.topicsCount.toLocaleString() : "—", icon: <List className="w-5 h-5 text-emerald-500" />, color: "text-emerald-600" },
    { label: "Queue Depth", value: stats ? stats.queueDepth.toLocaleString() : "—", icon: <Clock className="w-5 h-5 text-amber-500" />, color: stats && stats.queueDepth > 500 ? "text-red-600" : "text-amber-600" },
  ];

  return (
    <div className="p-6 space-y-6">
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm flex items-center justify-between gap-4">
          <span>{error}</span>
          <button onClick={() => fetchBrokerData()} className="underline shrink-0">Retry</button>
        </div>
      )}

      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Radio className="w-7 h-7 text-emerald-600" /> MQTT Bridge Dashboard
          </h1>
          <p className="text-gray-500 text-sm mt-1">Message broker telemetry, topic subscriptions and live message log</p>
        </div>
        <div className="flex items-center gap-3">
          <span className={`flex items-center gap-1.5 text-sm font-medium px-3 py-1.5 rounded-full ${stats?.brokerStatus === "Connected" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
            <span className={`w-2 h-2 rounded-full ${stats?.brokerStatus === "Connected" ? "bg-green-500 animate-pulse" : "bg-gray-400"}`} />
            {stats?.brokerStatus ?? "Unknown"}
          </span>
          <button onClick={fetchBrokerData} className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm font-medium">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {metricCards.map(card => (
          <div key={card.label} className="bg-white rounded-xl shadow-sm p-6">
            <div className="flex items-center gap-2 mb-2">{card.icon}<p className="text-xs text-gray-500">{card.label}</p></div>
            <p className={`text-2xl font-bold ${card.color}`}>{card.value}</p>
          </div>
        ))}
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold text-gray-800 mb-4">Topic Subscriptions</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-gray-500 border-b border-gray-100">
                <th className="pb-3 pr-4">Topic</th>
                <th className="pb-3 pr-4">Subscribers</th>
                <th className="pb-3 pr-4">Messages / sec</th>
                <th className="pb-3">Last Message</th>
              </tr>
            </thead>
            <tbody>
              {topics.map(t => (
                <tr key={t.topic} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-3 pr-4 font-mono text-xs text-gray-700">{t.topic}</td>
                  <td className="py-3 pr-4 text-gray-700">{t.subscribers}</td>
                  <td className="py-3 pr-4">
                    <span className={`text-xs font-medium ${t.messagesPerSec > 200 ? "text-blue-600" : "text-gray-600"}`}>{t.messagesPerSec}</span>
                  </td>
                  <td className="py-3 text-gray-400 text-xs">{t.lastMessage}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold text-gray-800 mb-3">Recent Message Log</h2>
        <div ref={logRef} className="bg-gray-900 rounded-lg p-4 h-52 overflow-y-auto font-mono text-xs text-green-400 space-y-1">
          {logLines.length === 0 ? <div className="text-gray-500">No broker message log available.</div> : logLines.map((line, i) => <div key={i}>{line}</div>)}
        </div>
      </div>
    </div>
  );
};

export default MQTTBridgeDashboard;
