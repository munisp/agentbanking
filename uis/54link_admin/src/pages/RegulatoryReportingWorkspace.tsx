import CrudWorkspace from "@/components/CrudWorkspace";
import type { CrudConfig } from "@/components/CrudWorkspace";
import { FileText } from "lucide-react";

const config: CrudConfig = {
  domainKey: "regulatory-reporting",
  title: "Regulatory Reporting",
  subtitle: "CBN, NFIU, NDIC regulatory filing and compliance reporting",
  icon: FileText,
  accentColor: "blue",
  apiBase: "/api/db/regulatoryReports",
  idField: "id",
  statusField: "status",
  searchFields: ["reportType"],
  fields: [
    { key: "reportType", label: "Report Type", type: "text" },
    { key: "filingPeriod", label: "Period", type: "text" },
    { key: "regulator", label: "Regulator", type: "text" },
    { key: "status", label: "Status", type: "text" },
  ],
  columns: [
    { key: "reportType", label: "Report Type" },
    { key: "filingPeriod", label: "Period" },
    { key: "regulator", label: "Regulator" },
    { key: "status", label: "Status" },
  ],
};

export default function RegulatoryReportingWorkspace() {
  return <CrudWorkspace config={config} />;
}
