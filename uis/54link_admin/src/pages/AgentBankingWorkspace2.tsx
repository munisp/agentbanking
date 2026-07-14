import CrudWorkspace from "@/components/CrudWorkspace";
import { MapPin } from "lucide-react";

export default function AgentBankingWorkspace2() {
  return (
    <CrudWorkspace
      config={{
        domainKey: "agent-banking-v2",
        title: "Agent Banking",
        subtitle: "Agent onboarding, float management, transaction processing, commission tracking, and suspension workflows",
        icon: MapPin,
        accentColor: "text-amber-600",
        idField: "id",
        statusField: "status",
        searchFields: ["id", "businessName", "ownerName", "state"],
        apiBase: "/api/db/agent-banking-agents",
        pageSize: 25,
        columns: [
          { key: "id", label: "Agent ID", sortable: true },
          { key: "businessName", label: "Business Name", sortable: true },
          { key: "ownerName", label: "Owner" },
          { key: "location", label: "Location" },
          { key: "state", label: "State", sortable: true },
          { key: "tier", label: "Tier" },
          { key: "floatBalance", label: "Float", sortable: true, render: (v) => `₦${Number(v).toLocaleString()}` },
          { key: "commissionEarned", label: "Commission", sortable: true, render: (v) => `₦${Number(v).toLocaleString()}` },
          { key: "transactionCount", label: "Txn Count", sortable: true },
          { key: "status", label: "Status" },
        ],
        fields: [
          { key: "businessName", label: "Business Name", type: "text", required: true },
          { key: "ownerName", label: "Owner Name", type: "text", required: true },
          { key: "location", label: "Location", type: "text", required: true },
          { key: "lga", label: "LGA", type: "text" },
          { key: "state", label: "State", type: "text", required: true },
        ],
      }}
    />
  );
}
