import CrudWorkspace from "@/components/CrudWorkspace";
import { CreditCard } from "lucide-react";

export default function CardManagementWorkspace2() {
  return (
    <CrudWorkspace
      config={{
        domainKey: "card-management-v2",
        title: "Card Management",
        subtitle: "Card issuance, blocking, PIN management, tokenization, international toggle, and replacement workflows",
        icon: CreditCard,
        accentColor: "text-indigo-600",
        idField: "id",
        statusField: "status",
        searchFields: ["id", "customerName", "maskedPAN", "accountNumber"],
        apiBase: "/api/db/customer-cards",
        pageSize: 25,
        columns: [
          { key: "id", label: "Card ID", sortable: true },
          { key: "maskedPAN", label: "PAN" },
          { key: "customerName", label: "Customer", sortable: true },
          { key: "cardType", label: "Type", sortable: true },
          { key: "scheme", label: "Scheme" },
          { key: "dailyLimit", label: "Daily Limit", sortable: true, render: (v) => `₦${Number(v).toLocaleString()}` },
          { key: "internationalEnabled", label: "Int'l" },
          { key: "tokenizedDevices", label: "Tokens" },
          { key: "expiryDate", label: "Expiry" },
          { key: "status", label: "Status" },
        ],
        fields: [
          { key: "accountNumber", label: "Account Number", type: "text", required: true },
          { key: "customerName", label: "Customer Name", type: "text", required: true },
          { key: "cardType", label: "Card Type", type: "select", options: ["debit", "credit", "prepaid"], required: true },
          { key: "scheme", label: "Scheme", type: "select", options: ["visa", "mastercard", "verve"], required: true },
        ],
      }}
    />
  );
}
