import {
    AlertCircle,
    Building2,
    Calendar,
    Copy,
    Filter,
    Hash,
    RefreshCw,
    Search,
    Store as StoreIcon,
    TrendingUp,
    Users,
} from "lucide-react";
import React, { useEffect, useMemo, useState } from "react";
import { api, StoreRecord } from "../../utils/api";

// ─── helpers ──────────────────────────────────────────────────────────────────

const formatDate = (dateString: string) =>
  new Date(dateString).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

const formatDateTime = (dateString: string) =>
  new Date(dateString).toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

/** Returns a deterministic soft background+text colour pair from a string seed */
const avatarColor = (seed: string): string => {
  const palette = [
    "bg-[rgba(0,79,113,0.1)] text-[var(--tenant-primary-color,#002082)]",
    "bg-purple-100 text-purple-700",
    "bg-green-100 text-green-700",
    "bg-orange-100 text-orange-700",
    "bg-pink-100 text-pink-700",
    "bg-teal-100 text-teal-700",
    "bg-[rgba(0,79,113,0.1)] text-[var(--tenant-primary-color,#002082)]",
    "bg-rose-100 text-rose-700",
  ];
  const idx =
    seed.split("").reduce((acc, c) => acc + c.charCodeAt(0), 0) %
    palette.length;
  return palette[idx];
};

// ─── component ────────────────────────────────────────────────────────────────

const StoresList: React.FC = () => {
  const [stores, setStores] = useState<StoreRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [sortBy, setSortBy] = useState<"newest" | "oldest" | "name">("newest");
  const [copiedId, setCopiedId] = useState<string | null>(null);

  // ── data ──────────────────────────────────────────────────────────────────

  const loadStores = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getAllStores();
      setStores(data);
    } catch (err) {
      setError((err as Error).message || "Failed to load stores");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStores();
  }, []);

  // ── derived stats ─────────────────────────────────────────────────────────

  const stats = useMemo(() => {
    const now = Date.now();
    const week = 7 * 24 * 60 * 60 * 1000;
    const month = 30 * 24 * 60 * 60 * 1000;
    const uniqueOwners = new Set(stores.map((s) => s.owner_keycloak_id)).size;
    const thisWeek = stores.filter(
      (s) => now - new Date(s.created_at).getTime() < week,
    ).length;
    const thisMonth = stores.filter(
      (s) => now - new Date(s.created_at).getTime() < month,
    ).length;
    return { total: stores.length, uniqueOwners, thisWeek, thisMonth };
  }, [stores]);

  // ── filtering + sorting ───────────────────────────────────────────────────

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    const result = stores.filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        (s.description ?? "").toLowerCase().includes(q) ||
        s.owner_keycloak_id.toLowerCase().includes(q),
    );
    if (sortBy === "newest")
      return [...result].sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      );
    if (sortBy === "oldest")
      return [...result].sort(
        (a, b) =>
          new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
      );
    return [...result].sort((a, b) => a.name.localeCompare(b.name));
  }, [stores, search, sortBy]);

  // ── copy helper ───────────────────────────────────────────────────────────

  const copyId = (id: string) => {
    navigator.clipboard.writeText(id).catch(() => {});
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  // ── render ────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6 p-6">
      {/* ── Header ── */}
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
            <StoreIcon className="w-8 h-8 text-[var(--tenant-primary-color,#002082)]" />
            Businesses
          </h1>
          <p className="text-gray-500 mt-1">
            All agent stores (businesses) registered on the platform
          </p>
        </div>
        <button
          onClick={loadStores}
          disabled={loading}
          className="px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 flex items-center gap-2 text-sm"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      {/* ── Error banner ── */}
      {error && (
        <div className="flex items-center gap-2 bg-red-50 border border-red-200 text-red-700 rounded-lg px-4 py-3 text-sm">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          {error}
          <button
            onClick={loadStores}
            className="ml-auto underline text-red-600 hover:text-red-800"
          >
            Retry
          </button>
        </div>
      )}

      {/* ── Stats row ── */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          {
            label: "Total Businesses",
            value: stats.total,
            icon: StoreIcon,
            color: "text-[var(--tenant-primary-color,#002082)]",
            bg: "bg-[rgba(0,79,113,0.05)]",
          },
          {
            label: "Unique Owners",
            value: stats.uniqueOwners,
            icon: Users,
            color: "text-purple-500",
            bg: "bg-purple-50",
          },
          {
            label: "Added This Week",
            value: stats.thisWeek,
            icon: TrendingUp,
            color: "text-green-500",
            bg: "bg-green-50",
          },
          {
            label: "Added This Month",
            value: stats.thisMonth,
            icon: Calendar,
            color: "text-orange-500",
            bg: "bg-orange-50",
          },
        ].map((s) => (
          <div key={s.label} className="bg-white rounded-xl shadow p-5">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-500">{s.label}</p>
                <p className="text-2xl font-bold text-gray-900 mt-1">
                  {loading ? "…" : s.value}
                </p>
              </div>
              <div className={`p-3 rounded-full ${s.bg}`}>
                <s.icon className={`w-6 h-6 ${s.color}`} />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* ── Filters ── */}
      <div className="bg-white rounded-xl shadow p-4 flex flex-wrap gap-3 items-center">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="absolute left-3 top-2.5 w-4 h-4 text-gray-400" />
          <input
            type="text"
            placeholder="Search by name, description or owner ID…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)]"
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="w-4 h-4 text-gray-400" />
          <select
            value={sortBy}
            onChange={(e) =>
              setSortBy(e.target.value as "newest" | "oldest" | "name")
            }
            className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--tenant-secondary-color,#6CC049)]"
          >
            <option value="newest">Newest First</option>
            <option value="oldest">Oldest First</option>
            <option value="name">Sort by Name</option>
          </select>
        </div>
        {search && (
          <span className="text-sm text-gray-500">
            {filtered.length} result{filtered.length !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* ── Table ── */}
      <div className="bg-white rounded-xl shadow overflow-hidden">
        {loading ? (
          <div className="flex flex-col items-center justify-center py-24 gap-3 text-gray-400">
            <RefreshCw className="w-8 h-8 animate-spin text-[var(--tenant-primary-color,#002082)]" />
            <p className="text-sm">Loading stores…</p>
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-24 gap-4 text-gray-400">
            <div className="p-5 bg-gray-100 rounded-full">
              <Building2 className="w-10 h-10 text-gray-400" />
            </div>
            <div className="text-center">
              <p className="font-medium text-gray-600">
                {search
                  ? "No businesses match your search"
                  : "No businesses registered yet"}
              </p>
              <p className="text-sm mt-1">
                {search
                  ? "Try adjusting your search term"
                  : "Businesses created by agents will appear here"}
              </p>
            </div>
            {search && (
              <button
                onClick={() => setSearch("")}
                className="text-sm text-[var(--tenant-primary-color,#002082)] hover:underline"
              >
                Clear search
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto max-h-[65vh] overflow-scroll">
            <table className="min-w-full divide-y divide-gray-100">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    Business
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    Description
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    Account Number
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    Owner ID
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    <Hash className="inline w-3.5 h-3.5 mr-0.5 -mt-0.5" />
                    ID
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    Created
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {filtered.map((store) => {
                  const initials = store.name
                    .split(" ")
                    .map((w) => w[0])
                    .slice(0, 2)
                    .join("")
                    .toUpperCase();
                  const colours = avatarColor(store.name);
                  return (
                    <tr
                      key={store.id}
                      className="hover:bg-gray-50 transition-colors"
                    >
                      {/* Store name + avatar */}
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div
                            className={`w-9 h-9 rounded-lg flex items-center justify-center font-semibold text-sm flex-shrink-0 ${colours}`}
                          >
                            {initials}
                          </div>
                          <div>
                            <p className="text-sm font-semibold text-gray-900">
                              {store.name}
                            </p>
                            <p className="text-xs text-gray-400">
                              Updated {formatDate(store.updated_at)}
                            </p>
                          </div>
                        </div>
                      </td>

                      {/* Description */}
                      <td className="px-6 py-4 max-w-xs">
                        {store.description ? (
                          <p className="text-sm text-gray-600 line-clamp-2">
                            {store.description}
                          </p>
                        ) : (
                          <span className="text-xs text-gray-400 italic">
                            No description
                          </span>
                        )}
                      </td>

                      {/* Account number */}
                      <td className="px-6 py-4 whitespace-nowrap">
                        {store.account_number ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700">
                            {store.account_number}
                          </span>
                        ) : (
                          <span className="text-xs text-gray-400 italic">
                            N/A
                          </span>
                        )}
                      </td>

                      {/* Owner ID — truncated with copy */}
                      <td className="px-6 py-4 whitespace-nowrap">
                        <button
                          onClick={() => copyId(store.owner_keycloak_id)}
                          title={
                            copiedId === store.owner_keycloak_id
                              ? "Copied!"
                              : `Copy: ${store.owner_keycloak_id}`
                          }
                          className="flex items-center gap-1.5 group"
                        >
                          <span className="text-xs font-mono text-gray-500 bg-gray-100 group-hover:bg-[rgba(0,79,113,0.05)] group-hover:text-[var(--tenant-primary-color,#002082)] px-2 py-1 rounded transition-colors">
                            {store.owner_keycloak_id.substring(0, 12)}…
                          </span>
                          <Copy
                            className={`w-3 h-3 flex-shrink-0 transition-colors ${
                              copiedId === store.owner_keycloak_id
                                ? "text-green-500"
                                : "text-gray-300 group-hover:text-white opacity-70"
                            }`}
                          />
                        </button>
                      </td>

                      {/* Store ID */}
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-600">
                          #{store.id}
                        </span>
                      </td>

                      {/* Created date */}
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div>
                          <p className="text-sm text-gray-700">
                            {formatDate(store.created_at)}
                          </p>
                          <p className="text-xs text-gray-400">
                            {formatDateTime(store.created_at)
                              .split(",")[1]
                              ?.trim()}
                          </p>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            {/* Footer row count */}
            <div className="px-6 py-3 bg-gray-50 border-t border-gray-100 text-xs text-gray-400">
              Showing {filtered.length} of {stores.length} business
              {stores.length !== 1 ? "es" : ""}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default StoresList;
