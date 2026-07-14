import { FileText } from "lucide-react";
import CrudWorkspace from "@/components/CrudWorkspace";
import type { CrudConfig } from "@/components/CrudWorkspace";

const config: CrudConfig = {
  domainKey: "cbn-returns",
  title: "CBN Regulatory Returns",
  subtitle: "All Nigerian regulatory returns — CBN eFASS, NDIC, FIRS VAT, CTR/STR, Basel III",
  icon: FileText,
  accentColor: "red",
  fields: [
    { key: "id", label: "Return ID", type: "readonly" },
    { key: "code", label: "Code", type: "readonly" },
    { key: "name", label: "Return Name", type: "readonly" },
  ],
  columns: [
    { key: "id", label: "Return ID" },
    { key: "code", label: "Code" },
    { key: "name", label: "Return Name" },
    { key: "regulator", label: "Regulator" },
    { key: "frequency", label: "Frequency" },
    { key: "status", label: "Status" },
    { key: "dueDate", label: "Due Date" },
  ],
  idField: "id",
  searchFields: ["id", "code", "name", "regulator"],
  apiBase: "/api/db/regulatory-reports",
};

export default function CBNReturnsWorkspace() {
  return <CrudWorkspace config={config} />;
}
