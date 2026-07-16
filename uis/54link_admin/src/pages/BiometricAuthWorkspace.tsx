import CrudWorkspace from "@/components/CrudWorkspace";
import { Fingerprint } from "lucide-react";

export default function BiometricAuthWorkspace() {
  return (
    <CrudWorkspace
      config={{
        domainKey: "biometric-auth",
        title: "Biometric Auth",
        subtitle: "Fingerprint, facial, voice, iris biometric authentication (Rust :8189)",
        icon: Fingerprint,
        accentColor: "text-pink-700",
        idField: "id",
        statusField: "auth_result",
        searchFields: ["customer_name", "biometric_type", "device"],
        apiBase: "/api/db/accounts",
        pageSize: 25,
        columns: [
          { key: "id", label: "Record ID" },
          { key: "customer_name", label: "Customer", sortable: true },
          { key: "biometric_type", label: "Type", sortable: true },
          { key: "device", label: "Device", sortable: true },
          { key: "confidence_score", label: "Confidence %", sortable: true },
          { key: "location", label: "Location", sortable: true },
          { key: "auth_result", label: "Result", sortable: true },
          { key: "timestamp", label: "Time", sortable: true },
        ],
        fields: [],
      }}
    />
  );
}
