import { Smartphone, Shield, RefreshCw, CheckCircle, AlertTriangle, Plus, Trash2, Lock } from "lucide-react";
import React, { useEffect, useState } from "react";
import { authHeaders } from "../utils/api";
import { useAuth } from "../hooks/useAuth";

const CORE_BANKING_URL = import.meta.env.VITE_CORE_BANKING_URL || "https://54agent.upi.dev";

function getDeviceFingerprint() {
  const ua = navigator.userAgent;
  const screen = `${window.screen.width}x${window.screen.height}`;
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const lang = navigator.language;
  const platform = navigator.platform;
  const raw = `${ua}|${screen}|${tz}|${lang}|${platform}`;
  let hash = 0;
  for (let i = 0; i < raw.length; i++) { hash = ((hash << 5) - hash) + raw.charCodeAt(i); hash |= 0; }
  return { hash: Math.abs(hash).toString(16).toUpperCase().padStart(8, "0"), ua, screen, tz, lang, platform };
}

const AgentDeviceFingerprint = () => {
  const { user } = useAuth();
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(false);
  const [registering, setRegistering] = useState(false);
  const [currentFp, setCurrentFp] = useState(null);
  const [isCurrentRegistered, setIsCurrentRegistered] = useState(false);

  useEffect(() => {
    const fp = getDeviceFingerprint();
    setCurrentFp(fp);
    if (user?.keycloakId) fetchDevices(fp);
  }, [user?.keycloakId]);

  const fetchDevices = async (fp) => {
    const keycloakId = user?.keycloakId;
    if (!keycloakId) return;
    setLoading(true);
    try {
      const res = await fetch(`${CORE_BANKING_URL}/agent/api/v1/devices/${keycloakId}`, { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        const devList = Array.isArray(data.devices) ? data.devices : Array.isArray(data) ? data : [];
        setDevices(devList);
        if (fp) setIsCurrentRegistered(devList.some(d => d.fingerprint === fp.hash));
      }
    } catch { setDevices([]); }
    finally { setLoading(false); }
  };

  const registerDevice = async () => {
    if (!currentFp) return;
    setRegistering(true);
    try {
      const keycloakId = user?.keycloakId;
      const res = await fetch(`${CORE_BANKING_URL}/agent/api/v1/devices/${keycloakId}`, {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({
          fingerprint: currentFp.hash,
          user_agent: currentFp.ua,
          screen_resolution: currentFp.screen,
          timezone: currentFp.tz,
          language: currentFp.lang,
          platform: currentFp.platform,
          label: `${currentFp.platform} – ${new Date().toLocaleDateString()}`,
        }),
      });
      if (!res.ok) throw new Error("Device registration failed");
      fetchDevices(currentFp);
    } catch (err) { alert(err.message); }
    finally { setRegistering(false); }
  };

  const removeDevice = async (deviceId) => {
    if (!confirm("Remove this device? You will need to re-register to use it.")) return;
    try {
      const keycloakId = user?.keycloakId;
      await fetch(`${CORE_BANKING_URL}/agent/api/v1/devices/${keycloakId}/${deviceId}`, { method: "DELETE", headers: authHeaders() });
      fetchDevices(currentFp);
    } catch (err) { alert(err.message); }
  };

  return (
    <div className="p-6">
      <div className="max-w-2xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-600/20 rounded-lg"><Shield className="w-6 h-6 text-blue-400" /></div>
          <div>
            <h1 className="text-2xl font-bold">Device Fingerprinting</h1>
            <p className="text-gray-400 text-sm">Manage trusted devices for your account</p>
          </div>
        </div>

        {/* Current Device */}
        {currentFp && (
          <div className={`border rounded-xl p-5 ${isCurrentRegistered ? "border-emerald-700/50 bg-emerald-900/10" : "border-blue-700/50 bg-blue-900/10"}`}>
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-center gap-3">
                <Smartphone className="w-6 h-6 text-blue-400" />
                <div>
                  <div className="flex items-center gap-2">
                    <p className="font-semibold">Current Device</p>
                    {isCurrentRegistered ? (
                      <span className="flex items-center gap-1 text-xs text-emerald-400 px-2 py-0.5 bg-emerald-900/30 rounded-full border border-emerald-700/30">
                        <CheckCircle className="w-3 h-3" /> Trusted
                      </span>
                    ) : (
                      <span className="flex items-center gap-1 text-xs text-amber-400 px-2 py-0.5 bg-amber-900/30 rounded-full border border-amber-700/30">
                        <AlertTriangle className="w-3 h-3" /> Unregistered
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-400 font-mono mt-0.5">FP: {currentFp.hash}</p>
                </div>
              </div>
              {!isCurrentRegistered && (
                <button onClick={registerDevice} disabled={registering}
                  className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 rounded-lg text-xs font-medium transition-colors">
                  {registering ? <RefreshCw className="w-3 h-3 animate-spin" /> : <Plus className="w-3 h-3" />}
                  {registering ? "Registering..." : "Trust This Device"}
                </button>
              )}
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-gray-500">
              <span>Platform: {currentFp.platform}</span>
              <span>Timezone: {currentFp.tz}</span>
              <span>Screen: {currentFp.screen}</span>
              <span>Language: {currentFp.lang}</span>
            </div>
          </div>
        )}

        {/* Security Notice */}
        <div className="flex items-start gap-2 text-xs text-amber-300 bg-amber-900/20 border border-amber-700/30 rounded-lg p-3">
          <Lock className="w-4 h-4 mt-0.5 shrink-0" />
          <span>Transactions from unregistered devices may require additional verification. Only register devices you own and control.</span>
        </div>

        {/* Registered Devices */}
        <div className="bg-gray-100 border border-gray-200 rounded-xl overflow-hidden">
          <div className="flex items-center justify-between p-4 border-b border-gray-200">
            <h3 className="font-medium">Trusted Devices</h3>
            <button onClick={() => fetchDevices(currentFp)} className="text-xs text-blue-400 hover:text-blue-300 flex items-center gap-1">
              <RefreshCw className="w-3 h-3" /> Refresh
            </button>
          </div>
          {loading ? (
            <div className="p-8 text-center text-gray-500"><RefreshCw className="w-5 h-5 animate-spin mx-auto" /></div>
          ) : devices.length === 0 ? (
            <div className="p-10 text-center text-gray-500">
              <Shield className="w-8 h-8 mx-auto mb-2 opacity-30" />
              <p>No trusted devices registered</p>
            </div>
          ) : (
            <ul className="divide-y divide-gray-200">
              {devices.map((device, i) => {
                const isCurrent = device.fingerprint === currentFp?.hash;
                return (
                  <li key={device.id || i} className="flex items-center justify-between p-4">
                    <div className="flex items-center gap-3">
                      <Smartphone className={`w-5 h-5 ${isCurrent ? "text-emerald-400" : "text-gray-400"}`} />
                      <div>
                        <p className="text-sm font-medium">{device.label || `Device ${i + 1}`}{isCurrent && <span className="ml-2 text-xs text-emerald-400">(this device)</span>}</p>
                        <p className="text-xs text-gray-500 font-mono">FP: {device.fingerprint}</p>
                        <p className="text-xs text-gray-600">{device.platform} · Added {new Date(device.created_at || Date.now()).toLocaleDateString()}</p>
                      </div>
                    </div>
                    <button onClick={() => removeDevice(device.id)} className="text-gray-600 hover:text-red-400 transition-colors p-1">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
};

export default AgentDeviceFingerprint;
