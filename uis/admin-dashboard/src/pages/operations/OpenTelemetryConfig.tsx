import { Radio, Activity, FileText, RefreshCw, CheckCircle, XCircle, Zap } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_PLATFORM_MGMT_URL || import.meta.env.VITE_API_URL || "http://localhost:8010";

interface OtelSummary {
  tracesEnabled: boolean;
  tracesExporter: string;
  samplingRate: number;
  metricsEnabled: boolean;
  scrapeIntervalSeconds: number;
  logsEnabled: boolean;
  logLevel: string;
}

interface ExporterConfig {
  name: string;
  type: "OTLP" | "Jaeger" | "Prometheus";
  endpoint: string;
  status: "active" | "error";
}

interface InstrumentedService {
  service: string;
  traceVolume: number;
}

const MOCK_SUMMARY: OtelSummary = {
  tracesEnabled: true, tracesExporter: "https://otel.54agent.upi.dev:4317", samplingRate: 10,
  metricsEnabled: true, scrapeIntervalSeconds: 15,
  logsEnabled: true, logLevel: "info",
};

const MOCK_EXPORTERS: ExporterConfig[] = [
  { name: "primary-otlp", type: "OTLP", endpoint: "https://otel.54agent.upi.dev:4317", status: "active" },
  { name: "jaeger-tracing", type: "Jaeger", endpoint: "http://jaeger.internal:14268/api/traces", status: "active" },
  { name: "prometheus-metrics", type: "Prometheus", endpoint: "http://prometheus.internal:9090/metrics", status: "active" },
  { name: "backup-otlp", type: "OTLP", endpoint: "https://backup-otel.54agent.upi.dev:4317", status: "error" },
];

const MOCK_SERVICES: InstrumentedService[] = [
  { service: "core-banking-api", traceVolume: 142000 },
  { service: "agent-service", traceVolume: 88400 },
  { service: "kyc-service", traceVolume: 21300 },
  { service: "notification-service", traceVolume: 64800 },
  { service: "settlement-worker", traceVolume: 9200 },
  { service: "webhook-dispatcher", traceVolume: 18700 },
];

const EXPORTER_TYPE_STYLES: Record<string, string> = {
  OTLP: "bg-blue-100 text-blue-700",
  Jaeger: "bg-purple-100 text-purple-700",
  Prometheus: "bg-orange-100 text-orange-700",
};

const OpenTelemetryConfig: React.FC = () => {
  const [summary, setSummary] = useState<OtelSummary>(MOCK_SUMMARY);
  const [exporters, setExporters] = useState<ExporterConfig[]>([]);
  const [services, setServices] = useState<InstrumentedService[]>([]);
  const [loading, setLoading] = useState(false);
  const [testingExporter, setTestingExporter] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, string>>({});

  

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/ops/api/v1/otel-config`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) {
        const d = await res.json();
        setSummary(d.summary ?? MOCK_SUMMARY);
        setExporters(Array.isArray(d.exporters) ? d.exporters : MOCK_EXPORTERS);
        setServices(Array.isArray(d.services) ? d.services : MOCK_SERVICES);
      } else { setSummary(MOCK_SUMMARY); setExporters(MOCK_EXPORTERS); setServices(MOCK_SERVICES); }
    } catch { setSummary(MOCK_SUMMARY); setExporters(MOCK_EXPORTERS); setServices(MOCK_SERVICES); }
    finally { setLoading(false); }
  };

  const handleTestConnection = async (exporterName: string) => {
    setTestingExporter(exporterName);
    try {
      const res = await fetch(`${CORE_URL}/ops/api/v1/otel-config/exporters/${exporterName}/test`, {
        method: "POST",
        headers: getTenantHeadersFromStorage(),
      });
      const result = res.ok ? "Connection OK" : "Connection failed";
      setTestResults(prev => ({ ...prev, [exporterName]: result }));
    } catch { setTestResults(prev => ({ ...prev, [exporterName]: "Unreachable (demo)" })); }
    finally { setTestingExporter(null); }
  };

  const maxVolume = Math.max(...services.map(s => s.traceVolume), 1);

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Radio className="w-7 h-7 text-indigo-600" /> OpenTelemetry Config
          </h1>
          <p className="text-gray-500 text-sm mt-1">Observability pipeline: traces, metrics and logs</p>
        </div>
        <button onClick={fetchData} disabled={loading} className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium disabled:opacity-60">
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl shadow-sm p-6 space-y-2">
          <div className="flex items-center gap-2 mb-1">
            <Activity className="w-4 h-4 text-indigo-500" />
            <h3 className="font-semibold text-gray-800 text-sm">Traces</h3>
            <span className={`ml-auto text-xs px-2 py-0.5 rounded-full font-medium ${summary.tracesEnabled ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-500"}`}>
              {summary.tracesEnabled ? "Enabled" : "Disabled"}
            </span>
          </div>
          <p className="text-xs text-gray-500">Exporter</p>
          <p className="text-xs font-mono text-gray-700 truncate">{summary.tracesExporter}</p>
          <p className="text-xs text-gray-500">Sampling Rate <span className="font-semibold text-indigo-600">{summary.samplingRate}%</span></p>
        </div>
        <div className="bg-white rounded-xl shadow-sm p-6 space-y-2">
          <div className="flex items-center gap-2 mb-1">
            <Zap className="w-4 h-4 text-amber-500" />
            <h3 className="font-semibold text-gray-800 text-sm">Metrics</h3>
            <span className={`ml-auto text-xs px-2 py-0.5 rounded-full font-medium ${summary.metricsEnabled ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-500"}`}>
              {summary.metricsEnabled ? "Enabled" : "Disabled"}
            </span>
          </div>
          <p className="text-xs text-gray-500">Scrape Interval <span className="font-semibold text-amber-600">{summary.scrapeIntervalSeconds}s</span></p>
        </div>
        <div className="bg-white rounded-xl shadow-sm p-6 space-y-2">
          <div className="flex items-center gap-2 mb-1">
            <FileText className="w-4 h-4 text-blue-500" />
            <h3 className="font-semibold text-gray-800 text-sm">Logs</h3>
            <span className={`ml-auto text-xs px-2 py-0.5 rounded-full font-medium ${summary.logsEnabled ? "bg-emerald-100 text-emerald-700" : "bg-gray-100 text-gray-500"}`}>
              {summary.logsEnabled ? "Enabled" : "Disabled"}
            </span>
          </div>
          <p className="text-xs text-gray-500">Log Level <span className="font-semibold text-blue-600 uppercase">{summary.logLevel}</span></p>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold text-gray-900 mb-4">Exporter Configurations</h2>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100">
                {["Name", "Type", "Endpoint", "Status", "Action"].map(h => (
                  <th key={h} className="text-left py-2 px-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {exporters.map(exp => (
                <tr key={exp.name} className="border-b border-gray-50 hover:bg-gray-50">
                  <td className="py-2 px-3 font-mono text-gray-800 text-xs">{exp.name}</td>
                  <td className="py-2 px-3">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${EXPORTER_TYPE_STYLES[exp.type]}`}>{exp.type}</span>
                  </td>
                  <td className="py-2 px-3 text-gray-500 text-xs font-mono max-w-[200px] truncate">{exp.endpoint}</td>
                  <td className="py-2 px-3">
                    {exp.status === "active"
                      ? <span className="flex items-center gap-1 text-xs text-emerald-600"><CheckCircle className="w-3 h-3" /> Active</span>
                      : <span className="flex items-center gap-1 text-xs text-red-600"><XCircle className="w-3 h-3" /> Error</span>}
                  </td>
                  <td className="py-2 px-3">
                    <div className="flex items-center gap-2">
                      <button onClick={() => handleTestConnection(exp.name)} disabled={testingExporter === exp.name}
                        className="text-xs px-3 py-1.5 bg-indigo-50 text-indigo-600 hover:bg-indigo-100 rounded-lg font-medium disabled:opacity-60">
                        {testingExporter === exp.name ? "Testing..." : "Test"}
                      </button>
                      {testResults[exp.name] && (
                        <span className={`text-xs ${testResults[exp.name].includes("OK") ? "text-emerald-600" : "text-red-600"}`}>{testResults[exp.name]}</span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm p-6">
        <h2 className="font-semibold text-gray-900 mb-4">Instrumented Services — Trace Volume</h2>
        <div className="space-y-3">
          {services.map(svc => (
            <div key={svc.service}>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="font-mono font-medium text-gray-700">{svc.service}</span>
                <span className="text-gray-500">{svc.traceVolume.toLocaleString()} spans/day</span>
              </div>
              <div className="w-full bg-gray-100 rounded-full h-2">
                <div className="bg-indigo-500 h-2 rounded-full" style={{ width: `${(svc.traceVolume / maxVolume) * 100}%` }} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default OpenTelemetryConfig;
