import { Store, RefreshCw, CheckCircle, Link2, Clock, XCircle } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_PLATFORM_MGMT_URL || import.meta.env.VITE_API_URL || "http://localhost:8010";

type IntegrationStatus = "connected" | "available" | "coming-soon";
type IntegrationCategory = "Payment" | "Compliance" | "Analytics" | "Communication" | "ERP";

interface Integration {
  id: string;
  name: string;
  category: IntegrationCategory;
  status: IntegrationStatus;
  description: string;
  logo: string;
}

const MOCK_INTEGRATIONS: Integration[] = [
  { id: "nibss", name: "NIBSS", category: "Payment", status: "connected", description: "Nigeria Inter-Bank Settlement System for NIP and NEFT transfers between Nigerian banks.", logo: "NI" },
  { id: "mojaloop", name: "Mojaloop", category: "Payment", status: "connected", description: "Open-source interoperability platform for real-time inclusive financial services.", logo: "MJ" },
  { id: "flutterwave", name: "Flutterwave", category: "Payment", status: "connected", description: "Pan-African payments gateway supporting cards, bank transfers and mobile money.", logo: "FW" },
  { id: "paystack", name: "Paystack", category: "Payment", status: "available", description: "Modern Nigerian payments processor with support for card, bank and USSD payments.", logo: "PS" },
  { id: "stripe", name: "Stripe", category: "Payment", status: "available", description: "Global payments infrastructure for international card processing and disbursements.", logo: "ST" },
  { id: "cbn-api", name: "CBN Open API", category: "Compliance", status: "connected", description: "Central Bank of Nigeria regulatory reporting, BVN verification and policy feeds.", logo: "CB" },
  { id: "nfiu", name: "NFIU", category: "Compliance", status: "connected", description: "Nigeria Financial Intelligence Unit STR/CTR filing and AML transaction screening.", logo: "NF" },
  { id: "termii", name: "Termii SMS", category: "Communication", status: "connected", description: "Nigerian SMS gateway for OTP delivery, transactional SMS and voice notifications.", logo: "TM" },
  { id: "africas-talking", name: "Africa's Talking", category: "Communication", status: "available", description: "Multi-channel communications API for SMS, USSD, voice and airtime across Africa.", logo: "AT" },
  { id: "erpnext", name: "ERPNext", category: "ERP", status: "available", description: "Open-source ERP for accounting, inventory and HR integration with agent banking operations.", logo: "EN" },
  { id: "mixpanel", name: "Mixpanel", category: "Analytics", status: "available", description: "Product analytics platform for tracking user journeys and funnel optimisation.", logo: "MP" },
  { id: "remita", name: "Remita", category: "Payment", status: "coming-soon", description: "Government and enterprise payment collection platform used by IPPIS and federal agencies.", logo: "RM" },
  { id: "interswitch", name: "Interswitch", category: "Payment", status: "coming-soon", description: "Nigerian payment switching and processing network supporting Verve cards and Quickteller.", logo: "IW" },
  { id: "dojah", name: "Dojah KYC", category: "Compliance", status: "available", description: "Identity verification APIs for BVN lookup, NIN check, document OCR and liveness detection.", logo: "DJ" },
  { id: "google-analytics", name: "Google Analytics", category: "Analytics", status: "coming-soon", description: "Web and app analytics for dashboard usage tracking and admin user behaviour insights.", logo: "GA" },
];

const CATEGORIES: Array<"All" | IntegrationCategory> = ["All", "Payment", "Compliance", "Communication", "ERP", "Analytics"];

const STATUS_CONFIG: Record<IntegrationStatus, { label: string; bg: string; text: string; icon: React.FC<{className?: string}> }> = {
  connected: { label: "Connected", bg: "bg-green-100", text: "text-green-700", icon: CheckCircle },
  available: { label: "Available", bg: "bg-blue-100", text: "text-blue-700", icon: Link2 },
  "coming-soon": { label: "Coming Soon", bg: "bg-gray-100", text: "text-gray-500", icon: Clock },
};

const IntegrationMarketplace: React.FC = () => {
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [loading, setLoading] = useState(false);
  const [category, setCategory] = useState<"All" | IntegrationCategory>("All");
  const [connecting, setConnecting] = useState<string | null>(null);

  useEffect(() => { fetchIntegrations(); }, []);

  const fetchIntegrations = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/developer/api/v1/integrations`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) { const d = await res.json(); setIntegrations(Array.isArray(d.integrations) ? d.integrations : MOCK_INTEGRATIONS); }
      else { setIntegrations(MOCK_INTEGRATIONS); }
    } catch { setIntegrations(MOCK_INTEGRATIONS); }
    finally { setLoading(false); }
  };

  const toggleConnection = async (integration: Integration) => {
    if (integration.status === "coming-soon") return;
    setConnecting(integration.id);
    try {
      const action = integration.status === "connected" ? "disconnect" : "connect";
      await fetch(`${CORE_URL}/developer/api/v1/integrations/${integration.id}/${action}`, {
        method: "POST", headers: getTenantHeadersFromStorage(),
      });
      setIntegrations(prev => prev.map(i => i.id === integration.id
        ? { ...i, status: (action === "connect" ? "connected" : "available") as IntegrationStatus }
        : i
      ));
    } catch {
      setIntegrations(prev => prev.map(i => i.id === integration.id
        ? { ...i, status: (integration.status === "connected" ? "available" : "connected") as IntegrationStatus }
        : i
      ));
    } finally { setConnecting(null); }
  };

  const filtered = category === "All" ? integrations : integrations.filter(i => i.category === category);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Store className="w-7 h-7 text-blue-600" /> Integration Marketplace
          </h1>
          <p className="text-gray-500 text-sm mt-1">Connect 54agent with payment networks, compliance tools and third-party services</p>
        </div>
        <button onClick={fetchIntegrations} disabled={loading}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium disabled:opacity-50">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {[
          { label: "Connected", value: integrations.filter(i => i.status === "connected").length, color: "text-green-600" },
          { label: "Available", value: integrations.filter(i => i.status === "available").length, color: "text-blue-600" },
          { label: "Coming Soon", value: integrations.filter(i => i.status === "coming-soon").length, color: "text-gray-500" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
            <p className="text-xs text-gray-500">{label}</p>
            <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
          </div>
        ))}
      </div>

      <div className="flex bg-gray-100 rounded-lg p-1 w-fit flex-wrap gap-1">
        {CATEGORIES.map(cat => (
          <button key={cat} onClick={() => setCategory(cat)}
            className={`px-3 py-1.5 text-sm rounded-md font-medium transition-colors ${category === cat ? "bg-white text-blue-600 shadow-sm" : "text-gray-500 hover:text-gray-700"}`}>
            {cat}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filtered.map(integration => {
          const cfg = STATUS_CONFIG[integration.status];
          const Icon = cfg.icon;
          const isConnecting = connecting === integration.id;
          return (
            <div key={integration.id} className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm flex flex-col justify-between hover:border-gray-300 transition-colors">
              <div>
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-gray-100 flex items-center justify-center text-xs font-bold text-gray-600">{integration.logo}</div>
                    <div>
                      <p className="font-semibold text-gray-900 text-sm">{integration.name}</p>
                      <span className="text-xs text-gray-400">{integration.category}</span>
                    </div>
                  </div>
                  <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full font-medium ${cfg.bg} ${cfg.text}`}>
                    <Icon className="w-3 h-3" /> {cfg.label}
                  </span>
                </div>
                <p className="text-xs text-gray-500 leading-relaxed">{integration.description}</p>
              </div>
              <div className="mt-4">
                {integration.status === "coming-soon" ? (
                  <button disabled className="w-full py-2 bg-gray-100 text-gray-400 rounded-lg text-sm font-medium cursor-not-allowed flex items-center justify-center gap-1">
                    <Clock className="w-3.5 h-3.5" /> Coming Soon
                  </button>
                ) : integration.status === "connected" ? (
                  <button onClick={() => toggleConnection(integration)} disabled={isConnecting}
                    className="w-full py-2 bg-red-50 hover:bg-red-100 text-red-600 rounded-lg text-sm font-medium disabled:opacity-50 flex items-center justify-center gap-1">
                    <XCircle className="w-3.5 h-3.5" /> {isConnecting ? "Disconnecting…" : "Disconnect"}
                  </button>
                ) : (
                  <button onClick={() => toggleConnection(integration)} disabled={isConnecting}
                    className="w-full py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium disabled:opacity-50">
                    {isConnecting ? "Connecting…" : "Connect"}
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default IntegrationMarketplace;
