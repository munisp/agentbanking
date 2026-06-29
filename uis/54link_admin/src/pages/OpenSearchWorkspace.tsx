import { Search } from "lucide-react";
import CrudWorkspace, { type CrudConfig } from "@/components/CrudWorkspace";

const config: CrudConfig = {
  domainKey: "opensearch-analytics",
  title: "OpenSearch Analytics",
  subtitle: "Full-text search, log aggregation, analytics dashboards, and anomaly alerts",
  icon: Search,
  accentColor: "bg-yellow-600",
  idField: "id",
  statusField: "status",
  searchFields: ["id", "name", "status"],
  apiBase: "/api/db/opensearch-index-configs",
  fields: [
    { key: "name", label: "Index Name", type: "text", required: true, placeholder: "e.g. transactions, audit-logs" },
    { key: "mappings", label: "Mappings (JSON)", type: "text" },
  ],
  columns: [
    { key: "id", label: "Index ID" },
    { key: "name", label: "Name" },
    { key: "docCount", label: "Documents", render: (v) => Number(v).toLocaleString() },
    { key: "sizeBytes", label: "Size", render: (v) => `${(Number(v) / 1048576).toFixed(1)} MB` },
    { key: "status", label: "Health" },
  ],
  actions: [],
};

export default function OpenSearchWorkspace() {
  return <CrudWorkspace config={config} />;
}
