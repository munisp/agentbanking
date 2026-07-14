import {
  AlertCircle,
  Building2,
  ChevronDown,
  ChevronRight,
  DollarSign,
  Download,
  Filter,
  Loader,
  Search,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import React, { useEffect, useMemo, useState } from "react";
import { api } from "../../utils/api";

interface Account {
  id: string;
  tenant_id: string;
  code: string;
  name: string;
  description?: string;
  type: string;
  normal_balance: string;
  level: number;
  parent_id?: string;
  is_active: boolean;
  is_system_account: boolean;
  currency: string;
  tigerbeetle_ledger: number;
  tigerbeetle_code: number;
  cbn_code?: string;
  created_at: string;
  updated_at: string;
  current_balance?: number | null;
  debit_balance?: number | null;
  credit_balance?: number | null;
}

interface AccountNode extends Account {
  children: AccountNode[];
  computedLevel: number;
}

type FilterType = "all" | "asset" | "liability" | "equity" | "income" | "expense";

const TYPE_COLORS: Record<string, string> = {
  asset: "bg-blue-100 text-blue-800",
  liability: "bg-red-100 text-red-800",
  equity: "bg-purple-100 text-purple-800",
  income: "bg-green-100 text-green-800",
  expense: "bg-orange-100 text-orange-800",
};

function fmtBalance(amount: number | null | undefined, currency: string): string {
  if (amount == null) return "—";
  // amounts are stored in smallest unit (kobo); divide by 100 for display
  const major = amount / 100;
  return new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency: currency === "NGN" ? "NGN" : currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(major);
}

function buildTree(accounts: Account[]): AccountNode[] {
  const byCode = new Map<string, AccountNode>();
  accounts.forEach((acc) =>
    byCode.set(acc.code, { ...acc, children: [], computedLevel: 0 })
  );

  const roots: AccountNode[] = [];
  byCode.forEach((node) => {
    if (node.parent_id && byCode.has(node.parent_id)) {
      byCode.get(node.parent_id)!.children.push(node);
    } else {
      roots.push(node);
    }
  });

  function sort(nodes: AccountNode[], level: number) {
    nodes.sort((a, b) => a.code.localeCompare(b.code));
    nodes.forEach((n) => {
      n.computedLevel = level;
      sort(n.children, level + 1);
    });
  }
  sort(roots, 0);
  return roots;
}

function flattenVisible(nodes: AccountNode[], expanded: Set<string>): AccountNode[] {
  const result: AccountNode[] = [];
  for (const node of nodes) {
    result.push(node);
    if (node.children.length > 0 && expanded.has(node.code)) {
      result.push(...flattenVisible(node.children, expanded));
    }
  }
  return result;
}

function collectCodes(nodes: AccountNode[]): string[] {
  const codes: string[] = [];
  for (const node of nodes) {
    codes.push(node.code);
    codes.push(...collectCodes(node.children));
  }
  return codes;
}

const ChartOfAccounts: React.FC = () => {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [filterType, setFilterType] = useState<FilterType>("all");
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data: any = await api.getAllAccounts();
      const list: Account[] = Array.isArray(data) ? data : [];
      setAccounts(list);
      // expand top-level accounts by default
      const tree = buildTree(list);
      setExpanded(new Set(tree.map((n) => n.code)));
    } catch (err: any) {
      console.error("Error loading accounts:", err);
      setError(err.message || "Failed to load chart of accounts");
      setAccounts([]);
    } finally {
      setLoading(false);
    }
  };

  // code → account lookup for parent name resolution
  const byCode = useMemo(() => {
    const m = new Map<string, Account>();
    accounts.forEach((a) => m.set(a.code, a));
    return m;
  }, [accounts]);

  const tree = useMemo(() => {
    const filtered =
      filterType === "all" ? accounts : accounts.filter((a) => a.type === filterType);
    return buildTree(filtered);
  }, [accounts, filterType]);

  const isSearching = searchQuery.trim().length > 0;

  // flat search result
  const searchResults = useMemo(() => {
    if (!isSearching) return [];
    const q = searchQuery.toLowerCase();
    return accounts.filter((a) => {
      const matchesType = filterType === "all" || a.type === filterType;
      const matchesQuery =
        a.code?.toLowerCase().includes(q) ||
        a.name?.toLowerCase().includes(q) ||
        a.description?.toLowerCase().includes(q) ||
        a.currency?.toLowerCase().includes(q) ||
        (a.cbn_code?.toLowerCase().includes(q) ?? false);
      return matchesType && matchesQuery;
    });
  }, [accounts, searchQuery, filterType, isSearching]);

  const visibleRows = useMemo(
    () => (isSearching ? [] : flattenVisible(tree, expanded)),
    [tree, expanded, isSearching]
  );

  const displayRows: (Account & { computedLevel?: number })[] = isSearching
    ? searchResults
    : visibleRows;

  const toggleNode = (code: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(code)) next.delete(code);
      else next.add(code);
      return next;
    });
  };

  const expandAll = () => {
    const allCodes = collectCodes(tree);
    setExpanded(new Set(allCodes));
  };

  const collapseAll = () => {
    setExpanded(new Set(tree.map((n) => n.code)));
  };

  const countByType = (type: string) => accounts.filter((a) => a.type === type).length;

  const exportToCSV = () => {
    const headers = ["Code", "Name", "Type", "Normal Balance", "Currency", "Balance", "Debit", "Credit", "Active", "CBN Code", "Parent"];
    const rows = displayRows.map((acc) => {
      const parent = acc.parent_id ? byCode.get(acc.parent_id) : undefined;
      return [
        acc.code,
        `"${acc.name}"`,
        acc.type,
        acc.normal_balance,
        acc.currency,
        acc.current_balance != null ? (acc.current_balance / 100).toFixed(2) : "",
        acc.debit_balance != null ? (acc.debit_balance / 100).toFixed(2) : "",
        acc.credit_balance != null ? (acc.credit_balance / 100).toFixed(2) : "",
        acc.is_active ? "Yes" : "No",
        acc.cbn_code || "",
        parent ? `${parent.code} - ${parent.name}` : "",
      ];
    });
    const csv = [headers, ...rows].map((r) => r.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `chart-of-accounts-${new Date().toISOString().split("T")[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Building2 className="h-8 w-8" />
            Chart of Accounts
          </h1>
          <p className="text-gray-600 mt-1">General ledger account structure for your institution</p>
        </div>
        <button
          onClick={exportToCSV}
          disabled={displayRows.length === 0}
          className="inline-flex items-center px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Download className="h-5 w-5 mr-2" />
          Export CSV
        </button>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="bg-white rounded-lg shadow p-4">
          <p className="text-sm text-gray-600">Total</p>
          <p className="text-2xl font-bold text-gray-900 mt-1">{accounts.length}</p>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Assets</p>
              <p className="text-2xl font-bold text-blue-600 mt-1">{countByType("asset")}</p>
            </div>
            <TrendingUp className="h-6 w-6 text-blue-400" />
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Liabilities</p>
              <p className="text-2xl font-bold text-red-600 mt-1">{countByType("liability")}</p>
            </div>
            <TrendingDown className="h-6 w-6 text-red-400" />
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Equity</p>
              <p className="text-2xl font-bold text-purple-600 mt-1">{countByType("equity")}</p>
            </div>
            <Building2 className="h-6 w-6 text-purple-400" />
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-600">Income / Expense</p>
              <p className="text-2xl font-bold text-green-600 mt-1">
                {countByType("income") + countByType("expense")}
              </p>
            </div>
            <DollarSign className="h-6 w-6 text-green-400" />
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded flex items-center gap-2">
          <AlertCircle className="h-5 w-5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex flex-col md:flex-row gap-4">
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
            <input
              type="text"
              placeholder="Search by code, name, description, currency, CBN code..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
            />
          </div>
          <div className="flex items-center gap-2">
            <Filter className="h-5 w-5 text-gray-400" />
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value as FilterType)}
              className="px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-[var(--tenant-secondary-color,#69BC5E)] focus:border-transparent"
            >
              <option value="all">All Types</option>
              <option value="asset">Asset</option>
              <option value="liability">Liability</option>
              <option value="equity">Equity</option>
              <option value="income">Income</option>
              <option value="expense">Expense</option>
            </select>
          </div>
          {!isSearching && (
            <div className="flex items-center gap-2">
              <button
                onClick={expandAll}
                className="px-3 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Expand All
              </button>
              <button
                onClick={collapseAll}
                className="px-3 py-2 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Collapse All
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="bg-white rounded-lg shadow p-8 text-center">
          <Loader className="h-8 w-8 animate-spin mx-auto text-[var(--tenant-primary-color,#004F71)]" />
          <p className="mt-2 text-gray-600">Loading accounts...</p>
        </div>
      )}

      {/* Table */}
      {!loading && displayRows.length > 0 && (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="overflow-x-auto max-h-[65vh] overflow-y-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50 sticky top-0 z-10">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-28">
                    Code
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Account Name
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-28">
                    Type
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-32">
                    Normal Balance
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-24">
                    Currency
                  </th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider w-36">
                    Balance
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-24">
                    CBN Code
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-20">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-100">
                {displayRows.map((account) => {
                  const node = account as AccountNode;
                  const level = node.computedLevel ?? 0;
                  const hasChildren = node.children?.length > 0;
                  const isExpanded = expanded.has(account.code);
                  const parent = account.parent_id ? byCode.get(account.parent_id) : undefined;

                  return (
                    <tr
                      key={account.id}
                      className={`hover:bg-gray-50 ${level === 0 ? "bg-gray-50/60" : ""}`}
                    >
                      {/* Code */}
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span className="font-mono text-sm font-semibold text-gray-900">
                          {account.code}
                        </span>
                      </td>

                      {/* Account Name with indent + expand toggle */}
                      <td className="px-4 py-3">
                        <div
                          className="flex items-start gap-1"
                          style={{ paddingLeft: `${level * 20}px` }}
                        >
                          {/* expand/collapse button */}
                          {!isSearching && hasChildren ? (
                            <button
                              onClick={() => toggleNode(account.code)}
                              className="mt-0.5 flex-shrink-0 text-gray-400 hover:text-gray-700"
                            >
                              {isExpanded ? (
                                <ChevronDown className="h-4 w-4" />
                              ) : (
                                <ChevronRight className="h-4 w-4" />
                              )}
                            </button>
                          ) : (
                            <span className="w-4 flex-shrink-0" />
                          )}

                          <div>
                            <p
                              className={`text-gray-900 ${
                                level === 0 ? "font-semibold text-sm" : "font-medium text-sm"
                              }`}
                            >
                              {account.name}
                            </p>
                            {account.description && (
                              <p className="text-xs text-gray-500 mt-0.5">{account.description}</p>
                            )}
                            {parent && (
                              <p className="text-xs text-gray-400 mt-0.5">
                                Under: {parent.code} — {parent.name}
                              </p>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* Type */}
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium capitalize ${
                            TYPE_COLORS[account.type] || "bg-gray-100 text-gray-800"
                          }`}
                        >
                          {account.type}
                        </span>
                      </td>

                      {/* Normal Balance */}
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-700 capitalize">
                        {account.normal_balance}
                      </td>

                      {/* Currency */}
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-700">
                        {account.currency}
                      </td>

                      {/* Balance */}
                      <td className="px-4 py-3 whitespace-nowrap text-right">
                        {account.current_balance != null ? (
                          <div>
                            <p className="text-sm font-medium text-gray-900">
                              {fmtBalance(account.current_balance, account.currency)}
                            </p>
                            <p className="text-xs text-gray-400">
                              Dr {fmtBalance(account.debit_balance, account.currency)} / Cr {fmtBalance(account.credit_balance, account.currency)}
                            </p>
                          </div>
                        ) : (
                          <span className="text-sm text-gray-400">—</span>
                        )}
                      </td>

                      {/* CBN Code */}
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                        {account.cbn_code || "—"}
                      </td>

                      {/* Status */}
                      <td className="px-4 py-3 whitespace-nowrap">
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                            account.is_active
                              ? "bg-green-100 text-green-800"
                              : "bg-red-100 text-red-800"
                          }`}
                        >
                          {account.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="px-6 py-3 bg-gray-50 border-t text-sm text-gray-500">
            {isSearching
              ? `${displayRows.length} result${displayRows.length !== 1 ? "s" : ""} for "${searchQuery}"`
              : `Showing ${displayRows.length} of ${accounts.length} accounts`}
          </div>
        </div>
      )}

      {/* Empty State */}
      {!loading && displayRows.length === 0 && !error && (
        <div className="text-center py-12 bg-white rounded-lg shadow">
          <Building2 className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">
            {searchQuery || filterType !== "all"
              ? "No accounts match your search or filter."
              : "No accounts available."}
          </p>
        </div>
      )}
    </div>
  );
};

export default ChartOfAccounts;
