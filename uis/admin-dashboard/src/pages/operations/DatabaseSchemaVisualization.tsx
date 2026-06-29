import { Table2, Search, Download, Key, Link } from "lucide-react";
import React, { useEffect, useState } from "react";
import { getTenantHeadersFromStorage } from "../../services/tenant";

const CORE_URL = import.meta.env.VITE_PLATFORM_MGMT_URL || import.meta.env.VITE_API_URL || "http://localhost:8010";

interface Column {
  name: string;
  type: string;
  nullable: boolean;
  defaultValue: string | null;
  index: boolean;
}

interface ForeignKey {
  column: string;
  referencesTable: string;
  referencesColumn: string;
}

interface TableSchema {
  name: string;
  rowCount: number;
  sizeKB: number;
  columns: Column[];
  foreignKeys: ForeignKey[];
}

const MOCK_TABLES: TableSchema[] = [
  {
    name: "agents", rowCount: 48200, sizeKB: 9840,
    columns: [
      { name: "id", type: "uuid", nullable: false, defaultValue: "gen_random_uuid()", index: true },
      { name: "tenant_id", type: "uuid", nullable: false, defaultValue: null, index: true },
      { name: "phone", type: "varchar(20)", nullable: false, defaultValue: null, index: true },
      { name: "status", type: "varchar(20)", nullable: false, defaultValue: "'active'", index: false },
      { name: "created_at", type: "timestamptz", nullable: false, defaultValue: "now()", index: false },
    ],
    foreignKeys: [{ column: "tenant_id", referencesTable: "tenants", referencesColumn: "id" }],
  },
  {
    name: "transactions", rowCount: 4820000, sizeKB: 1024000,
    columns: [
      { name: "id", type: "uuid", nullable: false, defaultValue: "gen_random_uuid()", index: true },
      { name: "agent_id", type: "uuid", nullable: false, defaultValue: null, index: true },
      { name: "amount", type: "numeric(18,2)", nullable: false, defaultValue: null, index: false },
      { name: "currency", type: "char(3)", nullable: false, defaultValue: "'NGN'", index: false },
      { name: "type", type: "varchar(30)", nullable: false, defaultValue: null, index: true },
      { name: "status", type: "varchar(20)", nullable: false, defaultValue: "'pending'", index: true },
      { name: "created_at", type: "timestamptz", nullable: false, defaultValue: "now()", index: false },
    ],
    foreignKeys: [{ column: "agent_id", referencesTable: "agents", referencesColumn: "id" }],
  },
  {
    name: "kyc_verifications", rowCount: 51000, sizeKB: 20480,
    columns: [
      { name: "id", type: "uuid", nullable: false, defaultValue: "gen_random_uuid()", index: true },
      { name: "agent_id", type: "uuid", nullable: false, defaultValue: null, index: true },
      { name: "document_type", type: "varchar(40)", nullable: false, defaultValue: null, index: false },
      { name: "verified_at", type: "timestamptz", nullable: true, defaultValue: null, index: false },
      { name: "status", type: "varchar(20)", nullable: false, defaultValue: "'pending'", index: false },
    ],
    foreignKeys: [{ column: "agent_id", referencesTable: "agents", referencesColumn: "id" }],
  },
  {
    name: "tenants", rowCount: 12, sizeKB: 48,
    columns: [
      { name: "id", type: "uuid", nullable: false, defaultValue: "gen_random_uuid()", index: true },
      { name: "name", type: "varchar(120)", nullable: false, defaultValue: null, index: false },
      { name: "country_code", type: "char(2)", nullable: false, defaultValue: null, index: false },
      { name: "created_at", type: "timestamptz", nullable: false, defaultValue: "now()", index: false },
    ],
    foreignKeys: [],
  },
];

const DatabaseSchemaVisualization: React.FC = () => {
  const [tables, setTables] = useState<TableSchema[]>([]);
  const [selected, setSelected] = useState<TableSchema | null>(null);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);

  

  useEffect(() => { fetchData(); }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${CORE_URL}/ops/api/v1/schema`, { headers: getTenantHeadersFromStorage() });
      if (res.ok) {
        const d = await res.json();
        const t = Array.isArray(d.tables) ? d.tables : MOCK_TABLES;
        setTables(t);
        setSelected(t[0] ?? null);
      } else { setTables(MOCK_TABLES); setSelected(MOCK_TABLES[0]); }
    } catch { setTables(MOCK_TABLES); setSelected(MOCK_TABLES[0]); }
    finally { setLoading(false); }
  };

  const handleExportDDL = () => {
    if (!selected) return;
    const ddl = `-- DDL for ${selected.name}\nCREATE TABLE ${selected.name} (\n${selected.columns.map(c =>
      `  ${c.name} ${c.type}${c.nullable ? "" : " NOT NULL"}${c.defaultValue ? ` DEFAULT ${c.defaultValue}` : ""}`
    ).join(",\n")}\n);`;
    const blob = new Blob([ddl], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = `${selected.name}.sql`; a.click();
    URL.revokeObjectURL(url);
  };

  const filtered = tables.filter(t => t.name.includes(search));

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Table2 className="w-7 h-7 text-indigo-600" /> Database Schema Viewer
        </h1>
        <p className="text-gray-500 text-sm mt-1">Explore table structures, columns and relationships</p>
      </div>

      <div className="flex gap-4 h-[640px]">
        <div className="w-56 bg-white rounded-xl shadow-sm p-4 flex flex-col gap-3 shrink-0">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-gray-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search tables..."
              className="w-full pl-8 pr-2 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-400" />
          </div>
          <div className="flex-1 overflow-y-auto space-y-1">
            {loading && <p className="text-xs text-gray-400 text-center mt-4">Loading...</p>}
            {filtered.map(t => (
              <button key={t.name} onClick={() => setSelected(t)}
                className={`w-full text-left px-3 py-2 rounded-lg text-xs font-mono transition-colors ${selected?.name === t.name ? "bg-indigo-600 text-white" : "text-gray-700 hover:bg-gray-100"}`}>
                {t.name}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1 bg-white rounded-xl shadow-sm p-6 overflow-y-auto space-y-5">
          {selected ? (
            <>
              <div className="flex items-center justify-between flex-wrap gap-3">
                <div>
                  <h2 className="font-bold text-gray-900 font-mono text-lg">{selected.name}</h2>
                  <p className="text-xs text-gray-500 mt-0.5">{selected.rowCount.toLocaleString()} rows · {selected.sizeKB.toLocaleString()} KB</p>
                </div>
                <button onClick={handleExportDDL} className="flex items-center gap-2 text-xs px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg font-medium">
                  <Download className="w-3.5 h-3.5" /> Export DDL
                </button>
              </div>

              <div>
                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-1"><Key className="w-3 h-3" /> Columns</h3>
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-gray-100">
                      {["Column", "Type", "Nullable", "Default", "Index"].map(h => (
                        <th key={h} className="text-left py-2 px-2 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {selected.columns.map(col => (
                      <tr key={col.name} className="border-b border-gray-50 hover:bg-gray-50">
                        <td className="py-1.5 px-2 font-mono font-medium text-gray-800">{col.name}</td>
                        <td className="py-1.5 px-2 text-indigo-600 font-mono">{col.type}</td>
                        <td className="py-1.5 px-2">{col.nullable ? <span className="text-amber-600">YES</span> : <span className="text-gray-400">NO</span>}</td>
                        <td className="py-1.5 px-2 text-gray-500 font-mono">{col.defaultValue ?? "—"}</td>
                        <td className="py-1.5 px-2">{col.index ? <span className="text-emerald-600 font-semibold">IDX</span> : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {selected.foreignKeys.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2 flex items-center gap-1"><Link className="w-3 h-3" /> Foreign Keys</h3>
                  <div className="space-y-1.5">
                    {selected.foreignKeys.map(fk => (
                      <div key={fk.column} className="bg-gray-50 rounded-lg px-3 py-2 text-xs flex items-center gap-2">
                        <span className="font-mono font-medium text-gray-800">{fk.column}</span>
                        <span className="text-gray-400">→</span>
                        <span className="font-mono text-indigo-600">{fk.referencesTable}.{fk.referencesColumn}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="flex items-center justify-center h-full text-gray-400 text-sm">Select a table</div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DatabaseSchemaVisualization;
