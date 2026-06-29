import {
    Building2,
    ChevronDown,
    ChevronRight,
    Search,
    Store,
    TrendingUp,
    User,
    Users,
} from "lucide-react";
import React, { useState } from "react";

const HierarchyManagement = () => {
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedNodes, setExpandedNodes] = useState<number[]>([1]);

  const stats = [
    { label: "Total Agents", value: "1,245", icon: Users, color: "blue" },
    { label: "Total Customers", value: "45,890", icon: User, color: "green" },
    { label: "Active Stores", value: "3,567", icon: Store, color: "purple" },
    { label: "Hierarchy Levels", value: "4", icon: Building2, color: "orange" },
  ];

  const hierarchyData = [
    {
      id: 1,
      type: "region",
      name: "Lagos Region",
      agents: 450,
      customers: 18500,
      revenue: "₦85M",
      children: [
        {
          id: 11,
          type: "area",
          name: "Ikeja Area",
          agents: 180,
          customers: 7200,
          revenue: "₦35M",
          children: [
            {
              id: 111,
              type: "agent",
              name: "Agent AG42385 - Tani Store",
              customers: 420,
              revenue: "₦2.5M",
            },
            {
              id: 112,
              type: "agent",
              name: "Agent AG12345 - John Stores",
              customers: 380,
              revenue: "₦2.1M",
            },
            {
              id: 113,
              type: "agent",
              name: "Agent AG67890 - Grace Mart",
              customers: 350,
              revenue: "₦1.9M",
            },
          ],
        },
        {
          id: 12,
          type: "area",
          name: "Lekki Area",
          agents: 150,
          customers: 6000,
          revenue: "₦28M",
          children: [
            {
              id: 121,
              type: "agent",
              name: "Agent AG24680 - Lekki Express",
              customers: 520,
              revenue: "₦3.2M",
            },
            {
              id: 122,
              type: "agent",
              name: "Agent AG13579 - Peace Stores",
              customers: 440,
              revenue: "₦2.8M",
            },
          ],
        },
        {
          id: 13,
          type: "area",
          name: "Victoria Island",
          agents: 120,
          customers: 5300,
          revenue: "₦22M",
          children: [
            {
              id: 131,
              type: "agent",
              name: "Agent AG11111 - VI Mart",
              customers: 600,
              revenue: "₦3.5M",
            },
            {
              id: 132,
              type: "agent",
              name: "Agent AG22222 - City Shop",
              customers: 480,
              revenue: "₦2.9M",
            },
          ],
        },
      ],
    },
    {
      id: 2,
      type: "region",
      name: "Abuja Region",
      agents: 280,
      customers: 11200,
      revenue: "₦48M",
      children: [
        {
          id: 21,
          type: "area",
          name: "Central Area",
          agents: 150,
          customers: 6000,
          revenue: "₦28M",
          children: [
            {
              id: 211,
              type: "agent",
              name: "Agent AG33333 - Central Store",
              customers: 550,
              revenue: "₦3.1M",
            },
            {
              id: 212,
              type: "agent",
              name: "Agent AG44444 - Capital Mart",
              customers: 490,
              revenue: "₦2.7M",
            },
          ],
        },
        {
          id: 22,
          type: "area",
          name: "Garki Area",
          agents: 130,
          customers: 5200,
          revenue: "₦20M",
          children: [
            {
              id: 221,
              type: "agent",
              name: "Agent AG55555 - Garki Express",
              customers: 420,
              revenue: "₦2.4M",
            },
          ],
        },
      ],
    },
  ];

  const toggleNode = (nodeId: number) => {
    setExpandedNodes((prev) =>
      prev.includes(nodeId)
        ? prev.filter((id) => id !== nodeId)
        : [...prev, nodeId],
    );
  };

  const renderHierarchyNode = (node: any, level: number = 0) => {
    const isExpanded = expandedNodes.includes(node.id);
    const hasChildren = node.children && node.children.length > 0;
    const indent = level * 24;

    return (
      <div key={node.id} className="mb-2">
        <div
          className={`flex items-center p-3 rounded-lg cursor-pointer transition-colors ${
            node.type === "region"
              ? "bg-[rgba(0,79,113,0.05)] hover:bg-[rgba(0,79,113,0.1)]"
              : node.type === "area"
                ? "bg-green-50 hover:bg-green-100"
                : "bg-gray-50 hover:bg-gray-100"
          }`}
          style={{ marginLeft: `${indent}px` }}
          onClick={() => hasChildren && toggleNode(node.id)}
        >
          {hasChildren && (
            <div className="mr-2">
              {isExpanded ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
            </div>
          )}
          {!hasChildren && <div className="w-6" />}

          <div className="flex-1 flex items-center justify-between">
            <div className="flex items-center space-x-3">
              {node.type === "region" && (
                <Building2 className="h-5 w-5 text-[var(--tenant-primary-color,#002082)]" />
              )}
              {node.type === "area" && (
                <Store className="h-5 w-5 text-green-600" />
              )}
              {node.type === "agent" && (
                <User className="h-5 w-5 text-gray-600" />
              )}
              <div>
                <p className="font-medium text-gray-900">{node.name}</p>
                <div className="flex items-center space-x-4 text-xs text-gray-500 mt-1">
                  {node.agents !== undefined && (
                    <span>{node.agents} agents</span>
                  )}
                  <span>{node.customers} customers</span>
                  <span className="text-green-600 font-medium">
                    {node.revenue}
                  </span>
                </div>
              </div>
            </div>
            {node.type !== "agent" && (
              <TrendingUp className="h-4 w-4 text-green-600" />
            )}
          </div>
        </div>

        {hasChildren && isExpanded && (
          <div className="mt-2">
            {node.children.map((child: any) =>
              renderHierarchyNode(child, level + 1),
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">
            Hierarchy Management
          </h1>
          <p className="text-gray-600 mt-1">
            View and manage organizational structure
          </p>
        </div>
        <button className="inline-flex items-center px-4 py-2 bg-[var(--tenant-primary-color,#002082)] text-white rounded-lg hover:bg-[color-mix(in srgb, var(--tenant-primary-color,#002082) 60%, black)] transition-colors">
          <Building2 className="h-5 w-5 mr-2" />
          Add Region
        </button>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        {stats.map((stat, index) => {
          const IconComponent = stat.icon;
          return (
            <div key={index} className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-600">{stat.label}</p>
                  <p
                    className={`text-2xl font-bold mt-2 text-${stat.color}-600`}
                  >
                    {stat.value}
                  </p>
                </div>
                <div className={`p-3 bg-${stat.color}-100 rounded-lg`}>
                  <IconComponent className={`h-6 w-6 text-${stat.color}-600`} />
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
        <input
          type="text"
          placeholder="Search regions, areas, or agents..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)] focus:border-transparent"
        />
      </div>

      {/* Hierarchy Tree */}
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-lg font-semibold text-gray-900">
            Organizational Structure
          </h2>
          <div className="flex items-center space-x-4 text-sm">
            <div className="flex items-center">
              <div className="w-4 h-4 bg-[rgba(0,79,113,0.1)] rounded mr-2"></div>
              <span className="text-gray-600">Region</span>
            </div>
            <div className="flex items-center">
              <div className="w-4 h-4 bg-green-100 rounded mr-2"></div>
              <span className="text-gray-600">Area</span>
            </div>
            <div className="flex items-center">
              <div className="w-4 h-4 bg-gray-100 rounded mr-2"></div>
              <span className="text-gray-600">Agent</span>
            </div>
          </div>
        </div>
        <div className="space-y-2">
          {hierarchyData.map((node) => renderHierarchyNode(node))}
        </div>
      </div>

      {/* Top Performing Branches */}
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Top Performing Branches
        </h2>
        <div className="space-y-3">
          {[
            {
              name: "Ikeja Area",
              region: "Lagos",
              revenue: "₦35M",
              growth: "+25%",
              rank: 1,
            },
            {
              name: "Central Area",
              region: "Abuja",
              revenue: "₦28M",
              growth: "+20%",
              rank: 2,
            },
            {
              name: "Lekki Area",
              region: "Lagos",
              revenue: "₦28M",
              growth: "+18%",
              rank: 3,
            },
          ].map((branch) => (
            <div
              key={branch.rank}
              className="flex items-center justify-between p-4 bg-gray-50 rounded-lg"
            >
              <div className="flex items-center space-x-4">
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-white ${
                    branch.rank === 1
                      ? "bg-yellow-500"
                      : branch.rank === 2
                        ? "bg-gray-400"
                        : "bg-orange-600"
                  }`}
                >
                  {branch.rank}
                </div>
                <div>
                  <p className="font-medium text-gray-900">{branch.name}</p>
                  <p className="text-sm text-gray-500">
                    {branch.region} Region
                  </p>
                </div>
              </div>
              <div className="text-right">
                <p className="font-semibold text-green-600">{branch.revenue}</p>
                <p className="text-sm text-green-600">{branch.growth} growth</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default HierarchyManagement;
