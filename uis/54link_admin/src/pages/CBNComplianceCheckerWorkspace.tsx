import CrudWorkspace from "@/components/CrudWorkspace";
import type { CrudConfig } from "@/components/CrudWorkspace";
import { FileCheck } from "lucide-react";

const config: CrudConfig = {
  domainKey: "cbn-compliance",
  title: "CBN Compliance",
  subtitle: "CBN security circular compliance",
  icon: FileCheck,
  accentColor: "green",
  apiBase: "/api/db/cbn-compliance",
  idField: "id",
  statusField: "status",
  searchFields: ["circular"],
  fields: [
    { key: "circular", label: "Circular", type: "text" },
    { key: "title", label: "Title", type: "text" },
    { key: "complianceScore", label: "Score", type: "number" },
    { key: "status", label: "Status", type: "text" }
  ],
  columns: [
    { key: "circular", label: "Circular" },
    { key: "title", label: "Title" },
    { key: "complianceScore", label: "Score" },
    { key: "status", label: "Status" }
  ],
};

export default function CBNComplianceCheckerWorkspace() {
  return <CrudWorkspace config={config} />;
}
