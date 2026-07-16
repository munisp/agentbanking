import CrudWorkspace from "@/components/CrudWorkspace";
import type { CrudConfig } from "@/components/CrudWorkspace";
import { Landmark } from "lucide-react";

const config: CrudConfig = {
  domainKey: "cbn-anchor-borrowers",
  title: "CBN Anchor Borrowers Programme",
  subtitle: "ABP application flow: farmer to cooperative to anchor to PFI to CBN",
  icon: Landmark,
  accentColor: "indigo",
  apiBase: "/api/db/cbn-anchor-borrowers",
  idField: "id",
  statusField: "status",
  searchFields: ["name"],
  fields: [
    { key: "id", label: "ID", type: "text" },
    { key: "name", label: "Programme", type: "text" },
    { key: "category", label: "Category", type: "text" },
    { key: "amount", label: "Amount", type: "number" },
    { key: "region", label: "Region", type: "text" },
    { key: "status", label: "Status", type: "text" }
  ],
  columns: [
    { key: "id", label: "ID" },
    { key: "name", label: "Programme" },
    { key: "category", label: "Anchor Type" },
    { key: "amount", label: "Amount (NGN)" },
    { key: "region", label: "Region" },
    { key: "status", label: "Status" }
  ],
};

export default function CbnAnchorBorrowersWorkspace() {
  return <CrudWorkspace config={config} />;
}
