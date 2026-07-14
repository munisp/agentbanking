import { Database } from "lucide-react";
import CrudWorkspace, { type CrudConfig } from "@/components/CrudWorkspace";

const config: CrudConfig = {
  domainKey: "lakehouse",
  title: "Data Lakehouse",
  subtitle: "Delta Lake-style versioned datasets, SQL queries, ETL pipelines, and data ingestion",
  icon: Database,
  accentColor: "bg-emerald-700",
  idField: "id",
  statusField: "status",
  searchFields: ["id", "name", "schema_name", "format"],
  apiBase: "/api/db/avro-schemas",
  fields: [
    { key: "name", label: "Dataset Name", type: "text", required: true },
    { key: "schema_name", label: "Schema", type: "select", options: ["bronze", "silver", "gold"], defaultValue: "bronze" },
    { key: "format", label: "Format", type: "select", options: ["delta", "parquet", "iceberg"], defaultValue: "delta" },
    { key: "retention_days", label: "Retention (days)", type: "number", defaultValue: 90 },
  ],
  columns: [
    { key: "id", label: "Dataset ID" },
    { key: "name", label: "Name" },
    { key: "schema_name", label: "Schema" },
    { key: "format", label: "Format" },
    { key: "row_count", label: "Rows", render: (v) => Number(v).toLocaleString() },
    { key: "size_bytes", label: "Size", render: (v) => `${(Number(v) / 1073741824).toFixed(1)} GB` },
    { key: "status", label: "Status" },
  ],
  actions: [],
};

export default function LakehouseWorkspace() {
  return <CrudWorkspace config={config} />;
}
