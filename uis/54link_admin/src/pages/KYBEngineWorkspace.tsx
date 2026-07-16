import CrudWorkspace from "@/components/CrudWorkspace";
import type { CrudConfig } from "@/components/CrudWorkspace";
import { Building2 } from "lucide-react";

const config: CrudConfig = {
  domainKey: "kyb-engine",
  title: "KYB Verification Engine",
  subtitle: "CAC registry verification, UBO identification (>25% threshold), director screening, Docling financial statement parsing",
  icon: Building2,
  accentColor: "amber",
  fields: [
    { key: "company_name", label: "Company Name", type: "text", required: true },
    { key: "rc_number", label: "RC Number", type: "text", required: true },
    { key: "tin", label: "Tax ID (TIN)", type: "text" },
  ],
  columns: [
    { key: "id", label: "KYB ID", sortable: true },
    { key: "companyName", label: "Company", sortable: true },
    { key: "rcNumber", label: "RC Number" },
    { key: "companyType", label: "Type", sortable: true },
    { key: "cacVerified", label: "CAC Verified" },
    { key: "sanctionsClean", label: "Sanctions Clean" },
    { key: "pepExposure", label: "PEP Exposure" },
    { key: "riskScore", label: "Risk Score", sortable: true },
    { key: "riskLevel", label: "Risk Level", sortable: true },
    { key: "status", label: "Status", sortable: true },
  ],
  idField: "id",
  statusField: "status",
  searchFields: ["companyName", "rcNumber", "tin", "status"],
  apiBase: "/api/db/accounts",
  pageSize: 25,
};

export default function KYBEngineWorkspace() {
  return <CrudWorkspace config={config} />;
}
