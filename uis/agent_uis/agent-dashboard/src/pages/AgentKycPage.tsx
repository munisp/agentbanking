import DashboardLayout from "@/components/DashboardLayout";
import { useState } from "react";

import { trpc } from "@/lib/trpc";
export default function AgentKycPage() {
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [showSubmitForm, setShowSubmitForm] = useState(false);

  const profiles = [
    {
      agentId: "AGT-001",
      name: "Adebayo Okonkwo",
      kycLevel: 2,
      status: "complete",
      risk: 15,
      docs: 2,
      verified: 2,
    },
    {
      agentId: "AGT-002",
      name: "Fatima Bello",
      kycLevel: 1,
      status: "basic",
      risk: 40,
      docs: 1,
      verified: 1,
    },
    {
      agentId: "AGT-003",
      name: "James Mwangi",
      kycLevel: 1,
      status: "basic",
      risk: 35,
      docs: 1,
      verified: 1,
    },
    {
      agentId: "AGT-004",
      name: "Amina Diallo",
      kycLevel: 0,
      status: "incomplete",
      risk: 80,
      docs: 1,
      verified: 0,
    },
    {
      agentId: "AGT-005",
      name: "Kwame Asante",
      kycLevel: 0,
      status: "incomplete",
      risk: 90,
      docs: 0,
      verified: 0,
    },
  ];

  const documents: Record<
    string,
    {
      docId: string;
      type: string;
      number: string;
      status: string;
      confidence: number;
    }[]
  > = {
    "AGT-001": [
      {
        docId: "DOC-001A",
        type: "NIN",
        number: "123****8901",
        status: "verified",
        confidence: 95,
      },
      {
        docId: "DOC-001B",
        type: "BVN",
        number: "223****8901",
        status: "verified",
        confidence: 98,
      },
    ],
    "AGT-002": [
      {
        docId: "DOC-002A",
        type: "NIN",
        number: "987****2101",
        status: "verified",
        confidence: 95,
      },
    ],
    "AGT-003": [
      {
        docId: "DOC-003A",
        type: "Passport",
        number: "A****5678",
        status: "verified",
        confidence: 90,
      },
    ],
    "AGT-004": [
      {
        docId: "DOC-004A",
        type: "NIN",
        number: "INVALID",
        status: "rejected",
        confidence: 0,
      },
    ],
  };

  const levelColor: Record<number, string> = {
    0: "text-red-400",
    1: "text-yellow-400",
    2: "text-green-400",
    3: "text-blue-400",
  };
  const statusBg: Record<string, string> = {
    verified: "bg-green-900 text-green-300",
    rejected: "bg-red-900 text-red-300",
    pending: "bg-yellow-900 text-yellow-300",
    manual_review: "bg-blue-900 text-blue-300",
  };
  // Sprint 87: Wired to kycDocumentManagement router
  const { data, isLoading } = trpc.kycDocumentManagement.list.useQuery({
    page: 1,
    limit: 10,
  });

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-white">
            Agent KYC Verification
          </h1>
          <button
            onClick={() => setShowSubmitForm(!showSubmitForm)}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-500"
          >
            + Submit Document
          </button>
        </div>

        <div className="grid grid-cols-5 gap-4">
          <div className="bg-gray-800 rounded p-4 text-center">
            <div className="text-2xl font-bold text-white">
              {profiles.length}
            </div>
            <div className="text-gray-400 text-sm">Total Agents</div>
          </div>
          <div className="bg-gray-800 rounded p-4 text-center">
            <div className="text-2xl font-bold text-green-400">
              {profiles.filter(p => p.status === "complete").length}
            </div>
            <div className="text-gray-400 text-sm">KYC Complete</div>
          </div>
          <div className="bg-gray-800 rounded p-4 text-center">
            <div className="text-2xl font-bold text-yellow-400">
              {profiles.filter(p => p.status === "basic").length}
            </div>
            <div className="text-gray-400 text-sm">Basic KYC</div>
          </div>
          <div className="bg-gray-800 rounded p-4 text-center">
            <div className="text-2xl font-bold text-red-400">
              {profiles.filter(p => p.status === "incomplete").length}
            </div>
            <div className="text-gray-400 text-sm">Incomplete</div>
          </div>
          <div className="bg-gray-800 rounded p-4 text-center">
            <div className="text-2xl font-bold text-blue-400">80%</div>
            <div className="text-gray-400 text-sm">Verification Rate</div>
          </div>
        </div>

        <div className="bg-gray-800 rounded overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-700">
              <tr>
                <th className="text-left p-3 text-gray-300 text-sm">Agent</th>
                <th className="text-left p-3 text-gray-300 text-sm">Name</th>
                <th className="text-center p-3 text-gray-300 text-sm">
                  KYC Level
                </th>
                <th className="text-center p-3 text-gray-300 text-sm">
                  Status
                </th>
                <th className="text-center p-3 text-gray-300 text-sm">
                  Risk Score
                </th>
                <th className="text-center p-3 text-gray-300 text-sm">
                  Documents
                </th>
                <th className="text-center p-3 text-gray-300 text-sm">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {profiles.map(p => (
                <tr
                  key={p.agentId}
                  className="border-t border-gray-700 hover:bg-gray-750"
                >
                  <td className="p-3 text-white font-mono text-sm">
                    {p.agentId}
                  </td>
                  <td className="p-3 text-white">{p.name}</td>
                  <td
                    className={`p-3 text-center font-bold ${levelColor[p.kycLevel]}`}
                  >
                    Level {p.kycLevel}
                  </td>
                  <td className="p-3 text-center">
                    <span
                      className={`px-2 py-1 rounded text-xs ${p.status === "complete" ? "bg-green-900 text-green-300" : p.status === "basic" ? "bg-yellow-900 text-yellow-300" : "bg-red-900 text-red-300"}`}
                    >
                      {p.status}
                    </span>
                  </td>
                  <td
                    className={`p-3 text-center ${p.risk > 60 ? "text-red-400" : p.risk > 30 ? "text-yellow-400" : "text-green-400"}`}
                  >
                    {p.risk}
                  </td>
                  <td className="p-3 text-center text-gray-300">
                    {p.verified}/{p.docs}
                  </td>
                  <td className="p-3 text-center">
                    <button
                      onClick={() =>
                        setSelectedAgent(
                          selectedAgent === p.agentId ? null : p.agentId
                        )
                      }
                      className="px-3 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-500"
                    >
                      {selectedAgent === p.agentId ? "Hide" : "View"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {selectedAgent && documents[selectedAgent] && (
          <div className="bg-gray-800 rounded p-4">
            <h3 className="text-lg font-semibold text-white mb-3">
              Documents for {selectedAgent}
            </h3>
            <div className="space-y-2">
              {documents[selectedAgent].map(doc => (
                <div
                  key={doc.docId}
                  className="flex items-center justify-between bg-gray-700 rounded p-3"
                >
                  <div>
                    <span className="text-white font-mono text-sm">
                      {doc.docId}
                    </span>
                    <span className="text-gray-400 ml-3">
                      {doc.type}: {doc.number}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-gray-400 text-sm">
                      Confidence: {doc.confidence}%
                    </span>
                    <span
                      className={`px-2 py-1 rounded text-xs ${statusBg[doc.status] || "bg-gray-600 text-gray-300"}`}
                    >
                      {doc.status}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
