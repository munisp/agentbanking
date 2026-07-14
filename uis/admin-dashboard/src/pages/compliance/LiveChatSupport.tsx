import { MessageSquare, Send, Bot, Clock, Users, AlertCircle } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_SUPPORT_COMMS_URL || import.meta.env.VITE_API_URL || "http://localhost:8011";

interface ChatMessage {
  id: string;
  sender: "customer" | "support";
  text: string;
  time: string;
}

interface ChatSession {
  id: string;
  agentName: string;
  customer: string;
  waitTime: string;
  status: "active" | "queued" | "resolved";
  messages: ChatMessage[];
  aiAssigned: boolean;
}

const MOCK_SESSIONS: ChatSession[] = [
  {
    id: "s1", agentName: "Ade Okafor", customer: "Mrs. Bello", waitTime: "2m", status: "active", aiAssigned: false,
    messages: [
      { id: "m1", sender: "customer", text: "Hello, I'm having trouble with my cash-in transaction.", time: "10:32" },
      { id: "m2", sender: "support", text: "Hi Mrs. Bello, I'm here to help. Can you share your transaction reference?", time: "10:33" },
      { id: "m3", sender: "customer", text: "It's TXN-20240501-8821. I deposited ₦20,000 but my balance didn't update.", time: "10:34" },
      { id: "m4", sender: "support", text: "Thank you, I'm looking into that now. Please hold on for a moment.", time: "10:35" },
    ],
  },
  {
    id: "s2", agentName: "Chike Eze", customer: "Mr. Adeyemi", waitTime: "5m", status: "queued", aiAssigned: false,
    messages: [
      { id: "m5", sender: "customer", text: "I need help resetting my agent PIN.", time: "10:40" },
    ],
  },
  {
    id: "s3", agentName: "Ngozi Uche", customer: "Fatima Musa", waitTime: "0m", status: "resolved", aiAssigned: true,
    messages: [
      { id: "m6", sender: "customer", text: "How do I register a new beneficiary?", time: "09:15" },
      { id: "m7", sender: "support", text: "Go to Transfers > Beneficiaries > Add New. Fill in the details and confirm with your PIN.", time: "09:15" },
      { id: "m8", sender: "customer", text: "Got it, thanks!", time: "09:16" },
    ],
  },
  {
    id: "s4", agentName: "Emeka Nwosu", customer: "Grace Obi", waitTime: "8m", status: "queued", aiAssigned: false,
    messages: [
      { id: "m9", sender: "customer", text: "My KYC submission was rejected. What do I do?", time: "10:45" },
    ],
  },
];

const STATUS_STYLES: Record<string, string> = {
  active: "bg-green-100 text-green-700",
  queued: "bg-amber-100 text-amber-700",
  resolved: "bg-gray-100 text-gray-500",
};

const LiveChatSupport: React.FC = () => {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => { fetchSessions(); }, []);

  const fetchSessions = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/support/api/v1/chat-sessions`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) { const d = await res.json(); setSessions(Array.isArray(d.sessions) ? d.sessions : MOCK_SESSIONS); }
      else { setSessions(MOCK_SESSIONS); }
    } catch { setSessions(MOCK_SESSIONS); }
    finally { setLoading(false); }
  };

  const selected = sessions.find(s => s.id === selectedId) ?? sessions[0] ?? null;

  const toggleAIBot = (id: string) => {
    setSessions(s => s.map(sess => sess.id === id ? { ...sess, aiAssigned: !sess.aiAssigned } : sess));
  };

  const sendMessage = () => {
    if (!message.trim() || !selected) return;
    const newMsg: ChatMessage = { id: `m${Date.now()}`, sender: "support", text: message.trim(), time: new Date().toLocaleTimeString("en-NG", { hour: "2-digit", minute: "2-digit" }) };
    setSessions(s => s.map(sess => sess.id === selected.id ? { ...sess, messages: [...sess.messages, newMsg] } : sess));
    setMessage("");
  };

  const totalQueued = sessions.filter(s => s.status === "queued").length;
  const slaBreaches = sessions.filter(s => s.status === "queued" && parseInt(s.waitTime) > 5).length;

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <MessageSquare className="w-7 h-7 text-indigo-600" /> Live Chat Support
        </h1>
        <p className="text-gray-500 text-sm mt-1">Real-time support console for agent and customer queries</p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Total Queued", value: totalQueued, icon: <Users className="w-4 h-4 text-amber-500" />, color: "text-amber-600" },
          { label: "Avg Wait Time", value: "4m 20s", icon: <Clock className="w-4 h-4 text-blue-500" />, color: "text-blue-600" },
          { label: "SLA Breaches", value: slaBreaches, icon: <AlertCircle className="w-4 h-4 text-red-500" />, color: "text-red-600" },
        ].map(stat => (
          <div key={stat.label} className="bg-white rounded-xl shadow-sm p-4 flex items-center gap-3">
            {stat.icon}
            <div>
              <p className="text-xs text-gray-500">{stat.label}</p>
              <p className={`text-xl font-bold ${stat.color}`}>{stat.value}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-3 gap-6">
        <div className="bg-white rounded-xl shadow-sm p-4 space-y-2">
          <h2 className="font-semibold text-gray-800 text-sm mb-3">Active Sessions</h2>
          {sessions.map(sess => (
            <button key={sess.id} onClick={() => setSelectedId(sess.id)}
              className={`w-full text-left p-3 rounded-lg border transition-colors ${selectedId === sess.id || (!selectedId && sess === sessions[0]) ? "border-indigo-200 bg-indigo-50" : "border-gray-100 hover:bg-gray-50"}`}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium text-gray-900">{sess.customer}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_STYLES[sess.status]}`}>{sess.status}</span>
              </div>
              <p className="text-xs text-gray-500">Agent: {sess.agentName}</p>
              <p className="text-xs text-gray-400 mt-0.5">Wait: {sess.waitTime}</p>
            </button>
          ))}
        </div>

        {selected && (
          <div className="col-span-2 bg-white rounded-xl shadow-sm p-4 flex flex-col">
            <div className="flex items-center justify-between border-b border-gray-100 pb-3 mb-4">
              <div>
                <p className="font-semibold text-gray-900">{selected.customer}</p>
                <p className="text-xs text-gray-500">Agent: {selected.agentName} · Status: <span className="capitalize">{selected.status}</span></p>
              </div>
              <label className="flex items-center gap-2 cursor-pointer">
                <span className="text-xs text-gray-500 flex items-center gap-1"><Bot className="w-4 h-4" /> Assign to AI Bot</span>
                <div onClick={() => toggleAIBot(selected.id)} className={`relative w-10 h-5 rounded-full transition-colors ${selected.aiAssigned ? "bg-indigo-500" : "bg-gray-200"}`}>
                  <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${selected.aiAssigned ? "translate-x-5" : "translate-x-0.5"}`} />
                </div>
              </label>
            </div>

            <div className="flex-1 overflow-y-auto space-y-3 mb-4 max-h-64">
              {selected.messages.map(msg => (
                <div key={msg.id} className={`flex ${msg.sender === "support" ? "justify-end" : "justify-start"}`}>
                  <div className={`max-w-xs px-3 py-2 rounded-xl text-sm ${msg.sender === "support" ? "bg-indigo-600 text-white" : "bg-gray-100 text-gray-800"}`}>
                    <p>{msg.text}</p>
                    <p className={`text-xs mt-1 ${msg.sender === "support" ? "text-indigo-200" : "text-gray-400"}`}>{msg.time}</p>
                  </div>
                </div>
              ))}
            </div>

            <div className="flex items-center gap-2">
              <input value={message} onChange={e => setMessage(e.target.value)}
                onKeyDown={e => e.key === "Enter" && sendMessage()}
                placeholder="Type a message..."
                className="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500" />
              <button onClick={sendMessage} className="p-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg">
                <Send className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default LiveChatSupport;
