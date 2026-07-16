import CrudWorkspace from "@/components/CrudWorkspace";
import { Heart } from "lucide-react";

export default function InsuranceWorkspace() {
  return (
    <CrudWorkspace
      config={{
        domainKey: "insurance",
        title: "Bancassurance",
        subtitle: "Life, property, health, motor, travel insurance (Python :8194)",
        icon: Heart,
        accentColor: "text-rose-800",
        idField: "id",
        statusField: "status",
        searchFields: ["product_name", "policy_type", "customer_name"],
        apiBase: "/api/db/accounts",
        pageSize: 25,
        columns: [
          { key: "id", label: "Policy ID" },
          { key: "policy_type", label: "Type", sortable: true },
          { key: "product_name", label: "Product", sortable: true },
          { key: "customer_name", label: "Customer", sortable: true },
          { key: "premium_amount", label: "Premium", sortable: true, render: (v) => `₦${Number(v).toLocaleString()}` },
          { key: "sum_assured", label: "Sum Assured", sortable: true, render: (v) => `₦${Number(v).toLocaleString()}` },
          { key: "start_date", label: "Start", sortable: true },
          { key: "status", label: "Status", sortable: true },
        ],
        fields: [],
      }}
    />
  );
}
