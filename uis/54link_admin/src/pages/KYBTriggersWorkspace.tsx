import CrudWorkspace from "@/components/CrudWorkspace";
import type { CrudConfig } from "@/components/CrudWorkspace";
import { Building2 } from "lucide-react";

const config: CrudConfig = {
  domainKey: "kyb-triggers",
  title: "KYB Triggers",
  subtitle: "Admin-initiated and event-driven KYB (Know Your Business) verification triggers for corporate clients",
  icon: Building2,
  accentColor: "amber",
  fields: [
    { key: "companyName", label: "Company Name", type: "text", required: true },
    { key: "rcNumber", label: "RC Number", type: "text", required: true },
    { key: "priority", label: "Priority", type: "select", options: ["low", "normal", "high", "urgent"] },
    { key: "notes", label: "Notes", type: "text" },
  ],
  columns: [
    { key: "id", label: "Trigger ID", sortable: true },
    { key: "companyName", label: "Company", sortable: true },
    { key: "rcNumber", label: "RC Number", sortable: true },
    { key: "triggerType", label: "Trigger Type", sortable: true },
    { key: "triggerSource", label: "Source", sortable: true },
    { key: "status", label: "Status", sortable: true },
    { key: "result", label: "Result", sortable: true },
    { key: "priority", label: "Priority", sortable: true },
    { key: "requestedBy", label: "Requested By" },
  ],
  idField: "id",
  statusField: "status",
  searchFields: ["companyName", "rcNumber", "triggerType", "status"],
  apiBase: "/api/db/accounts",
  pageSize: 25,
  actions: [
    { label: "Re-verify", key: "re-verify", condition: (r) => r.status === "completed" },
    { label: "Cancel", key: "cancel", condition: (r) => r.status === "pending" },
  ],
};

export default function KYBTriggersWorkspace() {
  return <CrudWorkspace config={config} />;
}
