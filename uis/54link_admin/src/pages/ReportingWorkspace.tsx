import CrudWorkspace from "@/components/CrudWorkspace";
import { FileBarChart } from "lucide-react";

export default function ReportingWorkspace() {
  return (
    <CrudWorkspace
      config={{
        domainKey: "reporting-engine",
        title: "Reporting Engine",
        subtitle: "Regulatory returns (CBN, NDIC, FIRS), management reports, and operational dashboards",
        icon: FileBarChart,
        accentColor: "text-teal-600",
        idField: "id",
        statusField: "status",
        searchFields: ["name", "category", "frequency", "description"],
        apiBase: "/api/db/regulatory-reports",
        pageSize: 25,
        columns: [
          { key: "id", label: "ID", sortable: true },
          { key: "name", label: "Report Name", sortable: true },
          { key: "category", label: "Category", sortable: true },
          { key: "frequency", label: "Frequency", sortable: true },
          { key: "lastGenerated", label: "Last Generated" },
          { key: "nextDue", label: "Next Due" },
          { key: "status", label: "Status" },
        ],
        fields: [
          { key: "name", label: "Report Name", type: "text", required: true },
          { key: "category", label: "Category", type: "select", options: ["regulatory", "management", "operational", "custom"], required: true },
          { key: "frequency", label: "Frequency", type: "select", options: ["daily", "weekly", "monthly", "quarterly", "annual", "on_demand"], required: true },
          { key: "description", label: "Description", type: "text" },
        ],
      }}
    />
  );
}
