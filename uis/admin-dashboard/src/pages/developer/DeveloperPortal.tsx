import { Code2, Key, Webhook, BookOpen, Activity, ArrowRight, Copy, CheckCircle, Terminal } from "lucide-react";
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";

const BASE_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

const ENDPOINTS = [
  { method: "GET", path: "/developer/api/v1/api-keys", description: "List all API keys" },
  { method: "POST", path: "/developer/api/v1/api-keys", description: "Create a new API key" },
  { method: "POST", path: "/developer/api/v1/api-keys/:id/revoke", description: "Revoke an API key" },
  { method: "GET", path: "/developer/api/v1/webhooks", description: "List webhook endpoints" },
  { method: "POST", path: "/developer/api/v1/webhooks", description: "Register a webhook endpoint" },
  { method: "POST", path: "/developer/api/v1/webhooks/:id/test", description: "Send a test event" },
  { method: "GET", path: "/transaction/api/v1/transactions", description: "List transactions" },
  { method: "POST", path: "/payment-hub/api/v1/transfers", description: "Initiate a transfer" },
  { method: "GET", path: "/agent/api/v1/agents", description: "List agents" },
];

const METHOD_COLORS: Record<string, string> = { GET: "bg-blue-100 text-blue-700", POST: "bg-emerald-100 text-emerald-700", PATCH: "bg-amber-100 text-amber-700", DELETE: "bg-red-100 text-red-700" };

const SAMPLE_CODE = `// Authenticate with your API key
const response = await fetch('${BASE_URL}/transaction/api/v1/transactions', {
  headers: {
    'Authorization': 'Bearer sk_live_your_api_key',
    'X-Tenant-ID': 'your_tenant_id',
    'Content-Type': 'application/json'
  }
});

const data = await response.json();
console.log(data.transactions);`;

const DeveloperPortal: React.FC = () => {
  const navigate = useNavigate();
  const [copiedCode, setCopiedCode] = useState(false);

  const copyCode = () => {
    navigator.clipboard.writeText(SAMPLE_CODE);
    setCopiedCode(true);
    setTimeout(() => setCopiedCode(false), 2000);
  };

  const cards = [
    { icon: Key, title: "API Keys", description: "Generate and manage API credentials for your integrations", path: "/developer/api-keys", color: "text-blue-600", bg: "bg-blue-50", borderHover: "hover:border-blue-300" },
    { icon: Webhook, title: "Webhooks", description: "Configure real-time event notifications to your endpoints", path: "/developer/webhooks", color: "text-purple-600", bg: "bg-purple-50", borderHover: "hover:border-purple-300" },
    { icon: Activity, title: "API Usage", description: "Monitor API call volumes, latency and error rates", path: "/monitoring", color: "text-emerald-600", bg: "bg-emerald-50", borderHover: "hover:border-emerald-300" },
    { icon: BookOpen, title: "Audit Logs", description: "Full audit trail of all API calls with request/response details", path: "/audit", color: "text-amber-600", bg: "bg-amber-50", borderHover: "hover:border-amber-300" },
  ];

  return (
    <div className="p-6 space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Code2 className="w-7 h-7 text-blue-600" /> Developer Portal
        </h1>
        <p className="text-gray-500 text-sm mt-1">Integrate with the 54agent platform using our REST APIs and webhooks</p>
      </div>

      <div className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-2xl p-6 text-white">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold mb-1">Base URL</h2>
            <code className="text-blue-100 text-sm">{BASE_URL}</code>
            <p className="text-blue-200 text-xs mt-2">All API endpoints are prefixed with the service path. Include <code className="bg-white/20 px-1 rounded">Authorization: Bearer YOUR_KEY</code> header.</p>
          </div>
          <Terminal className="w-12 h-12 text-white/30 shrink-0" />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4">
        {cards.map(({ icon: Icon, title, description, path, color, bg, borderHover }) => (
          <button key={title} onClick={() => navigate(path)}
            className={`bg-white border border-gray-200 ${borderHover} rounded-xl p-5 shadow-sm text-left hover:shadow-md transition-all group`}>
            <div className={`w-10 h-10 ${bg} rounded-xl flex items-center justify-center mb-3`}>
              <Icon className={`w-5 h-5 ${color}`} />
            </div>
            <h3 className="font-semibold text-gray-900 mb-1">{title}</h3>
            <p className="text-sm text-gray-500">{description}</p>
            <div className={`flex items-center gap-1 mt-3 text-xs font-medium ${color}`}>
              Open <ArrowRight className="w-3 h-3 group-hover:translate-x-1 transition-transform" />
            </div>
          </button>
        ))}
      </div>

      <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
        <div className="p-4 border-b border-gray-100">
          <h3 className="font-semibold text-gray-800">Quick Reference — API Endpoints</h3>
        </div>
        <div className="divide-y divide-gray-50">
          {ENDPOINTS.map(ep => (
            <div key={ep.path} className="flex items-center gap-3 px-4 py-3 hover:bg-gray-50">
              <span className={`text-xs font-bold px-2 py-0.5 rounded shrink-0 ${METHOD_COLORS[ep.method]}`}>{ep.method}</span>
              <code className="text-sm text-gray-700 flex-1 font-mono">{ep.path}</code>
              <span className="text-xs text-gray-400">{ep.description}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-gray-900 rounded-xl overflow-hidden shadow-sm">
        <div className="flex items-center justify-between px-4 py-2 border-b border-gray-700">
          <span className="text-xs text-gray-400 font-mono">JavaScript example</span>
          <button onClick={copyCode} className="flex items-center gap-1 text-xs text-gray-400 hover:text-white transition-colors">
            {copiedCode ? <CheckCircle className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
            {copiedCode ? "Copied!" : "Copy"}
          </button>
        </div>
        <pre className="p-4 text-sm text-gray-300 font-mono overflow-x-auto whitespace-pre-wrap">{SAMPLE_CODE}</pre>
      </div>
    </div>
  );
};

export default DeveloperPortal;
