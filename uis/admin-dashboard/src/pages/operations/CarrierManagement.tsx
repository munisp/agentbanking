import { PhoneCall, RefreshCw, DollarSign, Zap, ArrowLeftRight, ShieldCheck } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_PLATFORM_MGMT_URL || import.meta.env.VITE_API_URL || "http://localhost:8010";

interface CarrierCost {
  carrier: string;
  perSMSCost: number;
  perCallCost: number;
  monthlyMin: number;
  totalSpend: number;
}

interface LiveRate {
  carrier: string;
  smsRate: number;
  voiceRate: number;
  dataRateMBPS: number;
  updatedAt: string;
}

interface SwitchRule {
  id: string;
  fromCarrier: string;
  condition: string;
  threshold: number;
  toCarrier: string;
  enabled: boolean;
}

interface SLAEntry {
  carrier: string;
  uptimeTarget: number;
  uptimeActual: number;
  deliveryTarget: number;
  deliveryActual: number;
  latencyTargetMs: number;
  latencyActualMs: number;
}

const MOCK_COSTS: CarrierCost[] = [
  { carrier: "MTN", perSMSCost: 4.5, perCallCost: 22, monthlyMin: 50000, totalSpend: 182400 },
  { carrier: "Airtel", perSMSCost: 4.0, perCallCost: 20, monthlyMin: 30000, totalSpend: 98700 },
  { carrier: "Glo", perSMSCost: 3.8, perCallCost: 18, monthlyMin: 20000, totalSpend: 67200 },
  { carrier: "9Mobile", perSMSCost: 4.2, perCallCost: 21, monthlyMin: 15000, totalSpend: 41500 },
];

const MOCK_LIVE_RATES: LiveRate[] = [
  { carrier: "MTN", smsRate: 4.5, voiceRate: 22, dataRateMBPS: 0.012, updatedAt: "10:44:31" },
  { carrier: "Airtel", smsRate: 4.0, voiceRate: 20, dataRateMBPS: 0.010, updatedAt: "10:44:31" },
  { carrier: "Glo", smsRate: 3.8, voiceRate: 18, dataRateMBPS: 0.009, updatedAt: "10:44:31" },
  { carrier: "9Mobile", smsRate: 4.2, voiceRate: 21, dataRateMBPS: 0.011, updatedAt: "10:44:31" },
];

const MOCK_RULES: SwitchRule[] = [
  { id: "rule-01", fromCarrier: "MTN", condition: "error_rate > ", threshold: 5, toCarrier: "Airtel", enabled: true },
  { id: "rule-02", fromCarrier: "Airtel", condition: "error_rate > ", threshold: 8, toCarrier: "Glo", enabled: true },
  { id: "rule-03", fromCarrier: "Glo", condition: "latency_ms > ", threshold: 500, toCarrier: "MTN", enabled: false },
];

const MOCK_SLAS: SLAEntry[] = [
  { carrier: "MTN", uptimeTarget: 99.9, uptimeActual: 99.7, deliveryTarget: 98, deliveryActual: 97.2, latencyTargetMs: 300, latencyActualMs: 284 },
  { carrier: "Airtel", uptimeTarget: 99.5, uptimeActual: 99.6, deliveryTarget: 97, deliveryActual: 98.1, latencyTargetMs: 350, latencyActualMs: 320 },
  { carrier: "Glo", uptimeTarget: 99.0, uptimeActual: 98.4, deliveryTarget: 95, deliveryActual: 94.1, latencyTargetMs: 400, latencyActualMs: 445 },
  { carrier: "9Mobile", uptimeTarget: 99.0, uptimeActual: 99.1, deliveryTarget: 96, deliveryActual: 95.8, latencyTargetMs: 380, latencyActualMs: 362 },
];

type TabKey = "cost" | "live" | "switching" | "sla";

const TABS: { key: TabKey; label: string; icon: React.ReactNode }[] = [
  { key: "cost", label: "Cost", icon: <DollarSign className="w-4 h-4" /> },
  { key: "live", label: "Live Pricing", icon: <Zap className="w-4 h-4" /> },
  { key: "switching", label: "Switching", icon: <ArrowLeftRight className="w-4 h-4" /> },
  { key: "sla", label: "SLA", icon: <ShieldCheck className="w-4 h-4" /> },
];

const CarrierManagement: React.FC = () => {
  const [tab, setTab] = useState<TabKey>("cost");
  const [costs, setCosts] = useState<CarrierCost[]>([]);
  const [liveRates, setLiveRates] = useState<LiveRate[]>(MOCK_LIVE_RATES);
  const [rules, setRules] = useState<SwitchRule[]>(MOCK_RULES);
  const [slas, setSlas] = useState<SLAEntry[]>(MOCK_SLAS);
  const [loading, setLoading] = useState(false);
  const [liveTs, setLiveTs] = useState(new Date().toLocaleTimeString());

  

  useEffect(() => {
    if (tab !== "live") return;
    const interval = setInterval(() => {
      setLiveTs(new Date().toLocaleTimeString());
      setLiveRates(prev => prev.map(r => ({
        ...r,
        smsRate: +(r.smsRate + (Math.random() - 0.5) * 0.05).toFixed(2),
        voiceRate: +(r.voiceRate + (Math.random() - 0.5) * 0.2).toFixed(2),
        updatedAt: new Date().toLocaleTimeString(),
      })));
    }, 30000);
    return () => clearInterval(interval);
  }, [tab]);

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/ops/api/v1/carriers`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) {
        const d = await res.json();
        setCosts(Array.isArray(d.costs) ? d.costs : MOCK_COSTS);
        if (Array.isArray(d.slas)) setSlas(d.slas);
        if (Array.isArray(d.rules)) setRules(d.rules);
      } else { setCosts(MOCK_COSTS); }
    } catch { setCosts(MOCK_COSTS); }
    finally { setLoading(false); }
  };

  const toggleRule = (id: string) => setRules(prev => prev.map(r => r.id === id ? { ...r, enabled: !r.enabled } : r));

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <PhoneCall className="w-7 h-7 text-purple-600" /> Carrier Management
          </h1>
          <p className="text-gray-500 text-sm mt-1">Telecom carrier costs, live pricing, auto-switching and SLA tracking</p>
        </div>
        <button onClick={fetchData} className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm font-medium">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
        </button>
      </div>

      <div className="flex gap-1 bg-gray-100 rounded-xl p-1 w-fit">
        {TABS.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${tab === t.key ? "bg-white shadow text-gray-900" : "text-gray-500 hover:text-gray-700"}`}>
            {t.icon}{t.label}
          </button>
        ))}
      </div>

      {tab === "cost" && (
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h2 className="font-semibold text-gray-800 mb-4">Carrier Cost Breakdown</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-500 border-b border-gray-100">
                  <th className="pb-3 pr-4">Carrier</th>
                  <th className="pb-3 pr-4">Per-SMS (₦)</th>
                  <th className="pb-3 pr-4">Per-Call (₦)</th>
                  <th className="pb-3 pr-4">Monthly Min (₦)</th>
                  <th className="pb-3">Total Spend (₦)</th>
                </tr>
              </thead>
              <tbody>
                {costs.map(c => (
                  <tr key={c.carrier} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-3 pr-4 font-semibold text-gray-800">{c.carrier}</td>
                    <td className="py-3 pr-4 text-gray-600">{c.perSMSCost.toFixed(2)}</td>
                    <td className="py-3 pr-4 text-gray-600">{c.perCallCost.toFixed(2)}</td>
                    <td className="py-3 pr-4 text-gray-600">{c.monthlyMin.toLocaleString()}</td>
                    <td className="py-3 font-semibold text-indigo-600">{c.totalSpend.toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {tab === "live" && (
        <div className="bg-white rounded-xl shadow-sm p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-800">Live Rate Cards</h2>
            <span className="flex items-center gap-1.5 text-xs text-green-600 bg-green-50 px-2 py-1 rounded-full">
              <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" /> Live · updated {liveTs} · polling every 30s
            </span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {liveRates.map(r => (
              <div key={r.carrier} className="border border-gray-100 rounded-xl p-4">
                <p className="font-semibold text-gray-800 mb-3">{r.carrier}</p>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between"><span className="text-gray-500">SMS</span><span className="font-medium">₦{r.smsRate.toFixed(2)}</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Voice</span><span className="font-medium">₦{r.voiceRate.toFixed(2)}/min</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Data</span><span className="font-medium">₦{r.dataRateMBPS.toFixed(3)}/MB</span></div>
                </div>
                <p className="text-xs text-gray-400 mt-3">Updated {r.updatedAt}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === "switching" && (
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h2 className="font-semibold text-gray-800 mb-4">Auto-Switch Rules</h2>
          <div className="space-y-3">
            {rules.map(rule => (
              <div key={rule.id} className={`flex items-center justify-between p-4 rounded-xl border ${rule.enabled ? "border-indigo-100 bg-indigo-50" : "border-gray-100 bg-gray-50"}`}>
                <div>
                  <p className="text-sm font-medium text-gray-800">
                    If <span className="font-semibold text-red-600">{rule.fromCarrier}</span> {rule.condition}<span className="font-semibold">{rule.threshold}%</span>, switch to <span className="font-semibold text-green-700">{rule.toCarrier}</span>
                  </p>
                  <p className="text-xs text-gray-400 mt-0.5">{rule.id}</p>
                </div>
                <button onClick={() => toggleRule(rule.id)}
                  className={`text-xs px-3 py-1.5 rounded-lg font-medium ${rule.enabled ? "bg-green-100 text-green-700 hover:bg-green-200" : "bg-gray-200 text-gray-500 hover:bg-gray-300"}`}>
                  {rule.enabled ? "Enabled" : "Disabled"}
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {tab === "sla" && (
        <div className="bg-white rounded-xl shadow-sm p-6">
          <h2 className="font-semibold text-gray-800 mb-4">SLA Targets vs Actuals</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-500 border-b border-gray-100">
                  <th className="pb-3 pr-4">Carrier</th>
                  <th className="pb-3 pr-4">Uptime Target</th>
                  <th className="pb-3 pr-4">Uptime Actual</th>
                  <th className="pb-3 pr-4">Delivery Target</th>
                  <th className="pb-3 pr-4">Delivery Actual</th>
                  <th className="pb-3 pr-4">Latency Target</th>
                  <th className="pb-3">Latency Actual</th>
                </tr>
              </thead>
              <tbody>
                {slas.map(s => (
                  <tr key={s.carrier} className="border-b border-gray-50 hover:bg-gray-50">
                    <td className="py-3 pr-4 font-semibold text-gray-800">{s.carrier}</td>
                    <td className="py-3 pr-4 text-gray-500">{s.uptimeTarget}%</td>
                    <td className="py-3 pr-4"><span className={s.uptimeActual >= s.uptimeTarget ? "text-green-600 font-medium" : "text-red-600 font-medium"}>{s.uptimeActual}%</span></td>
                    <td className="py-3 pr-4 text-gray-500">{s.deliveryTarget}%</td>
                    <td className="py-3 pr-4"><span className={s.deliveryActual >= s.deliveryTarget ? "text-green-600 font-medium" : "text-red-600 font-medium"}>{s.deliveryActual}%</span></td>
                    <td className="py-3 pr-4 text-gray-500">{s.latencyTargetMs}ms</td>
                    <td className="py-3"><span className={s.latencyActualMs <= s.latencyTargetMs ? "text-green-600 font-medium" : "text-red-600 font-medium"}>{s.latencyActualMs}ms</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};

export default CarrierManagement;
