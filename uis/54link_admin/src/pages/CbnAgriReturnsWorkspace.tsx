import CrudWorkspace from "@/components/CrudWorkspace";
import type { CrudConfig } from "@/components/CrudWorkspace";
import { FileText } from "lucide-react";

const config: CrudConfig = {
  domainKey: "cbn-agri-returns",
  title: "CBN Agricultural Returns",
  subtitle: "Automated quarterly CBN agricultural lending portfolio returns",
  icon: FileText,
  accentColor: "gray",
  apiBase: "/api/db/cbn-agri-returns",
  idField: "id",
  statusField: "status",
  searchFields: ["name"],
  fields: [
    { key: "id", label: "ID", type: "text" },
    { key: "name", label: "Name", type: "text" },
    { key: "category", label: "Type", type: "text" },
    { key: "status", label: "Status", type: "text" }
  ],
  columns: [
    { key: "id", label: "ID" },
    { key: "name", label: "Name" },
    { key: "category", label: "Return Type" },
    { key: "amount", label: "Amount" },
    { key: "region", label: "Region" },
    { key: "status", label: "Status" }
  ],
};

export default function CbnAgriReturnsWorkspace() {
  return <CrudWorkspace config={config} />;
}
