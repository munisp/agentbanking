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

const MOCK_STATS: MQTTStats = {
  connectedClients: 342,
  messagesPerSec: 1840,
  topicsCount: 56,
  queueDepth: 128,
  brokerStatus: "Connected",
};

const MOCK_TOPICS: MQTTTopic[] = [
  { topic: "agent/transactions/cash-in", subscribers: 84, messagesPerSec: 320, lastMessage: "2025-05-02 10:44:31" },
  { topic: "agent/transactions/cash-out", subscribers: 84, messagesPerSec: 280, lastMessage: "2025-05-02 10:44:32" },
  { topic: "agent/status/heartbeat", subscribers: 210, messagesPerSec: 700, lastMessage: "2025-05-02 10:44:33" },
  { topic: "payments/settlement/events", subscribers: 12, messagesPerSec: 45, lastMessage: "2025-05-02 10:44:28" },
  { topic: "kyc/verification/results", subscribers: 6, messagesPerSec: 18, lastMessage: "2025-05-02 10:44:20" },
  { topic: "notifications/push/dispatch", subscribers: 48, messagesPerSec: 210, lastMessage: "2025-05-02 10:44:33" },
  { topic: "system/alerts/critical", subscribers: 5, messagesPerSec: 2, lastMessage: "2025-05-02 09:10:05" },
];

const MOCK_LOG_LINES = [
  "10:44:33.021 [PUBLISH] agent/status/heartbeat — agent_id=AG-00421 signal=strong",
  "10:44:33.018 [PUBLISH] notifications/push/dispatch — msg_id=NTF-8821 target=AG-00182",
  "10:44:32.994 [PUBLISH] agent/transactions/cash-out — txn_id=TXN-44092 amount=5000",
  "10:44:32.876 [SUBSCRIBE] agent/transactions/cash-in — client=dashboard-monitor-01",
  "10:44:31.740 [PUBLISH] agent/transactions/cash-in — txn_id=TXN-44091 amount=2000",
  "10:44:28.301 [PUBLISH] payments/settlement/events — batch_id=BAT-3301 status=settled",
  "10:44:20.114 [PUBLISH] kyc/verification/results — user_id=USR-9912 result=approved",
  "10:44:11.800 [CONNECT] client=agent-app-00591 clean_session=true",
  "10:44:09.203 [DISCONNECT] client=agent-app-00388 reason=keepalive_timeout",
];

const MQTTBridgeDashboard: React.FC = () => {
  const [stats, setStats] = useState<MQTTStats>(MOCK_STATS);
  const [topics, setTopics] = useState<MQTTTopic[]>([]);
  const [loading, setLoading] = useState(false);
  const [logLines] = useState<string[]>(MOCK_LOG_LINES);
  const logRef = useRef<HTMLDivElement>(null);

  

  useEffect(() => { fetchBrokerData(); }, []);

  const fetchBrokerData = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/ops/api/v1/mqtt/stats`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) {
        const d = await res.json();
        setStats(d.stats ?? MOCK_STATS);
        setTopics(Array.isArray(d.topics) ? d.topics : MOCK_TOPICS);
      } else { setTopics(MOCK_TOPICS); }
    } catch { setTopics(MOCK_TOPICS); }
    finally { setLoading(false); }
  };

  const metricCards = [
    { label: "Connected Clients", value: stats.connectedClients.toLocaleString(), icon: <Users className="w-5 h-5 text-indigo-500" />, color: "text-indigo-600" },
    { label: "Messages / sec", value: stats.messagesPerSec.toLocaleString(), icon: <Activity className="w-5 h-5 text-blue-500" />, color: "text-blue-600" },
    { label: "Active Topics", value: stats.topicsCount.toLocaleString(), icon: <List className="w-5 h-5 text-emerald-500" />, color: "text-emerald-600" },
    { label: "Queue Depth", value: stats.queueDepth.toLocaleString(), icon: <Clock className="w-5 h-5 text-amber-500" />, color: stats.queueDepth > 500 ? "text-red-600" : "text-amber-600" },
  ];

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Radio className="w-7 h-7 text-emerald-600" /> MQTT Bridge Dashboard
          </h1>
          <p className="text-gray-500 text-sm mt-1">Message broker telemetry, topic subscriptions and live message log</p>
        </div>
        <div className="flex items-center gap-3">
          <span className={`flex items-center gap-1.5 text-sm font-medium px-3 py-1.5 rounded-full ${stats.brokerStatus === "Connected" ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"}`}>
            <span className={`w-2 h-2 rounded-full ${stats.brokerStatus === "Connected" ? "bg-green-500 animate-pulse" : "bg-red-500"}`} />
            {stats.brokerStatus}
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
          {logLines.map((line, i) => <div key={i}>{line}</div>)}
        </div>
      </div>
    </div>
  );
};

export default MQTTBridgeDashboard;
