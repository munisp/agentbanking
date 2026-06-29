import CrudWorkspace from "@/components/CrudWorkspace";
import type { CrudConfig } from "@/components/CrudWorkspace";
import { Landmark } from "lucide-react";

const config: CrudConfig = {
  domainKey: "cbn-agsmeis",
  title: "CBN AGSMEIS Integration",
  subtitle: "Agri-Business SME Investment Scheme loan application workflow",
  icon: Landmark,
  accentColor: "violet",
  apiBase: "/api/db/cbn-agsmeis",
  idField: "id",
  statusField: "status",
  searchFields: ["name"],
  fields: [
    { key: "id", label: "ID", type: "text" },
    { key: "name", label: "Name", type: "text" },
    { key: "category", label: "Type", type: "text" },
    { key: "amount", label: "Amount", type: "number" },
    { key: "status", label: "Status", type: "text" }
  ],
  columns: [
    { key: "id", label: "ID" },
    { key: "name", label: "Name" },
    { key: "category", label: "Scheme" },
    { key: "amount", label: "Amount (NGN)" },
    { key: "region", label: "Region" },
    { key: "status", label: "Status" }
  ],
};

export default function CbnAgsmeisWorkspace() {
  return <CrudWorkspace config={config} />;
}
